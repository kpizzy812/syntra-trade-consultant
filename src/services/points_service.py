# coding: utf-8
"""
$SYNTRA Points Service

Centralized service for managing points earning, spending, and balance operations.

Features:
- Atomic transactions with idempotency
- Level progression and multipliers
- Daily streak tracking
- Transaction history
"""

import json
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, List, Tuple
from decimal import Decimal

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.database.models import (
    User,
    PointsBalance,
    PointsTransaction,
    PointsLevel,
    PointsTransactionType,
    SubscriptionTier,
)
from config.points_config import (
    get_points_for_action,
    get_subscription_bonus,
    get_subscription_cost_in_points,
    get_streak_bonus,
    MAX_DAILY_POINTS_EARNING,
    MIN_EARNING_INTERVAL_SECONDS,
    POINTS_EXPIRATION_ENABLED,
    POINTS_EXPIRATION_DAYS,
)


class PointsService:
    """Service for managing $SYNTRA points"""

    @staticmethod
    async def get_or_create_balance(
        session: AsyncSession,
        user_id: int
    ) -> PointsBalance:
        """
        Get or create points balance for user

        Args:
            session: Database session
            user_id: User ID

        Returns:
            PointsBalance model
        """
        stmt = select(PointsBalance).where(PointsBalance.user_id == user_id)
        result = await session.execute(stmt)
        balance = result.scalar_one_or_none()

        if not balance:
            balance = PointsBalance(user_id=user_id)
            session.add(balance)
            await session.commit()
            await session.refresh(balance)
            logger.info(f"Created points balance for user {user_id}")

        return balance

    @staticmethod
    async def get_user_level_multiplier(
        session: AsyncSession,
        lifetime_earned: int
    ) -> Tuple[int, float]:
        """
        Get user level and multiplier based on lifetime earned points

        Args:
            session: Database session
            lifetime_earned: Total points earned

        Returns:
            Tuple of (level, multiplier)
        """
        stmt = (
            select(PointsLevel)
            .where(PointsLevel.points_required <= lifetime_earned)
            .order_by(PointsLevel.points_required.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        level_config = result.scalar_one_or_none()

        if level_config:
            return level_config.level, level_config.earning_multiplier

        return 1, 1.0  # Default level 1

    @staticmethod
    async def earn_points(
        session: AsyncSession,
        user_id: int,
        transaction_type: str,
        amount: Optional[int] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
        transaction_id: Optional[str] = None,
        expires_in_days: Optional[int] = None,
    ) -> Optional[PointsTransaction]:
        """
        Award points to user

        Args:
            session: Database session
            user_id: User ID
            transaction_type: Type of transaction (PointsTransactionType)
            amount: Points amount (if None, will be calculated from config)
            description: Human-readable description
            metadata: Additional metadata dict
            transaction_id: Unique transaction ID for idempotency
            expires_in_days: Days until points expire (optional)

        Returns:
            PointsTransaction if successful, None if failed/duplicate
        """
        try:
            # Check idempotency
            if transaction_id:
                stmt = select(PointsTransaction).where(
                    PointsTransaction.transaction_id == transaction_id
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                if existing:
                    logger.debug(f"Transaction {transaction_id} already exists, skipping")
                    return existing

            # Get user and balance
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if not user:
                logger.error(f"User {user_id} not found")
                return None

            balance = await PointsService.get_or_create_balance(session, user_id)

            # Calculate points amount if not provided
            if amount is None:
                subscription_tier = user.subscription.tier if user.subscription and user.subscription.is_active else SubscriptionTier.FREE
                amount = get_points_for_action(
                    transaction_type,
                    balance.earning_multiplier,
                    subscription_tier
                )

            if amount <= 0:
                logger.warning(f"Amount is 0 for transaction_type {transaction_type}, skipping")
                return None

            # Check rate limiting
            min_interval = MIN_EARNING_INTERVAL_SECONDS.get(transaction_type)
            if min_interval:
                stmt = (
                    select(PointsTransaction)
                    .where(
                        and_(
                            PointsTransaction.user_id == user_id,
                            PointsTransaction.transaction_type == transaction_type,
                            PointsTransaction.created_at >= datetime.now(UTC) - timedelta(seconds=min_interval)
                        )
                    )
                    .order_by(PointsTransaction.created_at.desc())
                    .limit(1)
                )
                result = await session.execute(stmt)
                recent = result.scalar_one_or_none()
                if recent:
                    logger.debug(f"Rate limit hit for {transaction_type}, user {user_id}")
                    return None

            # Check daily limit
            today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            stmt = select(func.sum(PointsTransaction.amount)).where(
                and_(
                    PointsTransaction.user_id == user_id,
                    PointsTransaction.created_at >= today_start,
                    PointsTransaction.amount > 0  # Only earning transactions
                )
            )
            result = await session.execute(stmt)
            today_earned = result.scalar() or 0

            if today_earned >= MAX_DAILY_POINTS_EARNING:
                logger.warning(f"User {user_id} reached daily points limit")
                return None

            # Cap amount to daily limit
            if today_earned + amount > MAX_DAILY_POINTS_EARNING:
                amount = MAX_DAILY_POINTS_EARNING - today_earned
                logger.info(f"Capped points amount to {amount} for user {user_id}")

            # Create transaction
            balance_before = balance.balance
            balance_after = balance_before + amount

            expires_at = None
            if POINTS_EXPIRATION_ENABLED and expires_in_days:
                expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)
            elif POINTS_EXPIRATION_ENABLED:
                expires_at = datetime.now(UTC) + timedelta(days=POINTS_EXPIRATION_DAYS)

            transaction = PointsTransaction(
                balance_id=balance.id,
                user_id=user_id,
                transaction_type=transaction_type,
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                description=description,
                metadata_json=json.dumps(metadata) if metadata else None,
                transaction_id=transaction_id,
                expires_at=expires_at,
            )
            session.add(transaction)

            # Update balance
            balance.balance = balance_after
            balance.lifetime_earned += amount

            # Update level
            new_level, new_multiplier = await PointsService.get_user_level_multiplier(
                session, balance.lifetime_earned
            )
            if new_level > balance.level:
                logger.info(f"User {user_id} leveled up: {balance.level} -> {new_level}")
                balance.level = new_level
            balance.earning_multiplier = new_multiplier

            await session.commit()
            await session.refresh(transaction)

            logger.info(
                f"Awarded {amount} points to user {user_id} "
                f"({transaction_type}, balance: {balance_after})"
            )

            return transaction

        except Exception as e:
            logger.error(f"Error awarding points to user {user_id}: {e}")
            await session.rollback()
            return None

    @staticmethod
    async def spend_points(
        session: AsyncSession,
        user_id: int,
        transaction_type: str,
        amount: int,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
        transaction_id: Optional[str] = None,
    ) -> Optional[PointsTransaction]:
        """
        Deduct points from user

        Args:
            session: Database session
            user_id: User ID
            transaction_type: Type of transaction (PointsTransactionType)
            amount: Points amount to deduct (positive number)
            description: Human-readable description
            metadata: Additional metadata dict
            transaction_id: Unique transaction ID for idempotency

        Returns:
            PointsTransaction if successful, None if failed/insufficient balance
        """
        try:
            # Check idempotency
            if transaction_id:
                stmt = select(PointsTransaction).where(
                    PointsTransaction.transaction_id == transaction_id
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                if existing:
                    logger.debug(f"Transaction {transaction_id} already exists, skipping")
                    return existing

            balance = await PointsService.get_or_create_balance(session, user_id)

            # Check sufficient balance
            if balance.balance < amount:
                logger.warning(
                    f"User {user_id} has insufficient balance: {balance.balance} < {amount}"
                )
                return None

            # Create transaction (amount is negative for spending)
            balance_before = balance.balance
            balance_after = balance_before - amount

            transaction = PointsTransaction(
                balance_id=balance.id,
                user_id=user_id,
                transaction_type=transaction_type,
                amount=-amount,  # Negative for spending
                balance_before=balance_before,
                balance_after=balance_after,
                description=description,
                metadata_json=json.dumps(metadata) if metadata else None,
                transaction_id=transaction_id,
            )
            session.add(transaction)

            # Update balance
            balance.balance = balance_after
            balance.lifetime_spent += amount

            await session.commit()
            await session.refresh(transaction)

            logger.info(
                f"Deducted {amount} points from user {user_id} "
                f"({transaction_type}, balance: {balance_after})"
            )

            return transaction

        except Exception as e:
            logger.error(f"Error spending points for user {user_id}: {e}")
            await session.rollback()
            return None

    @staticmethod
    async def process_daily_login(
        session: AsyncSession,
        user_id: int
    ) -> Optional[PointsTransaction]:
        """
        Process daily login and award streak bonuses

        Args:
            session: Database session
            user_id: User ID

        Returns:
            PointsTransaction if points awarded
        """
        balance = await PointsService.get_or_create_balance(session, user_id)

        now = datetime.now(UTC)
        last_login = balance.last_daily_login

        # Check if already logged in today
        if last_login and last_login.date() == now.date():
            logger.debug(f"User {user_id} already logged in today")
            return None

        # Calculate streak
        if last_login:
            days_diff = (now.date() - last_login.date()).days
            if days_diff == 1:
                # Continue streak
                balance.current_streak += 1
            else:
                # Streak broken
                balance.current_streak = 1
        else:
            # First login
            balance.current_streak = 1

        # Update longest streak
        if balance.current_streak > balance.longest_streak:
            balance.longest_streak = balance.current_streak

        # Calculate bonus
        streak_bonus = get_streak_bonus(balance.current_streak)

        # Update last login
        balance.last_daily_login = now
        await session.commit()

        # Award points
        return await PointsService.earn_points(
            session=session,
            user_id=user_id,
            transaction_type=PointsTransactionType.EARN_DAILY_LOGIN,
            amount=streak_bonus,
            description=f"Ежедневный вход (streak: {balance.current_streak} дней)",
            metadata={
                "streak": balance.current_streak,
                "longest_streak": balance.longest_streak,
            },
            transaction_id=f"daily_login:{user_id}:{now.date().isoformat()}",
        )

    @staticmethod
    async def get_balance(
        session: AsyncSession,
        user_id: int
    ) -> Dict:
        """
        Get user's points balance summary

        Args:
            session: Database session
            user_id: User ID

        Returns:
            Dict with balance info
        """
        balance = await PointsService.get_or_create_balance(session, user_id)

        # Get level info
        stmt = select(PointsLevel).where(PointsLevel.level == balance.level)
        result = await session.execute(stmt)
        level_config = result.scalar_one_or_none()

        # Get next level info
        stmt = select(PointsLevel).where(PointsLevel.level == balance.level + 1)
        result = await session.execute(stmt)
        next_level_config = result.scalar_one_or_none()

        return {
            "balance": balance.balance,
            "lifetime_earned": balance.lifetime_earned,
            "lifetime_spent": balance.lifetime_spent,
            "level": balance.level,
            "level_name_ru": level_config.name_ru if level_config else "Новичок",
            "level_name_en": level_config.name_en if level_config else "Beginner",
            "level_icon": level_config.icon if level_config else "🌱",
            "earning_multiplier": balance.earning_multiplier,
            "current_streak": balance.current_streak,
            "longest_streak": balance.longest_streak,
            "next_level": next_level_config.level if next_level_config else None,
            "next_level_points_required": next_level_config.points_required if next_level_config else None,
            "points_to_next_level": (next_level_config.points_required - balance.lifetime_earned) if next_level_config else 0,
        }

    @staticmethod
    async def get_transaction_history(
        session: AsyncSession,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """
        Get user's transaction history

        Args:
            session: Database session
            user_id: User ID
            limit: Number of transactions to return
            offset: Pagination offset

        Returns:
            List of transaction dicts
        """
        stmt = (
            select(PointsTransaction)
            .where(PointsTransaction.user_id == user_id)
            .order_by(PointsTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        transactions = result.scalars().all()

        return [
            {
                "id": tx.id,
                "type": tx.transaction_type,
                "amount": tx.amount,
                "balance_before": tx.balance_before,
                "balance_after": tx.balance_after,
                "description": tx.description,
                "metadata": json.loads(tx.metadata_json) if tx.metadata_json else None,
                "created_at": tx.created_at.isoformat(),
                "expires_at": tx.expires_at.isoformat() if tx.expires_at else None,
                "is_expired": tx.is_expired,
            }
            for tx in transactions
        ]
