"""
Subscription limits configuration for Syntra Trade Consultant Bot

Defines precise limits for each subscription tier:
- Text requests (AI chat analysis)
- Chart/Graph requests (technical chart generation)
- Vision requests (screenshot/image analysis)
"""

from src.database.models import SubscriptionTier
from typing import Dict, Any


# ============================================================================
# SUBSCRIPTION LIMITS BY TIER
# ============================================================================

TIER_LIMITS = {
    # FREE TIER - Promo for new users (after 7-day Premium trial ends)
    SubscriptionTier.FREE: {
        "text_per_day": 2,          # Text requests (AI analysis)
        "charts_per_day": 1,         # Chart/graph generations
        "vision_per_day": 0,         # Vision analysis (screenshots)
        "futures_per_day": 0,        # Futures signals (Premium+ only)

        # Token limits (to control API costs)
        "max_input_tokens": 2000,    # Max tokens in user message + history
        "max_output_tokens": 800,    # Max tokens in AI response

        # Chat context/memory
        "chat_history_messages": 0,  # 🚨 NO MEMORY - Each request is independent
        "save_chat_history": True,   # ✅ SAVE chat history to DB (for chat management UI)

        # Model routing
        "primary_model": "gpt-4o-mini",  # Primary text model
        "reasoning_model": "deepseek-chat",  # Secondary reasoning model
        "use_two_step": True,        # Use 2-step analysis (mini + deepseek)
        "use_advanced_routing": False,  # No smart 4o routing

        # Feature flags
        "candlestick_patterns": False,    # ❌ No candlestick pattern detection
        "onchain_metrics": False,         # ❌ No CoinMetrics on-chain data
        "funding_rates": False,           # ❌ No funding rates
        "liquidations": False,            # ❌ No liquidation history
        "cycle_analysis": False,          # ❌ No market cycle analysis
        "advanced_indicators": False,     # ❌ Limited technical indicators

        # What FREE users GET
        "basic_price": True,              # ✅ Current price
        "basic_indicators": True,         # ✅ RSI, MACD, EMA
        "news": True,                     # ✅ Crypto news
        "fear_greed": True,               # ✅ Fear & Greed Index

        "price_usd": 0.00,
    },

    # BASIC TIER - Entry level paid subscription
    SubscriptionTier.BASIC: {
        "text_per_day": 10,          # Quality over quantity
        "charts_per_day": 3,          # Sustainable limits
        "vision_per_day": 2,          # Screenshot analysis
        "futures_per_day": 0,        # Futures signals (Premium+ only)

        # Token limits
        "max_input_tokens": 4000,    # More context allowed
        "max_output_tokens": 1200,   # More detailed responses

        # Chat context/memory
        "chat_history_messages": 5,  # ✅ LIMITED MEMORY - Last 5 messages
        "save_chat_history": True,   # ✅ Save chat history to DB

        # Model routing
        "primary_model": "gpt-4o-mini",
        "reasoning_model": "deepseek-reasoner",  # 🔥 Reasoning mode for complex queries!
        "use_two_step": True,
        "use_advanced_routing": False,  # No expensive models yet

        # Feature flags
        "candlestick_patterns": True,     # ✅ Candlestick patterns
        "onchain_metrics": False,         # ❌ Still no on-chain
        "funding_rates": True,            # ✅ Funding rates
        "liquidations": False,            # ❌ No liquidations yet
        "cycle_analysis": False,          # ❌ No cycle analysis
        "advanced_indicators": True,      # ✅ All technical indicators

        "basic_price": True,
        "basic_indicators": True,
        "news": True,
        "fear_greed": True,

        "price_usd": 9.99,
    },

    # PREMIUM TIER - Full-featured subscription (7-day trial for new users)
    SubscriptionTier.PREMIUM: {
        "text_per_day": 15,           # Quality over quantity - value in features
        "charts_per_day": 5,           # Sustainable limits
        "vision_per_day": 5,           # Full vision access
        "futures_per_day": 1,         # Futures signals (1/day for Premium)

        # Token limits
        "max_input_tokens": 8000,    # Extended context (full history)
        "max_output_tokens": 1500,   # Full detailed analysis

        # Chat context/memory
        "chat_history_messages": 10,  # ✅ GOOD MEMORY - Last 10 messages
        "save_chat_history": True,    # ✅ Save chat history to DB

        # Model routing
        "primary_model": "gpt-5-mini",           # 🔥 Upgraded to GPT-5!
        "reasoning_model": "gpt-5.1",            # 🔥 Latest flagship for complex analysis
        "use_two_step": True,
        "use_advanced_routing": True,            # ✅ Smart routing (complex -> GPT-5.1)

        # Feature flags - ALL ENABLED
        "candlestick_patterns": True,
        "onchain_metrics": True,          # ✅ Full on-chain data
        "funding_rates": True,
        "liquidations": True,             # ✅ Liquidation history
        "cycle_analysis": True,           # ✅ Market cycles
        "advanced_indicators": True,

        "basic_price": True,
        "basic_indicators": True,
        "news": True,
        "fear_greed": True,

        "price_usd": 24.99,

        # Trial settings
        "trial_duration_days": 7,
        "post_trial_discount_percent": 20,  # -20% for first purchase
        "post_trial_discount_hours": 48,    # Discount valid for 48h
    },

    # VIP TIER - Premium + higher limits + priority + UltraThink
    SubscriptionTier.VIP: {
        "text_per_day": 30,            # Quality over quantity - UltraThink value
        "charts_per_day": 10,          # Sustainable limits
        "vision_per_day": 10,          # Full vision access
        "futures_per_day": 5,          # Futures signals (5/day for VIP)

        # Token limits
        "max_input_tokens": 16000,   # Maximum context window
        "max_output_tokens": 2000,   # Unlimited detailed responses

        # Chat context/memory
        "chat_history_messages": 50,  # ✅ MAXIMUM MEMORY - Last 50 messages
        "save_chat_history": True,    # ✅ Save chat history to DB

        # Model routing
        "primary_model": "gpt-5.1",              # 🔥 Always best model
        "reasoning_model": "o4-mini",            # 🧠 UltraThink: Deep reasoning mode
        "ultrathink_model": "o4-mini",           # 🧠 Dedicated reasoning for complex queries
        "use_two_step": True,
        "use_advanced_routing": True,
        "use_ultrathink": True,                  # ✅ Enable UltraThink reasoning mode
        "priority_routing": True,                # ✅ Priority access to best models

        # Feature flags - ALL ENABLED + VIP perks
        "candlestick_patterns": True,
        "onchain_metrics": True,
        "funding_rates": True,
        "liquidations": True,
        "cycle_analysis": True,
        "advanced_indicators": True,

        "basic_price": True,
        "basic_indicators": True,
        "news": True,
        "fear_greed": True,

        # VIP perks
        "priority_support": True,
        "custom_alerts": True,           # Future: custom price alerts
        "api_access": False,             # Future: API access

        "price_usd": 49.99,
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_tier_limits(tier: SubscriptionTier) -> Dict[str, Any]:
    """
    Get limits for a specific subscription tier

    Args:
        tier: Subscription tier enum

    Returns:
        Dict with limits and feature flags
    """
    return TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])


def get_text_limit(tier: SubscriptionTier) -> int:
    """Get daily text request limit for tier"""
    return TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])["text_per_day"]


def get_chart_limit(tier: SubscriptionTier) -> int:
    """Get daily chart generation limit for tier"""
    return TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])["charts_per_day"]


def get_vision_limit(tier: SubscriptionTier) -> int:
    """Get daily vision request limit for tier"""
    return TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])["vision_per_day"]


def get_futures_limit(tier: SubscriptionTier) -> int:
    """Get daily futures signal limit for tier (Premium+ only)"""
    return TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])["futures_per_day"]


def has_feature(tier: SubscriptionTier, feature: str) -> bool:
    """
    Check if tier has access to a specific feature

    Args:
        tier: Subscription tier
        feature: Feature name (e.g., 'candlestick_patterns', 'onchain_metrics')

    Returns:
        True if feature is enabled for this tier
    """
    tier_config = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])
    return tier_config.get(feature, False)


def get_model_config(tier: SubscriptionTier) -> Dict[str, Any]:
    """
    Get model routing configuration for tier

    Args:
        tier: Subscription tier

    Returns:
        Dict with model configuration
    """
    tier_config = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])
    return {
        "primary_model": tier_config["primary_model"],
        "reasoning_model": tier_config["reasoning_model"],
        "use_two_step": tier_config["use_two_step"],
        "use_advanced_routing": tier_config.get("use_advanced_routing", False),
        "priority_routing": tier_config.get("priority_routing", False),
    }


def get_token_limits(tier: SubscriptionTier) -> Dict[str, int]:
    """
    Get token limits for a specific subscription tier

    Args:
        tier: Subscription tier

    Returns:
        Dict with max_input_tokens and max_output_tokens
    """
    tier_config = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])
    return {
        "max_input_tokens": tier_config.get("max_input_tokens", 2000),
        "max_output_tokens": tier_config.get("max_output_tokens", 800),
    }


def get_chat_history_limit(tier: SubscriptionTier) -> int:
    """
    Get chat history messages limit for a specific subscription tier

    Args:
        tier: Subscription tier

    Returns:
        Number of history messages to include in context (0 = no memory)
    """
    tier_config = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])
    return tier_config.get("chat_history_messages", 0)


def should_save_chat_history(tier: SubscriptionTier) -> bool:
    """
    Check if chat history should be saved to database for this tier

    Args:
        tier: Subscription tier

    Returns:
        True if chat history should be saved, False otherwise
    """
    tier_config = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])
    return tier_config.get("save_chat_history", False)


# ============================================================================
# LIMIT TYPES (for tracking)
# ============================================================================

class LimitType:
    """Types of limits to track separately"""
    TEXT = "text"           # Text AI requests
    CHART = "chart"         # Chart/graph generations
    VISION = "vision"       # Vision/image analysis
    FUTURES = "futures"     # Futures signal generation


# ============================================================================
# TRIAL CONFIGURATION
# ============================================================================

TRIAL_CONFIG = {
    # New users get 7-day Premium trial
    "tier": SubscriptionTier.PREMIUM,
    "duration_days": 7,

    # Post-trial discount
    "discount_percent": 20,  # -20% on first purchase
    "discount_duration_hours": 48,  # Valid for 48 hours after trial ends

    # Notification timing
    "notify_before_end_hours": 24,  # Notify 24h before trial ends
    "notify_after_end_hours": 0,    # Notify immediately after trial ends
}


# ============================================================================
# COST TRACKING (for unit economics)
# ============================================================================

# Approximate cost per request type (USD) - Updated with GPT-5 & reasoning models
COST_PER_REQUEST = {
    "text_free": 0.003,       # FREE: mini + deepseek (simplified)
    "text_basic": 0.005,      # BASIC: mini + deepseek-reasoner (reasoning mode!)
    "text_premium": 0.018,    # PREMIUM: gpt-5-mini + gpt-5.1 (latest models)
    "text_vip": 0.030,        # VIP: gpt-5.1 + o4-mini UltraThink (reasoning)

    "chart": 0.002,           # Chart generation (minimal cost)
    "vision": 0.020,          # Vision analysis (GPT-4o vision)
}


def calculate_tier_cost_per_day(tier: SubscriptionTier) -> float:
    """
    Calculate maximum cost per day if user exhausts all limits

    Args:
        tier: Subscription tier

    Returns:
        Maximum daily cost in USD
    """
    limits = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])

    # Determine text request cost
    if tier == SubscriptionTier.FREE:
        text_cost = COST_PER_REQUEST["text_free"]
    elif tier == SubscriptionTier.BASIC:
        text_cost = COST_PER_REQUEST["text_basic"]
    else:
        text_cost = COST_PER_REQUEST["text_premium"]

    # Calculate total daily cost
    total_cost = (
        limits["text_per_day"] * text_cost +
        limits["charts_per_day"] * COST_PER_REQUEST["chart"] +
        limits["vision_per_day"] * COST_PER_REQUEST["vision"]
    )

    return round(total_cost, 4)


def calculate_monthly_margin(tier: SubscriptionTier, usage_percent: float = 100.0) -> Dict[str, float]:
    """
    Calculate monthly margin for a tier

    Args:
        tier: Subscription tier
        usage_percent: Percentage of daily limits used (0-100)

    Returns:
        Dict with revenue, cost, profit, margin_percent
    """
    limits = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])

    # Monthly revenue
    revenue = limits["price_usd"]

    # Monthly cost (30 days)
    daily_cost = calculate_tier_cost_per_day(tier)
    monthly_cost = daily_cost * 30 * (usage_percent / 100)

    # Profit and margin
    profit = revenue - monthly_cost
    margin_percent = (profit / revenue * 100) if revenue > 0 else 0

    return {
        "revenue": round(revenue, 2),
        "cost": round(monthly_cost, 2),
        "profit": round(profit, 2),
        "margin_percent": round(margin_percent, 1),
        "is_profitable": profit > 0,
    }


if __name__ == "__main__":
    # Test: Print tier limits and economics
    print("🎯 Syntra Subscription Limits & Economics\n")

    for tier in [SubscriptionTier.FREE, SubscriptionTier.BASIC,
                 SubscriptionTier.PREMIUM, SubscriptionTier.VIP]:
        limits = get_tier_limits(tier)
        margin_100 = calculate_monthly_margin(tier, usage_percent=100)
        margin_50 = calculate_monthly_margin(tier, usage_percent=50)

        print(f"{'='*60}")
        print(f"{tier.value.upper()} - ${limits['price_usd']}/month")
        print(f"{'='*60}")
        print(f"Limits:")
        print(f"  Text: {limits['text_per_day']}/day")
        print(f"  Charts: {limits['charts_per_day']}/day")
        print(f"  Vision: {limits['vision_per_day']}/day")
        print(f"\nModels:")
        print(f"  Primary: {limits['primary_model']}")
        print(f"  Reasoning: {limits['reasoning_model']}")
        print(f"  Advanced routing: {limits.get('use_advanced_routing', False)}")
        print(f"\nEconomics (100% usage):")
        print(f"  Revenue: ${margin_100['revenue']}/mo")
        print(f"  Cost: ${margin_100['cost']}/mo")
        print(f"  Profit: ${margin_100['profit']}/mo ({margin_100['margin_percent']}% margin)")
        print(f"\nEconomics (50% usage):")
        print(f"  Cost: ${margin_50['cost']}/mo")
        print(f"  Profit: ${margin_50['profit']}/mo ({margin_50['margin_percent']}% margin)")
        print()
