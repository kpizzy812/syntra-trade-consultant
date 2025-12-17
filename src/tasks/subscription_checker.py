# coding: utf-8
"""
Subscription Checker Cron Job - runs every 6 hours to verify subscriptions.

Checks if users are still subscribed to Telegram channels/chats.
If not subscribed - revokes reward and applies penalty.

Run: python -m src.tasks.subscription_checker

Crontab (every 6 hours):
    0 */6 * * * cd /path && .venv/bin/python -m src.tasks.subscription_checker
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from loguru import logger
from aiogram import Bot

from config.config import BOT_TOKEN
from src.database.engine import get_session_maker
from src.services.social_tasks_service import SocialTasksService


async def main():
    """
    Main cron job entry point
    """
    logger.info("=" * 80)
    logger.info("Subscription Checker Cron Job - Starting")
    logger.info("=" * 80)

    # Initialize bot
    bot = Bot(token=BOT_TOKEN)

    # Initialize database session
    SessionLocal = await get_session_maker()

    async with SessionLocal() as session:
        try:
            # Run subscription recheck
            results = await SocialTasksService.recheck_subscriptions(
                session=session,
                bot=bot,
            )

            logger.info("=" * 80)
            logger.info("Subscription Checker Cron Job - Results:")
            logger.info(f"  - Total completions checked: {results['total_checked']}")
            logger.info(f"  - Still subscribed: {results['still_subscribed']}")
            logger.info(f"  - Rewards revoked: {results['revoked']}")
            logger.info(f"  - Total penalty points applied: {results['total_penalty']}")
            logger.info(f"  - Errors: {results['errors']}")
            logger.info("=" * 80)

            # Log details of revoked rewards
            if results.get('revoked_details'):
                logger.info("Revoked rewards details:")
                for detail in results['revoked_details']:
                    logger.info(
                        f"  - User {detail['user_id']} unsub task "
                        f"{detail['task_id']}: -{detail['penalty']} pts"
                    )

        except Exception as e:
            logger.error(f"Error in subscription checker cron job: {e}", exc_info=True)
            raise
        finally:
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
