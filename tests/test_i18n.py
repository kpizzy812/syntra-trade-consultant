"""
Unit tests for i18n utilities
"""

import pytest
import json
import tempfile
from pathlib import Path

from src.utils.i18n import I18n, get_user_language


def test_i18n_initialization():
    """Test I18n class initialization"""
    # Test with default settings
    i18n = I18n(locales_dir="src/locales", default_language="ru")

    assert i18n.default_language == "ru"
    assert "ru" in i18n.translations
    assert "en" in i18n.translations


def test_i18n_get_simple_key():
    """Test getting simple translation key"""
    i18n = I18n(locales_dir="src/locales", default_language="ru")

    # Test Russian
    welcome = i18n.get("welcome.title", language="ru")
    assert isinstance(welcome, str)
    assert len(welcome) > 0

    # Test English
    welcome_en = i18n.get("welcome.title", language="en")
    assert isinstance(welcome_en, str)
    assert len(welcome_en) > 0


def test_i18n_get_nested_key():
    """Test getting nested translation key"""
    i18n = I18n(locales_dir="src/locales", default_language="ru")

    # Test nested key
    menu_help = i18n.get("menu.help", language="ru")
    assert isinstance(menu_help, str)


def test_i18n_get_with_formatting():
    """Test translation with formatting arguments"""
    i18n = I18n(locales_dir="src/locales", default_language="ru")

    # Test formatting (limits.used key has {count} and {limit})
    result = i18n.get("limits.used", language="ru", count=3, limit=5)
    assert "3" in result
    assert "5" in result


def test_i18n_get_missing_key():
    """Test getting non-existent translation key"""
    i18n = I18n(locales_dir="src/locales", default_language="ru")

    # Should return the key itself if not found
    result = i18n.get("nonexistent.key.here", language="ru")
    assert result == "nonexistent.key.here"


def test_i18n_get_default_language_fallback():
    """Test fallback to default language"""
    i18n = I18n(locales_dir="src/locales", default_language="ru")

    # Request in non-existent language, should fallback to default
    result = i18n.get("welcome.title", language="fr")
    assert isinstance(result, str)
    assert len(result) > 0


def test_i18n_reload():
    """Test reloading translations"""
    i18n = I18n(locales_dir="src/locales", default_language="ru")

    initial_count = len(i18n.translations)
    i18n.reload()

    # Should still have translations after reload
    assert len(i18n.translations) == initial_count


def test_i18n_with_temp_locale():
    """Test i18n with temporary locale files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test locale files
        test_locale = {"test": {"key": "Test Value", "formatted": "Hello {name}"}}

        locale_file = Path(tmpdir) / "en.json"
        with open(locale_file, "w", encoding="utf-8") as f:
            json.dump(test_locale, f)

        # Initialize i18n with temp directory
        i18n = I18n(locales_dir=tmpdir, default_language="en")

        # Test getting value
        assert i18n.get("test.key", language="en") == "Test Value"

        # Test formatting
        result = i18n.get("test.formatted", language="en", name="World")
        assert result == "Hello World"


def test_get_user_language_with_saved_preference():
    """Test get_user_language with saved preference"""
    result = get_user_language(user_language="en", telegram_language="ru")
    assert result == "en"


def test_get_user_language_with_telegram_language():
    """Test get_user_language with Telegram language"""
    # Test English variants
    assert get_user_language(telegram_language="en") == "en"
    assert get_user_language(telegram_language="en-US") == "en"
    assert get_user_language(telegram_language="en-GB") == "en"

    # Test Russian
    assert get_user_language(telegram_language="ru") == "ru"
    assert get_user_language(telegram_language="ru-RU") == "ru"


def test_get_user_language_default():
    """Test get_user_language default fallback"""
    # No preferences, should default to Russian
    result = get_user_language()
    assert result == "ru"

    # Unknown language, should default to Russian
    result = get_user_language(telegram_language="fr")
    assert result == "ru"
