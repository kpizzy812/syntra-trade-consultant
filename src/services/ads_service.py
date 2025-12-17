# coding: utf-8
"""
Advertising Service for Syntra Ecosystem

Manages native advertising for AI Trading platform (syntratrade.xyz)
across all channels: Telegram bot, Mini App, Web API.

Features:
- Frequency limiting per user
- Contextual relevance scoring
- A/B testing support
- Analytics tracking
"""
from datetime import datetime, UTC
from typing import Optional, Dict, Any, Tuple
import random

from loguru import logger

from config.ads_config import (
    ADS_CONFIG,
    get_native_ad_ending,
    get_bot_ad_message,
    should_show_ad_in_chat,
    get_webapp_banner,
)


# In-memory cache for ad tracking (per user)
# Format: {user_id: {"last_in_chat_ad": datetime, "ads_today": int, "messages_since_ad": int}}
_user_ad_cache: Dict[int, Dict[str, Any]] = {}


def _get_user_ad_state(user_id: int) -> Dict[str, Any]:
    """Get or create user ad tracking state"""
    if user_id not in _user_ad_cache:
        _user_ad_cache[user_id] = {
            "last_in_chat_ad": None,
            "last_bot_push": None,
            "ads_today": 0,
            "ads_today_date": datetime.now(UTC).date(),
            "messages_since_ad": 0,
            "total_messages": 0,  # Всего сообщений за всё время
            "has_seen_ad": False,  # Видел ли хоть одну рекламу
            "total_impressions": 0,
            "total_clicks": 0,
        }

    state = _user_ad_cache[user_id]

    # Reset daily counter if it's a new day
    today = datetime.now(UTC).date()
    if state.get("ads_today_date") != today:
        state["ads_today"] = 0
        state["ads_today_date"] = today

    return state


class AdsService:
    """
    Service for managing advertisements across all Syntra channels

    Usage:
        ads_service = AdsService()

        # Check if we should add ad to AI response
        should_add, ad_text = ads_service.maybe_add_chat_ad(
            user_id=123,
            user_message="Устал от ручного трейдинга",
            user_language="ru",
            user_tier="basic"
        )

        # Get ad for bot push
        ad_message = ads_service.get_bot_ad(user_id=123, language="ru")

        # Track ad click
        ads_service.track_click(user_id=123, ad_type="in_chat")
    """

    def __init__(self):
        """Initialize ads service"""
        self.config = ADS_CONFIG

    def maybe_add_chat_ad(
        self,
        user_id: int,
        user_message: str,
        user_language: str = "ru",
        user_tier: str = "free",
        ai_response: str = "",
        user_created_at: Optional[datetime] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if we should add native ad to AI response

        УМНАЯ СТРАТЕГИЯ:
        1. Первые 24 часа — вообще без рекламы (не отпугиваем новичков)
        2. Первые 7 сообщений — без рекламы (сначала ценность)
        3. После 20 сообщений — гарантированный показ если ещё не видел
        4. Иначе — показ по контексту и вероятности

        Args:
            user_id: User's database ID
            user_message: User's message text
            user_language: User's language ('ru' or 'en')
            user_tier: User's subscription tier
            ai_response: AI's response (for quality check)
            user_created_at: User's registration datetime (for smart timing)

        Returns:
            Tuple of (should_add: bool, ad_text: Optional[str])
        """
        state = _get_user_ad_state(user_id)

        # Increment message counters
        state["messages_since_ad"] = state.get("messages_since_ad", 0) + 1
        state["total_messages"] = state.get("total_messages", 0) + 1

        # Calculate hours since registration
        hours_since_registration = 999.0  # Default: treat as old user
        if user_created_at:
            delta = datetime.now(UTC) - user_created_at.replace(tzinfo=UTC)
            hours_since_registration = delta.total_seconds() / 3600

        # Smart contextual check (returns tuple: should_show, ad_type)
        should_show, ad_type = should_show_ad_in_chat(
            user_message=user_message,
            messages_since_last_ad=state["messages_since_ad"],
            ads_today=state["ads_today"],
            user_tier=user_tier,
            ai_response=ai_response,
            total_user_messages=state["total_messages"],
            user_hours_since_registration=hours_since_registration,
            user_has_seen_ad=state.get("has_seen_ad", False),
        )

        if not should_show:
            logger.debug(f"Ad not shown to user {user_id}: reason={ad_type}")
            return False, None

        # Get contextually relevant ad text
        ad_text = get_native_ad_ending(user_language, ad_type=ad_type)

        # Update state
        state["last_in_chat_ad"] = datetime.now(UTC)
        state["ads_today"] += 1
        state["messages_since_ad"] = 0
        state["has_seen_ad"] = True  # Теперь точно видел рекламу
        state["total_impressions"] += 1

        logger.info(
            f"Showing in-chat ad to user {user_id} "
            f"(tier={user_tier}, ads_today={state['ads_today']}, "
            f"total_msgs={state['total_messages']}, ad_type={ad_type})"
        )

        return True, ad_text

    def can_send_bot_push(self, user_id: int, last_activity: Optional[datetime] = None) -> bool:
        """
        Check if we can send promotional push to user

        Args:
            user_id: User's database ID
            last_activity: User's last activity timestamp

        Returns:
            True if push can be sent
        """
        config = self.config["bot_push"]

        if not config["enabled"]:
            return False

        state = _get_user_ad_state(user_id)

        # Check minimum interval
        if state.get("last_bot_push"):
            hours_since_last = (datetime.now(UTC) - state["last_bot_push"]).total_seconds() / 3600
            if hours_since_last < config["min_interval_hours"]:
                return False

        # Check if user was active recently (if required)
        if config["only_active_users"] and last_activity:
            days_since_active = (datetime.now(UTC) - last_activity).days
            if days_since_active > 7:
                return False

        return True

    def get_bot_ad(
        self,
        user_id: int,
        language: str = "ru",
    ) -> Optional[Dict[str, str]]:
        """
        Get promotional message for bot push

        Args:
            user_id: User's database ID
            language: User's language

        Returns:
            Dict with ad message or None if shouldn't send
        """
        if not self.can_send_bot_push(user_id):
            return None

        state = _get_user_ad_state(user_id)

        # Get ad message
        ad = get_bot_ad_message(language)

        # Update state
        state["last_bot_push"] = datetime.now(UTC)
        state["total_impressions"] += 1

        logger.info(f"Generated bot push ad for user {user_id}")

        return ad

    def get_webapp_banner(
        self,
        user_id: int,
        language: str = "ru",
        last_dismissed: Optional[datetime] = None,
    ) -> Optional[Dict[str, str]]:
        """
        Get banner config for WebApp/Mini App

        Args:
            user_id: User's database ID
            language: User's language
            last_dismissed: When user last dismissed the banner

        Returns:
            Dict with banner config or None
        """
        config = self.config["webapp_banner"]

        if not config["enabled"]:
            return None

        state = _get_user_ad_state(user_id)

        # Check dismiss cooldown
        if last_dismissed:
            hours_since_dismiss = (datetime.now(UTC) - last_dismissed).total_seconds() / 3600
            if hours_since_dismiss < config["dismiss_cooldown_hours"]:
                return None

        # Check probability
        if random.random() > config["show_probability"]:
            return None

        # Get banner
        banner = get_webapp_banner(language)

        state["total_impressions"] += 1

        logger.debug(f"Showing webapp banner to user {user_id}")

        return banner

    def track_click(self, user_id: int, ad_type: str = "in_chat") -> None:
        """
        Track ad click

        Args:
            user_id: User's database ID
            ad_type: Type of ad ('in_chat', 'bot_push', 'webapp_banner')
        """
        state = _get_user_ad_state(user_id)
        state["total_clicks"] = state.get("total_clicks", 0) + 1

        logger.info(f"Ad click tracked: user={user_id}, type={ad_type}")

    def get_user_ad_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Get ad statistics for user

        Args:
            user_id: User's database ID

        Returns:
            Dict with ad stats
        """
        state = _get_user_ad_state(user_id)

        return {
            "total_impressions": state.get("total_impressions", 0),
            "total_clicks": state.get("total_clicks", 0),
            "ads_today": state.get("ads_today", 0),
            "last_in_chat_ad": state.get("last_in_chat_ad"),
            "last_bot_push": state.get("last_bot_push"),
            "ctr": (
                state.get("total_clicks", 0) / state.get("total_impressions", 1)
                if state.get("total_impressions", 0) > 0
                else 0
            ),
        }

    def reset_daily_stats(self) -> int:
        """
        Reset daily ad counters for all users

        Should be called at midnight UTC

        Returns:
            Number of users reset
        """
        count = 0
        for user_id in _user_ad_cache:
            _user_ad_cache[user_id]["ads_today"] = 0
            _user_ad_cache[user_id]["ads_today_date"] = datetime.now(UTC).date()
            count += 1

        logger.info(f"Reset daily ad stats for {count} users")
        return count


# Global service instance
_ads_service: Optional[AdsService] = None


def get_ads_service() -> AdsService:
    """
    Get or create ads service instance

    Returns:
        AdsService instance
    """
    global _ads_service

    if _ads_service is None:
        _ads_service = AdsService()

    return _ads_service


# ============================================================================
# HELPER FUNCTIONS FOR EASY INTEGRATION
# ============================================================================

def enhance_response_with_ad(
    response: str,
    user_id: int,
    user_message: str,
    user_language: str = "ru",
    user_tier: str = "free",
    user_created_at: Optional[datetime] = None,
) -> str:
    """
    Enhance AI response with native ad if appropriate

    This function should be called AFTER the AI generates response,
    as post-processing step.

    УМНАЯ СТРАТЕГИЯ:
    - Первые 24 часа — без рекламы (не отпугиваем)
    - Первые 7 сообщений — без рекламы (сначала ценность)
    - После 20 сообщений — гарантированный показ если не видел
    - Контекстный анализ и вероятность

    Args:
        response: AI's response text
        user_id: User's database ID
        user_message: User's original message
        user_language: User's language
        user_tier: User's subscription tier
        user_created_at: User's registration datetime

    Returns:
        Response with optional ad appended
    """
    ads_service = get_ads_service()

    should_add, ad_text = ads_service.maybe_add_chat_ad(
        user_id=user_id,
        user_message=user_message,
        user_language=user_language,
        user_tier=user_tier,
        ai_response=response,
        user_created_at=user_created_at,
    )

    if should_add and ad_text:
        return response.rstrip() + ad_text

    return response


def increment_message_counter(user_id: int) -> None:
    """
    Increment message counter for user (without showing ad)

    Call this when processing a message that won't show an ad.

    Args:
        user_id: User's database ID
    """
    state = _get_user_ad_state(user_id)
    state["messages_since_ad"] = state.get("messages_since_ad", 0) + 1
