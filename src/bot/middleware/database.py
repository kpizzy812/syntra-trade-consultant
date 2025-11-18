"""
Database middleware - provides database session and user object to handlers
"""

from typing import Callable, Dict, Any, Awaitable
import logging

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, PreCheckoutQuery

from src.database.engine import get_session_maker
from src.database.crud import get_or_create_user


logger = logging.getLogger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """
    Middleware that provides database session and user object to handlers.

    Usage in handler:
        async def my_handler(message: Message, user: User, session: AsyncSession):
            # Use session and user here
            pass
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Create database session and get user object, pass to handler

        Args:
            handler: Next handler in chain
            event: Update event (Message, CallbackQuery, PreCheckoutQuery, etc.)
            data: Handler data dict

        Returns:
            Handler result
        """
        # Get session from async context manager
        session_maker = get_session_maker()
        async with session_maker() as session:
            # Add session to handler data
            data["session"] = session

            # Get telegram user from event
            telegram_user = None
            if isinstance(event, (Message, CallbackQuery)):
                telegram_user = event.from_user
            elif isinstance(event, PreCheckoutQuery):
                telegram_user = event.from_user

            # Get or create user in database if telegram_user exists
            if telegram_user:
                try:
                    db_user, _ = await get_or_create_user(
                        session,
                        telegram_id=telegram_user.id,
                        username=telegram_user.username,
                        first_name=telegram_user.first_name,
                        last_name=telegram_user.last_name,
                    )
                    # Add user to handler data
                    data["user"] = db_user
                    logger.debug(f"User {db_user.id} (telegram_id={telegram_user.id}) loaded")
                except Exception as e:
                    logger.error(f"Error getting user from database: {e}")
                    # Continue without user object

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
