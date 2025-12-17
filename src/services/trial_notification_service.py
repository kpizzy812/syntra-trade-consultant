"""
Trial Notification Service - sends notifications for trial events

Handles:
- 24h before trial end notification
- Trial ended + discount activation notification
- Discount expiring soon notification
"""

from datetime import datetime, UTC
from typing import Optional
from loguru import logger

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User, Subscription
from src.services.trial_service import (
    check_trial_ending_24h,
    mark_trial_notification_sent,
    get_trial_days_remaining,
    get_discount_hours_remaining,
)
from src.utils.i18n import i18n


async def send_trial_ending_24h_notification(
    bot: Bot, user: User, subscription: Subscription, session: AsyncSession
) -> bool:
    """
    Send notification 24h before trial ends

    Args:
        bot: Telegram bot instance
        user: User model
        subscription: Subscription model
        session: Database session

    Returns:
        True if sent successfully
    """
    lang = user.language or "ru"

    # Get trial info
    days_remaining = get_trial_days_remaining(subscription)

    # Build message
    message = i18n.get(
        "trial.ending_24h",
        lang,
        days_remaining=days_remaining,
    )

    # Keyboard with upgrade button
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.get("trial.upgrade_button", lang),
                    web_app={"url": f"https://t.me/your_bot_username/premium"},
                )
            ]
        ]
    )

    try:
        await bot.send_message(
            chat_id=user.telegram_id, text=message, reply_markup=keyboard
        )

        # Mark as sent
        await mark_trial_notification_sent(session, subscription, "24h")

        logger.info(
            f"Sent trial ending 24h notification to user {user.telegram_id} "
            f"(@{user.username})"
        )
        return True

    except Exception as e:
        logger.error(
            f"Failed to send trial ending notification to {user.telegram_id}: {e}"
        )
        return False


async def send_trial_ended_notification(
    bot: Bot, user: User, subscription: Subscription, session: AsyncSession
) -> bool:
    """
    Send notification when trial ends + discount activated

    Args:
        bot: Telegram bot instance
        user: User model
        subscription: Subscription model (already downgraded with discount)
        session: Database session

    Returns:
        True if sent successfully
    """
    lang = user.language or "ru"

    # Get discount info
    hours_remaining = get_discount_hours_remaining(subscription)

    # Build message
    message = i18n.get(
        "trial.ended_with_discount",
        lang,
        hours_remaining=hours_remaining,
        discount_percent=20,
    )

    # Keyboard with discounted upgrade button
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.get("trial.activate_discount_button", lang),
                    web_app={"url": f"https://t.me/your_bot_username/premium?discount=true"},
                )
            ]
        ]
    )

    try:
        await bot.send_message(
            chat_id=user.telegram_id, text=message, reply_markup=keyboard
        )

        # Mark as sent
        await mark_trial_notification_sent(session, subscription, "end")

        logger.info(
            f"Sent trial ended + discount notification to user {user.telegram_id} "
            f"(@{user.username})"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to send trial ended notification to {user.telegram_id}: {e}")
        return False


async def send_discount_expiring_notification(
    bot: Bot, user: User, subscription: Subscription
) -> bool:
    """
    Send reminder that discount is expiring soon (optional, can be called manually)

    Args:
        bot: Telegram bot instance
        user: User model
        subscription: Subscription model

    Returns:
        True if sent successfully
    """
    lang = user.language or "ru"

    # Get remaining hours
    hours_remaining = get_discount_hours_remaining(subscription)

    if hours_remaining <= 0:
        return False

    # Build message
    message = i18n.get(
        "trial.discount_expiring",
        lang,
        hours_remaining=hours_remaining,
        discount_percent=20,
    )

    # Keyboard
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.get("trial.activate_discount_button", lang),
                    web_app={"url": f"https://t.me/your_bot_username/premium?discount=true"},
                )
            ]
        ]
    )

    try:
        await bot.send_message(
            chat_id=user.telegram_id, text=message, reply_markup=keyboard
        )

        logger.info(
            f"Sent discount expiring notification to user {user.telegram_id} "
            f"(@{user.username})"
        )
        return True

    except Exception as e:
        logger.error(
            f"Failed to send discount expiring notification to {user.telegram_id}: {e}"
        )
        return False


async def process_trial_notifications(bot: Bot, session: AsyncSession) -> dict:
    """
    Process all trial notifications (called by cron job)

    Args:
        bot: Telegram bot instance
        session: Database session

    Returns:
        Dict with results
    """
    results = {
        "notifications_24h_sent": 0,
        "notifications_24h_failed": 0,
    }

    # Find users with trial ending in 24h
    trials_ending_24h = await check_trial_ending_24h(session)

    for user, subscription in trials_ending_24h:
        success = await send_trial_ending_24h_notification(
            bot, user, subscription, session
        )

        if success:
            results["notifications_24h_sent"] += 1
        else:
            results["notifications_24h_failed"] += 1

    logger.info(
        f"Trial notifications processed: {results['notifications_24h_sent']} sent, "
        f"{results['notifications_24h_failed']} failed"
    )

    return results


# ============================================================================
# HELPER FOR TRIAL ENDED NOTIFICATIONS (called from trial_service)
# ============================================================================


async def notify_trial_ended(
    bot: Bot, user: User, subscription: Subscription, session: AsyncSession
) -> None:
    """
    Helper to send trial ended notification (called when downgrading)

    Args:
        bot: Telegram bot instance
        user: User model
        subscription: Subscription model (already downgraded)
        session: Database session
    """
    await send_trial_ended_notification(bot, user, subscription, session)
