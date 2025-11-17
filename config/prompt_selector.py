"""
Prompt selector - chooses appropriate prompts based on user language
"""

# Import Russian prompts
from config import prompts as prompts_ru
from config import vision_prompts as vision_prompts_ru

# Import English prompts
from config import prompts_en
from config import vision_prompts_en


def get_system_prompt(language: str = 'ru', mode: str = 'medium') -> str:
    """
    Get system prompt in user's language

    Args:
        language: User language ('ru' or 'en')
        mode: Sarcasm mode ('soft', 'medium', 'hard')

    Returns:
        System prompt in appropriate language
    """
    if language == 'en':
        # For English, we don't have get_system_prompt_with_mode yet, so just return basic prompt
        return prompts_en.SYNTRA_SYSTEM_PROMPT
    else:
        return prompts_ru.get_system_prompt_with_mode(mode)


def get_vision_analysis_prompt(language: str = 'ru') -> str:
    """
    Get vision analysis prompt in user's language

    Args:
        language: User language ('ru' or 'en')

    Returns:
        Vision analysis prompt in appropriate language
    """
    if language == 'en':
        return vision_prompts_en.BASIC_ANALYSIS_PROMPT
    else:
        return vision_prompts_ru.BASIC_ANALYSIS_PROMPT


def get_enhanced_vision_prompt(
    language: str,
    coin_name: str,
    current_price: float,
    change_24h: float,
    volume_24h: float = None,
    market_cap: float = None
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
    if language == 'en':
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
    change_24h: float = None
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
    if language == 'en':
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
    news: str
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
    if language == 'en':
        return prompts_en.PRICE_ANALYSIS_PROMPT_TEMPLATE.format(
            coin_name=coin_name,
            current_price=current_price,
            change_24h=change_24h,
            market_cap=market_cap,
            volume_24h=volume_24h,
            news=news
        )
    else:
        return prompts_ru.PRICE_ANALYSIS_PROMPT_TEMPLATE.format(
            coin_name=coin_name,
            current_price=current_price,
            change_24h=change_24h,
            market_cap=market_cap,
            volume_24h=volume_24h,
            news=news
        )


def get_general_question_prompt(language: str = 'ru') -> str:
    """
    Get general question prompt

    Args:
        language: User language ('ru' or 'en')

    Returns:
        General question prompt in appropriate language
    """
    if language == 'en':
        return prompts_en.GENERAL_QUESTION_PROMPT
    else:
        return prompts_ru.GENERAL_QUESTION_PROMPT


def get_coin_detection_prompt(language: str = 'ru') -> str:
    """
    Get coin detection prompt for vision

    Args:
        language: User language ('ru' or 'en')

    Returns:
        Coin detection prompt in appropriate language
    """
    if language == 'en':
        return vision_prompts_en.COIN_DETECTION_PROMPT
    else:
        return vision_prompts_ru.COIN_DETECTION_PROMPT
