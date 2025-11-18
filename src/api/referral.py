"""
Referral API Endpoints
Provides referral system functionality for Mini App
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
from datetime import datetime

from src.database.models import User, Referral
from src.database.engine import get_session
from src.api.auth import get_current_user
from src.database.crud import (
    generate_referral_code,
    get_referral_stats,
    get_referral_tier,
)
from sqlalchemy import select

# Create router
router = APIRouter(prefix="/referral", tags=["referral"])


@router.get("/stats")
async def get_stats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Get referral statistics for current user

    Returns:
        {
            "total_referrals": 15,
            "active_referrals": 12,
            "tier": "gold",
            "tier_benefits": {
                "monthly_bonus": 50,
                "discount_percent": 15,
                "revenue_share_percent": 10
            },
            "premium_conversions": 8,
            "conversion_rate": 53.3,
            "leaderboard_rank": 42,
            "next_tier": {
                "name": "platinum",
                "referrals_needed": 35
            }
        }
    """
    try:
        # Get stats from CRUD
        stats = await get_referral_stats(session, user.id)

        # Calculate next tier info
        tier = stats['tier']
        total_refs = stats['total_referrals']

        next_tier_info = None
        if tier == "bronze" and total_refs < 5:
            next_tier_info = {"name": "silver", "referrals_needed": 5 - total_refs}
        elif tier == "silver" and total_refs < 15:
            next_tier_info = {"name": "gold", "referrals_needed": 15 - total_refs}
        elif tier == "gold" and total_refs < 50:
            next_tier_info = {"name": "platinum", "referrals_needed": 50 - total_refs}

        return {
            "total_referrals": stats['total_referrals'],
            "active_referrals": stats['active_referrals'],
            "tier": stats['tier'],
            "tier_benefits": {
                "monthly_bonus": stats['monthly_bonus'],
                "discount_percent": stats['discount_percent'],
                "revenue_share_percent": stats['revenue_share_percent'],
            },
            "premium_conversions": stats['premium_conversions'],
            "conversion_rate": round(stats['conversion_rate'], 1),
            "leaderboard_rank": stats.get('leaderboard_rank'),
            "next_tier": next_tier_info,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch referral stats: {str(e)}"
        )


@router.get("/link")
async def get_referral_link(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Get referral link for current user

    If user doesn't have a referral code yet, generates one.

    Returns:
        {
            "referral_code": "ABC12345",
            "referral_link": "https://t.me/syntra_bot?start=ref_ABC12345",
            "qr_code_url": "https://api.qrserver.com/v1/create-qr-code/?data=...",
            "created_at": "2025-01-18T00:00:00Z"
        }
    """
    try:
        # Check if user has referral code
        if not user.referral_code:
            # Generate new code
            code = await generate_referral_code(session, user.id)

            # Update user
            user.referral_code = code
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            code = user.referral_code

        # Build referral link (assuming @syntra_bot username)
        # TODO: Replace with actual bot username from config
        bot_username = "syntra_bot"  # Replace with actual bot username
        referral_link = f"https://t.me/{bot_username}?start=ref_{code}"

        # Generate QR code URL (using public QR API)
        qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={referral_link}"

        return {
            "referral_code": code,
            "referral_link": referral_link,
            "qr_code_url": qr_code_url,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get referral link: {str(e)}"
        )


@router.get("/history")
async def get_referral_history(
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Get referral history for current user

    Args:
        limit: Maximum number of referrals to return (default: 50)

    Returns:
        {
            "referrals": [
                {
                    "id": 1,
                    "referee_name": "John Doe",
                    "referee_username": "johndoe",
                    "status": "active",
                    "is_premium": true,
                    "joined_at": "2025-01-15T00:00:00Z",
                    "became_active_at": "2025-01-16T00:00:00Z"
                },
                ...
            ],
            "total_count": 15
        }
    """
    try:
        # Get user's referrals
        stmt = (
            select(Referral)
            .where(Referral.referrer_id == user.id)
            .order_by(Referral.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        referrals = result.scalars().all()

        # Get total count
        stmt_count = (
            select(Referral)
            .where(Referral.referrer_id == user.id)
        )
        result_count = await session.execute(stmt_count)
        total_count = len(result_count.scalars().all())

        # Build referral history
        history = []
        for ref in referrals:
            # Get referee user info
            stmt_user = select(User).where(User.id == ref.referee_id)
            result_user = await session.execute(stmt_user)
            referee = result_user.scalar_one_or_none()

            if referee:
                history.append({
                    "id": ref.id,
                    "referee_name": referee.first_name or "Unknown",
                    "referee_username": referee.username,
                    "status": ref.status,
                    "is_premium": referee.is_premium or False,
                    "joined_at": ref.created_at.isoformat() if ref.created_at else None,
                    "became_active_at": ref.activated_at.isoformat() if ref.activated_at else None,
                })

        return {
            "referrals": history,
            "total_count": total_count,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch referral history: {str(e)}"
        )
