"""
Language middleware - automatically detects and sets user language
"""

import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.i18n import get_user_language

logger = logging.getLogger(__name__)


class LanguageMiddleware(BaseMiddleware):
    """
    Middleware to detect and set user language

    Adds 'user_language' to handler data
    """

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery | PreCheckoutQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery | PreCheckoutQuery,
        data: Dict[str, Any],
    ) -> Any:
        """
        Process message/callback/pre-checkout and detect user language

        Args:
            handler: Next handler in chain
            event: Incoming update (Message, CallbackQuery or PreCheckoutQuery)
            data: Handler data dictionary

        Returns:
            Handler result
        """
        telegram_user = event.from_user
        session: AsyncSession = data.get("session")
        db_user = data.get("user")  # Provided by DatabaseMiddleware

        if not session or not telegram_user:
            # No session or telegram user - skip language detection
            data["user_language"] = "ru"
            return await handler(event, data)

        try:
            if db_user and db_user.language:
                # User exists in database - use saved language
                user_lang = db_user.language
            else:
                # New user or no language set - detect from Telegram
                telegram_lang = telegram_user.language_code
                user_lang = get_user_language(None, telegram_lang)

                logger.info(
                    f"Auto-detected language for user {telegram_user.id}: "
                    f"{user_lang} (Telegram: {telegram_lang})"
                )

            # Set language in data for handlers
            data["user_language"] = user_lang

        except Exception as e:
            logger.error(f"Error in LanguageMiddleware for user {telegram_user.id}: {e}")
            # Fallback to default language
            data["user_language"] = "ru"

        return await handler(event, data)
