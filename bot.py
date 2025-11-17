"""
Syntra Trade Consultant - Main Bot Entry Point
"""
import asyncio
import logging
import sys
import warnings
from typing import Dict

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config.config import BOT_TOKEN, validate_config
from config.logging import setup_logging
from config.sentry import init_sentry
from src.database.engine import init_db, dispose_engine
from src.bot.handlers import start, help_cmd, chat, vision, crypto, menu, admin, limits
from src.bot.middleware.database import DatabaseMiddleware
from src.bot.middleware.subscription import SubscriptionMiddleware
from src.bot.middleware.request_limit import RequestLimitMiddleware
from src.bot.middleware.logging import LoggingMiddleware
from src.bot.middleware.admin import AdminMiddleware
from src.bot.middleware.language import LanguageMiddleware
from src.services.retention_service import start_retention_service, stop_retention_service


logger = logging.getLogger(__name__)


async def setup_bot_commands(bot: Bot) -> None:
    """
    Setup bot commands menu

    Args:
        bot: Bot instance
    """
    commands = [
        BotCommand(command="start", description="🚀 Start the bot"),
        BotCommand(command="help", description="💡 Get help and information"),
        BotCommand(command="price", description="💰 Get cryptocurrency prices"),
        BotCommand(command="analyze", description="📊 Analyze crypto market"),
        BotCommand(command="market", description="📈 Market overview"),
        BotCommand(command="news", description="📰 Latest crypto news"),
        BotCommand(command="limits", description="⚡ Check your usage limits"),
    ]

    await bot.set_my_commands(commands)
    logger.info("Bot commands menu initialized successfully")


async def on_startup(bot: Bot, **kwargs) -> None:
    """Actions to perform on bot startup"""
    logger.info("Starting Syntra Trade Consultant Bot...")

    # Initialize database
    await init_db()
    logger.info("Database initialized successfully")

    # Setup bot commands menu
    await setup_bot_commands(bot)

    # Start retention service
    await start_retention_service(bot)
    logger.info("Retention service started")

    # Get bot info
    bot_info = await bot.get_me()
    logger.info(f"Bot started: @{bot_info.username} (ID: {bot_info.id})")


async def on_shutdown(bot: Bot, **kwargs) -> None:
    """Actions to perform on bot shutdown"""
    logger.info("Shutting down Syntra Trade Consultant Bot...")

    # Stop retention service
    await stop_retention_service()
    logger.info("Retention service stopped")

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
    warnings.filterwarnings("ignore", message="coroutine 'Event.wait' was never awaited")

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
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True
        )
    )

    # Create dispatcher with FSM storage
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register middleware (order matters!)
    # 1. Logging middleware (first to log everything)
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())

    # 2. Database middleware (provides session to handlers)
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())

    # 3. Language middleware (detects and sets user language)
    dp.message.middleware(LanguageMiddleware())
    dp.callback_query.middleware(LanguageMiddleware())

    # 4. Admin middleware (checks admin rights for admin commands)
    dp.message.middleware(AdminMiddleware())
    dp.callback_query.middleware(AdminMiddleware())

    # 5. Subscription middleware (checks channel subscription)
    dp.message.middleware(SubscriptionMiddleware())

    # 6. Request limit middleware (checks daily limits)
    dp.message.middleware(RequestLimitMiddleware())

    # Register routers (order matters - specific routes first, general last)
    dp.include_router(start.router)
    dp.include_router(menu.router)  # Menu callback handlers
    dp.include_router(admin.router)  # Admin panel (before help to catch admin commands)
    dp.include_router(help_cmd.router)
    dp.include_router(limits.router)  # Limits command (/limits)
    dp.include_router(crypto.router)  # Crypto commands (/price, /analyze, /market, /news)
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
            drop_pending_updates=True  # Skip old updates on startup
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
