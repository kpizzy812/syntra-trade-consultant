"""
CRUD operations for Syntra Trade Consultant Bot

Async database operations using SQLAlchemy 2.0
"""

import logging
from datetime import date, datetime, timedelta, UTC
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from src.database.models import (
    User,
    ChatHistory,
    RequestLimit,
    CostTracking,
    AdminLog,
    Subscription,
    Payment,
    SubscriptionTier,
    PaymentStatus,
    PaymentProvider,
    Referral,
    BonusRequest,
    ReferralTier,
    ReferralBalance,
    BalanceTransaction,
    ReferralStatus,
    BonusSource,
    ReferralTierLevel,
    BalanceTransactionType,
    Watchlist,
)

logger = logging.getLogger(__name__)


# ===========================
# USER OPERATIONS
# ===========================


async def get_user_by_telegram_id(
    session: AsyncSession, telegram_id: int
) -> Optional[User]:
    """
    Get user by Telegram ID

    Args:
        session: Database session
        telegram_id: Telegram user ID

    Returns:
        User model or None
    """
    stmt = select(User).where(User.telegram_id == telegram_id).options(
        selectinload(User.subscription)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    is_admin: bool = False,
    language: str = "ru",
) -> User:
    """
    Create new user

    Args:
        session: Database session
        telegram_id: Telegram user ID
        username: Telegram username
        first_name: User first name
        last_name: User last name
        is_admin: Is user an admin
        language: User language (ru or en)

    Returns:
        Created User model
    """
    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        is_admin=is_admin,
        language=language,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user, ["subscription"])

    logger.info(f"User created: {telegram_id} (@{username}) with language: {language}")
    return user


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    language: Optional[str] = None,
    telegram_language: Optional[str] = None,
) -> tuple[User, bool]:
    """
    Get existing user or create new one

    Args:
        session: Database session
        telegram_id: Telegram user ID
        username: Telegram username
        first_name: User first name
        last_name: User last name
        language: User language preference
        telegram_language: Telegram language code for auto-detection

    Returns:
        Tuple of (User model, is_created)
    """
    user = await get_user_by_telegram_id(session, telegram_id)

    if user:
        # Update last activity
        user.last_activity = datetime.now(UTC)
        await session.commit()
        return user, False

    # Create new user - detect language if not provided
    from src.utils.i18n import get_user_language

    if not language:
        language = get_user_language(None, telegram_language)

    user = await create_user(
        session,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        language=language,
    )
    return user, True


async def update_user_subscription(
    session: AsyncSession, telegram_id: int, is_subscribed: bool
) -> Optional[User]:
    """
    Update user subscription status

    Args:
        session: Database session
        telegram_id: Telegram user ID
        is_subscribed: New subscription status

    Returns:
        Updated User model or None
    """
    stmt = (
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(is_subscribed=is_subscribed)
    )
    await session.execute(stmt)
    await session.commit()

    logger.info(f"User {telegram_id} subscription updated: {is_subscribed}")
    return await get_user_by_telegram_id(session, telegram_id)


async def update_user_language(
    session: AsyncSession, telegram_id: int, language: str
) -> Optional[User]:
    """
    Update user language preference

    Args:
        session: Database session
        telegram_id: Telegram user ID
        language: New language (ru or en)

    Returns:
        Updated User model or None
    """
    stmt = update(User).where(User.telegram_id == telegram_id).values(language=language)
    await session.execute(stmt)
    await session.commit()

    logger.info(f"User {telegram_id} language updated: {language}")
    return await get_user_by_telegram_id(session, telegram_id)


async def get_inactive_users(session: AsyncSession, days: int = 7) -> List[User]:
    """
    Get users inactive for N days

    Args:
        session: Database session
        days: Number of days of inactivity

    Returns:
        List of inactive users
    """
    threshold = datetime.now(UTC) - timedelta(days=days)
    stmt = select(User).where(User.last_activity < threshold).options(
        selectinload(User.subscription)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ===========================
# CHAT HISTORY OPERATIONS
# ===========================


async def add_chat_message(
    session: AsyncSession,
    user_id: int,
    role: str,
    content: str,
    tokens_used: Optional[int] = None,
    model: Optional[str] = None,
) -> ChatHistory:
    """
    Add message to chat history

    Args:
        session: Database session
        user_id: User ID (database ID, not telegram_id)
        role: Message role (user, assistant, system)
        content: Message content
        tokens_used: Tokens used (for AI responses)
        model: AI model used

    Returns:
        Created ChatHistory model
    """
    message = ChatHistory(
        user_id=user_id,
        role=role,
        content=content,
        tokens_used=tokens_used,
        model=model,
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)

    return message


async def get_chat_history(
    session: AsyncSession, user_id: int, limit: int = 10
) -> List[ChatHistory]:
    """
    Get recent chat history for user

    Args:
        session: Database session
        user_id: User ID (database ID)
        limit: Maximum number of messages to return

    Returns:
        List of ChatHistory models (ordered by timestamp)
    """
    stmt = (
        select(ChatHistory)
        .where(ChatHistory.user_id == user_id)
        .order_by(ChatHistory.timestamp.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    messages = list(result.scalars().all())

    # Reverse to get chronological order
    return list(reversed(messages))


async def clear_chat_history(session: AsyncSession, user_id: int) -> int:
    """
    Clear chat history for user

    Args:
        session: Database session
        user_id: User ID (database ID)

    Returns:
        Number of deleted messages
    """
    stmt = delete(ChatHistory).where(ChatHistory.user_id == user_id)
    result = await session.execute(stmt)
    await session.commit()

    deleted_count = result.rowcount
    logger.info(f"Cleared {deleted_count} messages for user {user_id}")
    return deleted_count


async def get_chat_message_by_id(
    session: AsyncSession, message_id: int, user_id: int
) -> Optional[ChatHistory]:
    """
    Get chat message by ID (with ownership check)

    Args:
        session: Database session
        message_id: Message ID
        user_id: User ID (for ownership verification)

    Returns:
        ChatHistory model or None if not found or not owned by user
    """
    stmt = (
        select(ChatHistory)
        .where(ChatHistory.id == message_id)
        .where(ChatHistory.user_id == user_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def delete_chat_message(
    session: AsyncSession, message_id: int, user_id: int
) -> bool:
    """
    Delete chat message by ID (with ownership check)

    Args:
        session: Database session
        message_id: Message ID
        user_id: User ID (for ownership verification)

    Returns:
        True if deleted, False if not found or not owned by user
    """
    stmt = (
        delete(ChatHistory)
        .where(ChatHistory.id == message_id)
        .where(ChatHistory.user_id == user_id)
    )
    result = await session.execute(stmt)
    await session.commit()

    deleted = result.rowcount > 0
    if deleted:
        logger.info(f"Deleted message {message_id} for user {user_id}")
    return deleted


async def get_previous_user_message(
    session: AsyncSession, message_id: int, user_id: int
) -> Optional[ChatHistory]:
    """
    Get the previous user message before the given message ID

    Args:
        session: Database session
        message_id: Current message ID (usually an assistant message)
        user_id: User ID (for ownership verification)

    Returns:
        Previous user message or None if not found
    """
    # First get the timestamp of the current message
    current_msg_stmt = select(ChatHistory).where(
        ChatHistory.id == message_id,
        ChatHistory.user_id == user_id,
    )
    current_msg_result = await session.execute(current_msg_stmt)
    current_msg = current_msg_result.scalar_one_or_none()

    if not current_msg:
        return None

    # Find the most recent user message before this timestamp
    stmt = (
        select(ChatHistory)
        .where(ChatHistory.user_id == user_id)
        .where(ChatHistory.role == "user")
        .where(ChatHistory.timestamp < current_msg.timestamp)
        .order_by(ChatHistory.timestamp.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ===========================
# REQUEST LIMIT OPERATIONS
# ===========================


async def get_or_create_request_limit(
    session: AsyncSession, user_id: int, today: Optional[date] = None
) -> RequestLimit:
    """
    Get or create request limit for user for today

    Args:
        session: Database session
        user_id: User ID (database ID)
        today: Date (defaults to today)

    Returns:
        RequestLimit model
    """
    if today is None:
        today = date.today()

    stmt = select(RequestLimit).where(
        RequestLimit.user_id == user_id, RequestLimit.date == today
    )
    result = await session.execute(stmt)
    limit_record = result.scalar_one_or_none()

    if not limit_record:
        limit_record = RequestLimit(user_id=user_id, date=today)
        session.add(limit_record)
        await session.commit()
        await session.refresh(limit_record)

    return limit_record


async def increment_request_count(session: AsyncSession, user_id: int) -> RequestLimit:
    """
    Increment request count for user today

    Args:
        session: Database session
        user_id: User ID (database ID)

    Returns:
        Updated RequestLimit model
    """
    limit_record = await get_or_create_request_limit(session, user_id)
    limit_record.count += 1
    await session.commit()
    await session.refresh(limit_record)

    logger.info(
        f"User {user_id} request count: {limit_record.count}/{limit_record.limit}"
    )
    return limit_record


async def check_request_limit(
    session: AsyncSession, user: User
) -> tuple[bool, int, int]:
    """
    Check if user has requests remaining (with subscription tier support)

    Args:
        session: Database session
        user: User model (with subscription loaded)

    Returns:
        Tuple of (has_requests_remaining, current_count, limit)
    """
    # Get user's limit based on subscription tier
    user_limit = user.get_request_limit()

    # Get or create request limit record
    limit_record = await get_or_create_request_limit(session, user.id)

    # Update limit if it changed (e.g. user upgraded subscription)
    if limit_record.limit != user_limit:
        limit_record.limit = user_limit
        await session.commit()
        await session.refresh(limit_record)

    has_remaining = limit_record.count < limit_record.limit

    return has_remaining, limit_record.count, limit_record.limit


async def reset_request_limit(session: AsyncSession, user_id: int) -> RequestLimit:
    """
    Reset request count for user (admin function)

    Args:
        session: Database session
        user_id: User ID (database ID)

    Returns:
        Updated RequestLimit model
    """
    limit_record = await get_or_create_request_limit(session, user_id)
    limit_record.count = 0
    await session.commit()
    await session.refresh(limit_record)

    logger.info(f"Request limit reset for user {user_id}")
    return limit_record


async def set_user_limit(
    session: AsyncSession, user_id: int, new_limit: int
) -> RequestLimit:
    """
    Set custom request limit for user (admin function)

    Args:
        session: Database session
        user_id: User ID (database ID)
        new_limit: New daily request limit

    Returns:
        Updated RequestLimit model
    """
    limit_record = await get_or_create_request_limit(session, user_id)
    limit_record.limit = new_limit
    await session.commit()
    await session.refresh(limit_record)

    logger.info(f"Request limit set to {new_limit} for user {user_id}")
    return limit_record


async def get_daily_limit_info(session: AsyncSession, user_id: int) -> dict:
    """
    Get daily request limit information for user

    Args:
        session: Database session
        user_id: User ID (database ID)

    Returns:
        Dictionary with limit info:
        {
            "limit": 100,
            "used": 45,
            "remaining": 55,
            "reset_at": "2025-01-19T00:00:00Z"
        }
    """
    from datetime import datetime, time, UTC, timedelta

    # Get today's limit record
    limit_record = await get_or_create_request_limit(session, user_id)

    # Calculate reset time (midnight UTC tomorrow)
    today = datetime.now(UTC).date()
    tomorrow = today + timedelta(days=1)
    reset_time = datetime.combine(tomorrow, time.min, tzinfo=UTC)

    return {
        "limit": limit_record.limit,
        "used": limit_record.count,
        "remaining": max(0, limit_record.limit - limit_record.count),
        "reset_at": reset_time.isoformat(),
    }


# ===========================
# COST TRACKING OPERATIONS
# ===========================


async def track_cost(
    session: AsyncSession,
    user_id: int,
    service: str,
    tokens: int,
    cost: float,
    model: Optional[str] = None,
    request_type: Optional[str] = None,
) -> CostTracking:
    """
    Track API cost

    Args:
        session: Database session
        user_id: User ID (database ID)
        service: Service name (openai, together)
        tokens: Tokens used
        cost: Cost in USD
        model: Model used
        request_type: Type of request

    Returns:
        Created CostTracking model
    """
    cost_record = CostTracking(
        user_id=user_id,
        service=service,
        model=model,
        tokens=tokens,
        cost=cost,
        request_type=request_type,
    )
    session.add(cost_record)
    await session.commit()
    await session.refresh(cost_record)

    logger.info(f"Cost tracked: {service} - ${cost:.4f} ({tokens} tokens)")
    return cost_record


async def get_total_costs(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    service: Optional[str] = None,
) -> dict:
    """
    Get total costs for period

    Args:
        session: Database session
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        service: Filter by service

    Returns:
        Dict with total_cost, total_tokens, request_count
    """
    stmt = select(
        func.sum(CostTracking.cost).label("total_cost"),
        func.sum(CostTracking.tokens).label("total_tokens"),
        func.count(CostTracking.id).label("request_count"),
    )

    if start_date:
        stmt = stmt.where(CostTracking.timestamp >= start_date)
    if end_date:
        stmt = stmt.where(CostTracking.timestamp <= end_date)
    if service:
        stmt = stmt.where(CostTracking.service == service)

    result = await session.execute(stmt)
    row = result.one()

    return {
        "total_cost": float(row.total_cost or 0),
        "total_tokens": int(row.total_tokens or 0),
        "request_count": int(row.request_count or 0),
    }


async def get_user_costs(
    session: AsyncSession, user_id: int, start_date: Optional[datetime] = None
) -> dict:
    """
    Get costs for specific user

    Args:
        session: Database session
        user_id: User ID (database ID)
        start_date: Start date (defaults to today)

    Returns:
        Dict with total_cost, total_tokens, request_count
    """
    if start_date is None:
        start_date = datetime.combine(date.today(), datetime.min.time())

    stmt = select(
        func.sum(CostTracking.cost).label("total_cost"),
        func.sum(CostTracking.tokens).label("total_tokens"),
        func.count(CostTracking.id).label("request_count"),
    ).where(CostTracking.user_id == user_id, CostTracking.timestamp >= start_date)

    result = await session.execute(stmt)
    row = result.one()

    return {
        "total_cost": float(row.total_cost or 0),
        "total_tokens": int(row.total_tokens or 0),
        "request_count": int(row.request_count or 0),
    }


# ===========================
# ADMIN LOG OPERATIONS
# ===========================


async def log_admin_action(
    session: AsyncSession,
    admin_id: int,
    action: str,
    target_user_id: Optional[int] = None,
    details: Optional[str] = None,
    success: bool = True,
) -> AdminLog:
    """
    Log admin action

    Args:
        session: Database session
        admin_id: Admin telegram ID
        action: Action name
        target_user_id: Target user ID (if applicable)
        details: Additional details
        success: Was action successful

    Returns:
        Created AdminLog model
    """
    log_entry = AdminLog(
        admin_id=admin_id,
        action=action,
        target_user_id=target_user_id,
        details=details,
        success=success,
    )
    session.add(log_entry)
    await session.commit()
    await session.refresh(log_entry)

    logger.info(f"Admin action logged: {action} by {admin_id}")
    return log_entry


async def get_admin_logs(
    session: AsyncSession,
    limit: int = 50,
    admin_id: Optional[int] = None,
    action: Optional[str] = None,
) -> List[AdminLog]:
    """
    Get admin logs

    Args:
        session: Database session
        limit: Maximum number of logs
        admin_id: Filter by admin ID
        action: Filter by action

    Returns:
        List of AdminLog models
    """
    stmt = select(AdminLog).order_by(AdminLog.timestamp.desc()).limit(limit)

    if admin_id:
        stmt = stmt.where(AdminLog.admin_id == admin_id)
    if action:
        stmt = stmt.where(AdminLog.action == action)

    result = await session.execute(stmt)
    return list(result.scalars().all())


# ===========================
# STATISTICS
# ===========================


async def get_user_stats(session: AsyncSession) -> dict:
    """
    Get overall user statistics

    Returns:
        Dict with total_users, subscribed_users, active_today
    """
    # Total users
    total_stmt = select(func.count(User.id))
    total_result = await session.execute(total_stmt)
    total_users = total_result.scalar()

    # Subscribed users
    subscribed_stmt = select(func.count(User.id)).where(User.is_subscribed == True)
    subscribed_result = await session.execute(subscribed_stmt)
    subscribed_users = subscribed_result.scalar()

    # Active today
    today_start = datetime.combine(date.today(), datetime.min.time())
    active_stmt = select(func.count(User.id)).where(User.last_activity >= today_start)
    active_result = await session.execute(active_stmt)
    active_today = active_result.scalar()

    return {
        "total_users": total_users,
        "subscribed_users": subscribed_users,
        "active_today": active_today,
    }


async def get_detailed_user_stats(session: AsyncSession, days: int = 7) -> dict:
    """
    Get detailed user statistics for period

    Args:
        session: Database session
        days: Number of days to analyze

    Returns:
        Dict with detailed statistics
    """
    # Basic stats
    basic_stats = await get_user_stats(session)

    # Active users in last N days
    period_start = datetime.now(UTC) - timedelta(days=days)
    active_period_stmt = select(func.count(User.id)).where(
        User.last_activity >= period_start
    )
    active_period_result = await session.execute(active_period_stmt)
    active_period = active_period_result.scalar()

    # New users in last N days
    new_users_stmt = select(func.count(User.id)).where(User.created_at >= period_start)
    new_users_result = await session.execute(new_users_stmt)
    new_users = new_users_result.scalar()

    # Inactive users (>7 days)
    inactive_threshold = datetime.now(UTC) - timedelta(days=7)
    inactive_stmt = select(func.count(User.id)).where(
        User.last_activity < inactive_threshold
    )
    inactive_result = await session.execute(inactive_stmt)
    inactive_users = inactive_result.scalar()

    return {
        **basic_stats,
        f"active_last_{days}d": active_period,
        f"new_users_{days}d": new_users,
        "inactive_7d": inactive_users,
    }


async def get_all_users(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 10,
    order_by: str = "created_at",
) -> List[User]:
    """
    Get all users with pagination

    Args:
        session: Database session
        offset: Offset for pagination
        limit: Limit for pagination
        order_by: Field to order by ('created_at', 'last_activity', 'telegram_id')

    Returns:
        List of User models
    """
    # Build query based on order_by
    # Use joinedload for one-to-one relationship to avoid MissingGreenlet
    stmt = select(User).offset(offset).limit(limit).options(
        joinedload(User.subscription)
    ).execution_options(populate_existing=True)

    if order_by == "last_activity":
        stmt = stmt.order_by(User.last_activity.desc())
    elif order_by == "telegram_id":
        stmt = stmt.order_by(User.telegram_id)
    else:  # Default to created_at
        stmt = stmt.order_by(User.created_at.desc())

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_users_count(session: AsyncSession) -> int:
    """
    Get total number of users

    Args:
        session: Database session

    Returns:
        Total count of users
    """
    stmt = select(func.count(User.id))
    result = await session.execute(stmt)
    return result.scalar() or 0


async def search_users(
    session: AsyncSession, query: str, limit: int = 10
) -> List[User]:
    """
    Search users by username, first_name, or telegram_id

    Args:
        session: Database session
        query: Search query
        limit: Maximum results

    Returns:
        List of matching users
    """
    # Try to parse as telegram_id
    telegram_id = None
    try:
        telegram_id = int(query)
    except ValueError:
        pass

    # Build search query
    search_pattern = f"%{query}%"

    if telegram_id:
        # Search by telegram_id or username/name
        stmt = (
            select(User)
            .where(
                (User.telegram_id == telegram_id)
                | (User.username.ilike(search_pattern))
                | (User.first_name.ilike(search_pattern))
            )
            .options(joinedload(User.subscription))
            .execution_options(populate_existing=True)
            .limit(limit)
        )
    else:
        # Search only by username/name
        stmt = (
            select(User)
            .where(
                (User.username.ilike(search_pattern))
                | (User.first_name.ilike(search_pattern))
            )
            .options(joinedload(User.subscription))
            .execution_options(populate_existing=True)
            .limit(limit)
        )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_top_users_by_cost(
    session: AsyncSession, limit: int = 10, start_date: Optional[datetime] = None
) -> List[dict]:
    """
    Get top users by API costs

    Args:
        session: Database session
        limit: Number of top users
        start_date: Start date for filtering (defaults to all time)

    Returns:
        List of dicts with user info and costs
    """
    stmt = (
        select(
            User.telegram_id,
            User.username,
            User.first_name,
            func.sum(CostTracking.cost).label("total_cost"),
            func.sum(CostTracking.tokens).label("total_tokens"),
            func.count(CostTracking.id).label("request_count"),
        )
        .join(CostTracking, User.id == CostTracking.user_id)
        .group_by(User.id, User.telegram_id, User.username, User.first_name)
        .order_by(func.sum(CostTracking.cost).desc())
        .limit(limit)
    )

    if start_date:
        stmt = stmt.where(CostTracking.timestamp >= start_date)

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "telegram_id": row.telegram_id,
            "username": row.username,
            "first_name": row.first_name,
            "total_cost": float(row.total_cost or 0),
            "total_tokens": int(row.total_tokens or 0),
            "request_count": int(row.request_count or 0),
        }
        for row in rows
    ]


async def get_costs_by_service(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[dict]:
    """
    Get costs grouped by service

    Args:
        session: Database session
        start_date: Start date (inclusive)
        end_date: End date (inclusive)

    Returns:
        List of dicts with service costs
    """
    stmt = (
        select(
            CostTracking.service,
            CostTracking.model,
            func.sum(CostTracking.cost).label("total_cost"),
            func.sum(CostTracking.tokens).label("total_tokens"),
            func.count(CostTracking.id).label("request_count"),
        )
        .group_by(CostTracking.service, CostTracking.model)
        .order_by(func.sum(CostTracking.cost).desc())
    )

    if start_date:
        stmt = stmt.where(CostTracking.timestamp >= start_date)
    if end_date:
        stmt = stmt.where(CostTracking.timestamp <= end_date)

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "service": row.service,
            "model": row.model,
            "total_cost": float(row.total_cost or 0),
            "total_tokens": int(row.total_tokens or 0),
            "request_count": int(row.request_count or 0),
        }
        for row in rows
    ]


async def get_costs_by_day(session: AsyncSession, days: int = 7) -> List[dict]:
    """
    Get daily costs for last N days

    Args:
        session: Database session
        days: Number of days

    Returns:
        List of dicts with daily costs
    """
    start_date = datetime.now(UTC) - timedelta(days=days)

    stmt = (
        select(
            func.date(CostTracking.timestamp).label("date"),
            func.sum(CostTracking.cost).label("total_cost"),
            func.sum(CostTracking.tokens).label("total_tokens"),
            func.count(CostTracking.id).label("request_count"),
        )
        .where(CostTracking.timestamp >= start_date)
        .group_by(func.date(CostTracking.timestamp))
        .order_by(func.date(CostTracking.timestamp).desc())
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "date": row.date.isoformat() if row.date else None,
            "total_cost": float(row.total_cost or 0),
            "total_tokens": int(row.total_tokens or 0),
            "request_count": int(row.request_count or 0),
        }
        for row in rows
    ]


# ===========================
# SUBSCRIPTION OPERATIONS
# ===========================


async def get_subscription(
    session: AsyncSession, user_id: int
) -> Optional[Subscription]:
    """
    Get user subscription

    Args:
        session: Database session
        user_id: User ID (database ID, not telegram_id)

    Returns:
        Subscription model or None
    """
    stmt = select(Subscription).where(Subscription.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_subscription(
    session: AsyncSession,
    user_id: int,
    tier: str = SubscriptionTier.FREE.value,
) -> Subscription:
    """
    Create new subscription for user

    Args:
        session: Database session
        user_id: User ID
        tier: Subscription tier (default: FREE)

    Returns:
        Created Subscription model
    """
    subscription = Subscription(
        user_id=user_id,
        tier=tier,
        is_active=True,
    )
    session.add(subscription)
    await session.commit()
    await session.refresh(subscription)

    logger.info(f"Created subscription for user {user_id}, tier: {tier}")
    return subscription


async def activate_subscription(
    session: AsyncSession,
    user_id: int,
    tier: str,
    duration_months: int,
) -> Subscription:
    """
    Activate paid subscription for user

    Args:
        session: Database session
        user_id: User ID
        tier: Subscription tier (basic/premium/vip)
        duration_months: Duration in months (1, 3, 12)

    Returns:
        Updated Subscription model
    """
    # Get or create subscription
    subscription = await get_subscription(session, user_id)
    if not subscription:
        subscription = await create_subscription(session, user_id, tier)
        await session.refresh(subscription)

    # Calculate expiration date
    start_date = datetime.now(UTC)
    expires_at = start_date + timedelta(days=30 * duration_months)

    # Update subscription
    subscription.tier = tier
    subscription.started_at = start_date
    subscription.expires_at = expires_at
    subscription.is_active = True
    subscription.updated_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(subscription)

    logger.info(
        f"Activated subscription for user {user_id}: {tier} for {duration_months} months"
    )
    return subscription


async def deactivate_subscription(
    session: AsyncSession, user_id: int
) -> Subscription:
    """
    Deactivate subscription (downgrade to FREE)

    Args:
        session: Database session
        user_id: User ID

    Returns:
        Updated Subscription model
    """
    subscription = await get_subscription(session, user_id)
    if not subscription:
        # Create FREE subscription if doesn't exist
        return await create_subscription(session, user_id)

    # Downgrade to FREE
    subscription.tier = SubscriptionTier.FREE.value
    subscription.is_active = True
    subscription.expires_at = None
    subscription.auto_renew = False
    subscription.updated_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(subscription)

    logger.info(f"Deactivated subscription for user {user_id}, downgraded to FREE")
    return subscription


async def update_subscription(
    session: AsyncSession, user_id: int, **kwargs
) -> Subscription:
    """
    Update subscription fields

    Args:
        session: Database session
        user_id: User ID
        **kwargs: Fields to update

    Returns:
        Updated Subscription model
    """
    subscription = await get_subscription(session, user_id)
    if not subscription:
        raise ValueError(f"Subscription not found for user {user_id}")

    # Update fields
    for key, value in kwargs.items():
        if hasattr(subscription, key):
            setattr(subscription, key, value)

    subscription.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(subscription)

    logger.info(f"Updated subscription for user {user_id}: {kwargs}")
    return subscription


async def check_subscription_expired(
    session: AsyncSession, user_id: int
) -> bool:
    """
    Check if subscription is expired

    Args:
        session: Database session
        user_id: User ID

    Returns:
        True if expired, False otherwise
    """
    subscription = await get_subscription(session, user_id)
    if not subscription:
        return False

    # FREE tier never expires
    if subscription.tier == SubscriptionTier.FREE.value:
        return False

    # Check expiration
    if subscription.expires_at and subscription.expires_at < datetime.now(UTC):
        return True

    return False


async def get_expiring_subscriptions(
    session: AsyncSession, days: int = 7
) -> List[Subscription]:
    """
    Get subscriptions expiring in N days

    Args:
        session: Database session
        days: Number of days to look ahead

    Returns:
        List of Subscription models
    """
    now = datetime.now(UTC)
    future = now + timedelta(days=days)

    stmt = (
        select(Subscription)
        .where(Subscription.is_active == True)
        .where(Subscription.expires_at.isnot(None))
        .where(Subscription.expires_at > now)
        .where(Subscription.expires_at <= future)
        .order_by(Subscription.expires_at)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_expired_subscriptions(session: AsyncSession) -> List[Subscription]:
    """
    Get all expired subscriptions that are still active

    Args:
        session: Database session

    Returns:
        List of Subscription models
    """
    now = datetime.now(UTC)

    stmt = (
        select(Subscription)
        .where(Subscription.is_active == True)
        .where(Subscription.expires_at.isnot(None))
        .where(Subscription.expires_at < now)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())


# ===========================
# PAYMENT OPERATIONS
# ===========================


async def create_payment(
    session: AsyncSession,
    user_id: int,
    provider: str,
    amount: float,
    currency: str,
    tier: str,
    duration_months: int,
    subscription_id: Optional[int] = None,
    provider_payment_id: Optional[str] = None,
    provider_data: Optional[str] = None,
) -> Payment:
    """
    Create new payment record

    Args:
        session: Database session
        user_id: User ID
        provider: Payment provider
        amount: Payment amount
        currency: Currency (USD, STARS, TON, USDT)
        tier: Subscription tier
        duration_months: Duration in months
        subscription_id: Subscription ID (optional, will be set after payment completion)
        provider_payment_id: External payment ID
        provider_data: Additional provider data (JSON)

    Returns:
        Created Payment model
    """
    payment = Payment(
        user_id=user_id,
        subscription_id=subscription_id,
        provider=provider,
        status=PaymentStatus.PENDING.value,
        amount=amount,
        currency=currency,
        tier=tier,
        duration_months=duration_months,
        provider_payment_id=provider_payment_id,
        provider_data=provider_data,
    )

    session.add(payment)
    await session.commit()
    await session.refresh(payment)

    logger.info(
        f"Created payment {payment.id} for user {user_id}: {amount} {currency}"
    )
    return payment


async def get_payment(session: AsyncSession, payment_id: int) -> Optional[Payment]:
    """
    Get payment by ID

    Args:
        session: Database session
        payment_id: Payment ID

    Returns:
        Payment model or None
    """
    stmt = select(Payment).where(Payment.id == payment_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_payment_by_provider_id(
    session: AsyncSession, provider_payment_id: str
) -> Optional[Payment]:
    """
    Get payment by provider payment ID

    Args:
        session: Database session
        provider_payment_id: External payment ID from provider

    Returns:
        Payment model or None
    """
    stmt = select(Payment).where(Payment.provider_payment_id == provider_payment_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_payments(
    session: AsyncSession, user_id: int, limit: int = 10
) -> List[Payment]:
    """
    Get user's payment history

    Args:
        session: Database session
        user_id: User ID
        limit: Maximum number of records

    Returns:
        List of Payment models
    """
    stmt = (
        select(Payment)
        .where(Payment.user_id == user_id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_all_payments(
    session: AsyncSession,
    status: Optional[PaymentStatus] = None,
    limit: int = 100,
) -> List[Payment]:
    """
    Get all payments with optional status filter

    Args:
        session: Database session
        status: Filter by payment status (optional)
        limit: Maximum number of records

    Returns:
        List of Payment models
    """
    stmt = select(Payment).order_by(Payment.created_at.desc()).limit(limit)

    if status:
        stmt = stmt.where(Payment.status == status)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_payment_status(
    session: AsyncSession,
    payment_id: int,
    status: str,
    provider_payment_id: Optional[str] = None,
    provider_data: Optional[str] = None,
) -> Payment:
    """
    Update payment status

    Args:
        session: Database session
        payment_id: Payment ID
        status: New status
        provider_payment_id: External payment ID (optional)
        provider_data: Additional provider data (optional)

    Returns:
        Updated Payment model
    """
    payment = await get_payment(session, payment_id)
    if not payment:
        raise ValueError(f"Payment {payment_id} not found")

    payment.status = status

    if provider_payment_id:
        payment.provider_payment_id = provider_payment_id

    if provider_data:
        payment.provider_data = provider_data

    # Set completion timestamp if completed
    if status == PaymentStatus.COMPLETED.value:
        payment.completed_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(payment)

    logger.info(f"Updated payment {payment_id} status to {status}")
    return payment


async def complete_payment(session: AsyncSession, payment_id: int) -> Payment:
    """
    Mark payment as completed and activate subscription

    Args:
        session: Database session
        payment_id: Payment ID

    Returns:
        Updated Payment model
    """
    payment = await get_payment(session, payment_id)
    if not payment:
        raise ValueError(f"Payment {payment_id} not found")

    # Update payment status
    payment.status = PaymentStatus.COMPLETED.value
    payment.completed_at = datetime.now(UTC)

    # Activate subscription
    subscription = await activate_subscription(
        session,
        payment.user_id,
        payment.tier,
        payment.duration_months,
    )

    # Link payment to subscription
    payment.subscription_id = subscription.id

    await session.commit()
    await session.refresh(payment)

    logger.info(f"Completed payment {payment_id}, activated subscription {subscription.id}")
    return payment


# ===========================
# SUBSCRIPTION ANALYTICS
# ===========================


async def get_subscription_stats(session: AsyncSession) -> dict:
    """
    Get subscription statistics

    Args:
        session: Database session

    Returns:
        Dict with subscription stats
    """
    # Total subscriptions by tier
    stmt_tiers = (
        select(Subscription.tier, func.count(Subscription.id).label("count"))
        .where(Subscription.is_active == True)
        .group_by(Subscription.tier)
    )

    result_tiers = await session.execute(stmt_tiers)
    tiers = {row.tier: row.count for row in result_tiers.all()}

    # Total active subscriptions
    stmt_total = select(func.count(Subscription.id)).where(
        Subscription.is_active == True
    )
    result_total = await session.execute(stmt_total)
    total_active = result_total.scalar_one()

    # Expiring soon (7 days)
    expiring_soon = len(await get_expiring_subscriptions(session, days=7))

    return {
        "total_active": total_active,
        "by_tier": tiers,
        "expiring_soon_7d": expiring_soon,
    }


async def get_revenue_stats(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    """
    Get revenue statistics

    Args:
        session: Database session
        start_date: Start date (optional)
        end_date: End date (optional)

    Returns:
        Dict with revenue stats
    """
    stmt = select(
        func.count(Payment.id).label("total_payments"),
        func.sum(Payment.amount).label("total_revenue"),
        func.avg(Payment.amount).label("avg_payment"),
    ).where(Payment.status == PaymentStatus.COMPLETED.value)

    if start_date:
        stmt = stmt.where(Payment.completed_at >= start_date)
    if end_date:
        stmt = stmt.where(Payment.completed_at <= end_date)

    result = await session.execute(stmt)
    row = result.one()

    # Revenue by tier
    stmt_tiers = (
        select(
            Payment.tier,
            func.sum(Payment.amount).label("revenue"),
            func.count(Payment.id).label("count"),
        )
        .where(Payment.status == PaymentStatus.COMPLETED.value)
        .group_by(Payment.tier)
    )

    if start_date:
        stmt_tiers = stmt_tiers.where(Payment.completed_at >= start_date)
    if end_date:
        stmt_tiers = stmt_tiers.where(Payment.completed_at <= end_date)

    result_tiers = await session.execute(stmt_tiers)
    by_tier = {
        row.tier: {"revenue": float(row.revenue or 0), "count": row.count}
        for row in result_tiers.all()
    }

    return {
        "total_payments": row.total_payments or 0,
        "total_revenue": float(row.total_revenue or 0),
        "avg_payment": float(row.avg_payment or 0),
        "by_tier": by_tier,
    }


# ===========================
# BUSINESS METRICS
# ===========================


async def get_mrr(session: AsyncSession) -> dict:
    """
    Calculate Monthly Recurring Revenue (MRR)

    MRR = Sum of all active subscription monthly values

    Args:
        session: Database session

    Returns:
        Dict with MRR stats
    """
    # Import prices from telegram_stars_service to avoid hardcoding
    from src.services.telegram_stars_service import SUBSCRIPTION_PLANS

    # Tier prices per month (USD) - get from actual pricing config
    tier_prices = {
        SubscriptionTier.FREE.value: 0,
        SubscriptionTier.BASIC.value: SUBSCRIPTION_PLANS[SubscriptionTier.BASIC]["1"]["usd"],
        SubscriptionTier.PREMIUM.value: SUBSCRIPTION_PLANS[SubscriptionTier.PREMIUM]["1"]["usd"],
        SubscriptionTier.VIP.value: SUBSCRIPTION_PLANS[SubscriptionTier.VIP]["1"]["usd"],
    }

    # Get active subscriptions by tier
    stmt = (
        select(Subscription.tier, func.count(Subscription.id).label("count"))
        .where(Subscription.is_active == True)
        .where(Subscription.tier != SubscriptionTier.FREE.value)
        .group_by(Subscription.tier)
    )

    result = await session.execute(stmt)
    rows = result.all()

    # Calculate MRR
    mrr_by_tier = {}
    total_mrr = 0.0

    for row in rows:
        tier_mrr = tier_prices.get(row.tier, 0) * row.count
        mrr_by_tier[row.tier] = {
            "count": row.count,
            "price": tier_prices.get(row.tier, 0),
            "mrr": tier_mrr,
        }
        total_mrr += tier_mrr

    return {
        "total_mrr": total_mrr,
        "by_tier": mrr_by_tier,
        "currency": "USD",
    }


async def get_profit_loss(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    """
    Calculate Profit/Loss = Revenue - Costs

    Args:
        session: Database session
        start_date: Start date (optional, defaults to 30 days ago)
        end_date: End date (optional, defaults to now)

    Returns:
        Dict with profit/loss stats
    """
    if not start_date:
        start_date = datetime.now(UTC) - timedelta(days=30)
    if not end_date:
        end_date = datetime.now(UTC)

    # Get revenue from payments
    revenue_stats = await get_revenue_stats(session, start_date, end_date)
    total_revenue = revenue_stats["total_revenue"]

    # Get costs from CostTracking
    costs_stats = await get_total_costs(session, start_date, end_date)
    total_costs = costs_stats["total_cost"]

    # Calculate profit/loss
    profit = total_revenue - total_costs
    margin = (profit / total_revenue * 100) if total_revenue > 0 else 0

    return {
        "revenue": total_revenue,
        "costs": total_costs,
        "profit": profit,
        "margin_percent": margin,
        "is_profitable": profit >= 0,
        "period_days": (end_date - start_date).days,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


async def get_unit_economics(session: AsyncSession, user_id: int) -> dict:
    """
    Calculate unit economics for a specific user

    Metrics:
    - LTV (Lifetime Value) = total revenue from user
    - Total Cost = API costs for this user
    - Profit = LTV - Total Cost

    Args:
        session: Database session
        user_id: User ID (internal DB id, not telegram_id)

    Returns:
        Dict with unit economics for the user
    """
    # Get user revenue (all completed payments)
    stmt_revenue = (
        select(func.sum(Payment.amount))
        .where(Payment.user_id == user_id)
        .where(Payment.status == PaymentStatus.COMPLETED.value)
    )
    result_revenue = await session.execute(stmt_revenue)
    ltv = float(result_revenue.scalar() or 0)

    # Get user costs (all API requests)
    stmt_costs = (
        select(func.sum(CostTracking.cost))
        .where(CostTracking.user_id == user_id)
    )
    result_costs = await session.execute(stmt_costs)
    total_cost = float(result_costs.scalar() or 0)

    # Calculate profit
    profit = ltv - total_cost
    roi = ((profit / total_cost) * 100) if total_cost > 0 else 0

    # Get user subscription tier
    stmt_user = select(User).where(User.id == user_id)
    result_user = await session.execute(stmt_user)
    user = result_user.scalar_one_or_none()

    tier = None
    if user and user.subscription:
        tier = user.subscription.tier

    return {
        "user_id": user_id,
        "ltv": ltv,
        "total_cost": total_cost,
        "profit": profit,
        "roi_percent": roi,
        "is_profitable": profit >= 0,
        "tier": tier,
    }


async def get_churn_rate(session: AsyncSession, days: int = 30) -> dict:
    """
    Calculate churn rate

    Churn Rate = (Cancelled subscriptions / Total active at start) * 100

    Args:
        session: Database session
        days: Period in days to analyze

    Returns:
        Dict with churn rate stats
    """
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days)

    # Active subscriptions at period start
    stmt_start = (
        select(func.count(Subscription.id))
        .where(Subscription.created_at <= start_date)
        .where(Subscription.is_active == True)
    )
    result_start = await session.execute(stmt_start)
    active_at_start = result_start.scalar() or 0

    # Subscriptions that became inactive during period
    stmt_churned = (
        select(func.count(Subscription.id))
        .where(Subscription.updated_at >= start_date)
        .where(Subscription.updated_at <= end_date)
        .where(Subscription.is_active == False)
    )
    result_churned = await session.execute(stmt_churned)
    churned = result_churned.scalar() or 0

    # Calculate churn rate
    churn_rate = (churned / active_at_start * 100) if active_at_start > 0 else 0

    # Current active subscriptions
    stmt_current = (
        select(func.count(Subscription.id))
        .where(Subscription.is_active == True)
    )
    result_current = await session.execute(stmt_current)
    active_now = result_current.scalar() or 0

    return {
        "churn_rate_percent": churn_rate,
        "churned_count": churned,
        "active_at_start": active_at_start,
        "active_now": active_now,
        "period_days": days,
    }


async def get_business_metrics(session: AsyncSession) -> dict:
    """
    Get comprehensive business metrics dashboard

    Includes:
    - MRR (Monthly Recurring Revenue)
    - Profit/Loss (last 30 days)
    - ARPU (Average Revenue Per User)
    - Churn Rate
    - Conversion Rate

    Args:
        session: Database session

    Returns:
        Dict with all key business metrics
    """
    # MRR
    mrr_data = await get_mrr(session)
    mrr = mrr_data["total_mrr"]

    # Profit/Loss (last 30 days)
    profit_data = await get_profit_loss(session)
    profit = profit_data["profit"]
    margin = profit_data["margin_percent"]

    # User stats
    user_stats = await get_user_stats(session)
    total_users = user_stats["total_users"]

    # Subscription stats
    sub_stats = await get_subscription_stats(session)
    total_paying = sub_stats["total_active"]

    # ARPU (Average Revenue Per User) - only paying users
    arpu = (mrr / total_paying) if total_paying > 0 else 0

    # Conversion rate
    conversion = (total_paying / total_users * 100) if total_users > 0 else 0

    # Churn rate (last 30 days)
    churn_data = await get_churn_rate(session, days=30)
    churn = churn_data["churn_rate_percent"]

    # Revenue stats (last 30 days)
    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
    revenue_data = await get_revenue_stats(session, start_date=thirty_days_ago)
    total_revenue_30d = revenue_data["total_revenue"]

    # Cost stats (last 30 days)
    cost_data = await get_total_costs(session, start_date=thirty_days_ago)
    total_costs_30d = cost_data["total_cost"]

    return {
        # Revenue metrics
        "mrr": mrr,
        "revenue_30d": total_revenue_30d,
        "arpu": arpu,

        # Cost metrics
        "costs_30d": total_costs_30d,

        # Profitability
        "profit_30d": profit,
        "margin_percent": margin,
        "is_profitable": profit >= 0,

        # Growth metrics
        "total_users": total_users,
        "paying_users": total_paying,
        "conversion_percent": conversion,
        "churn_rate_percent": churn,

        # Health indicators
        "health_status": "healthy" if profit >= 0 and churn < 10 else "warning" if profit >= 0 else "critical",
    }


# ===========================
# REFERRAL SYSTEM OPERATIONS
# ===========================


async def generate_referral_code(session: AsyncSession, user_id: int) -> str:
    """
    Generate unique referral code for user

    Args:
        session: Database session
        user_id: User ID

    Returns:
        Unique referral code (8 characters)
    """
    import random
    import string

    while True:
        # Generate 8-character code
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        # Check uniqueness
        stmt = select(User).where(User.referral_code == code)
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            return code


async def create_referral(
    session: AsyncSession,
    referrer_id: int,
    referee_id: int,
    referral_code: str,
) -> Referral:
    """
    Create referral relationship

    Args:
        session: Database session
        referrer_id: User who referred
        referee_id: User who was referred
        referral_code: Referral code used

    Returns:
        Created Referral model or None if validation fails
    """
    from sqlalchemy.exc import IntegrityError

    # Block self-referrals
    if referrer_id == referee_id:
        logger.warning(f"Self-referral blocked: user {referrer_id} tried to refer themselves")
        return None

    try:
        referral = Referral(
            referrer_id=referrer_id,
            referee_id=referee_id,
            referral_code=referral_code,
            status=ReferralStatus.PENDING.value,
            trial_granted=False,
            bonus_granted=False,
        )
        session.add(referral)
        await session.commit()
        await session.refresh(referral)

        logger.info(f"Referral created: {referrer_id} → {referee_id} with code {referral_code}")
        return referral
    except IntegrityError:
        await session.rollback()
        logger.warning(f"Duplicate referral blocked: {referrer_id} → {referee_id}")
        return None


async def grant_referral_rewards(
    session: AsyncSession,
    referral_id: int,
) -> None:
    """
    Grant rewards to both referrer and referee

    Rewards:
    - Referee: +15 bonus requests
    - Referrer: +30 bonus requests

    Args:
        session: Database session
        referral_id: Referral ID
    """
    stmt = select(Referral).where(Referral.id == referral_id)
    result = await session.execute(stmt)
    referral = result.scalar_one_or_none()

    if not referral:
        logger.error(f"Referral {referral_id} not found")
        return

    # Grant bonus to referee (+15 requests)
    if not referral.trial_granted:
        await add_bonus_requests(
            session,
            user_id=referral.referee_id,
            amount=15,
            source=BonusSource.REFERRAL_SIGNUP.value,
            description="Бонус за регистрацию по реферальной ссылке",
        )
        referral.trial_granted = True
        logger.info(f"Granted +15 bonus requests to referee {referral.referee_id}")

    # Grant bonus to referrer (+30 requests)
    if not referral.bonus_granted:
        await add_bonus_requests(
            session,
            user_id=referral.referrer_id,
            amount=30,
            source=BonusSource.REFERRAL_SIGNUP.value,
            description="Бонус за приглашение друга",
        )
        referral.bonus_granted = True
        logger.info(f"Granted +30 bonus requests to referrer {referral.referrer_id}")

    # Update referral status
    referral.status = ReferralStatus.ACTIVE.value
    referral.activated_at = datetime.now(UTC)

    # Update referrer's tier
    await update_referral_tier(session, referral.referrer_id)

    await session.commit()


async def is_referral_active(session: AsyncSession, referee_id: int) -> bool:
    """
    Check if referral meets activation criteria and update status if criteria met

    Criteria:
    - Registered > 24 hours ago
    - Made at least 5 requests
    - Not banned
    - Has username

    Args:
        session: Database session
        referee_id: Referee user ID

    Returns:
        True if referral is active (or was just activated)
    """
    stmt = select(User).where(User.id == referee_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return False

    # Check criteria
    # Make sure both datetimes are timezone-aware
    user_created = user.created_at
    if user_created.tzinfo is None:
        user_created = user_created.replace(tzinfo=UTC)
    age_ok = (datetime.now(UTC) - user_created).days >= 1

    # Count requests made
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    stmt = (
        select(func.sum(RequestLimit.count))
        .where(RequestLimit.user_id == referee_id)
        .where(RequestLimit.date >= thirty_days_ago)
    )
    result = await session.execute(stmt)
    total_requests = result.scalar() or 0
    requests_ok = total_requests >= 5

    not_banned = not getattr(user, 'is_banned', False)
    has_username = user.username is not None

    # If all criteria met, update referral status in database
    if age_ok and requests_ok and not_banned and has_username:
        # Find referral record for this referee
        stmt = select(Referral).where(Referral.referee_id == referee_id)
        result = await session.execute(stmt)
        referral = result.scalar_one_or_none()

        if referral and referral.status == ReferralStatus.PENDING.value:
            # Activate the referral
            referral.status = ReferralStatus.ACTIVE.value
            referral.activated_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(referral)
            logger.info(f"Referral activated: {referral.referrer_id} → {referee_id}")

        return True

    return False


async def update_referral_tier(
    session: AsyncSession,
    user_id: int,
) -> ReferralTier:
    """
    Update user's referral tier based on active referrals

    Tiers:
    - Bronze: 0-4 active referrals
    - Silver: 5-14 active referrals (monthly_bonus=50, discount=10%)
    - Gold: 15-49 active referrals (monthly_bonus=150, discount=20%, revenue_share=10%)
    - Platinum: 50+ active referrals (monthly_bonus=500, discount=30%, revenue_share=15%)

    Args:
        session: Database session
        user_id: User ID

    Returns:
        Updated ReferralTier model
    """
    # Get or create tier
    stmt = select(ReferralTier).where(ReferralTier.user_id == user_id)
    result = await session.execute(stmt)
    tier_obj = result.scalar_one_or_none()

    if not tier_obj:
        tier_obj = ReferralTier(user_id=user_id)
        session.add(tier_obj)

    # Count active referrals
    stmt = (
        select(func.count())
        .select_from(Referral)
        .where(Referral.referrer_id == user_id)
        .where(Referral.status == ReferralStatus.ACTIVE.value)
    )
    result = await session.execute(stmt)
    active_count = result.scalar() or 0

    # Count total referrals
    stmt = (
        select(func.count())
        .select_from(Referral)
        .where(Referral.referrer_id == user_id)
    )
    result = await session.execute(stmt)
    total_count = result.scalar() or 0

    # Update counts
    tier_obj.active_referrals = active_count
    tier_obj.total_referrals = total_count

    # Determine tier and benefits
    old_tier = tier_obj.tier

    if active_count >= 50:
        tier_obj.tier = ReferralTierLevel.PLATINUM.value
        tier_obj.monthly_bonus = 500
        tier_obj.discount_percent = 30
        tier_obj.revenue_share_percent = 15.0
    elif active_count >= 15:
        tier_obj.tier = ReferralTierLevel.GOLD.value
        tier_obj.monthly_bonus = 150
        tier_obj.discount_percent = 20
        tier_obj.revenue_share_percent = 10.0
    elif active_count >= 5:
        tier_obj.tier = ReferralTierLevel.SILVER.value
        tier_obj.monthly_bonus = 50
        tier_obj.discount_percent = 10
        tier_obj.revenue_share_percent = 0.0
    else:
        tier_obj.tier = ReferralTierLevel.BRONZE.value
        tier_obj.monthly_bonus = 0
        tier_obj.discount_percent = 0
        tier_obj.revenue_share_percent = 0.0

    tier_obj.updated_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(tier_obj)

    if old_tier != tier_obj.tier:
        logger.info(f"User {user_id} tier updated: {old_tier} → {tier_obj.tier}")

    return tier_obj


async def get_referral_stats(session: AsyncSession, user_id: int) -> dict:
    """
    Get referral statistics for user

    Args:
        session: Database session
        user_id: User ID

    Returns:
        Dict with referral stats
    """
    # Get tier
    stmt = select(ReferralTier).where(ReferralTier.user_id == user_id)
    result = await session.execute(stmt)
    tier = result.scalar_one_or_none()

    # Get referrals
    stmt = select(Referral).where(Referral.referrer_id == user_id)
    result = await session.execute(stmt)
    referrals = result.scalars().all()

    # Count active referrals
    active_count = sum(1 for ref in referrals if ref.status == ReferralStatus.ACTIVE.value)

    # Count premium conversions
    premium_conversions = 0
    for ref in referrals:
        stmt = (
            select(Subscription)
            .where(Subscription.user_id == ref.referee_id)
            .where(Subscription.tier.in_(['basic', 'premium', 'vip']))
        )
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            premium_conversions += 1

    # Get leaderboard rank
    rank = await get_leaderboard_rank(session, user_id)

    return {
        'total_referrals': len(referrals),
        'active_referrals': active_count,
        'tier': tier.tier if tier else ReferralTierLevel.BRONZE.value,
        'monthly_bonus': tier.monthly_bonus if tier else 0,
        'discount_percent': tier.discount_percent if tier else 0,
        'revenue_share_percent': tier.revenue_share_percent if tier else 0,
        'premium_conversions': premium_conversions,
        'conversion_rate': (premium_conversions / len(referrals) * 100) if referrals else 0,
        'leaderboard_rank': rank,
    }


async def get_referrer(session: AsyncSession, user_id: int) -> Optional[User]:
    """
    Get the user who referred this user

    Args:
        session: Database session
        user_id: User ID (referee)

    Returns:
        User model of referrer, or None if user wasn't referred
    """
    # Find referral where this user is the referee
    stmt = select(Referral).where(Referral.referee_id == user_id)
    result = await session.execute(stmt)
    referral = result.scalar_one_or_none()

    if not referral:
        return None

    # Get referrer user
    stmt = select(User).where(User.id == referral.referrer_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ===========================
# BONUS REQUEST OPERATIONS
# ===========================


async def add_bonus_requests(
    session: AsyncSession,
    user_id: int,
    amount: int,
    source: str,
    description: Optional[str] = None,
    expires_in_days: Optional[int] = None,
    expires_at: Optional[datetime] = None,
) -> BonusRequest:
    """
    Add bonus requests to user

    Args:
        session: Database session
        user_id: User ID
        amount: Number of bonus requests
        source: Bonus source (referral_signup, tier_monthly, etc.)
        description: Description
        expires_in_days: Days until expiration (None = never expires)
        expires_at: Explicit expiration datetime (overrides expires_in_days)

    Returns:
        Created BonusRequest model
    """
    # Determine expiration time
    if expires_at is not None:
        expiration = expires_at
    elif expires_in_days is not None:
        expiration = datetime.now(UTC) + timedelta(days=expires_in_days)
    else:
        expiration = None

    bonus = BonusRequest(
        user_id=user_id,
        amount=amount,
        source=source,
        description=description,
        expires_at=expiration,
    )
    session.add(bonus)
    await session.commit()
    await session.refresh(bonus)

    logger.info(f"Bonus granted: {amount} requests to user {user_id} (source: {source})")
    return bonus


async def get_active_bonuses(session: AsyncSession, user_id: int) -> int:
    """
    Get total active bonus requests for user

    Args:
        session: Database session
        user_id: User ID

    Returns:
        Total bonus requests (excluding expired)
    """
    stmt = (
        select(func.sum(BonusRequest.amount))
        .where(BonusRequest.user_id == user_id)
        .where(
            (BonusRequest.expires_at.is_(None))
            | (BonusRequest.expires_at > datetime.now(UTC))
        )
    )
    result = await session.execute(stmt)
    total = result.scalar() or 0
    return int(total)


async def expire_old_bonuses(session: AsyncSession) -> int:
    """
    Delete expired bonus requests

    Args:
        session: Database session

    Returns:
        Number of deleted bonuses
    """
    stmt = (
        delete(BonusRequest)
        .where(BonusRequest.expires_at.isnot(None))
        .where(BonusRequest.expires_at < datetime.now(UTC))
    )
    result = await session.execute(stmt)
    await session.commit()

    deleted = result.rowcount or 0
    if deleted > 0:
        logger.info(f"Expired {deleted} old bonus requests")

    return deleted


# ===========================
# REFERRAL BALANCE OPERATIONS
# ===========================


async def get_or_create_balance(
    session: AsyncSession,
    user_id: int,
) -> ReferralBalance:
    """
    Get or create referral balance for user

    Args:
        session: Database session
        user_id: User ID

    Returns:
        ReferralBalance model
    """
    stmt = select(ReferralBalance).where(ReferralBalance.user_id == user_id)
    result = await session.execute(stmt)
    balance = result.scalar_one_or_none()

    if not balance:
        balance = ReferralBalance(user_id=user_id)
        session.add(balance)
        await session.commit()
        await session.refresh(balance)
        logger.info(f"Created balance for user {user_id}")

    return balance


async def add_to_balance(
    session: AsyncSession,
    user_id: int,
    amount_usd: float,
    description: str,
) -> BalanceTransaction:
    """
    Add money to user's referral balance

    Args:
        session: Database session
        user_id: User ID
        amount_usd: Amount in USD
        description: Transaction description

    Returns:
        Created BalanceTransaction
    """
    # Get or create balance
    balance = await get_or_create_balance(session, user_id)

    # Update balance
    balance.balance_usd += amount_usd
    balance.earned_total_usd += amount_usd
    balance.updated_at = datetime.now(UTC)

    # Create transaction
    transaction = BalanceTransaction(
        balance_id=balance.id,
        type=BalanceTransactionType.EARN.value,
        amount_usd=amount_usd,
        description=description,
    )
    session.add(transaction)

    await session.commit()
    await session.refresh(transaction)

    logger.info(f"Added ${amount_usd:.2f} to balance of user {user_id}")
    return transaction


async def withdraw_balance(
    session: AsyncSession,
    user_id: int,
    amount_usd: Decimal,
    wallet_address: str,
) -> Optional[BalanceTransaction]:
    """
    Withdraw money from referral balance

    Args:
        session: Database session
        user_id: User ID
        amount_usd: Amount to withdraw in USD
        wallet_address: TON wallet address

    Returns:
        Created BalanceTransaction or None if insufficient balance
    """
    # Get balance
    balance = await get_or_create_balance(session, user_id)

    # Check minimum ($10)
    if amount_usd < Decimal('10'):
        logger.warning(f"Withdrawal amount ${amount_usd} < minimum $10")
        return None

    # Calculate with fee (5%)
    # amount_usd is what user wants to receive
    # fee is 5% of that amount
    # total_deducted is amount + fee (taken from balance)
    fee = amount_usd * Decimal('0.05')
    total_deducted = amount_usd + fee
    amount_to_send = amount_usd

    # Check balance (must have enough for amount + fee)
    if balance.balance_usd < total_deducted:
        logger.warning(f"Insufficient balance: ${balance.balance_usd} < ${total_deducted}")
        return None

    # Update balance
    balance.balance_usd -= total_deducted
    balance.withdrawn_total_usd += total_deducted
    balance.updated_at = datetime.now(UTC)

    # Create transaction
    transaction = BalanceTransaction(
        balance_id=balance.id,
        type=BalanceTransactionType.WITHDRAW.value,
        amount_usd=total_deducted,
        description=f"Вывод ${amount_to_send:.2f} (комиссия ${fee:.2f})",
        withdrawal_address=wallet_address,
        withdrawal_status="pending",
    )
    session.add(transaction)

    await session.commit()
    await session.refresh(transaction)

    logger.info(f"Withdrawal created: ${amount_usd} to {wallet_address} for user {user_id}")
    return transaction


async def spend_balance(
    session: AsyncSession,
    user_id: int,
    amount_usd: float,
    description: str,
) -> Optional[BalanceTransaction]:
    """
    Spend balance on subscription purchase

    Args:
        session: Database session
        user_id: User ID
        amount_usd: Amount to spend
        description: Description

    Returns:
        Created BalanceTransaction or None if insufficient balance
    """
    # Get balance
    balance = await get_or_create_balance(session, user_id)

    # Check balance
    if balance.balance_usd < amount_usd:
        logger.warning(f"Insufficient balance: ${balance.balance_usd} < ${amount_usd}")
        return None

    # Update balance
    balance.balance_usd -= amount_usd
    balance.spent_total_usd += amount_usd
    balance.updated_at = datetime.now(UTC)

    # Create transaction
    transaction = BalanceTransaction(
        balance_id=balance.id,
        type=BalanceTransactionType.SPEND.value,
        amount_usd=amount_usd,
        description=description,
    )
    session.add(transaction)

    await session.commit()
    await session.refresh(transaction)

    logger.info(f"Spent ${amount_usd} from balance of user {user_id}")
    return transaction


# ===========================
# REFERRAL ANALYTICS
# ===========================


async def get_leaderboard(
    session: AsyncSession,
    limit: int = 100,
) -> List[dict]:
    """
    Get top referrers leaderboard

    Args:
        session: Database session
        limit: Max number of results

    Returns:
        List of dicts with leaderboard data
    """
    stmt = (
        select(
            ReferralTier.user_id,
            User.username,
            User.first_name,
            ReferralTier.total_referrals,
            ReferralTier.active_referrals,
            ReferralTier.tier,
        )
        .join(User, ReferralTier.user_id == User.id)
        .where(ReferralTier.total_referrals > 0)
        .order_by(ReferralTier.active_referrals.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.all()

    leaderboard = []
    for rank, row in enumerate(rows, 1):
        leaderboard.append({
            'rank': rank,
            'user_id': row.user_id,
            'username': row.username,
            'first_name': row.first_name,
            'total_referrals': row.total_referrals,
            'active_referrals': row.active_referrals,
            'tier': row.tier,
        })

    return leaderboard


async def get_leaderboard_rank(
    session: AsyncSession,
    user_id: int,
) -> Optional[int]:
    """
    Get user's rank in leaderboard

    Args:
        session: Database session
        user_id: User ID

    Returns:
        Rank (1-indexed) or None if not ranked
    """
    # Get user's active referrals
    stmt = select(ReferralTier).where(ReferralTier.user_id == user_id)
    result = await session.execute(stmt)
    user_tier = result.scalar_one_or_none()

    if not user_tier or user_tier.active_referrals == 0:
        return None

    # Count users with more active referrals
    stmt = (
        select(func.count())
        .select_from(ReferralTier)
        .where(ReferralTier.active_referrals > user_tier.active_referrals)
    )
    result = await session.execute(stmt)
    count_above = result.scalar() or 0

    return count_above + 1


async def calculate_revenue_share(
    session: AsyncSession,
    user_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    """
    Calculate revenue share for referrer

    Args:
        session: Database session
        user_id: Referrer user ID
        start_date: Start date (default: 30 days ago)
        end_date: End date (default: now)

    Returns:
        Dict with revenue share data
    """
    if not start_date:
        start_date = datetime.now(UTC) - timedelta(days=30)
    if not end_date:
        end_date = datetime.now(UTC)

    # Get tier
    stmt = select(ReferralTier).where(ReferralTier.user_id == user_id)
    result = await session.execute(stmt)
    tier = result.scalar_one_or_none()

    if not tier or tier.revenue_share_percent == 0:
        return {
            'revenue_share_percent': 0,
            'total_revenue': 0,
            'revenue_share_amount': 0,
        }

    # Get active referrals
    stmt = (
        select(Referral.referee_id)
        .where(Referral.referrer_id == user_id)
        .where(Referral.status == ReferralStatus.ACTIVE.value)
    )
    result = await session.execute(stmt)
    referee_ids = [row[0] for row in result.all()]

    if not referee_ids:
        return {
            'revenue_share_percent': tier.revenue_share_percent,
            'total_revenue': 0,
            'revenue_share_amount': 0,
        }

    # Calculate total revenue from referrals
    stmt = (
        select(func.sum(Payment.amount))
        .where(Payment.user_id.in_(referee_ids))
        .where(Payment.status == PaymentStatus.COMPLETED.value)
        .where(Payment.completed_at >= start_date)
        .where(Payment.completed_at <= end_date)
    )
    result = await session.execute(stmt)
    total_revenue = result.scalar() or 0

    # Calculate share
    share_amount = total_revenue * (tier.revenue_share_percent / 100)

    return {
        'revenue_share_percent': tier.revenue_share_percent,
        'total_revenue': total_revenue,
        'revenue_share_amount': share_amount,
        'start_date': start_date,
        'end_date': end_date,
    }


async def get_referral_tier(session: AsyncSession, user_id: int) -> Optional[ReferralTier]:
    """
    Get referral tier for user

    Args:
        session: Database session
        user_id: User ID

    Returns:
        ReferralTier model or None
    """
    stmt = select(ReferralTier).where(ReferralTier.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_revenue_share(
    session: AsyncSession,
    referrer_id: int,
    referee_id: int,
    amount: float,
    payment_id: int,
) -> None:
    """
    Add revenue share to referrer's balance

    Args:
        session: Database session
        referrer_id: Referrer user ID
        referee_id: Referee user ID (who made payment)
        amount: Revenue share amount (USD)
        payment_id: Payment ID that generated this revenue share
    """
    # Get referrer to verify they exist
    stmt = select(User).where(User.id == referrer_id)
    result = await session.execute(stmt)
    referrer = result.scalar_one_or_none()

    if not referrer:
        logger.error(f"Referrer {referrer_id} not found when adding revenue share")
        return

    # Add to balance using existing function
    description = f"Revenue share from referral payment #{payment_id}"
    transaction = await add_to_balance(session, referrer_id, amount, description)

    logger.info(
        f"Revenue share added: referrer={referrer_id}, referee={referee_id}, "
        f"amount=${amount:.2f}, payment={payment_id}, "
        f"transaction_id={transaction.id}"
    )


async def get_referral_conversion_rate(session: AsyncSession) -> dict:
    """
    Get global referral conversion statistics

    Returns:
        Dict with conversion metrics
    """
    # Total referrals
    stmt = select(func.count()).select_from(Referral)
    result = await session.execute(stmt)
    total_referrals = result.scalar() or 0

    # Active referrals
    stmt = (
        select(func.count())
        .select_from(Referral)
        .where(Referral.status == ReferralStatus.ACTIVE.value)
    )
    result = await session.execute(stmt)
    active_referrals = result.scalar() or 0

    # Referrals who purchased premium
    stmt = (
        select(func.count(func.distinct(Subscription.user_id)))
        .select_from(Referral)
        .join(Subscription, Referral.referee_id == Subscription.user_id)
        .where(Subscription.tier.in_(['basic', 'premium', 'vip']))
    )
    result = await session.execute(stmt)
    premium_referrals = result.scalar() or 0

    # Calculate rates
    activation_rate = (active_referrals / total_referrals * 100) if total_referrals > 0 else 0
    conversion_rate = (premium_referrals / total_referrals * 100) if total_referrals > 0 else 0

    return {
        'total_referrals': total_referrals,
        'active_referrals': active_referrals,
        'premium_referrals': premium_referrals,
        'activation_rate_percent': activation_rate,
        'conversion_rate_percent': conversion_rate,
    }


# ===========================
# WATCHLIST OPERATIONS
# ===========================


async def get_user_watchlist(
    session: AsyncSession,
    user_id: int,
) -> List[Watchlist]:
    """
    Get user's watchlist

    Args:
        session: Database session
        user_id: User ID

    Returns:
        List of Watchlist models
    """
    stmt = (
        select(Watchlist)
        .where(Watchlist.user_id == user_id)
        .order_by(Watchlist.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def add_to_watchlist(
    session: AsyncSession,
    user_id: int,
    coin_id: str,
    symbol: str,
    name: str,
) -> Optional[Watchlist]:
    """
    Add coin to user's watchlist

    Args:
        session: Database session
        user_id: User ID
        coin_id: CoinGecko coin ID (e.g., 'bitcoin')
        symbol: Coin symbol (e.g., 'BTC')
        name: Coin name (e.g., 'Bitcoin')

    Returns:
        Created Watchlist model or None if already exists
    """
    from sqlalchemy.exc import IntegrityError

    try:
        watchlist_item = Watchlist(
            user_id=user_id,
            coin_id=coin_id,
            symbol=symbol,
            name=name,
        )
        session.add(watchlist_item)
        await session.commit()
        await session.refresh(watchlist_item)

        logger.info(f"Added {symbol} to watchlist for user {user_id}")
        return watchlist_item
    except IntegrityError:
        await session.rollback()
        logger.warning(f"Coin {coin_id} already in watchlist for user {user_id}")
        return None


async def remove_from_watchlist(
    session: AsyncSession,
    user_id: int,
    coin_id: str,
) -> bool:
    """
    Remove coin from user's watchlist

    Args:
        session: Database session
        user_id: User ID
        coin_id: CoinGecko coin ID

    Returns:
        True if removed, False if not found
    """
    stmt = (
        delete(Watchlist)
        .where(Watchlist.user_id == user_id)
        .where(Watchlist.coin_id == coin_id)
    )
    result = await session.execute(stmt)
    await session.commit()

    removed = result.rowcount > 0
    if removed:
        logger.info(f"Removed {coin_id} from watchlist for user {user_id}")
    else:
        logger.warning(f"Coin {coin_id} not found in watchlist for user {user_id}")

    return removed


async def is_in_watchlist(
    session: AsyncSession,
    user_id: int,
    coin_id: str,
) -> bool:
    """
    Check if coin is in user's watchlist

    Args:
        session: Database session
        user_id: User ID
        coin_id: CoinGecko coin ID

    Returns:
        True if in watchlist, False otherwise
    """
    stmt = (
        select(Watchlist)
        .where(Watchlist.user_id == user_id)
        .where(Watchlist.coin_id == coin_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None
