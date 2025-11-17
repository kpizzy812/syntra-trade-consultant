"""
Language middleware - automatically detects and sets user language
"""

import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud import get_user_by_telegram_id, update_user_language
from src.utils.i18n import get_user_language

logger = logging.getLogger(__name__)


class LanguageMiddleware(BaseMiddleware):
    """
    Middleware to detect and set user language

    Adds 'user_language' to handler data
    """

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        """
        Process message/callback and detect user language

        Args:
            handler: Next handler in chain
            event: Incoming update (Message or CallbackQuery)
            data: Handler data dictionary

        Returns:
            Handler result
        """
        user = event.from_user
        session: AsyncSession = data.get("session")

        if not session or not user:
            # No session or user - skip language detection
            data["user_language"] = "ru"
            return await handler(event, data)

        try:
            # Get user from database
            db_user = await get_user_by_telegram_id(session, user.id)

            if db_user:
                # User exists - use saved language
                user_lang = db_user.language
            else:
                # New user - detect from Telegram
                telegram_lang = user.language_code
                user_lang = get_user_language(None, telegram_lang)

                logger.info(
                    f"Auto-detected language for new user {user.id}: "
                    f"{user_lang} (Telegram: {telegram_lang})"
                )

            # Set language in data for handlers
            data["user_language"] = user_lang

        except Exception as e:
            logger.error(f"Error in LanguageMiddleware for user {user.id}: {e}")
            # Fallback to default language
            data["user_language"] = "ru"

        return await handler(event, data)
