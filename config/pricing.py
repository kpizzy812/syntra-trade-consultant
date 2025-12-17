"""
Pricing configuration for Syntra subscriptions

All prices in USD
"""

from dataclasses import dataclass
from typing import Dict
from src.database.models import SubscriptionTier


@dataclass
class TierPricing:
    """Pricing information for a subscription tier"""

    tier: str
    monthly_price: float  # USD
    discount_price: float  # USD (for post-trial discount)
    discount_percent: int  # % discount


# Pricing for each tier
TIER_PRICES: Dict[str, TierPricing] = {
    SubscriptionTier.FREE.value: TierPricing(
        tier=SubscriptionTier.FREE.value,
        monthly_price=0.00,
        discount_price=0.00,
        discount_percent=0,
    ),
    SubscriptionTier.BASIC.value: TierPricing(
        tier=SubscriptionTier.BASIC.value,
        monthly_price=9.99,
        discount_price=7.99,  # -20%
        discount_percent=20,
    ),
    SubscriptionTier.PREMIUM.value: TierPricing(
        tier=SubscriptionTier.PREMIUM.value,
        monthly_price=24.99,
        discount_price=19.99,  # -20%
        discount_percent=20,
    ),
    SubscriptionTier.VIP.value: TierPricing(
        tier=SubscriptionTier.VIP.value,
        monthly_price=49.99,
        discount_price=39.99,  # -20%
        discount_percent=20,
    ),
}


# Helper functions
def get_tier_price(tier: str, with_discount: bool = False) -> float:
    """
    Get price for tier

    Args:
        tier: Subscription tier
        with_discount: Apply post-trial discount

    Returns:
        Price in USD
    """
    pricing = TIER_PRICES.get(tier)
    if not pricing:
        return 0.00

    return pricing.discount_price if with_discount else pricing.monthly_price


def get_tier_pricing(tier: str) -> TierPricing:
    """
    Get full pricing info for tier

    Args:
        tier: Subscription tier

    Returns:
        TierPricing object
    """
    return TIER_PRICES.get(tier, TIER_PRICES[SubscriptionTier.FREE.value])


# Telegram Stars conversion rate (approximate)
# 1 USD ≈ 50 Stars (adjust based on current rate)
USD_TO_STARS_RATE = 50


def usd_to_stars(usd_amount: float) -> int:
    """
    Convert USD to Telegram Stars

    Args:
        usd_amount: Amount in USD

    Returns:
        Amount in Stars (rounded)
    """
    return round(usd_amount * USD_TO_STARS_RATE)


def get_tier_price_in_stars(tier: str, with_discount: bool = False) -> int:
    """
    Get price for tier in Telegram Stars

    Args:
        tier: Subscription tier
        with_discount: Apply post-trial discount

    Returns:
        Price in Stars
    """
    usd_price = get_tier_price(tier, with_discount)
    return usd_to_stars(usd_price)


# Predefined pricing for quick access
BASIC_PRICE = 9.99
BASIC_PRICE_DISCOUNTED = 7.99
PREMIUM_PRICE = 24.99
PREMIUM_PRICE_DISCOUNTED = 19.99
VIP_PRICE = 49.99
VIP_PRICE_DISCOUNTED = 39.99

# Stars prices
BASIC_STARS = usd_to_stars(BASIC_PRICE)
BASIC_STARS_DISCOUNTED = usd_to_stars(BASIC_PRICE_DISCOUNTED)
PREMIUM_STARS = usd_to_stars(PREMIUM_PRICE)
PREMIUM_STARS_DISCOUNTED = usd_to_stars(PREMIUM_PRICE_DISCOUNTED)
VIP_STARS = usd_to_stars(VIP_PRICE)
VIP_STARS_DISCOUNTED = usd_to_stars(VIP_PRICE_DISCOUNTED)
