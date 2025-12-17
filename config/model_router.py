"""
Model Router - selects AI models based on subscription tier

Routes requests to appropriate models based on:
- User's subscription tier
- Request complexity
- Cost optimization
"""

from dataclasses import dataclass
from typing import Optional
from loguru import logger

from src.database.models import SubscriptionTier
from config.limits import TIER_LIMITS


@dataclass
class ModelConfig:
    """Configuration for model selection"""

    primary_model: str  # Main model for analysis
    reasoning_model: Optional[str]  # For 2-step reasoning
    vision_model: str  # For image analysis
    use_two_step: bool  # Whether to use 2-step analysis
    use_advanced_routing: bool  # Whether to use advanced routing logic


def get_model_config(tier: SubscriptionTier) -> ModelConfig:
    """
    Get model configuration for user's tier

    Args:
        tier: User's subscription tier

    Returns:
        ModelConfig with appropriate models
    """
    tier_config = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])

    primary_model = tier_config["primary_model"]
    reasoning_model = tier_config.get("reasoning_model")
    vision_model = tier_config.get("vision_model", "gpt-4o-mini")
    use_two_step = tier_config.get("use_two_step_analysis", False)
    use_advanced_routing = tier_config.get("use_advanced_routing", False)

    config = ModelConfig(
        primary_model=primary_model,
        reasoning_model=reasoning_model,
        vision_model=vision_model,
        use_two_step=use_two_step,
        use_advanced_routing=use_advanced_routing,
    )

    logger.debug(
        f"Model config for {tier.value}: primary={primary_model}, "
        f"reasoning={reasoning_model}, two_step={use_two_step}"
    )

    return config


def select_model_for_request(
    tier: SubscriptionTier,
    request_type: str = "text",
    complexity: str = "medium",
) -> str:
    """
    Select appropriate model for specific request

    Args:
        tier: User's subscription tier
        request_type: Type of request ('text', 'vision', 'chart')
        complexity: Estimated complexity ('simple', 'medium', 'complex')

    Returns:
        Model name to use
    """
    config = get_model_config(tier)

    # Vision requests always use vision model
    if request_type == "vision":
        return config.vision_model

    # For FREE tier, always use cheapest option
    if tier == SubscriptionTier.FREE:
        return "deepseek-chat"

    # For BASIC tier, use mini for simple, deepseek for complex
    if tier == SubscriptionTier.BASIC:
        if complexity == "simple":
            return "gpt-4o-mini"
        return config.reasoning_model or "deepseek-chat"

    # For PREMIUM/VIP with advanced routing
    if config.use_advanced_routing:
        # Route based on complexity
        if complexity == "simple":
            return "gpt-4o-mini"  # Cheap for simple stuff
        elif complexity == "medium":
            return config.primary_model  # GPT-4o
        else:  # complex
            return "gpt-4o"  # Best model for complex analysis

    # Default: use primary model
    return config.primary_model


def should_use_two_step_analysis(tier: SubscriptionTier, query: str) -> bool:
    """
    Determine if request should use 2-step analysis (reasoning + generation)

    Args:
        tier: User's subscription tier
        query: User query

    Returns:
        True if should use 2-step, False otherwise
    """
    config = get_model_config(tier)

    # FREE tier doesn't get 2-step
    if tier == SubscriptionTier.FREE:
        return False

    # Check if tier has 2-step enabled
    if not config.use_two_step:
        return False

    # For tiers with 2-step, detect complex queries
    complex_keywords = [
        "анализ",
        "прогноз",
        "сравни",
        "разбери",
        "strategy",
        "analysis",
        "forecast",
        "compare",
        "analyze",
        "scenario",
        "сценарий",
    ]

    query_lower = query.lower()
    return any(keyword in query_lower for keyword in complex_keywords)


def get_tier_features(tier: SubscriptionTier) -> dict:
    """
    Get all features available for tier

    Args:
        tier: Subscription tier

    Returns:
        Dict with feature flags
    """
    tier_config = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])

    return {
        "candlestick_patterns": tier_config.get("candlestick_patterns", False),
        "onchain_metrics": tier_config.get("onchain_metrics", False),
        "funding_rates": tier_config.get("funding_rates", False),
        "liquidations": tier_config.get("liquidations", False),
        "cycle_analysis": tier_config.get("cycle_analysis", False),
        "advanced_indicators": tier_config.get("advanced_indicators", False),
        "whale_tracking": tier_config.get("whale_tracking", False),
        "sentiment_analysis": tier_config.get("sentiment_analysis", False),
        "use_two_step_analysis": tier_config.get("use_two_step_analysis", False),
        "use_advanced_routing": tier_config.get("use_advanced_routing", False),
    }


# Quick access functions for common cases
def get_chat_model(tier: SubscriptionTier) -> str:
    """Get model for chat/text requests"""
    return select_model_for_request(tier, "text", "medium")


def get_vision_model(tier: SubscriptionTier) -> str:
    """Get model for vision/chart analysis"""
    config = get_model_config(tier)
    return config.vision_model


def get_reasoning_model(tier: SubscriptionTier) -> Optional[str]:
    """Get reasoning model for 2-step analysis"""
    config = get_model_config(tier)
    return config.reasoning_model


# Cost estimation (Standard tier, updated Nov 2025)
MODEL_COSTS = {
    # GPT-5 models
    "gpt-5.1": {"input": 1.25, "input_cached": 0.125, "output": 10.00},
    "gpt-5-mini": {"input": 0.25, "input_cached": 0.025, "output": 2.00},

    # GPT-4o models (legacy)
    "gpt-4o": {"input": 2.50, "input_cached": 1.25, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "input_cached": 0.075, "output": 0.60},

    # Reasoning models (UltraThink)
    "o4-mini": {"input": 1.10, "input_cached": 0.275, "output": 4.40},
    "o3-mini": {"input": 1.10, "input_cached": 0.55, "output": 4.40},

    # DeepSeek models
    "deepseek-chat": {"input": 0.28, "input_cached": 0.028, "output": 0.42},
    "deepseek-reasoner": {"input": 0.28, "input_cached": 0.028, "output": 0.42},
}


def estimate_request_cost(
    tier: SubscriptionTier,
    input_tokens: int,
    output_tokens: int,
    request_type: str = "text",
) -> float:
    """
    Estimate cost of request in USD

    Args:
        tier: User's subscription tier
        input_tokens: Estimated input tokens
        output_tokens: Estimated output tokens
        request_type: Type of request

    Returns:
        Estimated cost in USD
    """
    model = select_model_for_request(tier, request_type)
    costs = MODEL_COSTS.get(model, MODEL_COSTS["gpt-4o-mini"])

    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]

    total_cost = input_cost + output_cost

    logger.debug(
        f"Cost estimate for {tier.value} ({model}): "
        f"{input_tokens}+{output_tokens} tokens = ${total_cost:.4f}"
    )

    return total_cost
