"""
Request Limit Manager - manages separate limits for text/chart/vision requests

Provides unified interface for checking and incrementing different request types.
"""

from datetime import date, datetime, UTC
from typing import Tuple, Optional
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.database.models import RequestLimit, User, SubscriptionTier
from config.limits import (
    get_text_limit,
    get_chart_limit,
    get_vision_limit,
    get_futures_limit,
    LimitType,
)


class RequestType(str, Enum):
    """Types of requests that can be limited"""
    TEXT = "text"       # Text AI analysis
    CHART = "chart"     # Chart/graph generation
    VISION = "vision"   # Vision/image analysis
    FUTURES = "futures" # Futures signal generation


async def get_or_create_limit_record(
    session: AsyncSession, user_id: int
) -> RequestLimit:
    """
    Get or create request limit record for user today

    Args:
        session: Database session
        user_id: User ID (database ID)

    Returns:
        RequestLimit model for today
    """
    today = date.today()

    # Try to get existing record
    stmt = (
        select(RequestLimit)
        .where(RequestLimit.user_id == user_id)
        .where(RequestLimit.date == today)
    )
    result = await session.execute(stmt)
    limit_record = result.scalar_one_or_none()

    if limit_record:
        return limit_record

    # Create new record
    limit_record = RequestLimit(
        user_id=user_id,
        date=today,
        text_count=0,
        chart_count=0,
        vision_count=0,
        futures_count=0,
        count=0,  # Legacy field
        limit=5,  # Legacy field
    )
    session.add(limit_record)
    await session.commit()
    await session.refresh(limit_record)

    logger.info(f"Created request limit record for user {user_id}, date {today}")
    return limit_record


async def check_limit(
    session: AsyncSession,
    user: User,
    request_type: RequestType,
) -> Tuple[bool, int, int]:
    """
    Check if user has requests remaining for specific request type

    Args:
        session: Database session
        user: User model (with subscription loaded)
        request_type: Type of request (text/chart/vision)

    Returns:
        Tuple of (has_requests_remaining, current_count, limit)
    """
    # Get limit for user's tier
    if not user.subscription:
        tier = SubscriptionTier.FREE
    else:
        tier = SubscriptionTier(user.subscription.tier)

    # Get limit based on request type
    if request_type == RequestType.TEXT:
        limit = get_text_limit(tier)
    elif request_type == RequestType.CHART:
        limit = get_chart_limit(tier)
    elif request_type == RequestType.VISION:
        limit = get_vision_limit(tier)
    elif request_type == RequestType.FUTURES:
        limit = get_futures_limit(tier)
    else:
        raise ValueError(f"Unknown request type: {request_type}")

    # Get current count
    limit_record = await get_or_create_limit_record(session, user.id)

    if request_type == RequestType.TEXT:
        current_count = limit_record.text_count
    elif request_type == RequestType.CHART:
        current_count = limit_record.chart_count
    elif request_type == RequestType.VISION:
        current_count = limit_record.vision_count
    elif request_type == RequestType.FUTURES:
        current_count = limit_record.futures_count
    else:
        current_count = 0

    # Check if has remaining
    has_remaining = current_count < limit

    logger.debug(
        f"User {user.id} ({user.telegram_id}): {request_type.value} "
        f"{current_count}/{limit}, tier={tier.value}"
    )

    return has_remaining, current_count, limit


async def increment_limit(
    session: AsyncSession,
    user_id: int,
    request_type: RequestType,
) -> RequestLimit:
    """
    Increment request count for specific request type

    Args:
        session: Database session
        user_id: User ID (database ID)
        request_type: Type of request (text/chart/vision)

    Returns:
        Updated RequestLimit model
    """
    limit_record = await get_or_create_limit_record(session, user_id)

    # Increment appropriate counter
    if request_type == RequestType.TEXT:
        limit_record.text_count += 1
        limit_record.count += 1  # Legacy field (backward compatibility)
    elif request_type == RequestType.CHART:
        limit_record.chart_count += 1
    elif request_type == RequestType.VISION:
        limit_record.vision_count += 1
    elif request_type == RequestType.FUTURES:
        limit_record.futures_count += 1
    else:
        raise ValueError(f"Unknown request type: {request_type}")

    await session.commit()
    await session.refresh(limit_record)

    logger.info(
        f"User {user_id} {request_type.value} count incremented: "
        f"text={limit_record.text_count}, chart={limit_record.chart_count}, "
        f"vision={limit_record.vision_count}, futures={limit_record.futures_count}"
    )

    return limit_record


async def get_usage_stats(
    session: AsyncSession,
    user: User,
) -> dict:
    """
    Get current usage statistics for all request types

    Args:
        session: Database session
        user: User model (with subscription loaded)

    Returns:
        Dict with usage stats for each request type
    """
    # Get tier
    if not user.subscription:
        tier = SubscriptionTier.FREE
    else:
        tier = SubscriptionTier(user.subscription.tier)

    # Get limits
    text_limit = get_text_limit(tier)
    chart_limit = get_chart_limit(tier)
    vision_limit = get_vision_limit(tier)
    futures_limit = get_futures_limit(tier)

    # Get current counts
    limit_record = await get_or_create_limit_record(session, user.id)

    return {
        "text": {
            "count": limit_record.text_count,
            "limit": text_limit,
            "remaining": max(0, text_limit - limit_record.text_count),
            "percentage": int((limit_record.text_count / text_limit * 100) if text_limit > 0 else 0),
        },
        "chart": {
            "count": limit_record.chart_count,
            "limit": chart_limit,
            "remaining": max(0, chart_limit - limit_record.chart_count),
            "percentage": int((limit_record.chart_count / chart_limit * 100) if chart_limit > 0 else 0),
        },
        "vision": {
            "count": limit_record.vision_count,
            "limit": vision_limit,
            "remaining": max(0, vision_limit - limit_record.vision_count),
            "percentage": int((limit_record.vision_count / vision_limit * 100) if vision_limit > 0 else 0),
        },
        "futures": {
            "count": limit_record.futures_count,
            "limit": futures_limit,
            "remaining": max(0, futures_limit - limit_record.futures_count),
            "percentage": int((limit_record.futures_count / futures_limit * 100) if futures_limit > 0 else 0),
            "available": futures_limit > 0,  # True only for Premium/VIP
        },
        "tier": tier.value,
        "date": limit_record.date.isoformat(),
    }


async def reset_limit(
    session: AsyncSession,
    user_id: int,
    request_type: Optional[RequestType] = None,
) -> RequestLimit:
    """
    Reset request count for user (admin function)

    Args:
        session: Database session
        user_id: User ID (database ID)
        request_type: Specific request type to reset (None = reset all)

    Returns:
        Updated RequestLimit model
    """
    limit_record = await get_or_create_limit_record(session, user_id)

    if request_type is None:
        # Reset all counters
        limit_record.text_count = 0
        limit_record.chart_count = 0
        limit_record.vision_count = 0
        limit_record.futures_count = 0
        limit_record.count = 0
        logger.info(f"Admin: Reset ALL limits for user {user_id}")
    elif request_type == RequestType.TEXT:
        limit_record.text_count = 0
        limit_record.count = 0
        logger.info(f"Admin: Reset TEXT limit for user {user_id}")
    elif request_type == RequestType.CHART:
        limit_record.chart_count = 0
        logger.info(f"Admin: Reset CHART limit for user {user_id}")
    elif request_type == RequestType.VISION:
        limit_record.vision_count = 0
        logger.info(f"Admin: Reset VISION limit for user {user_id}")
    elif request_type == RequestType.FUTURES:
        limit_record.futures_count = 0
        logger.info(f"Admin: Reset FUTURES limit for user {user_id}")

    await session.commit()
    await session.refresh(limit_record)

    return limit_record


# ============================================================================
# BACKWARD COMPATIBILITY (for existing code using old API)
# ============================================================================

async def check_request_limit(
    session: AsyncSession, user: User
) -> Tuple[bool, int, int]:
    """
    DEPRECATED: Use check_limit() with RequestType instead

    Check if user has TEXT requests remaining (backward compatibility)

    Args:
        session: Database session
        user: User model (with subscription loaded)

    Returns:
        Tuple of (has_requests_remaining, current_count, limit)
    """
    return await check_limit(session, user, RequestType.TEXT)


async def increment_request_count(
    session: AsyncSession, user_id: int
) -> RequestLimit:
    """
    DEPRECATED: Use increment_limit() with RequestType instead

    Increment TEXT request count (backward compatibility)

    Args:
        session: Database session
        user_id: User ID (database ID)

    Returns:
        Updated RequestLimit model
    """
    return await increment_limit(session, user_id, RequestType.TEXT)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def detect_request_type(message_text: Optional[str] = None, has_photo: bool = False) -> RequestType:
    """
    Detect request type from message content

    Args:
        message_text: Message text (can be None)
        has_photo: Whether message has photo attachment

    Returns:
        Detected RequestType
    """
    # Vision request if has photo
    if has_photo:
        return RequestType.VISION

    # Chart request if contains chart keywords
    if message_text:
        chart_keywords = ["график", "chart", "свечи", "candles", "индикатор", "indicator"]
        message_lower = message_text.lower()
        if any(keyword in message_lower for keyword in chart_keywords):
            return RequestType.CHART

    # Default to text request
    return RequestType.TEXT
