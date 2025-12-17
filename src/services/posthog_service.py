# coding: utf-8
"""
PostHog Analytics Service for Product Analytics

Tracks key events:
- User lifecycle (registration, subscription)
- AI interactions (requests, limits)
- Payments (conversions, revenue)
- Engagement (features used, retention)
"""
import os
from typing import Dict, Any, Optional
from loguru import logger

# PostHog is optional (graceful degradation if not configured)
try:
    from posthog import Posthog
    POSTHOG_AVAILABLE = True
except ImportError:
    POSTHOG_AVAILABLE = False
    logger.warning("PostHog not installed. Analytics disabled. Install: pip install posthog")


class PostHogService:
    """
    Product analytics service using PostHog

    Features:
    - Event tracking (user actions)
    - User identification (properties)
    - Feature flags (A/B testing)
    - Graceful degradation if not configured
    """

    def __init__(self):
        """Initialize PostHog client"""
        self.enabled = False
        self.client = None

        if not POSTHOG_AVAILABLE:
            logger.warning("PostHog library not available")
            return

        # Get API key from environment
        api_key = os.getenv("POSTHOG_API_KEY")
        host = os.getenv("POSTHOG_HOST", "https://app.posthog.com")

        if not api_key:
            logger.warning(
                "POSTHOG_API_KEY not set. Analytics disabled. "
                "Set in .env: POSTHOG_API_KEY=your_key"
            )
            return

        try:
            self.client = Posthog(
                project_api_key=api_key,
                host=host,
            )
            self.enabled = True
            logger.info(f"✅ PostHog analytics initialized: {host}")
        except Exception as e:
            logger.error(f"Failed to initialize PostHog: {e}")

    def track(
        self,
        user_id: int,
        event: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track event

        Args:
            user_id: User's database ID
            event: Event name (e.g., "ai_request_sent")
            properties: Event properties (optional)
        """
        if not self.enabled:
            return

        try:
            self.client.capture(
                distinct_id=str(user_id),
                event=event,
                properties=properties or {}
            )
            logger.debug(f"📊 Tracked: {event} for user {user_id}")
        except Exception as e:
            logger.error(f"PostHog track error: {e}")

    def identify(
        self,
        user_id: int,
        properties: Dict[str, Any]
    ) -> None:
        """
        Identify user with properties

        Args:
            user_id: User's database ID
            properties: User properties (tier, language, etc.)
        """
        if not self.enabled:
            return

        try:
            self.client.identify(
                distinct_id=str(user_id),
                properties=properties
            )
            logger.debug(f"👤 Identified user {user_id}: {properties}")
        except Exception as e:
            logger.error(f"PostHog identify error: {e}")

    def shutdown(self) -> None:
        """Shutdown PostHog client (flush pending events)"""
        if self.enabled and self.client:
            try:
                self.client.shutdown()
                logger.info("PostHog shutdown complete")
            except Exception as e:
                logger.error(f"PostHog shutdown error: {e}")


# Global instance
_posthog_service: Optional[PostHogService] = None


def get_posthog_service() -> PostHogService:
    """Get or create PostHog service singleton"""
    global _posthog_service
    if _posthog_service is None:
        _posthog_service = PostHogService()
    return _posthog_service


# ============================================================================
# EVENT TRACKING HELPERS (convenience functions)
# ============================================================================

def track_user_registered(user_id: int, language: str, referred_by: Optional[int] = None):
    """Track new user registration"""
    get_posthog_service().track(user_id, "user_registered", {
        "language": language,
        "referred_by": referred_by,
        "source": "telegram",
    })


def track_ai_request(
    user_id: int,
    tier: str,
    model: str,
    tokens: int,
    cost: float,
    request_type: str = "text"
):
    """Track AI request"""
    get_posthog_service().track(user_id, "ai_request_sent", {
        "tier": tier,
        "model": model,
        "tokens_used": tokens,
        "cost_usd": cost,
        "request_type": request_type,  # text, vision, chart
    })


def track_limit_hit(user_id: int, tier: str, limit_type: str, count: int, limit: int):
    """Track when user hits request limit"""
    get_posthog_service().track(user_id, "limit_hit", {
        "tier": tier,
        "limit_type": limit_type,  # text, chart, vision
        "requests_used": count,
        "requests_limit": limit,
    })


def track_pricing_viewed(user_id: int, current_tier: str):
    """Track when user views pricing page"""
    get_posthog_service().track(user_id, "pricing_page_viewed", {
        "current_tier": current_tier,
    })


def track_payment_started(
    user_id: int,
    tier: str,
    duration_months: int,
    amount: float,
    provider: str
):
    """Track when user starts payment process"""
    get_posthog_service().track(user_id, "payment_started", {
        "tier": tier,
        "duration_months": duration_months,
        "amount_usd": amount,
        "provider": provider,
    })


def track_payment_completed(
    user_id: int,
    tier: str,
    duration_months: int,
    amount: float,
    provider: str,
    is_upgrade: bool = False
):
    """Track successful payment"""
    get_posthog_service().track(user_id, "subscription_purchased", {
        "tier": tier,
        "duration_months": duration_months,
        "amount_usd": amount,
        "provider": provider,
        "is_upgrade": is_upgrade,
    })


def track_feature_used(user_id: int, feature: str, tier: str):
    """Track when user uses a specific feature"""
    get_posthog_service().track(user_id, "feature_used", {
        "feature": feature,
        "tier": tier,
    })


def identify_user(
    user_id: int,
    telegram_id: int,
    username: Optional[str],
    tier: str,
    language: str,
    created_at: str
):
    """Identify user with properties"""
    get_posthog_service().identify(user_id, {
        "telegram_id": telegram_id,
        "username": username,
        "tier": tier,
        "language": language,
        "created_at": created_at,
    })
