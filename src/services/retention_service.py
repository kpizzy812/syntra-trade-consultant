# coding: utf-8
"""
Retention service - manages user retention through automated messages

Uses APScheduler to send:
- Follow-up messages to non-subscribers (1h, 24h after /start)
- Reminder messages to inactive users (7d, 14d)
- Subscription status checks
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config.prompts import (
    RETENTION_1_HOUR_NO_SUB,
    RETENTION_24_HOURS_NO_SUB,
    REMINDER_7_DAYS_INACTIVE,
    REMINDER_14_DAYS_INACTIVE,
    ACTIVE_USER_MOTIVATION,
    get_random_catchphrase,
)
from config.config import REQUIRED_CHANNEL
from src.database.engine import get_session
from src.database.crud import (
    get_user_by_telegram_id,
    get_inactive_users,
    update_user_subscription,
    log_admin_action,
    check_request_limit,
)
from src.services.coingecko_service import CoinGeckoService


logger = logging.getLogger(__name__)


class RetentionService:
    """
    Service for managing user retention through automated messaging with real-time market data

    Features:
    - Follow-up messages for non-subscribers
    - Inactive user reminders
    - Subscription status monitoring
    - Motivation messages for active users
    """

    def __init__(self, bot: Bot):
        """
        Initialize retention service

        Args:
            bot: Telegram Bot instance
        """
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.is_running = False
        self.coingecko = CoinGeckoService()

    async def start(self):
        """Start the retention service scheduler"""
        if self.is_running:
            logger.warning("Retention service is already running")
            return

        logger.info("Starting retention service...")

        # Schedule jobs
        self._schedule_jobs()

        # Start scheduler
        self.scheduler.start()
        self.is_running = True

        logger.info("Retention service started successfully")

    async def stop(self):
        """Stop the retention service scheduler"""
        if not self.is_running:
            return

        logger.info("Stopping retention service...")
        self.scheduler.shutdown(wait=False)
        self.is_running = False
        logger.info("Retention service stopped")

    def _schedule_jobs(self):
        """Schedule all retention jobs"""

        # Check non-subscribers every hour (for 1h and 24h follow-ups)
        self.scheduler.add_job(
            self.check_non_subscribers,
            trigger=IntervalTrigger(hours=1),
            id="check_non_subscribers",
            name="Check non-subscribers for follow-ups",
            replace_existing=True,
        )

        # Check inactive users daily at 10:00 UTC
        self.scheduler.add_job(
            self.check_inactive_users,
            trigger=CronTrigger(hour=10, minute=0),
            id="check_inactive_users",
            name="Check inactive users for reminders",
            replace_existing=True,
        )

        # Check subscription status every 6 hours
        self.scheduler.add_job(
            self.check_subscription_status,
            trigger=IntervalTrigger(hours=6),
            id="check_subscription_status",
            name="Verify user subscription status",
            replace_existing=True,
        )

        # Send motivation to active users weekly on Sunday at 12:00 UTC
        self.scheduler.add_job(
            self.motivate_active_users,
            trigger=CronTrigger(day_of_week="sun", hour=12, minute=0),
            id="motivate_active_users",
            name="Send motivation to active users",
            replace_existing=True,
        )

        logger.info("Scheduled 4 retention jobs")

    async def check_non_subscribers(self):
        """
        Check users who haven't subscribed and send follow-up messages

        Sends:
        - 1 hour message: 1 hour after registration
        - 24 hours message: 24 hours after registration
        """
        logger.info("Running non-subscriber check...")

        try:
            async with get_session() as session:
                # Time windows
                now = datetime.utcnow()
                one_hour_ago = now - timedelta(hours=1)
                one_hour_window = timedelta(minutes=30)  # ±30 min window

                twenty_four_hours_ago = now - timedelta(hours=24)
                twenty_four_hour_window = timedelta(hours=1)  # ±1 hour window

                # Find users registered ~1 hour ago who aren't subscribed
                from src.database.models import User
                from sqlalchemy import select, and_

                # 1 hour follow-up
                stmt_1h = select(User).where(
                    and_(
                        User.is_subscribed == False,
                        User.created_at >= one_hour_ago - one_hour_window,
                        User.created_at <= one_hour_ago + one_hour_window,
                    )
                )
                result_1h = await session.execute(stmt_1h)
                users_1h = list(result_1h.scalars().all())

                for user in users_1h:
                    try:
                        message = RETENTION_1_HOUR_NO_SUB.format(
                            channel_link=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}"
                        )
                        await self.bot.send_message(
                            chat_id=user.telegram_id, text=message
                        )
                        logger.info(f"Sent 1h follow-up to user {user.telegram_id}")
                    except (TelegramForbiddenError, TelegramBadRequest) as e:
                        logger.warning(
                            f"Failed to send 1h follow-up to {user.telegram_id}: {e}"
                        )
                    except Exception as e:
                        logger.exception(
                            f"Error sending 1h follow-up to {user.telegram_id}: {e}"
                        )

                # 24 hour follow-up
                stmt_24h = select(User).where(
                    and_(
                        User.is_subscribed == False,
                        User.created_at
                        >= twenty_four_hours_ago - twenty_four_hour_window,
                        User.created_at
                        <= twenty_four_hours_ago + twenty_four_hour_window,
                    )
                )
                result_24h = await session.execute(stmt_24h)
                users_24h = list(result_24h.scalars().all())

                for user in users_24h:
                    try:
                        message = RETENTION_24_HOURS_NO_SUB.format(
                            channel_link=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}"
                        )
                        await self.bot.send_message(
                            chat_id=user.telegram_id, text=message
                        )
                        logger.info(f"Sent 24h follow-up to user {user.telegram_id}")
                    except (TelegramForbiddenError, TelegramBadRequest) as e:
                        logger.warning(
                            f"Failed to send 24h follow-up to {user.telegram_id}: {e}"
                        )
                    except Exception as e:
                        logger.exception(
                            f"Error sending 24h follow-up to {user.telegram_id}: {e}"
                        )

                logger.info(
                    f"Non-subscriber check complete: "
                    f"{len(users_1h)} 1h messages, {len(users_24h)} 24h messages"
                )

        except Exception as e:
            logger.exception(f"Error in non-subscriber check: {e}")

    async def check_inactive_users(self):
        """
        Check inactive users and send reminder messages

        Sends:
        - 7 days reminder: Users inactive for 7 days
        - 14 days reminder: Users inactive for 14 days
        """
        logger.info("Running inactive users check...")

        try:
            async with get_session() as session:
                # Get users inactive for 7 days
                users_7d = await get_inactive_users(session, days=7)

                # Filter out users who were inactive for exactly 7 days (±1 day)
                now = datetime.utcnow()
                users_7d_exact = [
                    u
                    for u in users_7d
                    if timedelta(days=6) <= (now - u.last_activity) <= timedelta(days=8)
                ]

                for user in users_7d_exact:
                    try:
                        # Get BTC market data from CoinGecko
                        btc_data = await self.coingecko.get_price(
                            coin_id="bitcoin",
                            vs_currency="usd",
                            include_24h_change=True,
                        )

                        # Calculate BTC change description
                        if btc_data and "bitcoin" in btc_data:
                            btc_change_pct = btc_data["bitcoin"].get(
                                "usd_24h_change", 0
                            )
                            if btc_change_pct > 5:
                                btc_change = f"pumping +{btc_change_pct:.1f}%"
                                market_sentiment = "bullish"
                            elif btc_change_pct > 2:
                                btc_change = f"rising +{btc_change_pct:.1f}%"
                                market_sentiment = "slightly bullish"
                            elif btc_change_pct < -5:
                                btc_change = f"dumping {btc_change_pct:.1f}%"
                                market_sentiment = "bearish"
                            elif btc_change_pct < -2:
                                btc_change = f"falling {btc_change_pct:.1f}%"
                                market_sentiment = "slightly bearish"
                            else:
                                btc_change = f"stable ({btc_change_pct:+.1f}%)"
                                market_sentiment = "consolidating"
                        else:
                            # Fallback if API fails
                            btc_change = "stable"
                            market_sentiment = "consolidating"
                            logger.warning(
                                "Failed to fetch BTC data, using fallback values"
                            )

                        # Get user limits
                        _, current_count, limit = await check_request_limit(
                            session, user.id
                        )
                        limits_remaining = limit - current_count

                        message = REMINDER_7_DAYS_INACTIVE.format(
                            btc_change=btc_change,
                            market_sentiment=market_sentiment,
                            limits_remaining=limits_remaining,
                        )

                        await self.bot.send_message(
                            chat_id=user.telegram_id, text=message
                        )
                        logger.info(f"Sent 7d reminder to user {user.telegram_id}")
                    except (TelegramForbiddenError, TelegramBadRequest) as e:
                        logger.warning(
                            f"Failed to send 7d reminder to {user.telegram_id}: {e}"
                        )
                    except Exception as e:
                        logger.exception(
                            f"Error sending 7d reminder to {user.telegram_id}: {e}"
                        )

                # Get users inactive for 14 days
                users_14d = await get_inactive_users(session, days=14)

                # Filter exact 14 days (±1 day)
                users_14d_exact = [
                    u
                    for u in users_14d
                    if timedelta(days=13)
                    <= (now - u.last_activity)
                    <= timedelta(days=15)
                ]

                for user in users_14d_exact:
                    try:
                        # Get user limits
                        _, current_count, limit = await check_request_limit(
                            session, user.id
                        )
                        limits_remaining = limit - current_count

                        message = REMINDER_14_DAYS_INACTIVE.format(
                            limits_remaining=limits_remaining
                        )

                        await self.bot.send_message(
                            chat_id=user.telegram_id, text=message
                        )
                        logger.info(f"Sent 14d reminder to user {user.telegram_id}")
                    except (TelegramForbiddenError, TelegramBadRequest) as e:
                        logger.warning(
                            f"Failed to send 14d reminder to {user.telegram_id}: {e}"
                        )
                    except Exception as e:
                        logger.exception(
                            f"Error sending 14d reminder to {user.telegram_id}: {e}"
                        )

                logger.info(
                    f"Inactive users check complete: "
                    f"{len(users_7d_exact)} 7d reminders, {len(users_14d_exact)} 14d reminders"
                )

        except Exception as e:
            logger.exception(f"Error in inactive users check: {e}")

    async def check_subscription_status(self):
        """
        Check subscription status for all users and update database

        This helps detect users who unsubscribed from the channel
        """
        logger.info("Running subscription status check...")

        try:
            async with get_session() as session:
                # Get all users who were previously subscribed
                from src.database.models import User
                from sqlalchemy import select

                stmt = select(User).where(User.is_subscribed == True)
                result = await session.execute(stmt)
                subscribed_users = list(result.scalars().all())

                unsubscribed_count = 0

                for user in subscribed_users:
                    try:
                        # Check current subscription status
                        from aiogram.enums import ChatMemberStatus

                        member = await self.bot.get_chat_member(
                            chat_id=REQUIRED_CHANNEL, user_id=user.telegram_id
                        )

                        is_subscribed = member.status in {
                            ChatMemberStatus.MEMBER,
                            ChatMemberStatus.ADMINISTRATOR,
                            ChatMemberStatus.CREATOR,
                        }

                        # If user unsubscribed, update database
                        if not is_subscribed:
                            await update_user_subscription(
                                session, user.telegram_id, is_subscribed=False
                            )
                            unsubscribed_count += 1
                            logger.info(
                                f"User {user.telegram_id} unsubscribed from channel"
                            )

                            # Optionally send unsubscribe message
                            # (commented out to avoid spam)
                            # try:
                            #     from config.prompts import UNSUBSCRIBED_MESSAGE
                            #     message = UNSUBSCRIBED_MESSAGE.format(
                            #         channel_name=REQUIRED_CHANNEL,
                            #         channel_link=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}"
                            #     )
                            #     await self.bot.send_message(
                            #         chat_id=user.telegram_id,
                            #         text=message
                            #     )
                            # except Exception:
                            #     pass

                    except TelegramBadRequest:
                        # User might have blocked bot or deleted account
                        pass
                    except Exception as e:
                        logger.error(
                            f"Error checking subscription for {user.telegram_id}: {e}"
                        )

                logger.info(
                    f"Subscription check complete: "
                    f"{len(subscribed_users)} checked, {unsubscribed_count} unsubscribed"
                )

        except Exception as e:
            logger.exception(f"Error in subscription status check: {e}")

    async def motivate_active_users(self):
        """
        Send motivation messages to active users

        Sends encouraging messages to users who use the bot regularly
        """
        logger.info("Running active users motivation...")

        try:
            async with get_session() as session:
                # Get active users (active in last 3 days)
                from src.database.models import User
                from sqlalchemy import select

                three_days_ago = datetime.utcnow() - timedelta(days=3)
                stmt = select(User).where(
                    User.last_activity >= three_days_ago, User.is_subscribed == True
                )
                result = await session.execute(stmt)
                active_users = list(result.scalars().all())

                sent_count = 0

                for user in active_users:
                    try:
                        # Get user limits
                        _, current_count, limit = await check_request_limit(
                            session, user.id
                        )
                        limits_remaining = limit - current_count

                        message = ACTIVE_USER_MOTIVATION.format(
                            limits_remaining=limits_remaining,
                            random_catchphrase=get_random_catchphrase(),
                        )

                        await self.bot.send_message(
                            chat_id=user.telegram_id, text=message
                        )
                        sent_count += 1
                        logger.info(f"Sent motivation to user {user.telegram_id}")
                    except (TelegramForbiddenError, TelegramBadRequest) as e:
                        logger.warning(
                            f"Failed to send motivation to {user.telegram_id}: {e}"
                        )
                    except Exception as e:
                        logger.exception(
                            f"Error sending motivation to {user.telegram_id}: {e}"
                        )

                logger.info(
                    f"Motivation complete: {sent_count}/{len(active_users)} messages sent"
                )

        except Exception as e:
            logger.exception(f"Error in active users motivation: {e}")


# Global retention service instance
_retention_service: Optional[RetentionService] = None


def get_retention_service(bot: Bot) -> RetentionService:
    """
    Get or create retention service instance

    Args:
        bot: Telegram Bot instance

    Returns:
        RetentionService instance
    """
    global _retention_service

    if _retention_service is None:
        _retention_service = RetentionService(bot)

    return _retention_service


async def start_retention_service(bot: Bot):
    """
    Start the retention service

    Args:
        bot: Telegram Bot instance
    """
    service = get_retention_service(bot)
    await service.start()


async def stop_retention_service():
    """Stop the retention service"""
    global _retention_service

    if _retention_service is not None:
        await _retention_service.stop()
        _retention_service = None
