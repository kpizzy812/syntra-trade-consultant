"""
Referral API Endpoints
Provides referral system functionality for Mini App
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
from datetime import datetime
from slowapi import Limiter
from slowapi.util import get_remote_address
from loguru import logger

from src.database.models import User, Referral, Subscription, LinkedAccountType
from src.database.engine import get_session
from src.api.auth import get_current_user, get_current_user_with_session
from src.database.crud import (
    generate_referral_code,
    get_referral_stats,
    create_referral,
    grant_referee_bonus,
)
from sqlalchemy import select, func
from sqlalchemy.orm import aliased
from typing import Tuple


class ApplyReferralRequest(BaseModel):
    """Request model for applying referral code with fingerprint data"""
    referral_code: str
    # Fingerprint data for self-referral detection
    visitor_id: Optional[str] = None
    fingerprint_hash: Optional[str] = None

# Create router
router = APIRouter(prefix="/referral", tags=["referral"])

# Initialize limiter for referral-specific rate limiting
limiter = Limiter(key_func=get_remote_address)


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
# НЕТ rate limit - endpoint защищен аутентификацией (get_current_user)
# Каждый юзер просто получает свой собственный код
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

        # Build referral link using configured bot username
        from config.config import BOT_USERNAME
        referral_link = f"https://t.me/{BOT_USERNAME}?start=ref_{code}"

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


@router.get("/check/{code}")
@limiter.limit("20/minute")  # Защита от брутфорса, но не блокируем легитимных юзеров
async def check_referral_code(
    code: str,
    request: Request,  # Требуется для limiter
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Check if referral code is valid (WITHOUT authentication)

    SECURITY: Rate limiting (20/min) to prevent brute force attacks while allowing legitimate use

    Args:
        code: Referral code to check (e.g., "ABC12345")

    Returns:
        {
            "valid": true,
            "referrer_name": "John Doe" (только если код валиден, если админ - скрывается)
        }
    """
    try:
        # Check if code exists
        stmt = select(User).where(User.referral_code == code.upper())
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # Если пригласитель - админ, не показываем реальное имя
            if user.is_admin:
                referrer_name = "Syntra Team"
            else:
                referrer_name = user.first_name or user.username or "User"

            return {
                "valid": True,
                "referrer_name": referrer_name
            }
        else:
            return {
                "valid": False
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check referral code: {str(e)}"
        )


@router.get("/history")
async def get_referral_history(
    limit: int = 50,
    user_session: Tuple[User, AsyncSession] = Depends(get_current_user_with_session),
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
    # Unpack user and session from combined dependency
    # This ensures they use the SAME database session
    user, session = user_session

    try:
        # Create aliases for referee user and their subscription
        RefereeUser = aliased(User)
        RefereeSubscription = aliased(Subscription)

        # Get user's referrals with referee info and subscription in single query
        # Using outerjoin for subscription since not all users have one
        stmt = (
            select(Referral, RefereeUser, RefereeSubscription)
            .join(RefereeUser, Referral.referee_id == RefereeUser.id)
            .outerjoin(
                RefereeSubscription, RefereeUser.id == RefereeSubscription.user_id
            )
            .where(Referral.referrer_id == user.id)
            .order_by(Referral.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.all()

        # Get total count efficiently
        stmt_count = (
            select(func.count(Referral.id))
            .where(Referral.referrer_id == user.id)
        )
        result_count = await session.execute(stmt_count)
        total_count = result_count.scalar() or 0

        # Build referral history from joined results
        history = []
        for ref, referee, subscription in rows:
            # Check premium status directly from subscription (avoid lazy loading)
            is_premium = bool(
                subscription
                and subscription.is_active
                and subscription.tier != 'free'
            )
            history.append({
                "id": ref.id,
                "referee_name": referee.first_name or "Unknown",
                "referee_username": referee.username,
                "status": ref.status,
                "is_premium": is_premium,
                "joined_at": ref.created_at.isoformat() if ref.created_at else None,
                "became_active_at": (
                    ref.activated_at.isoformat() if ref.activated_at else None
                ),
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


def get_client_ip(request: Request) -> Optional[str]:
    """Get client IP address from request"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    if request.client:
        return request.client.host

    return None


@router.post("/apply")
async def apply_referral_code(
    data: ApplyReferralRequest,
    request: Request,
    user_session: Tuple[User, AsyncSession] = Depends(get_current_user_with_session),
) -> Dict[str, Any]:
    """
    Apply a referral code with fraud detection for self-referral

    This endpoint checks if the referee (current user) and referrer
    share the same IP/fingerprint, which would indicate self-referral abuse.

    Body:
        {
            "referral_code": "ABC123",
            "visitor_id": "fp_xxx",
            "fingerprint_hash": "sha256..."
        }

    Returns:
        {
            "success": true,
            "message": "Referral applied successfully",
            "bonus_granted": true,
            "self_referral_blocked": false
        }

    Errors:
        400: Invalid referral code
        400: Self-referral detected
        409: Referral already applied
    """
    user, session = user_session

    try:
        from src.services.fraud_detection_service import (
            check_self_referral,
            save_device_fingerprint,
            create_or_update_linked_account,
        )

        referral_code = data.referral_code.upper().strip()

        # Find referrer by code
        stmt = select(User).where(User.referral_code == referral_code)
        result = await session.execute(stmt)
        referrer = result.scalar_one_or_none()

        if not referrer:
            raise HTTPException(
                status_code=400,
                detail="Invalid referral code"
            )

        # Block self-referral by user ID
        if referrer.id == user.id:
            logger.warning(f"Self-referral blocked: user {user.id} tried to use own code")
            raise HTTPException(
                status_code=400,
                detail="You cannot use your own referral code"
            )

        # Check if referral already exists
        existing_stmt = select(Referral).where(
            Referral.referrer_id == referrer.id,
            Referral.referee_id == user.id
        )
        existing_result = await session.execute(existing_stmt)
        existing_referral = existing_result.scalar_one_or_none()

        if existing_referral:
            raise HTTPException(
                status_code=409,
                detail="Referral already applied"
            )

        # Get client IP
        client_ip = get_client_ip(request) or "unknown"

        # ========================================
        # FRAUD DETECTION: Check for self-referral
        # ========================================
        is_self_referral, confidence, evidence = await check_self_referral(
            session,
            referrer_id=referrer.id,
            referee_ip=client_ip,
            referee_visitor_id=data.visitor_id,
            referee_fingerprint_hash=data.fingerprint_hash,
        )

        if is_self_referral:
            # Record the detected self-referral
            await create_or_update_linked_account(
                session,
                user_id_a=referrer.id,
                user_id_b=user.id,
                link_type=LinkedAccountType.SELF_REFERRAL.value,
                confidence_score=confidence,
                shared_ips=evidence.get("shared_ips", []) if evidence else [],
                shared_visitor_ids=evidence.get("shared_visitor_ids", []) if evidence else [],
                shared_fingerprints=evidence.get("shared_fingerprints", []) if evidence else [],
                evidence_details=evidence,
            )

            logger.warning(
                f"🚨 Self-referral abuse blocked: referrer={referrer.id}, "
                f"referee={user.id}, confidence={confidence:.2f}"
            )

            raise HTTPException(
                status_code=400,
                detail="This referral code cannot be used from this device"
            )

        # Save fingerprint for future fraud detection
        try:
            await save_device_fingerprint(
                session=session,
                user_id=user.id,
                ip_address=client_ip,
                platform="web",
                event_type="referral_use",
                visitor_id=data.visitor_id,
                fingerprint_hash=data.fingerprint_hash,
            )
        except Exception as e:
            logger.error(f"Failed to save fingerprint for referral: {e}")

        # Create referral relationship
        referral = await create_referral(
            session,
            referrer_id=referrer.id,
            referee_id=user.id,
            referral_code=referral_code
        )

        if not referral:
            raise HTTPException(
                status_code=400,
                detail="Failed to create referral"
            )

        # Grant welcome bonus to referee
        bonus_granted = False
        try:
            bonus_granted = await grant_referee_bonus(session, referral.id)
            if bonus_granted:
                logger.info(f"Welcome bonus granted to referee {user.id}: +5 requests")
        except Exception as e:
            logger.error(f"Error granting welcome bonus: {e}")

        await session.commit()

        logger.info(
            f"✅ Referral applied: {referrer.id} (@{referrer.username}) "
            f"referred {user.id} (bonus={bonus_granted})"
        )

        return {
            "success": True,
            "message": "Referral applied successfully!",
            "bonus_granted": bonus_granted,
            "referrer_name": referrer.first_name or referrer.username or "User",
            "self_referral_blocked": False,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to apply referral: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to apply referral: {str(e)}"
        )
