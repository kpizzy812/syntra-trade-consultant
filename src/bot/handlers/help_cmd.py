"""
/help command handler
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from loguru import logger

from src.utils.i18n import i18n
from config.config import (
    TERMS_OF_SERVICE_URL_RU,
    TERMS_OF_SERVICE_URL_EN,
    PRIVACY_POLICY_URL_RU,
    PRIVACY_POLICY_URL_EN,
)

router = Router(name="help")


@router.message(Command("help"))
async def cmd_help(message: Message, user_language: str = "ru"):
    """
    Handle /help command - show available commands and usage

    Args:
        message: Incoming message
        user_language: User language (provided by LanguageMiddleware)
    """
    # Get URLs based on language
    terms_url = TERMS_OF_SERVICE_URL_RU if user_language == "ru" else TERMS_OF_SERVICE_URL_EN
    privacy_url = PRIVACY_POLICY_URL_RU if user_language == "ru" else PRIVACY_POLICY_URL_EN

    # Build help text from translations
    help_text = f"""{i18n.get('help.title', user_language)}

{i18n.get('help.commands_title', user_language)}
{i18n.get('help.command_start', user_language)}
{i18n.get('help.command_help', user_language)}

{i18n.get('help.features_title', user_language)}

{i18n.get('help.feature_charts', user_language)}

{i18n.get('help.feature_price', user_language)}

{i18n.get('help.feature_news', user_language)}

{i18n.get('help.feature_analysis', user_language)}

{i18n.get('help.features_list_title', user_language)}
{i18n.get('help.features_list', user_language)}

{i18n.get('help.disclaimer', user_language)}

{i18n.get('help.limits_title', user_language)}
{i18n.get('help.limits_text', user_language)}

{i18n.get('help.footer', user_language)}
{i18n.get('help.legal_documents', user_language, terms_url=terms_url, privacy_url=privacy_url)}
"""

    await message.answer(help_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    logger.info(f"Help shown to user {message.from_user.id}")
