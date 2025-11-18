"""
Profile API Endpoints
Provides user profile and subscription management for Mini App
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from pydantic import BaseModel
from datetime import datetime

from src.database.models import User, Subscription, ReferralTier, ReferralBalance
from src.database.engine import get_session
from src.api.auth import get_current_user
from sqlalchemy import select

# Create router
router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("")
async def get_profile(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Get complete user profile information

    Returns:
        {
            "user": {
                "id": 123,
                "telegram_id": 987654321,
                "username": "john_doe",
                "first_name": "John",
                "last_name": "Doe",
                "language": "ru",
                "is_admin": false,
                "created_at": "2025-01-15T00:00:00Z",
                "last_activity": "2025-01-18T12:30:00Z"
            },
            "subscription": {
                "tier": "premium",
                "is_active": true,
                "started_at": "2025-01-01T00:00:00Z",
                "expires_at": "2025-02-01T00:00:00Z",
                "is_trial": false,
                "auto_renew": true,
                "daily_limit": 100,
                "requests_used_today": 45,
                "requests_remaining": 55
            },
            "referral": {
                "tier": "gold",
                "total_referrals": 25,
                "active_referrals": 20,
                "monthly_bonus": 50,
                "discount_percent": 15,
                "revenue_share_percent": 10.0
            },
            "balance": {
                "balance_usd": 125.50,
                "earned_total_usd": 200.00,
                "withdrawn_total_usd": 50.00,
                "spent_total_usd": 24.50
            }
        }
    """
    try:
        # Load subscription
        subscription_data = None
        if user.subscription:
            # Get today's request limit info
            from src.database.crud import get_daily_limit_info
            limit_info = await get_daily_limit_info(session, user.id)

            subscription_data = {
                "tier": user.subscription.tier,
                "is_active": user.subscription.is_active,
                "started_at": user.subscription.started_at.isoformat() if user.subscription.started_at else None,
                "expires_at": user.subscription.expires_at.isoformat() if user.subscription.expires_at else None,
                "is_trial": user.subscription.is_trial,
                "trial_ends_at": user.subscription.trial_ends_at.isoformat() if user.subscription.trial_ends_at else None,
                "auto_renew": user.subscription.auto_renew,
                "daily_limit": limit_info.get("limit", 5),
                "requests_used_today": limit_info.get("used", 0),
                "requests_remaining": max(0, limit_info.get("limit", 5) - limit_info.get("used", 0)),
            }
        else:
            # No subscription, return FREE tier defaults
            from src.database.crud import get_daily_limit_info
            limit_info = await get_daily_limit_info(session, user.id)

            subscription_data = {
                "tier": "free",
                "is_active": True,
                "started_at": user.created_at.isoformat() if user.created_at else None,
                "expires_at": None,
                "is_trial": False,
                "trial_ends_at": None,
                "auto_renew": False,
                "daily_limit": 5,
                "requests_used_today": limit_info.get("used", 0),
                "requests_remaining": max(0, 5 - limit_info.get("used", 0)),
            }

        # Load referral tier
        referral_data = None
        if user.referral_tier:
            referral_data = {
                "tier": user.referral_tier.tier,
                "total_referrals": user.referral_tier.total_referrals,
                "active_referrals": user.referral_tier.active_referrals,
                "monthly_bonus": user.referral_tier.monthly_bonus,
                "discount_percent": user.referral_tier.discount_percent,
                "revenue_share_percent": user.referral_tier.revenue_share_percent,
            }
        else:
            # No referral tier, return bronze defaults
            referral_data = {
                "tier": "bronze",
                "total_referrals": 0,
                "active_referrals": 0,
                "monthly_bonus": 0,
                "discount_percent": 0,
                "revenue_share_percent": 0.0,
            }

        # Load referral balance
        balance_data = None
        if user.referral_balance:
            balance_data = {
                "balance_usd": float(user.referral_balance.balance_usd),
                "earned_total_usd": float(user.referral_balance.earned_total_usd),
                "withdrawn_total_usd": float(user.referral_balance.withdrawn_total_usd),
                "spent_total_usd": float(user.referral_balance.spent_total_usd),
                "last_payout_at": user.referral_balance.last_payout_at.isoformat() if user.referral_balance.last_payout_at else None,
            }
        else:
            # No balance, return zeros
            balance_data = {
                "balance_usd": 0.0,
                "earned_total_usd": 0.0,
                "withdrawn_total_usd": 0.0,
                "spent_total_usd": 0.0,
                "last_payout_at": None,
            }

        return {
            "user": {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "language": user.language,
                "is_admin": user.is_admin,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_activity": user.last_activity.isoformat() if user.last_activity else None,
            },
            "subscription": subscription_data,
            "referral": referral_data,
            "balance": balance_data,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch profile: {str(e)}"
        )


class UpdateSettingsRequest(BaseModel):
    """Request model for updating user settings"""
    language: str | None = None


@router.patch("/settings")
async def update_settings(
    request: UpdateSettingsRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Update user settings (language preference)

    Args:
        request: Settings update request

    Returns:
        {
            "success": true,
            "language": "en",
            "updated_at": "2025-01-18T12:30:00Z"
        }
    """
    try:
        updated = False

        # Update language if provided
        if request.language is not None:
            # Validate language
            if request.language not in ["ru", "en"]:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid language. Must be 'ru' or 'en'"
                )

            user.language = request.language
            updated = True

        # Save changes if any updates were made
        if updated:
            session.add(user)
            await session.commit()
            await session.refresh(user)

        return {
            "success": True,
            "language": user.language,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update settings: {str(e)}"
        )


@router.get("/subscription")
async def get_subscription(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Get detailed subscription information

    Returns:
        {
            "tier": "premium",
            "is_active": true,
            "started_at": "2025-01-01T00:00:00Z",
            "expires_at": "2025-02-01T00:00:00Z",
            "days_remaining": 13,
            "is_trial": false,
            "auto_renew": true,
            "benefits": {
                "daily_limit": 100,
                "features": [
                    "Unlimited analysis",
                    "Advanced indicators",
                    "Priority support"
                ]
            },
            "usage": {
                "requests_used_today": 45,
                "requests_remaining": 55,
                "reset_at": "2025-01-19T00:00:00Z"
            },
            "available_upgrades": [
                {
                    "tier": "vip",
                    "price_monthly": 29.99,
                    "price_3months": 79.99,
                    "price_12months": 299.99,
                    "features": [...]
                }
            ]
        }
    """
    try:
        # Get subscription
        subscription = user.subscription

        if not subscription:
            # Create default FREE subscription data
            from src.database.crud import get_daily_limit_info
            limit_info = await get_daily_limit_info(session, user.id)

            return {
                "tier": "free",
                "is_active": True,
                "started_at": user.created_at.isoformat() if user.created_at else None,
                "expires_at": None,
                "days_remaining": None,
                "is_trial": False,
                "auto_renew": False,
                "benefits": {
                    "daily_limit": 5,
                    "features": [
                        "Basic crypto analysis",
                        "5 requests per day",
                        "Standard support"
                    ]
                },
                "usage": {
                    "requests_used_today": limit_info.get("used", 0),
                    "requests_remaining": max(0, 5 - limit_info.get("used", 0)),
                    "reset_at": limit_info.get("reset_at"),
                },
                "available_upgrades": [
                    {
                        "tier": "basic",
                        "price_monthly": 4.99,
                        "price_3months": 12.99,
                        "price_12months": 49.99,
                        "features": [
                            "20 requests per day",
                            "Basic technical indicators",
                            "Email support"
                        ]
                    },
                    {
                        "tier": "premium",
                        "price_monthly": 9.99,
                        "price_3months": 24.99,
                        "price_12months": 99.99,
                        "features": [
                            "100 requests per day",
                            "Advanced technical indicators",
                            "Priority support",
                            "On-chain metrics"
                        ]
                    },
                    {
                        "tier": "vip",
                        "price_monthly": 29.99,
                        "price_3months": 79.99,
                        "price_12months": 299.99,
                        "features": [
                            "Unlimited requests",
                            "All indicators and metrics",
                            "Dedicated support",
                            "Custom alerts",
                            "API access"
                        ]
                    }
                ],
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }

        # Calculate days remaining
        days_remaining = None
        if subscription.expires_at:
            from datetime import UTC
            now = datetime.now(UTC)
            delta = subscription.expires_at - now
            days_remaining = max(0, delta.days)

        # Get usage info
        from src.database.crud import get_daily_limit_info
        limit_info = await get_daily_limit_info(session, user.id)

        # Define tier benefits
        tier_benefits = {
            "free": {
                "daily_limit": 5,
                "features": [
                    "Basic crypto analysis",
                    "5 requests per day",
                    "Standard support"
                ]
            },
            "basic": {
                "daily_limit": 20,
                "features": [
                    "20 requests per day",
                    "Basic technical indicators",
                    "Email support"
                ]
            },
            "premium": {
                "daily_limit": 100,
                "features": [
                    "100 requests per day",
                    "Advanced technical indicators",
                    "Priority support",
                    "On-chain metrics"
                ]
            },
            "vip": {
                "daily_limit": 999999,
                "features": [
                    "Unlimited requests",
                    "All indicators and metrics",
                    "Dedicated support",
                    "Custom alerts",
                    "API access"
                ]
            }
        }

        current_tier = subscription.tier.lower()
        benefits = tier_benefits.get(current_tier, tier_benefits["free"])

        # Define available upgrades (only show higher tiers)
        all_upgrades = [
            {
                "tier": "basic",
                "price_monthly": 4.99,
                "price_3months": 12.99,
                "price_12months": 49.99,
                "features": tier_benefits["basic"]["features"]
            },
            {
                "tier": "premium",
                "price_monthly": 9.99,
                "price_3months": 24.99,
                "price_12months": 99.99,
                "features": tier_benefits["premium"]["features"]
            },
            {
                "tier": "vip",
                "price_monthly": 29.99,
                "price_3months": 79.99,
                "price_12months": 299.99,
                "features": tier_benefits["vip"]["features"]
            }
        ]

        # Filter to show only higher tiers
        tier_order = ["free", "basic", "premium", "vip"]
        current_tier_index = tier_order.index(current_tier) if current_tier in tier_order else 0
        available_upgrades = [
            u for u in all_upgrades
            if tier_order.index(u["tier"]) > current_tier_index
        ]

        return {
            "tier": subscription.tier,
            "is_active": subscription.is_active,
            "started_at": subscription.started_at.isoformat() if subscription.started_at else None,
            "expires_at": subscription.expires_at.isoformat() if subscription.expires_at else None,
            "days_remaining": days_remaining,
            "is_trial": subscription.is_trial,
            "trial_ends_at": subscription.trial_ends_at.isoformat() if subscription.trial_ends_at else None,
            "auto_renew": subscription.auto_renew,
            "benefits": benefits,
            "usage": {
                "requests_used_today": limit_info.get("used", 0),
                "requests_remaining": max(0, limit_info.get("limit", 5) - limit_info.get("used", 0)),
                "reset_at": limit_info.get("reset_at"),
            },
            "available_upgrades": available_upgrades,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch subscription info: {str(e)}"
        )
