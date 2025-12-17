"""
Prompt selector - chooses appropriate prompts based on user language and subscription tier
"""

# Import Russian prompts
from config import prompts as prompts_ru
from config import vision_prompts as vision_prompts_ru

# Import English prompts
from config import prompts_en
from config import vision_prompts_en

# Import FREE tier prompts
from config import prompts_free
from src.database.models import SubscriptionTier


def get_system_prompt(
    language: str = "ru",
    mode: str = "medium",
    user_message: str = None,
    tier: SubscriptionTier = None,
) -> str:
    """
    Get system prompt in user's language with dynamic sarcasm mode detection and tier-based features

    Args:
        language: User language ('ru' or 'en')
        mode: Sarcasm mode ('soft', 'medium', 'hard', 'disabled')
              If user_message is provided, mode will be auto-detected
        user_message: Optional user message for automatic mode detection
        tier: Subscription tier (FREE/BASIC/PREMIUM/VIP) - if FREE, uses simplified prompt

    Returns:
        System prompt in appropriate language with appropriate sarcasm level and features
    """
    # Check if user is on FREE tier - use simplified prompt
    if tier == SubscriptionTier.FREE:
        # FREE tier gets simplified prompt (only Russian for now, English uses same)
        return prompts_free.get_free_tier_prompt()

    # Auto-detect sarcasm mode from user message (for paid tiers)
    if user_message:
        if language == "en":
            mode = prompts_en.detect_sarcasm_level(user_message)
        else:
            mode = prompts_ru.detect_sarcasm_level(user_message)

    # Use full prompts for BASIC/PREMIUM/VIP tiers
    if language == "en":
        return prompts_en.get_system_prompt(mode)
    else:
        return prompts_ru.get_system_prompt(mode)


def get_few_shot_examples(
    language: str = "ru",
    mode: str = "medium",
    user_message: str = None,
    tier: SubscriptionTier = None,
) -> list:
    """
    Get few-shot examples in user's language for injecting into messages[]

    Args:
        language: User language ('ru' or 'en')
        mode: Sarcasm mode ('soft', 'medium', 'hard', 'disabled')
              If user_message is provided, mode will be auto-detected
        user_message: Optional user message for automatic mode detection
        tier: Subscription tier (FREE/BASIC/PREMIUM/VIP) - if FREE, uses simplified examples

    Returns:
        List of message dicts for few-shot learning
    """
    # Check if user is on FREE tier - use simplified examples
    if tier == SubscriptionTier.FREE:
        return prompts_free.get_free_tier_examples()

    # Auto-detect sarcasm mode from user message (for paid tiers)
    if user_message:
        if language == "en":
            mode = prompts_en.detect_sarcasm_level(user_message)
        else:
            mode = prompts_ru.detect_sarcasm_level(user_message)

    # Use full examples for BASIC/PREMIUM/VIP tiers
    if language == "en":
        return prompts_en.get_few_shot_examples(mode)
    else:
        return prompts_ru.get_few_shot_examples(mode)


def get_vision_analysis_prompt(
    language: str = "ru", tier: SubscriptionTier = None
) -> str:
    """
    Get vision analysis prompt in user's language based on subscription tier

    Args:
        language: User language ('ru' or 'en')
        tier: Subscription tier (FREE/BASIC/PREMIUM/VIP) - if FREE, uses simplified prompt

    Returns:
        Vision analysis prompt in appropriate language and feature level
    """
    # FREE tier gets simplified vision prompt
    if tier == SubscriptionTier.FREE:
        return prompts_free.VISION_ANALYSIS_PROMPT_FREE

    # Paid tiers get full vision analysis
    if language == "en":
        return vision_prompts_en.BASIC_ANALYSIS_PROMPT
    else:
        return vision_prompts_ru.BASIC_ANALYSIS_PROMPT


def get_enhanced_vision_prompt(
    language: str,
    coin_name: str,
    current_price: float,
    change_24h: float,
    volume_24h: float = None,
    market_cap: float = None,
) -> str:
    """
    Get enhanced vision analysis prompt with market data

    Args:
        language: User language ('ru' or 'en')
        coin_name: Cryptocurrency name
        current_price: Current price
        change_24h: 24h change percentage
        volume_24h: Optional 24h volume
        market_cap: Optional market cap

    Returns:
        Enhanced vision prompt in appropriate language
    """
    if language == "en":
        return vision_prompts_en.get_enhanced_analysis_prompt(
            coin_name, current_price, change_24h, volume_24h, market_cap
        )
    else:
        return vision_prompts_ru.get_enhanced_analysis_prompt(
            coin_name, current_price, change_24h, volume_24h, market_cap
        )


def get_question_vision_prompt(
    language: str,
    user_question: str,
    coin_name: str = None,
    current_price: float = None,
    change_24h: float = None,
) -> str:
    """
    Get question analysis prompt for vision

    Args:
        language: User language ('ru' or 'en')
        user_question: User's question
        coin_name: Optional coin name
        current_price: Optional current price
        change_24h: Optional 24h change

    Returns:
        Question analysis prompt in appropriate language
    """
    if language == "en":
        return vision_prompts_en.get_question_analysis_prompt(
            user_question, coin_name, current_price, change_24h
        )
    else:
        return vision_prompts_ru.get_question_analysis_prompt(
            user_question, coin_name, current_price, change_24h
        )


def get_price_analysis_prompt(
    language: str,
    coin_name: str,
    current_price: float,
    change_24h: float,
    market_cap: float,
    volume_24h: float,
    news: str,
) -> str:
    """
    Get price analysis prompt

    Args:
        language: User language ('ru' or 'en')
        coin_name: Cryptocurrency name
        current_price: Current price
        change_24h: 24h change
        market_cap: Market cap
        volume_24h: 24h volume
        news: Latest news

    Returns:
        Price analysis prompt in appropriate language
    """
    if language == "en":
        return prompts_en.PRICE_ANALYSIS_PROMPT_TEMPLATE.format(
            coin_name=coin_name,
            current_price=current_price,
            change_24h=change_24h,
            market_cap=market_cap,
            volume_24h=volume_24h,
            news=news,
        )
    else:
        return prompts_ru.PRICE_ANALYSIS_PROMPT_TEMPLATE.format(
            coin_name=coin_name,
            current_price=current_price,
            change_24h=change_24h,
            market_cap=market_cap,
            volume_24h=volume_24h,
            news=news,
        )


def get_general_question_prompt(language: str = "ru") -> str:
    """
    Get general question prompt

    Args:
        language: User language ('ru' or 'en')

    Returns:
        General question prompt in appropriate language
    """
    if language == "en":
        return prompts_en.GENERAL_QUESTION_PROMPT
    else:
        return prompts_ru.GENERAL_QUESTION_PROMPT


def get_coin_detection_prompt(language: str = "ru") -> str:
    """
    Get coin detection prompt for vision

    Args:
        language: User language ('ru' or 'en')

    Returns:
        Coin detection prompt in appropriate language
    """
    if language == "en":
        return vision_prompts_en.COIN_DETECTION_PROMPT
    else:
        return vision_prompts_ru.COIN_DETECTION_PROMPT
