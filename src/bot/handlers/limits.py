"""
/limits command handler - shows user request limits and remaining requests
"""

import logging
from datetime import datetime, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud import check_request_limit, get_user_by_telegram_id
from src.utils.i18n import i18n
from config.config import REQUEST_LIMIT_PER_DAY


logger = logging.getLogger(__name__)
router = Router(name="limits")


@router.message(Command("limits"))
async def cmd_limits(
    message: Message, session: AsyncSession, user_language: str = "ru"
):
    """
    Handle /limits command - show user's request limits and usage

    Args:
        message: Incoming message
        session: Database session (injected by DatabaseMiddleware)
        user_language: User language (provided by LanguageMiddleware)
    """
    user = await get_user_by_telegram_id(session, message.from_user.id)

    if not user:
        # Should not happen if middleware is working correctly
        await message.answer(i18n.get("errors.user_not_found", user_language))
        logger.error(f"User {message.from_user.id} not found in database")
        return

    # Get request limit info
    has_remaining, current_count, limit = await check_request_limit(session, user.id)
    remaining = limit - current_count

    # Calculate reset time (next midnight UTC)
    now_utc = datetime.now(timezone.utc)
    next_midnight = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    if now_utc.hour > 0 or now_utc.minute > 0:
        # Already past midnight today, so next reset is tomorrow
        from datetime import timedelta

        next_midnight = next_midnight + timedelta(days=1)

    hours_until_reset = int((next_midnight - now_utc).total_seconds() / 3600)

    # Build response message
    if has_remaining:
        status_emoji = "✅"
        status_text = i18n.get("limits.status_available", user_language)
    else:
        status_emoji = "🔴"
        status_text = i18n.get("limits.status_depleted", user_language)

    response = f"""{status_emoji} <b>{i18n.get('limits.title', user_language)}</b>

📊 <b>{i18n.get('limits.usage', user_language)}</b>
{i18n.get('limits.used', user_language, count=current_count, limit=limit)}
{i18n.get('limits.remaining', user_language, count=remaining)}

⏰ <b>{i18n.get('limits.reset', user_language)}</b>
{i18n.get('limits.reset_time', user_language, hours=hours_until_reset)}

{status_text}
"""

    await message.answer(response)

    logger.info(
        f"Limits shown to user {message.from_user.id}: "
        f"{current_count}/{limit} used, {remaining} remaining"
    )
