"""
Magic Link Authentication API

Passwordless authentication через email magic links для web-платформы
"""

import secrets
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt
from loguru import logger

from src.database.engine import get_session
from src.database.crud import (
    create_magic_link,
    get_magic_link_by_token,
    mark_magic_link_used,
    get_or_create_user_from_email,
    get_user_by_email,
    count_recent_magic_links,
)
from src.services.resend_service import get_resend_service
from config.config import WEBAPP_URL
from src.api.auth import NEXTAUTH_SECRET, NEXTAUTH_ALGORITHM


router = APIRouter(prefix="/auth/magic", tags=["magic-auth"])


# ===========================
# REQUEST/RESPONSE MODELS
# ===========================


class MagicLinkRequestModel(BaseModel):
    """Request model для создания magic link"""
    email: EmailStr
    language: Optional[str] = "en"  # ru or en
    referral_code: Optional[str] = None  # Referral code if joining via referral link
    # Fingerprint data (optional, collected from FingerprintJS)
    visitor_id: Optional[str] = None
    fingerprint_hash: Optional[str] = None


class MagicLinkResponseModel(BaseModel):
    """Response model после создания magic link"""
    success: bool
    message: str
    email: str


class MagicLinkVerifyResponseModel(BaseModel):
    """Response model после верификации magic link"""
    success: bool
    token: str  # JWT token для API calls
    user: Dict[str, Any]
    trial_blocked: bool = False  # True if trial was blocked due to abuse detection
    abuse_warning: Optional[str] = None  # Warning message if abuse detected


class MagicLinkVerifyRequestModel(BaseModel):
    """Request model for magic link verification with fingerprint"""
    token: str
    # Fingerprint data (collected from FingerprintJS on client)
    visitor_id: Optional[str] = None
    fingerprint_hash: Optional[str] = None
    user_agent: Optional[str] = None
    screen_resolution: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None


# ===========================
# HELPER FUNCTIONS
# ===========================


def generate_magic_token() -> str:
    """
    Generate secure random token for magic link

    Returns:
        URL-safe random token (32 bytes = 43 chars base64)
    """
    return secrets.token_urlsafe(32)


def generate_jwt_token(user_id: int, email: str) -> str:
    """
    Generate JWT token for authenticated user

    Args:
        user_id: User ID
        email: User email

    Returns:
        JWT token string (valid for 30 days)
    """
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.now(UTC) + timedelta(days=30),  # 30 days expiration
        "iat": datetime.now(UTC),
    }

    token = jwt.encode(payload, NEXTAUTH_SECRET, algorithm=NEXTAUTH_ALGORITHM)
    return token


def get_client_ip(request: Request) -> Optional[str]:
    """
    Get client IP address from request

    Args:
        request: FastAPI request

    Returns:
        Client IP address or None
    """
    # Check X-Forwarded-For header (behind proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to direct connection
    if request.client:
        return request.client.host

    return None


# ===========================
# API ENDPOINTS
# ===========================


@router.post("/request", response_model=MagicLinkResponseModel)
async def request_magic_link(
    data: MagicLinkRequestModel,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    Request magic link для email авторизации

    Flow:
    1. Validate email format
    2. Check rate limiting (max 3 requests per 5 minutes)
    3. Generate unique token
    4. Save to database with 15 min expiration
    5. Send email with magic link

    Body:
        {
            "email": "user@example.com",
            "language": "en"  // optional, defaults to "en"
        }

    Returns:
        {
            "success": true,
            "message": "Magic link sent to your email",
            "email": "user@example.com"
        }

    Errors:
        400: Invalid email format
        429: Rate limit exceeded (max 3 requests per 5 minutes)
        500: Email service unavailable
    """
    email = data.email.lower().strip()
    language = data.language or "en"

    # Validate language
    if language not in ["en", "ru"]:
        language = "en"

    # Get email service
    email_service = get_resend_service()
    if not email_service.is_available():
        raise HTTPException(
            status_code=500,
            detail="Email service is not configured. Please contact support."
        )

    # RATE LIMITING: Check recent magic links for this email
    recent_count = await count_recent_magic_links(session, email, minutes=5)
    if recent_count >= 3:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait 5 minutes before requesting another magic link."
        )

    logger.info(f"Magic link requested for {email} (recent: {recent_count}/3)")

    # Check if user already exists
    user = await get_user_by_email(session, email)
    user_id = user.id if user else None

    # Generate token
    token = generate_magic_token()
    expires_at = datetime.now(UTC) + timedelta(minutes=15)

    # Get client IP
    client_ip = get_client_ip(request)

    # Save to database
    await create_magic_link(
        session=session,
        email=email,
        token=token,
        expires_at=expires_at,
        request_ip=client_ip,
        user_id=user_id,
        referral_code=data.referral_code,
    )

    # Build magic link URL
    # Format: https://ai.syntratrade.xyz/auth/verify?token=<token>
    base_url = WEBAPP_URL.replace("/home", "")  # Remove /home suffix if present
    magic_link_url = f"{base_url}/auth/verify?token={token}"

    # Send email
    email_sent = await email_service.send_magic_link(
        to_email=email,
        magic_link_url=magic_link_url,
        language=language
    )

    if not email_sent:
        raise HTTPException(
            status_code=500,
            detail="Failed to send email. Please try again later."
        )

    return MagicLinkResponseModel(
        success=True,
        message="Magic link sent to your email. Check your inbox!",
        email=email
    )


@router.get("/verify", response_model=MagicLinkVerifyResponseModel)
async def verify_magic_link_get(
    token: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    Verify magic link token и создать JWT сессию (GET - backward compatibility)

    For fraud detection, use POST /verify with fingerprint data.
    """
    return await _verify_magic_link_internal(
        token=token,
        request=request,
        session=session,
    )


@router.post("/verify", response_model=MagicLinkVerifyResponseModel)
async def verify_magic_link_post(
    data: MagicLinkVerifyRequestModel,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    Verify magic link token с fingerprint данными для fraud detection

    Flow:
    1. Validate token exists
    2. Check expiration
    3. Check if already used
    4. Check for existing trial (fraud detection)
    5. Get or create user
    6. Save fingerprint data
    7. Detect and link accounts
    8. Mark token as used
    9. Generate JWT token
    10. Return user data + JWT

    Body:
        {
            "token": "abc123...",
            "visitor_id": "fp_xxx",
            "fingerprint_hash": "sha256...",
            "user_agent": "Mozilla/5.0...",
            "screen_resolution": "1920x1080",
            "timezone": "Europe/Moscow",
            "language": "ru"
        }

    Returns:
        {
            "success": true,
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "user": {...},
            "trial_blocked": false,
            "abuse_warning": null
        }
    """
    return await _verify_magic_link_internal(
        token=data.token,
        request=request,
        session=session,
        visitor_id=data.visitor_id,
        fingerprint_hash=data.fingerprint_hash,
        user_agent=data.user_agent,
        screen_resolution=data.screen_resolution,
        timezone=data.timezone,
        fp_language=data.language,
    )


async def _verify_magic_link_internal(
    token: str,
    request: Request,
    session: AsyncSession,
    visitor_id: Optional[str] = None,
    fingerprint_hash: Optional[str] = None,
    user_agent: Optional[str] = None,
    screen_resolution: Optional[str] = None,
    timezone: Optional[str] = None,
    fp_language: Optional[str] = None,
) -> MagicLinkVerifyResponseModel:
    """Internal implementation of magic link verification with fraud detection"""
    from src.services.fraud_detection_service import (
        save_device_fingerprint,
        check_for_existing_trial,
        detect_and_link_accounts,
        create_or_update_linked_account,
    )
    from src.database.models import LinkedAccountType

    # Get magic link from database
    magic_link = await get_magic_link_by_token(session, token)

    if not magic_link:
        logger.warning(f"⚠️ Magic link verification failed: token={token[:10]}... not found in database")
        raise HTTPException(
            status_code=400,
            detail="Invalid magic link token"
        )

    # Check if expired
    if magic_link.expires_at < datetime.now(UTC):
        logger.warning(
            f"⚠️ Magic link verification failed: token={token[:10]}... "
            f"expired (created_at={magic_link.created_at}, expires_at={magic_link.expires_at})"
        )
        raise HTTPException(
            status_code=400,
            detail="Magic link has expired. Please request a new one."
        )

    # Check if already used
    if magic_link.is_used:
        logger.warning(
            f"⚠️ Magic link verification failed: token={token[:10]}... "
            f"already used (used_at={magic_link.used_at})"
        )
        raise HTTPException(
            status_code=401,
            detail="Magic link has already been used. Please request a new one."
        )

    # Get client IP
    client_ip = get_client_ip(request) or "unknown"

    # User agent from request if not provided
    if not user_agent:
        user_agent = request.headers.get("User-Agent")

    # ========================================
    # FRAUD DETECTION: Check for existing trial
    # ========================================
    trial_blocked = False
    abuse_warning = None

    # Check if any linked account already had a trial (before creating user)
    existing_user = await get_user_by_email(session, magic_link.email)

    if not existing_user:
        # New user - check for multi-trial abuse
        has_existing_trial, evidence = await check_for_existing_trial(
            session,
            ip_address=client_ip,
            visitor_id=visitor_id,
            fingerprint_hash=fingerprint_hash,
        )

        if has_existing_trial:
            trial_blocked = True
            abuse_warning = "Another account from your device already used a trial. Trial not available."
            logger.warning(
                f"🚨 Multi-trial abuse detected for {magic_link.email}: "
                f"evidence={evidence}"
            )

    # Get or create user (may not get trial if blocked)
    user, is_new = await get_or_create_user_from_email(
        session=session,
        email=magic_link.email,
        language="en",
        referral_code=magic_link.referral_code,
        skip_trial=trial_blocked,  # Skip trial if abuse detected
    )

    # ========================================
    # FINGERPRINT: Save device fingerprint
    # ========================================
    try:
        await save_device_fingerprint(
            session=session,
            user_id=user.id,
            ip_address=client_ip,
            platform="web",
            event_type="registration" if is_new else "login",
            visitor_id=visitor_id,
            fingerprint_hash=fingerprint_hash,
            user_agent=user_agent,
            screen_resolution=screen_resolution,
            timezone=timezone,
            language=fp_language,
        )
    except Exception as e:
        logger.error(f"Failed to save fingerprint for user {user.id}: {e}")
        # Don't fail the auth, just log the error

    # ========================================
    # LINKED ACCOUNTS: Detect and create links
    # ========================================
    try:
        await detect_and_link_accounts(
            session=session,
            user_id=user.id,
            ip_address=client_ip,
            visitor_id=visitor_id,
            fingerprint_hash=fingerprint_hash,
        )

        # If trial was blocked, record it in linked_accounts
        if trial_blocked and evidence:
            for linked_user_id in evidence.get("users_with_trial", []):
                await create_or_update_linked_account(
                    session,
                    user_id_a=user.id,
                    user_id_b=linked_user_id,
                    link_type=LinkedAccountType.MULTI_TRIAL.value,
                    confidence_score=0.9,
                    evidence_details=evidence,
                )
    except Exception as e:
        logger.error(f"Failed to detect linked accounts for user {user.id}: {e}")

    # Mark magic link as used
    await mark_magic_link_used(session, magic_link, used_ip=client_ip)

    # Generate JWT token
    jwt_token = generate_jwt_token(user.id, user.email)

    # Log successful authentication
    log_msg = f"✅ Magic link verified for {user.email} (user_id: {user.id}, new_user: {is_new})"
    if trial_blocked:
        log_msg += " [TRIAL BLOCKED - multi-account abuse]"
    logger.info(log_msg)

    return MagicLinkVerifyResponseModel(
        success=True,
        token=jwt_token,
        user={
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "language": user.language,
            "is_premium": user.is_premium,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        trial_blocked=trial_blocked,
        abuse_warning=abuse_warning,
    )


@router.get("/check-email")
async def check_email_exists(
    email: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Check if email is already registered

    Useful для UI (показать "Welcome back!" vs "Create account")

    Query params:
        email: Email to check

    Returns:
        {
            "exists": true,
            "email": "user@example.com"
        }
    """
    email = email.lower().strip()
    user = await get_user_by_email(session, email)

    return {
        "exists": user is not None,
        "email": email
    }
