"""
CRUD operations for Syntra Trade Consultant Bot

Async database operations using SQLAlchemy 2.0
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    User,
    ChatHistory,
    RequestLimit,
    CostTracking,
    AdminLog,
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
    stmt = select(User).where(User.telegram_id == telegram_id)
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
    await session.refresh(user)

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
        user.last_activity = datetime.utcnow()
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
    threshold = datetime.utcnow() - timedelta(days=days)
    stmt = select(User).where(User.last_activity < threshold)
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
    session: AsyncSession, user_id: int
) -> tuple[bool, int, int]:
    """
    Check if user has requests remaining

    Args:
        session: Database session
        user_id: User ID (database ID)

    Returns:
        Tuple of (has_requests_remaining, current_count, limit)
    """
    limit_record = await get_or_create_request_limit(session, user_id)
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
    period_start = datetime.utcnow() - timedelta(days=days)
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
    inactive_threshold = datetime.utcnow() - timedelta(days=7)
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
    stmt = select(User).offset(offset).limit(limit)

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
    start_date = datetime.utcnow() - timedelta(days=days)

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
