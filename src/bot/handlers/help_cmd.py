"""
/help command handler
"""
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.utils.i18n import i18n


logger = logging.getLogger(__name__)
router = Router(name='help')


@router.message(Command('help'))
async def cmd_help(message: Message, user_language: str = 'ru'):
    """
    Handle /help command - show available commands and usage

    Args:
        message: Incoming message
        user_language: User language (provided by LanguageMiddleware)
    """
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
"""

    await message.answer(help_text)

    logger.info(f"Help shown to user {message.from_user.id}")
