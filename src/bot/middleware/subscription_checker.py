"""
Subscription checker middleware - checks subscription expiry and downgrades if needed
"""

from typing import Callable, Dict, Any, Awaitable
from datetime import datetime, UTC

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud import deactivate_subscription, get_subscription
from src.database.models import SubscriptionTier
from src.utils.i18n import i18n


class SubscriptionCheckerMiddleware(BaseMiddleware):
    """
    Middleware that checks subscription status and handles expiration

    Features:
    - Checks if subscription is expired
    - Auto-downgrades to FREE tier
    - Notifies user about expiration
    - Warns about upcoming expiration (7/3/1 days)
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Check subscription status before calling handler

        Args:
            handler: Next handler in chain
            event: Update event
            data: Handler data dict

        Returns:
            Handler result
        """
        # Only check for Message events
        if not isinstance(event, Message):
            return await handler(event, data)

        # Get session and user
        session: AsyncSession = data.get("session")
        user = data.get("user")  # DB User object (set by DatabaseMiddleware)

        if not session or not user:
            return await handler(event, data)

        # Load subscription if not already loaded
        if not user.subscription:
            await session.refresh(user, ["subscription"])

        subscription = user.subscription

        # If no subscription or FREE tier, skip check
        if not subscription or subscription.tier == SubscriptionTier.FREE.value:
            return await handler(event, data)

        # Check if expired
        now = datetime.now(UTC)
        if subscription.expires_at and subscription.expires_at < now:
            if subscription.is_active:
                logger.info(
                    f"Subscription expired for user {user.telegram_id}, downgrading to FREE"
                )

                # Downgrade to FREE
                await deactivate_subscription(session, user.id)

                # Get user language
                user_lang = data.get("user_language", "ru")

                # Get tier name from i18n
                tier_name = i18n.get(f"tier_names.{subscription.tier}", user_lang)

                # Notify user
                await event.answer(
                    i18n.get(
                        "subscription_expiry.expired",
                        user_lang,
                        tier=tier_name,
                    )
                )

        # Check for upcoming expiration (warn once per day)
        elif subscription.expires_at:
            days_left = (subscription.expires_at - now).days

            # Warn about expiration (7, 3, 1 days)
            if days_left in [7, 3, 1]:
                # Check if we already warned today (use cache or DB flag)
                # For now, just log
                logger.info(
                    f"Subscription expiring in {days_left} days for user {user.telegram_id}"
                )

                # Get user language
                user_lang = data.get("user_language", "ru")
                tier_name = i18n.get(f"tier_names.{subscription.tier}", user_lang)

                # Notify user (only if not notified today)
                # TODO: Add notification tracking to avoid spam
                # For now, show warning
                if days_left <= 3:  # Only show for 3 days or less (with discount offer)
                    await event.answer(
                        i18n.get(
                            "subscription_expiry.expiring_soon",
                            user_lang,
                            days=days_left,
                            tier=tier_name,
                        )
                    )
                elif days_left == 7:  # Reminder at 7 days
                    await event.answer(
                        i18n.get(
                            "subscription_expiry.expiring_7_days",
                            user_lang,
                            tier=tier_name,
                            date=subscription.expires_at.strftime('%d.%m.%Y'),
                        )
                    )

        return await handler(event, data)
