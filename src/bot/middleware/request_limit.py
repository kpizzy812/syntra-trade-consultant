"""
Request limit middleware - enforces daily request limits
"""

from typing import Callable, Dict, Any, Awaitable
import logging

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from sqlalchemy.ext.asyncio import AsyncSession

from config.config import REQUEST_LIMIT_PER_DAY
from src.database.crud import (
    check_request_limit,
    increment_request_count,
    get_or_create_user,
)
from src.utils.i18n import i18n


logger = logging.getLogger(__name__)


class RequestLimitMiddleware(BaseMiddleware):
    """
    Middleware that enforces daily request limits per user.
    Free users get limited requests per day.
    """

    # Commands that don't count towards limit
    EXEMPT_COMMANDS = {"/start", "/help"}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Check request limit before calling handler

        Args:
            handler: Next handler in chain
            event: Update event
            data: Handler data dict

        Returns:
            Handler result or None if limit exceeded
        """
        # Only check for Message events
        if not isinstance(event, Message):
            return await handler(event, data)

        # Skip check for exempt commands
        if event.text and event.text.split()[0] in self.EXEMPT_COMMANDS:
            return await handler(event, data)

        # Skip check for admin users (set by AdminMiddleware)
        is_admin = data.get("is_admin", False)
        if is_admin:
            logger.debug(f"Skipping limit check for admin user")
            return await handler(event, data)

        # Get user and session
        user = event.from_user
        session: AsyncSession = data.get("session")

        if not user or not session:
            return await handler(event, data)

        # Ensure user exists in database before checking limits
        db_user, _ = await get_or_create_user(
            session,
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )

        # Check if user has requests left
        has_requests, current_count, limit = await check_request_limit(
            session, db_user.id
        )

        if not has_requests:
            logger.info(f"User {user.id} (@{user.username}) exceeded daily limit")

            # Get user language from data (set by LanguageMiddleware)
            user_lang = data.get("user_language", "ru")

            await event.answer(i18n.get("errors.rate_limit", user_lang, limit=limit))

            # Block further processing
            return None

        # User has requests - increment counter
        await increment_request_count(session, db_user.id)

        # Calculate remaining requests
        remaining = limit - current_count - 1  # -1 for current request

        # Add remaining requests to handler data
        data["requests_remaining"] = remaining

        logger.debug(f"User {user.id} has {remaining} requests remaining today")

        return await handler(event, data)
