"""
Logging middleware - logs all incoming updates
"""

from typing import Callable, Dict, Any, Awaitable

import time

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery


from loguru import logger


class LoggingMiddleware(BaseMiddleware):
    """
    Middleware that logs all incoming updates and handler execution time
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Log update and measure handler execution time

        Args:
            handler: Next handler in chain
            event: Update event
            data: Handler data dict

        Returns:
            Handler result
        """
        # Get user info
        user_id = None
        username = None
        update_type = type(event).__name__

        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            username = event.from_user.username if event.from_user else None
            text = event.text or event.caption or f"[{event.content_type}]"
            logger.info(f"Message from @{username} (ID: {user_id}): {text[:100]}")

        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            username = event.from_user.username
            logger.info(f"Callback from @{username} (ID: {user_id}): {event.data}")

        # Measure execution time
        start_time = time.time()

        try:
            result = await handler(event, data)
            execution_time = time.time() - start_time

            logger.info(
                f"{update_type} processed in {execution_time:.3f}s "
                f"(user: {user_id})"
            )

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"{update_type} failed after {execution_time:.3f}s "
                f"(user: {user_id}): {e}"
            )
            raise
