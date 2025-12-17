"""
Config API Endpoints
Public endpoints for pricing, limits, and configuration
"""

from fastapi import APIRouter
from typing import Dict, Any, List
from datetime import datetime

from config.pricing import TIER_PRICES, get_tier_pricing
from config.limits import TIER_LIMITS, TRIAL_CONFIG
from src.database.models import SubscriptionTier

# Create router
router = APIRouter(prefix="/config", tags=["config"])


@router.get("/pricing")
async def get_pricing() -> Dict[str, Any]:
    """
    Get current pricing configuration

    Public endpoint - no authentication required

    Returns:
        {
            "tiers": [
                {
                    "name": "free",
                    "display_name": "Free",
                    "price": 0.00,
                    "price_discounted": 0.00,
                    "limits": {
                        "text_per_day": 1,
                        "charts_per_day": 1,
                        "vision_per_day": 0
                    },
                    "features": [...]
                },
                ...
            ],
            "trial": {
                "tier": "premium",
                "duration_days": 7,
                "discount_percent": 20,
                "discount_duration_hours": 48
            },
            "updated_at": "2025-01-18T00:00:00Z"
        }
    """

    tiers_data = []

    for tier_enum in [SubscriptionTier.FREE, SubscriptionTier.BASIC,
                      SubscriptionTier.PREMIUM, SubscriptionTier.VIP]:
        tier_name = tier_enum.value
        pricing = get_tier_pricing(tier_name)
        limits = TIER_LIMITS[tier_enum]

        # Build features list
        features = []

        # Text requests
        if limits["text_per_day"] > 0:
            features.append(f"{limits['text_per_day']} text requests/day")

        # Charts
        if limits["charts_per_day"] > 0:
            features.append(f"{limits['charts_per_day']} charts/day")

        # Vision
        if limits["vision_per_day"] > 0:
            features.append(f"{limits['vision_per_day']} screenshot analysis/day")

        # Advanced features (Premium+)
        if limits.get("candlestick_patterns"):
            features.append("Candlestick patterns")

        if limits.get("funding_rates"):
            features.append("Funding rates")

        if limits.get("onchain_metrics"):
            features.append("On-chain metrics")

        if limits.get("liquidations"):
            features.append("Liquidation history")

        if limits.get("cycle_analysis"):
            features.append("Market cycle analysis")

        # Model info
        if limits.get("reasoning_model") == "gpt-4o":
            features.append("GPT-4o for complex queries")

        tiers_data.append({
            "name": tier_name,
            "display_name": tier_name.capitalize(),
            "price": pricing.monthly_price,
            "price_discounted": pricing.discount_price,
            "discount_percent": pricing.discount_percent,
            "limits": {
                "text_per_day": limits["text_per_day"],
                "charts_per_day": limits["charts_per_day"],
                "vision_per_day": limits["vision_per_day"],
            },
            "features": features,
            "model": {
                "primary": limits.get("primary_model"),
                "reasoning": limits.get("reasoning_model"),
                "advanced_routing": limits.get("use_advanced_routing", False),
            },
        })

    return {
        "tiers": tiers_data,
        "trial": {
            "tier": TRIAL_CONFIG["tier"].value,
            "duration_days": TRIAL_CONFIG["duration_days"],
            "discount_percent": TRIAL_CONFIG["discount_percent"],
            "discount_duration_hours": TRIAL_CONFIG["discount_duration_hours"],
        },
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/features")
async def get_features() -> Dict[str, Any]:
    """
    Get all available features and their tier availability

    Returns:
        {
            "features": [
                {
                    "name": "candlestick_patterns",
                    "display_name": "Candlestick Patterns",
                    "description": "Advanced pattern recognition",
                    "available_in": ["basic", "premium", "vip"]
                },
                ...
            ]
        }
    """

    all_features = [
        {
            "name": "text_requests",
            "display_name": "AI Text Analysis",
            "description": "Get AI-powered crypto market analysis",
            "available_in": ["free", "basic", "premium", "vip"],
        },
        {
            "name": "charts",
            "display_name": "Technical Charts",
            "description": "Generate technical analysis charts",
            "available_in": ["free", "basic", "premium", "vip"],
        },
        {
            "name": "vision",
            "display_name": "Screenshot Analysis",
            "description": "Analyze charts from screenshots",
            "available_in": ["basic", "premium", "vip"],
        },
        {
            "name": "candlestick_patterns",
            "display_name": "Candlestick Patterns",
            "description": "Advanced pattern recognition (Doji, Hammer, Engulfing)",
            "available_in": ["basic", "premium", "vip"],
        },
        {
            "name": "funding_rates",
            "display_name": "Funding Rates",
            "description": "Perpetual futures funding rate analysis",
            "available_in": ["basic", "premium", "vip"],
        },
        {
            "name": "onchain_metrics",
            "display_name": "On-Chain Metrics",
            "description": "Network activity, addresses, transaction volume",
            "available_in": ["premium", "vip"],
        },
        {
            "name": "liquidations",
            "display_name": "Liquidation History",
            "description": "Track liquidation events and levels",
            "available_in": ["premium", "vip"],
        },
        {
            "name": "cycle_analysis",
            "display_name": "Market Cycle Analysis",
            "description": "Identify bull/bear market phases",
            "available_in": ["premium", "vip"],
        },
        {
            "name": "gpt4o",
            "display_name": "GPT-4o Advanced Model",
            "description": "Most advanced AI model for complex analysis",
            "available_in": ["premium", "vip"],
        },
    ]

    return {
        "features": all_features,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
