"""
/limits command handler - shows user request limits and remaining requests
"""

from datetime import datetime, timezone, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud import get_user_by_telegram_id
from src.database.limit_manager import get_usage_stats
from src.utils.i18n import i18n

router = Router(name="limits")


def _progress_bar(used: int, limit: int, length: int = 10) -> str:
    """Create a text progress bar"""
    if limit == 0:
        return "▓" * length
    filled = int((used / limit) * length)
    empty = length - filled
    return "▓" * filled + "░" * empty


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
        await message.answer(i18n.get("errors.user_not_found", user_language))
        logger.error(f"User {message.from_user.id} not found in database")
        return

    # Refresh subscription relationship
    await session.refresh(user, ["subscription"])

    # Get detailed usage stats
    stats = await get_usage_stats(session, user)

    # Calculate reset time (next midnight UTC)
    now_utc = datetime.now(timezone.utc)
    next_midnight = (now_utc + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    hours_until_reset = int((next_midnight - now_utc).total_seconds() / 3600)

    # Get tier name
    tier = stats["tier"].upper()
    tier_emoji = {"free": "🆓", "basic": "⭐", "premium": "💎", "vip": "👑"}.get(
        stats["tier"], "📊"
    )

    # Build detailed response
    text_bar = _progress_bar(stats["text"]["count"], stats["text"]["limit"])
    vision_bar = _progress_bar(stats["vision"]["count"], stats["vision"]["limit"])

    # Determine overall status
    total_remaining = stats["text"]["remaining"] + stats["vision"]["remaining"]
    if total_remaining > 0:
        status_emoji = "✅"
        status_text = i18n.get("limits.status_available", user_language)
    else:
        status_emoji = "🔴"
        status_text = i18n.get("limits.status_depleted", user_language)

    response = f"""{status_emoji} <b>{i18n.get('limits.title', user_language)}</b>

{tier_emoji} <b>{i18n.get('limits.your_plan', user_language)}:</b> {tier}

💬 <b>{i18n.get('limits.text_requests', user_language)}</b>
{text_bar} {stats['text']['count']}/{stats['text']['limit']}
{i18n.get('limits.remaining_short', user_language)}: {stats['text']['remaining']}

📷 <b>{i18n.get('limits.vision_requests', user_language)}</b>
{vision_bar} {stats['vision']['count']}/{stats['vision']['limit']}
{i18n.get('limits.remaining_short', user_language)}: {stats['vision']['remaining']}

⏰ <b>{i18n.get('limits.reset', user_language)}</b>
{i18n.get('limits.reset_time', user_language, hours=hours_until_reset)}

{status_text}
"""

    # Add Premium button for free users
    keyboard = None
    if stats["tier"] == "free":
        premium_text = i18n.get("trial.upgrade_button", user_language)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=premium_text, callback_data="premium_menu")]
            ]
        )

    await message.answer(response, reply_markup=keyboard, parse_mode="HTML")

    logger.info(
        f"Limits shown to user {message.from_user.id}: "
        f"text={stats['text']['count']}/{stats['text']['limit']}, "
        f"vision={stats['vision']['count']}/{stats['vision']['limit']}, "
        f"tier={stats['tier']}"
    )
