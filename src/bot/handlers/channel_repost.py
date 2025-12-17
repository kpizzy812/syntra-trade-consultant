# coding: utf-8
"""
Channel Auto-Repost Handler

Automatically forwards posts from the official channel to all bot users.
Can be enabled/disabled via admin panel.
"""

import asyncio

from aiogram import Router, Bot
from aiogram.types import Message
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.config import OFFICIAL_CHANNEL_ID, ADMIN_IDS
from src.database.engine import get_session_maker
from src.database.models import User
from src.cache import get_redis_manager

router = Router(name="channel_repost")

# Redis key for auto-repost setting
AUTO_REPOST_KEY = "settings:auto_repost_enabled"


async def get_auto_repost_enabled() -> bool:
    """
    Check if auto-repost from channel is enabled.
    Default: True (enabled)
    """
    redis = get_redis_manager()
    if not redis.is_available():
        return True  # Default to enabled if Redis is not available

    try:
        # Direct Redis call to avoid JSON parsing issues
        value = await redis._client.get(AUTO_REPOST_KEY)
        if value is None:
            return True  # Default enabled
        # Redis returns bytes, decode to string
        if isinstance(value, bytes):
            value = value.decode('utf-8')
        return str(value).lower() == "true"
    except Exception as e:
        logger.error(f"Error getting auto-repost setting: {e}")
        return True


async def set_auto_repost_enabled(enabled: bool) -> None:
    """
    Enable/disable auto-repost from channel.

    Args:
        enabled: True to enable, False to disable
    """
    redis = get_redis_manager()
    if not redis.is_available():
        logger.warning("Redis not available, cannot save auto-repost setting")
        return

    try:
        # Use permanent storage (no TTL) for settings
        await redis._client.set(AUTO_REPOST_KEY, "true" if enabled else "false")
        logger.info(f"Auto-repost setting changed to: {enabled}")
    except Exception as e:
        logger.error(f"Error setting auto-repost: {e}")


async def get_all_telegram_users(session: AsyncSession) -> list[User]:
    """Get all users with telegram_id who are not banned"""
    stmt = select(User).where(
        User.telegram_id.isnot(None),
        User.is_banned.is_(False),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.channel_post()
async def auto_repost_channel_post(message: Message, bot: Bot):
    """
    Automatically repost new posts from the official channel.

    Works only if:
    1. Auto-repost is enabled in settings
    2. Post is from the official channel (OFFICIAL_CHANNEL_ID)
    """
    # Check if official channel is configured
    if not OFFICIAL_CHANNEL_ID:
        return

    # Check if this is from our official channel
    if message.chat.id != OFFICIAL_CHANNEL_ID:
        return

    # Check if auto-repost is enabled
    if not await get_auto_repost_enabled():
        logger.debug(f"Auto-repost disabled, skipping post {message.message_id}")
        return

    logger.info(
        f"Auto-repost: new post in channel {message.chat.title}, "
        f"ID: {message.message_id}"
    )

    # Run repost in background to not block other handlers
    asyncio.create_task(
        broadcast_channel_post(bot, message)
    )


async def broadcast_channel_post(bot: Bot, message: Message):
    """Forward channel post to all bot users"""
    # Get users first, then close session before long broadcast
    async with get_session_maker()() as session:
        users = await get_all_telegram_users(session)

    if not users:
        logger.info("No users found for auto-repost")
        return

    logger.info(f"Starting auto-repost to {len(users)} users...")

    sent = 0
    blocked = 0
    failed = 0

    try:
        for user in users:
            try:
                await asyncio.sleep(0.05)  # Rate limit delay

                # Forward with source attribution
                await bot.forward_message(
                    chat_id=user.telegram_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                sent += 1

            except Exception as e:
                error_str = str(e).lower()
                if "blocked" in error_str or "chat not found" in error_str:
                    blocked += 1
                else:
                    failed += 1

        total = sent + blocked + failed
        logger.info(
            f"Auto-repost completed: sent={sent}/{total}, "
            f"blocked={blocked}, failed={failed}"
        )

        # Notify first admin about results
        if ADMIN_IDS:
            report = (
                f"<b>Auto-repost completed</b>\n\n"
                f"Post from: {message.chat.title}\n"
                f"Delivered: {sent:,}\n"
                f"Blocked: {blocked:,}\n"
                f"Errors: {failed:,}"
            )

            try:
                await bot.send_message(
                    ADMIN_IDS[0],
                    report,
                    parse_mode="HTML"
                )
            except Exception:
                pass  # Ignore admin notification errors

    except Exception as e:
        logger.exception(f"Auto-repost error: {e}")
