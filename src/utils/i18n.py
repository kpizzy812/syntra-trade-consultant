"""
Internationalization (i18n) utilities for bot localization
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class I18n:
    """
    Simple i18n class for managing translations
    """

    def __init__(self, locales_dir: str = "src/locales", default_language: str = "ru"):
        """
        Initialize i18n system

        Args:
            locales_dir: Directory containing translation files
            default_language: Default language code
        """
        self.locales_dir = Path(locales_dir)
        self.default_language = default_language
        self.translations: Dict[str, Dict[str, Any]] = {}
        self._load_translations()

    def _load_translations(self) -> None:
        """Load all translation files from locales directory"""
        if not self.locales_dir.exists():
            logger.warning(f"Locales directory not found: {self.locales_dir}")
            return

        for locale_file in self.locales_dir.glob("*.json"):
            language = locale_file.stem
            try:
                with open(locale_file, 'r', encoding='utf-8') as f:
                    self.translations[language] = json.load(f)
                logger.info(f"Loaded translations for language: {language}")
            except Exception as e:
                logger.error(f"Error loading translations for {language}: {e}")

    def get(self, key: str, language: Optional[str] = None, **kwargs) -> str:
        """
        Get translated string by key

        Args:
            key: Translation key (supports nested keys with dots, e.g., 'menu.help')
            language: Language code (if None, uses default)
            **kwargs: Format arguments for string formatting

        Returns:
            Translated string
        """
        lang = language or self.default_language

        # Get translations for language, fallback to default
        trans = self.translations.get(lang, self.translations.get(self.default_language, {}))

        # Navigate nested keys
        keys = key.split('.')
        value = trans
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                break

        # If translation not found, return key
        if value is None or not isinstance(value, str):
            logger.warning(f"Translation not found: {key} (language: {lang})")
            return key

        # Format string with kwargs if provided
        try:
            return value.format(**kwargs) if kwargs else value
        except KeyError as e:
            logger.error(f"Missing format argument in translation {key}: {e}")
            return value

    def reload(self) -> None:
        """Reload all translations"""
        self.translations.clear()
        self._load_translations()


# Global i18n instance
i18n = I18n()


def get_user_language(user_language: Optional[str] = None, telegram_language: Optional[str] = None) -> str:
    """
    Determine user language with fallback logic

    Priority:
    1. User's saved language preference
    2. Telegram language code
    3. Default language (Russian)

    Args:
        user_language: User's saved language preference from database
        telegram_language: Telegram user's language code

    Returns:
        Language code (ru or en)
    """
    # If user has saved preference, use it
    if user_language:
        return user_language

    # Try to detect from Telegram language
    if telegram_language:
        # Map Telegram language codes to supported languages
        telegram_language = telegram_language.lower()

        # English variants
        if telegram_language.startswith('en'):
            return 'en'

        # Russian is default, but also check explicitly
        if telegram_language.startswith('ru'):
            return 'ru'

    # Default to Russian
    return 'ru'
