"""
Trial Checker Cron Job - runs hourly to process trial expirations and send notifications

Run this with:
    python -m src.tasks.trial_checker

Or add to crontab:
    0 * * * * cd /path/to/project && /path/to/.venv/bin/python -m src.tasks.trial_checker
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger
from aiogram import Bot

from config.config import TELEGRAM_BOT_TOKEN
from src.database.engine import get_session_maker
from src.services.trial_service import (
    process_trial_expirations,
    get_active_trial_stats,
    check_trial_expiration,
)
from src.services.trial_notification_service import (
    process_trial_notifications,
    notify_trial_ended,
)


async def main():
    """
    Main cron job entry point
    """
    logger.info("=" * 80)
    logger.info("Trial Checker Cron Job - Starting")
    logger.info("=" * 80)

    # Initialize bot
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    # Initialize database session
    SessionLocal = await get_session_maker()

    async with SessionLocal() as session:
        try:
            # Get current stats
            stats = await get_active_trial_stats(session)
            logger.info(f"Active trials stats: {stats}")

            # 1. Send 24h notifications BEFORE processing expirations
            notification_results = await process_trial_notifications(bot, session)
            logger.info(f"24h notifications: {notification_results}")

            # 2. Find expired trials (for notifications)
            expired_trials = await check_trial_expiration(session)

            # 3. Process trial expirations and send ended notifications
            results = await process_trial_expirations(session)

            # 4. Send trial ended notifications for each expired trial
            for user, subscription in expired_trials:
                # Refresh to get updated subscription with discount
                await session.refresh(subscription)
                await notify_trial_ended(bot, user, subscription, session)

            logger.info("=" * 80)
            logger.info("Trial Checker Cron Job - Results:")
            logger.info(f"  - 24h notifications sent: {notification_results['notifications_24h_sent']}")
            logger.info(f"  - Expired trials downgraded: {results['expired_trials']}")
            logger.info(f"  - Trial ended notifications sent: {len(expired_trials)}")
            logger.info(f"  - Post-trial discounts expired: {results['expired_discounts']}")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Error in trial checker cron job: {e}", exc_info=True)
            raise
        finally:
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
