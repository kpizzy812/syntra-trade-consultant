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

        # Get user and session from data (provided by DatabaseMiddleware)
        session: AsyncSession = data.get("session")
        db_user = data.get("user")

        if not session or not db_user:
            # No session or user - skip limit check
            return await handler(event, data)

        # Refresh user to load subscription relationship
        await session.refresh(db_user, ["subscription"])

        # Check if user has requests left (now based on subscription tier)
        has_requests, current_count, limit = await check_request_limit(
            session, db_user  # Pass User object instead of user_id
        )

        if not has_requests:
            logger.info(f"User {db_user.telegram_id} (@{db_user.username or 'unknown'}) exceeded daily limit")

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

        logger.debug(f"User {db_user.telegram_id} has {remaining} requests remaining today")

        return await handler(event, data)
