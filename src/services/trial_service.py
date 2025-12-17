"""
Trial Subscription Service - manages 7-day Premium trials and auto-downgrade

This service handles:
- Checking trial expiration
- Auto-downgrading expired trials to FREE tier
- Activating post-trial discount (-20% for 48 hours)
- Sending notifications (24h before end, on end, discount expiry)
"""

from datetime import datetime, timedelta, UTC
from typing import List, Tuple
from loguru import logger

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User, Subscription, SubscriptionTier


async def check_trial_expiration(session: AsyncSession) -> List[Tuple[User, Subscription]]:
    """
    Find all users with expired trials that need to be downgraded

    Returns:
        List of (User, Subscription) tuples with expired trials
    """
    now = datetime.now(UTC)

    stmt = (
        select(User, Subscription)
        .join(Subscription)
        .where(Subscription.is_trial == True)  # noqa: E712
        .where(Subscription.is_active == True)  # noqa: E712
        .where(Subscription.trial_end <= now)
    )

    result = await session.execute(stmt)
    return result.all()


async def check_trial_ending_24h(session: AsyncSession) -> List[Tuple[User, Subscription]]:
    """
    Find all users whose trial ends in 24 hours and haven't been notified

    Returns:
        List of (User, Subscription) tuples with trial ending in 24h
    """
    now = datetime.now(UTC)
    tomorrow = now + timedelta(hours=24)

    stmt = (
        select(User, Subscription)
        .join(Subscription)
        .where(Subscription.is_trial == True)  # noqa: E712
        .where(Subscription.is_active == True)  # noqa: E712
        .where(Subscription.trial_end <= tomorrow)
        .where(Subscription.trial_end > now)
        .where(Subscription.trial_notified_24h == False)  # noqa: E712
    )

    result = await session.execute(stmt)
    return result.all()


async def downgrade_expired_trial(
    session: AsyncSession, user: User, subscription: Subscription
) -> Subscription:
    """
    Downgrade expired trial to FREE tier and activate post-trial discount

    Args:
        session: Database session
        user: User model
        subscription: Subscription model (expired trial)

    Returns:
        Updated Subscription model
    """
    now = datetime.now(UTC)
    # Post-trial discount valid for 30 days (1 month) - gives user time to decide
    discount_expires = now + timedelta(days=30)

    # Downgrade to FREE
    subscription.tier = SubscriptionTier.FREE.value
    subscription.is_trial = False
    subscription.expires_at = None

    # Activate post-trial discount (-20% for 30 days, one-time use)
    subscription.has_post_trial_discount = True
    subscription.discount_expires_at = discount_expires

    await session.commit()
    await session.refresh(subscription)

    logger.info(
        f"Downgraded expired trial for user {user.telegram_id} (@{user.username}), "
        f"post-trial discount active until {discount_expires.isoformat()}"
    )

    return subscription


async def expire_post_trial_discount(session: AsyncSession) -> int:
    """
    Expire post-trial discounts that have passed 48 hour window

    Returns:
        Number of expired discounts
    """
    now = datetime.now(UTC)

    stmt = (
        select(Subscription)
        .where(Subscription.has_post_trial_discount == True)  # noqa: E712
        .where(Subscription.discount_expires_at <= now)
    )

    result = await session.execute(stmt)
    subscriptions = result.scalars().all()

    count = 0
    for subscription in subscriptions:
        subscription.has_post_trial_discount = False
        subscription.discount_expires_at = None
        count += 1

    await session.commit()

    logger.info(f"Expired {count} post-trial discounts")
    return count


async def mark_trial_notification_sent(
    session: AsyncSession, subscription: Subscription, notification_type: str
) -> None:
    """
    Mark trial notification as sent

    Args:
        session: Database session
        subscription: Subscription model
        notification_type: '24h' or 'end'
    """
    if notification_type == "24h":
        subscription.trial_notified_24h = True
    elif notification_type == "end":
        subscription.trial_notified_end = True

    await session.commit()
    logger.debug(
        f"Marked trial notification '{notification_type}' as sent "
        f"for subscription {subscription.id}"
    )


async def get_active_trial_stats(session: AsyncSession) -> dict:
    """
    Get statistics on active trials

    Returns:
        Dict with trial statistics
    """
    stmt = select(Subscription).where(
        Subscription.is_trial == True,  # noqa: E712
        Subscription.is_active == True,  # noqa: E712
    )

    result = await session.execute(stmt)
    trials = result.scalars().all()

    now = datetime.now(UTC)

    stats = {
        "total_active_trials": len(trials),
        "expiring_today": 0,
        "expiring_tomorrow": 0,
        "expiring_this_week": 0,
    }

    today_end = now.replace(hour=23, minute=59, second=59)
    tomorrow_end = today_end + timedelta(days=1)
    week_end = today_end + timedelta(days=7)

    for trial in trials:
        if trial.trial_end <= today_end:
            stats["expiring_today"] += 1
        elif trial.trial_end <= tomorrow_end:
            stats["expiring_tomorrow"] += 1
        elif trial.trial_end <= week_end:
            stats["expiring_this_week"] += 1

    return stats


async def process_trial_expirations(session: AsyncSession) -> dict:
    """
    Main cron job function - process all trial-related tasks

    This should be called by a cron job every hour or so.

    Returns:
        Dict with processing results
    """
    results = {
        "expired_trials": 0,
        "notifications_24h": 0,
        "expired_discounts": 0,
    }

    # 1. Find and downgrade expired trials
    expired_trials = await check_trial_expiration(session)
    for user, subscription in expired_trials:
        await downgrade_expired_trial(session, user, subscription)
        results["expired_trials"] += 1

    # 2. Find trials ending in 24h (notifications handled by separate service)
    trials_ending_24h = await check_trial_ending_24h(session)
    results["notifications_24h"] = len(trials_ending_24h)

    # 3. Expire post-trial discounts (48h window)
    results["expired_discounts"] = await expire_post_trial_discount(session)

    logger.info(
        f"Trial processing complete: {results['expired_trials']} trials expired, "
        f"{results['notifications_24h']} need 24h notification, "
        f"{results['expired_discounts']} discounts expired"
    )

    return results


# ============================================================================
# HELPER FUNCTIONS FOR TRIAL MANAGEMENT
# ============================================================================


def get_trial_days_remaining(subscription: Subscription) -> int:
    """
    Get number of days remaining in trial

    Args:
        subscription: Subscription model

    Returns:
        Days remaining (0 if expired)
    """
    if not subscription.is_trial or not subscription.trial_end:
        return 0

    now = datetime.now(UTC)
    remaining = subscription.trial_end - now

    return max(0, remaining.days)


def get_discount_hours_remaining(subscription: Subscription) -> int:
    """
    Get number of hours remaining for post-trial discount

    Args:
        subscription: Subscription model

    Returns:
        Hours remaining (0 if expired)
    """
    if not subscription.has_post_trial_discount or not subscription.discount_expires_at:
        return 0

    now = datetime.now(UTC)
    remaining = subscription.discount_expires_at - now

    return max(0, int(remaining.total_seconds() / 3600))


def is_trial_active(subscription: Subscription) -> bool:
    """
    Check if trial is currently active

    Args:
        subscription: Subscription model

    Returns:
        True if trial active, False otherwise
    """
    if not subscription.is_trial or not subscription.is_active:
        return False

    if not subscription.trial_end:
        return False

    now = datetime.now(UTC)
    return subscription.trial_end > now


def has_post_trial_discount(subscription: Subscription) -> bool:
    """
    Check if user has active post-trial discount

    Args:
        subscription: Subscription model

    Returns:
        True if discount active, False otherwise
    """
    if not subscription.has_post_trial_discount:
        return False

    if not subscription.discount_expires_at:
        return False

    now = datetime.now(UTC)
    return subscription.discount_expires_at > now
