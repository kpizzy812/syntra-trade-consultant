"""
Syntra Trade Consultant - Main Bot Entry Point
"""

import asyncio
import sys
import warnings

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from loguru import logger

from config.config import BOT_TOKEN, validate_config
from config.logging import setup_logging
from config.sentry import init_sentry
from src.database.engine import dispose_engine
from src.cache import get_redis_manager
from src.bot.handlers import (
    start,
    help_cmd,
    chat,
    vision,
    crypto,
    menu,
    admin,
    limits,
    premium,
    referral,
    broadcast,
    channel_repost,
    points,
    points_admin,
    task_review,
    futures,
)
from src.bot.middleware.database import DatabaseMiddleware
from src.bot.middleware.subscription import SubscriptionMiddleware
from src.bot.middleware.subscription_checker import SubscriptionCheckerMiddleware
from src.bot.middleware.request_limit import RequestLimitMiddleware
from src.bot.middleware.logging import LoggingMiddleware
from src.bot.middleware.admin import AdminMiddleware
from src.bot.middleware.language import LanguageMiddleware
from src.services.retention_service import (
    start_retention_service,
    stop_retention_service,
)
from src.tasks.ton_scanner import start_ton_scanner
from src.tasks.referral_scheduler import schedule_referral_tasks
from src.tasks.broadcast_scheduler import schedule_broadcast_tasks
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Background tasks references
_ton_scanner_task = None
_scheduler = None


async def setup_bot_commands(bot: Bot) -> None:
    """
    Setup bot commands menu

    Args:
        bot: Bot instance
    """
    commands = [
        BotCommand(command="start", description="🚀 Start the bot"),
        BotCommand(command="futures", description="📊 Futures Signals"),
        BotCommand(command="help", description="💡 Get help and information"),
        BotCommand(command="limits", description="⚡ Check your usage limits"),
    ]

    await bot.set_my_commands(commands)
    logger.info("Bot commands menu initialized successfully")


async def on_startup(bot: Bot, **kwargs) -> None:
    """Actions to perform on bot startup"""
    global _ton_scanner_task, _scheduler

    logger.info("Starting Syntra Trade Consultant Bot...")

    # NOTE: Database tables managed by Alembic migrations
    # Run: alembic upgrade head

    # Initialize Redis cache
    redis_mgr = get_redis_manager()
    redis_available = await redis_mgr.initialize()
    if redis_available:
        logger.info("Redis cache initialized successfully")
    else:
        logger.warning("Redis cache unavailable - bot will work without caching")

    # Setup bot commands menu
    await setup_bot_commands(bot)

    # Start retention service
    await start_retention_service(bot)
    logger.info("Retention service started")

    # Start TON blockchain scanner
    _ton_scanner_task = asyncio.create_task(start_ton_scanner())
    logger.info("TON blockchain scanner started")

    # Start referral activation scheduler
    _scheduler = AsyncIOScheduler()
    schedule_referral_tasks(_scheduler)
    schedule_broadcast_tasks(_scheduler, bot)
    _scheduler.start()
    logger.info("Referral activation scheduler started")
    logger.info("Broadcast scheduler started")

    # Get bot info
    bot_info = await bot.get_me()
    logger.info(f"Bot started: @{bot_info.username} (ID: {bot_info.id})")


async def on_shutdown(bot: Bot, **kwargs) -> None:
    """Actions to perform on bot shutdown"""
    global _ton_scanner_task, _scheduler

    logger.info("Shutting down Syntra Trade Consultant Bot...")

    # Stop retention service
    await stop_retention_service()
    logger.info("Retention service stopped")

    # Stop TON scanner
    if _ton_scanner_task:
        _ton_scanner_task.cancel()
        try:
            await _ton_scanner_task
        except asyncio.CancelledError:
            pass
        logger.info("TON scanner stopped")

    # Stop referral scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        logger.info("Referral scheduler stopped")

    # Close Redis connections
    redis_mgr = get_redis_manager()
    await redis_mgr.close()
    logger.info("Redis cache closed")

    # Close database connections
    await dispose_engine()
    logger.info("Database connections closed")

    # Close bot session
    await bot.session.close()
    logger.info("Bot session closed")


async def main() -> None:
    """Main bot function"""

    # Setup logging
    setup_logging()

    # Suppress aiogram ChatActionSender warning
    warnings.filterwarnings(
        "ignore", message="coroutine 'Event.wait' was never awaited"
    )

    # Initialize Sentry error monitoring
    init_sentry()

    # Validate configuration
    if not validate_config():
        logger.error("Configuration validation failed. Please check your .env file.")
        sys.exit(1)

    logger.info("Configuration validated successfully")

    # Initialize bot and dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML, link_preview_is_disabled=True
        ),
    )

    # Create dispatcher with FSM storage
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register middleware (order matters!)
    # 1. Logging middleware (first to log everything)
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    dp.pre_checkout_query.middleware(LoggingMiddleware())

    # 2. Database middleware (provides session to handlers)
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())
    dp.pre_checkout_query.middleware(DatabaseMiddleware())

    # 3. Language middleware (detects user language and provides user object)
    dp.message.middleware(LanguageMiddleware())
    dp.callback_query.middleware(LanguageMiddleware())
    dp.pre_checkout_query.middleware(LanguageMiddleware())

    # 4. Admin middleware (checks admin rights for admin commands)
    dp.message.middleware(AdminMiddleware())
    dp.callback_query.middleware(AdminMiddleware())

    # 5. Subscription middleware (checks channel subscription)
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    # 6. Premium subscription checker (checks expiry, auto-downgrades)
    dp.message.middleware(SubscriptionCheckerMiddleware())

    # 7. Request limit middleware (checks daily limits based on tier)
    dp.message.middleware(RequestLimitMiddleware())

    # Register routers (order matters - specific routes first, general last)
    # Channel auto-repost (handles channel_post)
    dp.include_router(channel_repost.router)
    dp.include_router(start.router)
    dp.include_router(menu.router)  # Menu callback handlers
    dp.include_router(premium.router)  # Premium subscription handlers
    dp.include_router(referral.router)  # Referral system handlers
    dp.include_router(admin.router)  # Admin panel (before help to catch admin commands)
    dp.include_router(broadcast.router)  # Broadcast system (admin only)
    dp.include_router(points_admin.router)  # Points admin panel (analytics, config)
    dp.include_router(task_review.router)  # Task review callbacks (approve/reject)
    dp.include_router(help_cmd.router)
    dp.include_router(limits.router)  # Limits command (/limits)
    dp.include_router(futures.router)  # Futures signals (/futures)
    dp.include_router(points.router)  # $SYNTRA points commands (/points, /level)
    dp.include_router(
        crypto.router
    )  # Crypto commands (/price, /analyze, /market, /news)
    dp.include_router(vision.router)  # Vision handler for photos
    dp.include_router(chat.router)  # General chat handler (must be last)

    # Register startup/shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Start polling
    try:
        logger.info("Starting bot polling...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True,  # Skip old updates on startup
        )
    except Exception as e:
        logger.exception(f"Critical error during bot operation: {e}")
        raise
    finally:
        await on_shutdown(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
