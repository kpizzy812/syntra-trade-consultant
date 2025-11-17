"""
Unit tests for OpenAI service
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from src.services.openai_service import OpenAIService
from config.config import ModelConfig


@pytest.fixture
def openai_service():
    """Create OpenAI service instance for testing"""
    with patch("src.services.openai_service.AsyncOpenAI"):
        service = OpenAIService()
        return service


def test_count_tokens(openai_service):
    """Test token counting"""
    # Simple text
    text = "Hello, world!"
    tokens = openai_service.count_tokens(text)
    assert isinstance(tokens, int)
    assert tokens > 0

    # Longer text should have more tokens
    long_text = "This is a much longer text with many more words and tokens"
    long_tokens = openai_service.count_tokens(long_text)
    assert long_tokens > tokens

    # Empty text
    empty_tokens = openai_service.count_tokens("")
    assert empty_tokens == 0


def test_select_model_simple_message(openai_service):
    """Test model selection for simple messages"""
    # Simple greeting - should use GPT-4O-MINI
    simple_message = "Привет, как дела?"
    model = openai_service.select_model(simple_message, history_tokens=0)
    assert model == ModelConfig.GPT_4O_MINI


def test_select_model_complex_keywords(openai_service):
    """Test model selection with complex keywords"""
    # Message with 'анализ' keyword - should use GPT-4O
    complex_message = "Сделай подробный анализ рынка Bitcoin"
    model = openai_service.select_model(complex_message, history_tokens=0)
    assert model == ModelConfig.GPT_4O

    # Message with 'strategy' keyword
    strategy_message = "What's the best trading strategy for ETH?"
    model = openai_service.select_model(strategy_message, history_tokens=0)
    assert model == ModelConfig.GPT_4O

    # Message with 'прогноз' keyword
    forecast_message = "Какой прогноз на биткоин?"
    model = openai_service.select_model(forecast_message, history_tokens=0)
    assert model == ModelConfig.GPT_4O


def test_select_model_token_threshold(openai_service):
    """Test model selection based on token threshold"""
    # Short message with high history tokens - should use GPT-4O
    short_message = "Продолжай"
    model = openai_service.select_model(short_message, history_tokens=2000)
    assert model == ModelConfig.GPT_4O

    # Very long message exceeding threshold
    long_message = " ".join(["word" for _ in range(500)])  # Generate long text
    model = openai_service.select_model(long_message, history_tokens=0)
    # Should select GPT-4O due to length
    tokens = openai_service.count_tokens(long_message)
    if tokens > ModelConfig.MODEL_ROUTING_THRESHOLD:
        assert model == ModelConfig.GPT_4O


def test_select_model_english_keywords(openai_service):
    """Test model selection with English complex keywords"""
    # Test various English keywords
    test_cases = [
        "Give me a detailed analysis of the market",
        "Compare Bitcoin and Ethereum fundamentals",
        "Explain the complex technical indicators",
        "What's your forecast for crypto?",
    ]

    for message in test_cases:
        model = openai_service.select_model(message, history_tokens=0)
        assert model == ModelConfig.GPT_4O


def test_select_model_russian_keywords(openai_service):
    """Test model selection with Russian complex keywords"""
    # Messages with explicit complex keywords that should trigger GPT-4O
    test_cases = [
        "Дай глубокий анализ рынка",  # 'глубокий' keyword
        "Сделай подробный анализ",  # 'анализ' keyword
        "Какая стратегия лучше?",  # 'стратегия' keyword
    ]

    for message in test_cases:
        model = openai_service.select_model(message, history_tokens=0)
        assert model == ModelConfig.GPT_4O, f"Failed for message: {message}"


def test_select_model_mini_for_simple_queries(openai_service):
    """Test that simple queries use GPT-4O-MINI"""
    simple_messages = [
        "Привет",
        "Что такое BTC?",
        "Цена биткоина",
        "Hello",
        "What is Bitcoin?",
    ]

    for message in simple_messages:
        model = openai_service.select_model(message, history_tokens=0)
        # Should use MINI for simple queries
        assert model == ModelConfig.GPT_4O_MINI


def test_count_tokens_consistency(openai_service):
    """Test that token counting is consistent"""
    text = "Test message for token counting"

    # Count multiple times, should get same result
    count1 = openai_service.count_tokens(text)
    count2 = openai_service.count_tokens(text)
    count3 = openai_service.count_tokens(text)

    assert count1 == count2 == count3


def test_count_tokens_with_special_characters(openai_service):
    """Test token counting with special characters"""
    # Emoji and special characters
    text_with_emoji = "Hello 👋 Bitcoin 🚀"
    tokens = openai_service.count_tokens(text_with_emoji)
    assert tokens > 0

    # Cyrillic
    cyrillic_text = "Привет мир криптовалют"
    cyrillic_tokens = openai_service.count_tokens(cyrillic_text)
    assert cyrillic_tokens > 0


def test_select_model_case_insensitive(openai_service):
    """Test that keyword matching is case insensitive"""
    # Mixed case keywords
    test_cases = [
        "АНАЛИЗ рынка",
        "Analysis OF MARKET",
        "СТРАТЕГИЯ trading",
    ]

    for message in test_cases:
        model = openai_service.select_model(message, history_tokens=0)
        assert model == ModelConfig.GPT_4O
