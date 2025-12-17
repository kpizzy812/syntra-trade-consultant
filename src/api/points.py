# coding: utf-8
"""
Points API Endpoints
Provides $SYNTRA points management for Mini App and Telegram Bot
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from loguru import logger

from src.database.models import User
from src.database.engine import get_session
from src.api.auth import get_current_user
from src.services.points_service import PointsService

# Create router
router = APIRouter(prefix="/points", tags=["points"])


# ===========================
# RESPONSE MODELS
# ===========================


class PointsBalanceResponse(BaseModel):
    """User's points balance and level info"""

    balance: int
    lifetime_earned: int
    lifetime_spent: int
    level: int
    level_name_ru: str
    level_name_en: str
    level_icon: str
    earning_multiplier: float
    current_streak: int
    longest_streak: int
    last_daily_login: Optional[str]
    next_level_points: Optional[int]
    progress_to_next_level: float


class PointsTransactionResponse(BaseModel):
    """Individual points transaction"""

    id: int
    transaction_type: str
    amount: int
    balance_before: int
    balance_after: int
    description: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: str
    expires_at: Optional[str]


class LeaderboardEntryResponse(BaseModel):
    """Leaderboard entry"""

    rank: int
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    photo_url: Optional[str]
    balance: int
    level: int
    level_name: str
    level_icon: str
    is_current_user: bool


# ===========================
# ENDPOINTS
# ===========================


@router.get("/balance", response_model=PointsBalanceResponse)
async def get_balance(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get user's current points balance and level information

    Returns:
        Complete balance info including level, streak, and progress
    """
    try:
        balance_info = await PointsService.get_balance(session, user.id)

        if not balance_info:
            raise HTTPException(status_code=404, detail="Balance not found")

        # Calculate progress to next level
        points_to_next = balance_info.get("points_to_next_level", 0)
        next_level_required = balance_info.get("next_level_points_required")

        if next_level_required and next_level_required > 0:
            progress = (
                (next_level_required - points_to_next) / next_level_required
            ) * 100
        else:
            progress = 100.0  # Max level reached

        return PointsBalanceResponse(
            balance=balance_info["balance"],
            lifetime_earned=balance_info["lifetime_earned"],
            lifetime_spent=balance_info["lifetime_spent"],
            level=balance_info["level"],
            level_name_ru=balance_info["level_name_ru"],
            level_name_en=balance_info["level_name_en"],
            level_icon=balance_info["level_icon"],
            earning_multiplier=balance_info["earning_multiplier"],
            current_streak=balance_info["current_streak"],
            longest_streak=balance_info["longest_streak"],
            last_daily_login=None,  # TODO: implement last_daily_login tracking
            next_level_points=points_to_next,
            progress_to_next_level=progress,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching balance for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch balance")


@router.get("/history", response_model=List[PointsTransactionResponse])
async def get_transaction_history(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(
        50, ge=1, le=100, description="Number of transactions to return"
    ),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    transaction_type: Optional[str] = Query(
        None, description="Filter by transaction type"
    ),
):
    """
    Get user's points transaction history

    Args:
        limit: Number of transactions (max 100)
        offset: Pagination offset
        transaction_type: Optional filter by type

    Returns:
        List of transactions ordered by most recent first
    """
    try:
        transactions = await PointsService.get_transaction_history(
            session=session,
            user_id=user.id,
            limit=limit,
            offset=offset,
            transaction_type=transaction_type,
        )

        return [
            PointsTransactionResponse(
                id=t.id,
                transaction_type=t.transaction_type,
                amount=t.amount,
                balance_before=t.balance_before,
                balance_after=t.balance_after,
                description=t.description,
                metadata=t.metadata,
                created_at=t.created_at.isoformat(),
                expires_at=t.expires_at.isoformat() if t.expires_at else None,
            )
            for t in transactions
        ]

    except Exception as e:
        logger.exception(f"Error fetching transaction history for user {user.id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch transaction history"
        )


@router.get("/leaderboard", response_model=List[LeaderboardEntryResponse])
async def get_leaderboard(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=100, description="Number of top users to return"),
):
    """
    Get points leaderboard (top users by balance)

    Args:
        limit: Number of users to return (max 100)

    Returns:
        List of top users with their points and levels
    """
    try:
        from sqlalchemy import select, desc
        from src.database.models import PointsBalance, User as UserModel

        # Get top users by balance (exclude banned and specific test users)
        excluded_usernames = ['Kpeezy4L']
        stmt = (
            select(PointsBalance, UserModel)
            .join(UserModel, PointsBalance.user_id == UserModel.id)
            .where(~UserModel.is_banned)
            .where(~UserModel.username.in_(excluded_usernames))
            .order_by(desc(PointsBalance.balance))
            .limit(limit)
        )

        result = await session.execute(stmt)
        rows = result.all()

        # Get level names from database
        from src.database.models import PointsLevel

        levels_stmt = select(PointsLevel)
        levels_result = await session.execute(levels_stmt)
        levels_dict = {level.level: level for level in levels_result.scalars().all()}

        leaderboard = []
        for rank, (balance, db_user) in enumerate(rows, start=1):
            level_info = levels_dict.get(balance.level, None)
            level_name = level_info.name_ru if level_info else f"Level {balance.level}"
            level_icon = level_info.icon if level_info else "⭐"

            leaderboard.append(
                LeaderboardEntryResponse(
                    rank=rank,
                    user_id=db_user.id,
                    username=db_user.username,
                    first_name=db_user.first_name,
                    photo_url=db_user.photo_url,
                    balance=balance.balance,
                    level=balance.level,
                    level_name=level_name,
                    level_icon=level_icon,
                    is_current_user=(db_user.id == user.id),
                )
            )

        return leaderboard

    except Exception as e:
        logger.exception(f"Error fetching leaderboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch leaderboard")


@router.get("/levels", response_model=List[Dict[str, Any]])
async def get_levels(
    session: AsyncSession = Depends(get_session),
):
    """
    Get all available levels and their requirements

    Returns:
        List of all levels with points required and benefits
    """
    try:
        from sqlalchemy import select
        from src.database.models import PointsLevel

        stmt = select(PointsLevel).order_by(PointsLevel.level)
        result = await session.execute(stmt)
        levels = result.scalars().all()

        return [
            {
                "level": level.level,
                "name_ru": level.name_ru,
                "name_en": level.name_en,
                "icon": level.icon,
                "points_required": level.points_required,
                "earning_multiplier": level.earning_multiplier,
                "description_ru": level.description_ru,
                "description_en": level.description_en,
                "color": level.color,
            }
            for level in levels
        ]

    except Exception as e:
        logger.exception(f"Error fetching levels: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch levels")


@router.get("/stats", response_model=Dict[str, Any])
async def get_user_stats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get user's points earning statistics

    Returns:
        Detailed stats about how user earned points
    """
    try:
        from sqlalchemy import select, func
        from src.database.models import PointsTransaction

        # Get earning breakdown by type
        stmt = (
            select(
                PointsTransaction.transaction_type,
                func.count(PointsTransaction.id).label("count"),
                func.sum(PointsTransaction.amount).label("total"),
            )
            .where(PointsTransaction.user_id == user.id)
            .where(PointsTransaction.amount > 0)  # Only earnings
            .group_by(PointsTransaction.transaction_type)
        )

        result = await session.execute(stmt)
        rows = result.all()

        earning_breakdown = {}
        for row in rows:
            earning_breakdown[row.transaction_type] = {
                "count": row.count,
                "total_points": int(row.total) if row.total else 0,
            }

        # Get today's earnings
        from datetime import datetime, UTC

        today_start = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        stmt_today = (
            select(func.sum(PointsTransaction.amount))
            .where(PointsTransaction.user_id == user.id)
            .where(PointsTransaction.amount > 0)
            .where(PointsTransaction.created_at >= today_start)
        )

        result_today = await session.execute(stmt_today)
        today_earnings = int(result_today.scalar() or 0)

        # Get balance info
        balance_info = await PointsService.get_balance(session, user.id)

        return {
            "today_earnings": today_earnings,
            "lifetime_earned": balance_info["lifetime_earned"],
            "lifetime_spent": balance_info["lifetime_spent"],
            "current_balance": balance_info["balance"],
            "earning_breakdown": earning_breakdown,
            "current_streak": balance_info["current_streak"],
            "longest_streak": balance_info["longest_streak"],
        }

    except Exception as e:
        logger.exception(f"Error fetching stats for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch stats")
