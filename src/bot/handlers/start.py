"""
/start command handler
"""

import logging
import os
from pathlib import Path

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud import get_or_create_user
from src.utils.i18n import i18n


logger = logging.getLogger(__name__)
router = Router(name="start")


def get_main_menu(language: str = "ru") -> InlineKeyboardMarkup:
    """
    Create main menu inline keyboard

    Args:
        language: User language (ru or en)

    Returns:
        InlineKeyboardMarkup with main navigation buttons
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.get("menu.help", language), callback_data="menu_help"
                ),
                InlineKeyboardButton(
                    text=i18n.get("menu.profile", language),
                    callback_data="menu_profile",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.get("menu.referral", language),
                    callback_data="menu_referral",
                ),
                InlineKeyboardButton(
                    text=i18n.get("menu.premium", language),
                    callback_data="menu_premium",
                ),
            ],
        ]
    )
    return keyboard


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, user_language: str = "ru"):
    """
    Handle /start command - welcome message and user registration

    Args:
        message: Incoming message
        session: Database session (provided by DatabaseMiddleware)
        user_language: User language (provided by LanguageMiddleware)
    """
    user = message.from_user

    # Register or update user in database
    db_user, is_new = await get_or_create_user(
        session,
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        telegram_language=user.language_code,
    )

    # Use user's saved language from database
    lang = db_user.language

    if is_new:
        logger.info(
            f"New user registered: {user.id} (@{user.username}) with language: {lang}"
        )
        greeting = i18n.get("start.welcome_new", lang, name=user.first_name or "User")
    else:
        logger.info(f"Returning user: {user.id} (@{user.username})")
        greeting = i18n.get("start.welcome_back", lang, name=user.first_name or "User")

    # Try to send with image, fallback to text if image not found
    image_path = Path("assets/images/start.png")
    if image_path.exists():
        photo = FSInputFile(image_path)
        await message.answer_photo(
            photo=photo, caption=greeting, reply_markup=get_main_menu(lang)
        )
    else:
        await message.answer(greeting, reply_markup=get_main_menu(lang))
