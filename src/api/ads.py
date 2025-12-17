# coding: utf-8
"""
Ads API Endpoints for Mini App

Provides endpoints for:
- Getting promotional banner for AI Trading
- Tracking ad impressions and clicks
- Managing ad dismissals
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
from pydantic import BaseModel
from loguru import logger

from src.database.models import User
from src.database.engine import get_session
from src.api.auth import get_current_user
from src.services.ads_service import get_ads_service
from config.ads_config import get_webapp_banner, AI_TRADING_REFERRAL_URL, ADS_CONFIG


# Create router
router = APIRouter(prefix="/ads", tags=["ads"])


class BannerResponse(BaseModel):
    """Response model for banner endpoint"""
    show: bool
    title: Optional[str] = None
    subtitle: Optional[str] = None
    cta: Optional[str] = None
    url: Optional[str] = None
    type: str = "ai_trading"


class AdClickRequest(BaseModel):
    """Request model for ad click tracking"""
    ad_type: str  # 'in_chat', 'banner', 'push'
    ad_id: Optional[str] = None


class AdDismissRequest(BaseModel):
    """Request model for ad dismiss"""
    ad_type: str


@router.get("/banner")
async def get_banner(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BannerResponse:
    """
    Get promotional banner for Mini App

    Returns banner config if should be shown, otherwise show=False.

    The banner promotes AI Trading platform (syntratrade.xyz).
    Frequency is controlled by:
    - 30% base probability
    - 24h cooldown after dismiss
    - Max 3 impressions per day

    Args:
        user: Authenticated user
        session: Database session

    Returns:
        BannerResponse with banner config or show=False
    """
    try:
        # Check if ads are enabled
        if not ADS_CONFIG["webapp_banner"]["enabled"]:
            return BannerResponse(show=False)

        # Don't show to VIP users
        user_tier = "free"
        if hasattr(user, 'subscription') and user.subscription:
            user_tier = user.subscription.tier

        if user_tier == "vip":
            return BannerResponse(show=False)

        # Get ads service
        ads_service = get_ads_service()

        # Get banner (will return None if shouldn't show)
        user_lang = user.language or "ru"
        banner = ads_service.get_webapp_banner(
            user_id=user.id,
            language=user_lang,
            last_dismissed=None,  # TODO: Store dismiss time in DB
        )

        if not banner:
            return BannerResponse(show=False)

        logger.debug(f"Showing banner to user {user.id}")

        return BannerResponse(
            show=True,
            title=banner["title"],
            subtitle=banner["subtitle"],
            cta=banner["cta"],
            url=banner["url"],
            type="ai_trading",
        )

    except Exception as e:
        logger.error(f"Error getting banner for user {user.id}: {e}")
        return BannerResponse(show=False)


@router.post("/click")
async def track_ad_click(
    request: AdClickRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Track ad click

    Call this when user clicks on:
    - In-chat native ad link
    - Banner CTA button
    - Push notification CTA

    Args:
        request: Click tracking request
        user: Authenticated user
        session: Database session

    Returns:
        Success confirmation
    """
    try:
        ads_service = get_ads_service()
        ads_service.track_click(user.id, request.ad_type)

        logger.info(
            f"Ad click tracked: user={user.id}, type={request.ad_type}, "
            f"ad_id={request.ad_id}"
        )

        return {
            "success": True,
            "message": "Click tracked",
        }

    except Exception as e:
        logger.error(f"Error tracking ad click: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/dismiss")
async def dismiss_ad(
    request: AdDismissRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Dismiss ad (banner)

    Call this when user closes the banner.
    Will not show the banner again for 24 hours.

    Args:
        request: Dismiss request
        user: Authenticated user
        session: Database session

    Returns:
        Success confirmation
    """
    try:
        # TODO: Store dismiss timestamp in database
        # For now, just log it
        logger.info(f"Ad dismissed: user={user.id}, type={request.ad_type}")

        return {
            "success": True,
            "message": "Ad dismissed",
            "cooldown_hours": ADS_CONFIG["webapp_banner"]["dismiss_cooldown_hours"],
        }

    except Exception as e:
        logger.error(f"Error dismissing ad: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.get("/stats")
async def get_ad_stats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Get ad statistics for current user

    Returns impression and click counts.
    Useful for debugging and analytics.

    Args:
        user: Authenticated user
        session: Database session

    Returns:
        Ad statistics dict
    """
    try:
        ads_service = get_ads_service()
        stats = ads_service.get_user_ad_stats(user.id)

        return {
            "success": True,
            "stats": stats,
        }

    except Exception as e:
        logger.error(f"Error getting ad stats: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.get("/config")
async def get_ad_config() -> Dict[str, Any]:
    """
    Get public ad configuration

    Returns non-sensitive ad config for frontend.
    No authentication required.

    Returns:
        Public ad configuration
    """
    return {
        "ai_trading_url": AI_TRADING_REFERRAL_URL,
        "banner_enabled": ADS_CONFIG["webapp_banner"]["enabled"],
        "in_chat_enabled": ADS_CONFIG["in_chat"]["enabled"],
    }
