"""
Mini App Helpers - utilities for Telegram Mini App integration

Generates URLs for quick checkout, handles deep links, and navigation
"""

from urllib.parse import urlencode
from typing import Optional
from loguru import logger

from config.config import WEBAPP_URL
from src.database.models import SubscriptionTier
from config.pricing import get_tier_price


def build_miniapp_url(
    path: str = "",
    tier: Optional[str] = None,
    discount: bool = False,
    referral_code: Optional[str] = None,
    **params,
) -> str:
    """
    Build Mini App URL with parameters

    Args:
        path: Path within Mini App (e.g., '/premium', '/checkout')
        tier: Subscription tier for direct checkout
        discount: Apply discount (post-trial)
        referral_code: Referral code to track
        **params: Additional query parameters

    Returns:
        Full Mini App URL
    """
    # Base URL
    base_url = WEBAPP_URL.rstrip("/")

    # Build path
    if path and not path.startswith("/"):
        path = f"/{path}"

    # Build query params
    query_params = {}

    if tier:
        query_params["tier"] = tier

    if discount:
        query_params["discount"] = "true"

    if referral_code:
        query_params["ref"] = referral_code

    # Add custom params
    query_params.update(params)

    # Build final URL
    url = f"{base_url}{path}"
    if query_params:
        query_string = urlencode(query_params)
        url = f"{url}?{query_string}"

    logger.debug(f"Built Mini App URL: {url}")
    return url


def get_premium_checkout_url(
    tier: str = SubscriptionTier.PREMIUM.value,
    discount: bool = False,
    source: str = "notification",
) -> str:
    """
    Get checkout URL for Premium subscription

    Args:
        tier: Subscription tier (default: PREMIUM)
        discount: Apply post-trial discount
        source: Traffic source for analytics

    Returns:
        Mini App checkout URL
    """
    return build_miniapp_url(
        path="/premium",
        tier=tier,
        discount=discount,
        source=source,
    )


def get_trial_ending_checkout_url(tier: str = SubscriptionTier.PREMIUM.value) -> str:
    """
    Get checkout URL for trial ending notification

    Args:
        tier: Subscription tier

    Returns:
        Mini App URL with trial_ending flag
    """
    return build_miniapp_url(
        path="/premium",
        tier=tier,
        discount=False,
        source="trial_ending_24h",
        highlight="trial",
    )


def get_discount_checkout_url(tier: str = SubscriptionTier.PREMIUM.value) -> str:
    """
    Get checkout URL with post-trial discount activated

    Args:
        tier: Subscription tier

    Returns:
        Mini App URL with discount enabled
    """
    price = get_tier_price(tier, with_discount=True)

    return build_miniapp_url(
        path="/premium",
        tier=tier,
        discount="true",
        source="trial_ended",
        price=price,
        highlight="discount",
    )


def get_profile_url() -> str:
    """Get Mini App profile page URL"""
    return build_miniapp_url(path="/profile")


def get_referral_url(referral_code: str) -> str:
    """
    Get Mini App URL with referral tracking

    Args:
        referral_code: User's referral code

    Returns:
        Mini App URL with referral parameter
    """
    return build_miniapp_url(referral_code=referral_code, source="referral")


def get_limits_url() -> str:
    """Get Mini App limits/usage page URL"""
    return build_miniapp_url(path="/profile", tab="limits")


# Bot deep link helpers
def build_bot_deeplink(
    bot_username: str,
    command: str = "start",
    payload: Optional[str] = None,
) -> str:
    """
    Build Telegram bot deep link

    Args:
        bot_username: Bot username (without @)
        command: Command (default: start)
        payload: Optional payload

    Returns:
        Deep link URL
    """
    base_url = f"https://t.me/{bot_username}"

    if command == "start" and payload:
        return f"{base_url}?start={payload}"
    elif command:
        return f"{base_url}?{command}={payload or ''}"

    return base_url


def build_referral_deeplink(bot_username: str, referral_code: str) -> str:
    """
    Build referral deep link for sharing

    Args:
        bot_username: Bot username
        referral_code: Referral code

    Returns:
        Shareable deep link
    """
    return build_bot_deeplink(bot_username, "start", f"ref_{referral_code}")


# WebApp button helpers
def create_webapp_button_data(
    url: str, text: Optional[str] = None
) -> dict:
    """
    Create data for WebApp inline button

    Args:
        url: Mini App URL
        text: Button text (optional)

    Returns:
        Dict for InlineKeyboardButton web_app parameter
    """
    return {
        "url": url,
    }


# Analytics tracking
def track_miniapp_open(
    user_id: int,
    source: str,
    tier: Optional[str] = None,
    discount: bool = False,
) -> None:
    """
    Track Mini App opening (for analytics)

    Args:
        user_id: Telegram user ID
        source: Traffic source
        tier: Selected tier
        discount: Discount applied
    """
    logger.info(
        f"Mini App opened: user={user_id}, source={source}, "
        f"tier={tier}, discount={discount}"
    )
    # TODO: Send to analytics service (Google Analytics, Mixpanel, etc.)


# URL validation
def is_valid_miniapp_url(url: str) -> bool:
    """
    Validate that URL is safe Mini App URL

    Args:
        url: URL to validate

    Returns:
        True if valid and safe
    """
    if not url:
        return False

    # Must start with configured WEBAPP_URL
    return url.startswith(WEBAPP_URL)
