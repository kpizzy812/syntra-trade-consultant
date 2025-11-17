"""
Admin middleware - checks if user has admin rights
"""

from typing import Callable, Dict, Any, Awaitable
import logging

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from config.config import ADMIN_IDS


logger = logging.getLogger(__name__)


class AdminMiddleware(BaseMiddleware):
    """
    Middleware that checks if user is admin.
    Only allows admins to use admin commands.
    """

    # Admin commands that require admin rights
    ADMIN_COMMANDS = {
        "/admin",
        "/admin_stats",
        "/admin_users",
        "/admin_costs",
        "/admin_limits",
        "/admin_logs",
        "/admin_broadcast",
    }

    # Admin callback prefixes
    ADMIN_CALLBACK_PREFIXES = {"admin_"}

    def is_admin(self, user_id: int) -> bool:
        """
        Check if user is admin

        Args:
            user_id: User's Telegram ID

        Returns:
            True if admin, False otherwise
        """
        return user_id in ADMIN_IDS

    def is_admin_command(self, text: str) -> bool:
        """
        Check if command is admin command

        Args:
            text: Message text

        Returns:
            True if admin command, False otherwise
        """
        if not text:
            return False

        command = text.split()[0].lower()
        return command in self.ADMIN_COMMANDS

    def is_admin_callback(self, callback_data: str) -> bool:
        """
        Check if callback is admin callback

        Args:
            callback_data: Callback query data

        Returns:
            True if admin callback, False otherwise
        """
        if not callback_data:
            return False

        return any(
            callback_data.startswith(prefix) for prefix in self.ADMIN_CALLBACK_PREFIXES
        )

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Check admin rights before calling handler

        Args:
            handler: Next handler in chain
            event: Update event
            data: Handler data dict

        Returns:
            Handler result or None if blocked
        """
        user = None
        is_admin_action = False

        # Check for Message events
        if isinstance(event, Message):
            user = event.from_user
            if event.text:
                is_admin_action = self.is_admin_command(event.text)

        # Check for CallbackQuery events
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            if event.data:
                is_admin_action = self.is_admin_callback(event.data)

        # If not admin action, pass through
        if not is_admin_action:
            # Still add is_admin flag to data
            if user:
                data["is_admin"] = self.is_admin(user.id)
            return await handler(event, data)

        # Admin action - check rights
        if not user:
            logger.warning("Admin action attempted without user info")
            return None

        user_is_admin = self.is_admin(user.id)
        data["is_admin"] = user_is_admin

        if not user_is_admin:
            # User is not admin - block access
            logger.warning(
                f"Non-admin user {user.id} (@{user.username}) "
                f"attempted to use admin feature"
            )

            # Send access denied message
            if isinstance(event, Message):
                await event.answer(
                    "⛔ <b>Доступ запрещен</b>\n\n"
                    "Эта команда доступна только администраторам."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "⛔ Доступ запрещен. Только для администраторов.", show_alert=True
                )

            return None

        # User is admin - allow access
        logger.info(f"Admin {user.id} (@{user.username}) accessing admin feature")
        return await handler(event, data)
