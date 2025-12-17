"""
Startapp Parameter Tracking Admin API

Admin endpoints for viewing statistics on startapp parameters
from deep links (e.g., startapp=web3moves).
"""

from typing import List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from src.database.engine import get_session
from src.database.models import User
from src.api.auth import get_current_user


router = APIRouter(prefix="/admin/startapp", tags=["admin-startapp"])


# ===========================
# REQUEST/RESPONSE MODELS
# ===========================


class StartappStatResponse(BaseModel):
    """Response model for startapp parameter statistics"""
    startapp_param: str
    user_count: int
    first_seen: str
    last_seen: str


class StartappStatsResponse(BaseModel):
    """Response model for all startapp statistics"""
    total_with_startapp: int
    total_without_startapp: int
    stats: List[StartappStatResponse]


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
# ENDPOINTS
# ===========================


@router.get("/stats", response_model=StartappStatsResponse)
async def get_startapp_stats(
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
    limit: int = Query(100, ge=1, le=500, description="Number of results to return"),
):
    """
    Get statistics on startapp parameters

    Returns:
        - Total users with startapp parameter
        - Total users without startapp parameter
        - Breakdown by parameter value with user counts

    Requires: Admin privileges
    """
    # Get total users with startapp parameter
    stmt_with = select(func.count(User.id)).where(User.startapp_param.isnot(None))
    result_with = await session.execute(stmt_with)
    total_with_startapp = result_with.scalar() or 0

    # Get total users without startapp parameter
    stmt_without = select(func.count(User.id)).where(User.startapp_param.is_(None))
    result_without = await session.execute(stmt_without)
    total_without_startapp = result_without.scalar() or 0

    # Get breakdown by startapp parameter
    stmt = (
        select(
            User.startapp_param,
            func.count(User.id).label("user_count"),
            func.min(User.created_at).label("first_seen"),
            func.max(User.created_at).label("last_seen"),
        )
        .where(User.startapp_param.isnot(None))
        .group_by(User.startapp_param)
        .order_by(desc("user_count"))
        .limit(limit)
    )

    result = await session.execute(stmt)
    rows = result.all()

    stats = [
        StartappStatResponse(
            startapp_param=row.startapp_param,
            user_count=row.user_count,
            first_seen=row.first_seen.isoformat() if row.first_seen else "",
            last_seen=row.last_seen.isoformat() if row.last_seen else "",
        )
        for row in rows
    ]

    return StartappStatsResponse(
        total_with_startapp=total_with_startapp,
        total_without_startapp=total_without_startapp,
        stats=stats,
    )


@router.get("/users/{startapp_param}", response_model=List[dict])
async def get_users_by_startapp(
    startapp_param: str,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(require_admin),
    limit: int = Query(50, ge=1, le=200, description="Number of users to return"),
):
    """
    Get list of users who registered with a specific startapp parameter

    Args:
        startapp_param: The startapp parameter value (e.g., "web3moves")

    Returns:
        List of users with basic info

    Requires: Admin privileges
    """
    stmt = (
        select(User)
        .where(User.startapp_param == startapp_param)
        .order_by(desc(User.created_at))
        .limit(limit)
    )

    result = await session.execute(stmt)
    users = result.scalars().all()

    return [
        {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "language": user.language,
            "subscription_tier": user.subscription_tier,
            "is_premium": user.is_premium,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "registration_platform": user.registration_platform,
        }
        for user in users
    ]
