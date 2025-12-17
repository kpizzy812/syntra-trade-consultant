"""
Fraud Detection Admin API

Admin endpoints for viewing and managing linked accounts,
fingerprints, and abuse detection.
"""

from typing import Optional, List
from datetime import datetime, UTC

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.engine import get_session
from src.database.models import User, LinkedAccountStatus
from src.api.auth import get_current_user
from src.services.fraud_detection_service import (
    get_linked_accounts_with_users,
    get_abuse_summary_for_admin,
    update_linked_account_status,
    ban_linked_accounts,
    get_fingerprints_by_user,
    get_linked_accounts_for_user,
)


router = APIRouter(prefix="/admin/fraud", tags=["admin-fraud"])


# ===========================
# REQUEST/RESPONSE MODELS
# ===========================


class LinkedAccountResponse(BaseModel):
    """Response model for linked account"""
    id: int
    link_type: str
    confidence_score: float
    status: str
    created_at: str
    reviewed_at: Optional[str]
    shared_ips: List[str]
    shared_fingerprints: List[str]
    shared_visitor_ids: List[str]
    trial_blocked: bool
    referral_blocked: bool
    accounts_banned: bool
    admin_notes: Optional[str]
    user_a: Optional[dict]
    user_b: Optional[dict]


class AbuseSummaryResponse(BaseModel):
    """Response model for abuse summary"""
    period_days: int
    status_counts: dict
    type_counts: dict
    pending_review_count: int


class UpdateStatusRequest(BaseModel):
    """Request model for updating linked account status"""
    status: str
    admin_notes: Optional[str] = None


class BanAccountsRequest(BaseModel):
    """Request model for banning accounts"""
    ban_both: bool = True


class FingerprintResponse(BaseModel):
    """Response model for device fingerprint"""
    id: int
    ip_address: str
    platform: str
    event_type: str
    visitor_id: Optional[str]
    fingerprint_hash: Optional[str]
    user_agent: Optional[str]
    device_type: Optional[str]
    browser_name: Optional[str]
    os_name: Optional[str]
    ip_country: Optional[str]
    ip_city: Optional[str]
    created_at: str


# ===========================
# HELPER FUNCTIONS
# ===========================


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency that requires admin privileges"""
    if not user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )
    return user


# ===========================
# API ENDPOINTS
# ===========================


@router.get("/summary", response_model=AbuseSummaryResponse)
async def get_fraud_summary(
    days: int = Query(30, ge=1, le=365),
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Get fraud detection summary for admin dashboard

    Returns counts of detected abuse by status and type.

    Query params:
        days: Period to analyze (default: 30)

    Returns:
        AbuseSummaryResponse with counts
    """
    summary = await get_abuse_summary_for_admin(session, days)
    return AbuseSummaryResponse(**summary)


@router.get("/linked-accounts", response_model=List[LinkedAccountResponse])
async def list_linked_accounts(
    status: Optional[str] = Query(None, description="Filter by status: detected, confirmed_abuse, false_positive, ignored"),
    min_confidence: float = Query(0.5, ge=0.0, le=1.0, description="Minimum confidence score"),
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Get list of linked accounts for admin review

    Linked accounts are pairs of users that share:
    - Same IP address
    - Same browser fingerprint
    - Same FingerprintJS visitor ID

    Query params:
        status: Filter by status (detected, confirmed_abuse, false_positive, ignored)
        min_confidence: Minimum confidence score (0.0-1.0)
        limit: Max results (default: 50)

    Returns:
        List of LinkedAccountResponse with user details
    """
    # Validate status if provided
    if status:
        valid_statuses = [s.value for s in LinkedAccountStatus]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {valid_statuses}"
            )

    links = await get_linked_accounts_with_users(
        session,
        status=status,
        min_confidence=min_confidence,
        limit=limit,
    )

    return [LinkedAccountResponse(**link) for link in links]


@router.get("/linked-accounts/{link_id}", response_model=LinkedAccountResponse)
async def get_linked_account_detail(
    link_id: int,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Get detailed info about a specific linked account pair
    """
    links = await get_linked_accounts_with_users(session, limit=200)
    link = next((l for l in links if l["id"] == link_id), None)

    if not link:
        raise HTTPException(status_code=404, detail="Linked account not found")

    return LinkedAccountResponse(**link)


@router.put("/linked-accounts/{link_id}/status")
async def update_link_status(
    link_id: int,
    request: UpdateStatusRequest,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Update status of a linked account pair

    Statuses:
    - detected: Automatically detected, not reviewed
    - confirmed_abuse: Admin confirmed this is abuse
    - false_positive: Admin marked as not abuse
    - ignored: Admin chose to ignore this link

    Body:
        {
            "status": "confirmed_abuse",
            "admin_notes": "Both accounts used same credit card"
        }
    """
    # Validate status
    valid_statuses = [s.value for s in LinkedAccountStatus]
    if request.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    updated = await update_linked_account_status(
        session,
        link_id=link_id,
        status=request.status,
        admin_user_id=admin.id,
        admin_notes=request.admin_notes,
    )

    if not updated:
        raise HTTPException(status_code=404, detail="Linked account not found")

    return {
        "success": True,
        "link_id": link_id,
        "new_status": request.status,
    }


@router.post("/linked-accounts/{link_id}/ban")
async def ban_linked_users(
    link_id: int,
    request: BanAccountsRequest,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Ban users based on linked account detection

    Body:
        {
            "ban_both": true  // If true, ban both accounts; if false, only newer one
        }

    Returns:
        List of banned user IDs
    """
    result = await ban_linked_accounts(
        session,
        link_id=link_id,
        admin_user_id=admin.id,
        ban_both=request.ban_both,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Ban failed"))

    return result


@router.get("/users/{user_id}/fingerprints", response_model=List[FingerprintResponse])
async def get_user_fingerprints(
    user_id: int,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Get all fingerprints recorded for a user

    Useful for investigating a specific user's devices and IPs.
    """
    fingerprints = await get_fingerprints_by_user(session, user_id)

    return [
        FingerprintResponse(
            id=fp.id,
            ip_address=fp.ip_address,
            platform=fp.platform,
            event_type=fp.event_type,
            visitor_id=fp.visitor_id,
            fingerprint_hash=fp.fingerprint_hash,
            user_agent=fp.user_agent,
            device_type=fp.device_type,
            browser_name=fp.browser_name,
            os_name=fp.os_name,
            ip_country=fp.ip_country,
            ip_city=fp.ip_city,
            created_at=fp.created_at.isoformat(),
        )
        for fp in fingerprints
    ]


@router.get("/users/{user_id}/linked-accounts")
async def get_user_links(
    user_id: int,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Get all linked accounts for a specific user

    Shows all other users that share IP/fingerprint with this user.
    """
    links = await get_linked_accounts_for_user(session, user_id)

    return [
        {
            "id": link.id,
            "other_user_id": link.user_id_b if link.user_id_a == user_id else link.user_id_a,
            "link_type": link.link_type,
            "confidence_score": link.confidence_score,
            "status": link.status,
            "created_at": link.created_at.isoformat(),
        }
        for link in links
    ]
