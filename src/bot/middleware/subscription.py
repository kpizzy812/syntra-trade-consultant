"""
Subscription middleware - checks if user is subscribed to required channel
"""
from typing import Callable, Dict, Any, Awaitable
import logging

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest

from config.config import REQUIRED_CHANNEL, SKIP_SUBSCRIPTION_CHECK
from src.utils.i18n import i18n


logger = logging.getLogger(__name__)


class SubscriptionMiddleware(BaseMiddleware):
    """
    Middleware that checks if user is subscribed to required channel.
    Blocks non-subscribers from using the bot.
    """

    # Commands that work without subscription
    ALLOWED_COMMANDS = {'/start', '/help'}

    async def check_subscription(self, bot, user_id: int) -> bool:
        """
        Check if user is subscribed to required channel

        Args:
            bot: Bot instance
            user_id: User's Telegram ID

        Returns:
            True if subscribed, False otherwise
        """
        if not REQUIRED_CHANNEL:
            # No required channel configured
            return True

        try:
            member = await bot.get_chat_member(
                chat_id=REQUIRED_CHANNEL,
                user_id=user_id
            )

            # Check if user is member, admin or creator
            return member.status in {
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.CREATOR
            }

        except TelegramBadRequest as e:
            error_msg = str(e)

            # If bot is not admin in channel, log warning
            if "member list is inaccessible" in error_msg.lower():
                logger.warning(
                    f"⚠️ Bot cannot check subscription - not admin in {REQUIRED_CHANNEL}. "
                    f"Add bot as channel admin to enable subscription checks!"
                )

                # In development mode, can skip subscription check (SKIP_SUBSCRIPTION_CHECK=true)
                # In production, MUST fail closed (SKIP_SUBSCRIPTION_CHECK=false or unset)
                if SKIP_SUBSCRIPTION_CHECK:
                    logger.warning("⚠️ SKIP_SUBSCRIPTION_CHECK is enabled - allowing access without verification!")
                    return True
                else:
                    logger.error("🔒 Subscription check failed - denying access (production mode)")
                    return False

            # For other Telegram errors, deny access (fail closed)
            logger.error(f"Telegram error checking subscription for user {user_id}: {e}")
            return False

        except Exception as e:
            logger.exception(f"Unexpected error checking subscription: {e}")
            # For unexpected errors, deny access (fail closed)
            return False

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Check subscription before calling handler

        Args:
            handler: Next handler in chain
            event: Update event
            data: Handler data dict

        Returns:
            Handler result or None if blocked
        """
        # Check both Message and CallbackQuery events
        if isinstance(event, Message):
            # Allow commands that work without subscription
            if event.text and event.text.split()[0] in self.ALLOWED_COMMANDS:
                return await handler(event, data)

            user = event.from_user
        elif isinstance(event, CallbackQuery):
            # Check subscription for button clicks too
            user = event.from_user
        else:
            # Other event types - skip check
            return await handler(event, data)

        # Get bot
        bot = data.get('bot')

        if not user:
            return await handler(event, data)

        # Check subscription
        is_subscribed = await self.check_subscription(bot, user.id)

        if is_subscribed:
            # Update subscription status in handler data
            data['is_subscribed'] = True
            return await handler(event, data)

        # User not subscribed - send subscription prompt
        logger.info(f"User {user.id} (@{user.username}) is not subscribed")

        # Get user language from data (set by LanguageMiddleware)
        user_lang = data.get('user_language', 'ru')

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 " + ("Subscribe to channel" if user_lang == 'en' else "Подписаться на канал"),
                    url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=i18n.get('subscription.check_button', user_lang),
                    callback_data="check_subscription"
                )
            ]
        ])

        subscription_text = i18n.get('subscription.required', user_lang, channel=f"@{REQUIRED_CHANNEL.lstrip('@')}")

        # Send different messages for Message vs CallbackQuery
        if isinstance(event, Message):
            await event.answer(
                subscription_text,
                reply_markup=keyboard
            )
        elif isinstance(event, CallbackQuery):
            await event.answer(
                i18n.get('subscription.not_found', user_lang).split('.')[0],  # Short message for alert
                show_alert=True
            )
            await event.message.answer(
                subscription_text,
                reply_markup=keyboard
            )

        # Block further processing
        return None
