"""
Request limit middleware - enforces daily request limits with separate counters

Supports three types of request limits:
- Text requests (AI chat analysis)
- Chart requests (technical chart generation)
- Vision requests (screenshot/image analysis)
"""

from datetime import datetime, timezone, timedelta
from typing import Callable, Dict, Any, Awaitable
from loguru import logger

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.limit_manager import (
    check_limit,
    increment_limit,
    detect_request_type,
    RequestType,
)
from src.utils.i18n import i18n


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
        logger.info(f"[REQUEST_LIMIT] Middleware called, event type: {type(event).__name__}")

        # Only check for Message events
        if not isinstance(event, Message):
            logger.info(f"[REQUEST_LIMIT] Skipping - not a Message event")
            return await handler(event, data)

        # Skip check for exempt commands
        if event.text and event.text.split()[0] in self.EXEMPT_COMMANDS:
            logger.info(f"[REQUEST_LIMIT] Skipping - exempt command: {event.text.split()[0]}")
            return await handler(event, data)

        # Skip check for admin users (set by AdminMiddleware)
        is_admin = data.get("is_admin", False)
        if is_admin:
            logger.info(f"[REQUEST_LIMIT] Skipping - admin user")
            return await handler(event, data)

        # Get user and session from data (provided by DatabaseMiddleware)
        session: AsyncSession = data.get("session")
        db_user = data.get("user")

        logger.info(f"[REQUEST_LIMIT] session={session is not None}, db_user={db_user is not None}")

        if not session or not db_user:
            # No session or user - skip limit check
            logger.warning(f"[REQUEST_LIMIT] Skipping - no session or user!")
            return await handler(event, data)

        # Refresh user to load subscription relationship
        await session.refresh(db_user, ["subscription"])

        # Detect request type from message
        has_photo = bool(event.photo)
        message_text = event.text or event.caption
        request_type = detect_request_type(message_text, has_photo)

        logger.info(f"[REQUEST_LIMIT] Detected request type: {request_type.value}")

        # Check if user has requests left for this type
        has_requests, current_count, limit = await check_limit(
            session, db_user, request_type
        )

        if not has_requests:
            logger.info(
                f"User {db_user.telegram_id} (@{db_user.username or 'unknown'}) "
                f"exceeded {request_type.value} limit: {current_count}/{limit}"
            )

            # Get user language from data (set by LanguageMiddleware)
            user_lang = data.get("user_language", "ru")

            # Calculate hours until reset (next midnight UTC)
            now_utc = datetime.now(timezone.utc)
            next_midnight = (now_utc + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            hours_until_reset = int((next_midnight - now_utc).total_seconds() / 3600)

            # Send limit exceeded message with Premium button
            error_msg = i18n.get(
                "errors.rate_limit_bot",
                user_lang,
                limit=limit,
                hours=hours_until_reset,
            )

            # Create keyboard with Premium button
            premium_button_text = i18n.get("trial.upgrade_button", user_lang)
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=premium_button_text, callback_data="premium_menu")]
                ]
            )

            await event.answer(error_msg, reply_markup=keyboard, parse_mode="HTML")

            # Block further processing
            return None

        # User has requests - increment counter
        logger.info(
            f"[REQUEST_LIMIT] Incrementing {request_type.value} counter "
            f"for user {db_user.telegram_id}"
        )
        await increment_limit(session, db_user.id, request_type)

        # Calculate remaining requests
        remaining = limit - current_count - 1  # -1 for current request

        # Add request info to handler data
        data["request_type"] = request_type
        data["requests_remaining"] = remaining
        data["requests_limit"] = limit

        logger.info(
            f"[REQUEST_LIMIT] User {db_user.telegram_id} has {remaining}/{limit} "
            f"{request_type.value} requests remaining today"
        )

        return await handler(event, data)
