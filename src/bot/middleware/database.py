"""
Database middleware - provides database session to handlers
"""

from typing import Callable, Dict, Any, Awaitable
import logging

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from src.database.engine import get_session_maker


logger = logging.getLogger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """
    Middleware that provides database session to handlers.

    Usage in handler:
        async def my_handler(message: Message, session: AsyncSession):
            # Use session here
            pass
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Create database session and pass it to handler

        Args:
            handler: Next handler in chain
            event: Update event (Message, CallbackQuery, etc.)
            data: Handler data dict

        Returns:
            Handler result
        """
        # Get session from async context manager
        session_maker = get_session_maker()
        async with session_maker() as session:
            # Add session to handler data
            data["session"] = session

            try:
                # Call next handler
                result = await handler(event, data)

                # Commit changes if handler succeeded
                await session.commit()

                return result

            except Exception as e:
                # Rollback on error
                await session.rollback()
                logger.error(f"Database error in handler: {e}")
                raise
