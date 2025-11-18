"""
Database models for Syntra Trade Consultant Bot

SQLAlchemy 2.0 models with full type hints
"""

from datetime import datetime, date, UTC
from typing import Optional
from enum import Enum
from decimal import Decimal

from sqlalchemy import (
    String,
    BigInteger,
    Text,
    Integer,
    Float,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    UniqueConstraint,
    Numeric,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models"""

    pass


# ===========================
# ENUMS
# ===========================


class SubscriptionTier(str, Enum):
    """Subscription tier levels"""

    FREE = "free"  # 5 requests/day
    BASIC = "basic"  # 20 requests/day
    PREMIUM = "premium"  # 100 requests/day
    VIP = "vip"  # Unlimited


class PaymentStatus(str, Enum):
    """Payment transaction status"""

    PENDING = "pending"  # Payment initiated, awaiting confirmation
    COMPLETED = "completed"  # Payment successful
    FAILED = "failed"  # Payment failed
    REFUNDED = "refunded"  # Payment refunded
    CANCELLED = "cancelled"  # Payment cancelled by user


class PaymentProvider(str, Enum):
    """Payment providers"""

    TELEGRAM_STARS = "telegram_stars"  # Telegram Stars (native)
    TON_CONNECT = "ton_connect"  # TON Connect (USDT/TON)
    CRYPTO_BOT = "crypto_bot"  # CryptoBot (optional)


class ReferralStatus(str, Enum):
    """Referral status"""

    PENDING = "pending"  # Registered but not active yet
    ACTIVE = "active"  # Active referral (met conditions)
    CHURNED = "churned"  # Stopped using the bot


class BonusSource(str, Enum):
    """Bonus request source"""

    REFERRAL_SIGNUP = "referral_signup"  # Bonus for inviting a friend
    TIER_MONTHLY = "tier_monthly"  # Monthly bonus from tier
    CHALLENGE = "challenge"  # Reward from challenge
    ACHIEVEMENT = "achievement"  # Reward from achievement
    ADMIN_GRANT = "admin_grant"  # Manual grant by admin


class ReferralTierLevel(str, Enum):
    """Referral tier levels"""

    BRONZE = "bronze"  # 0-4 referrals
    SILVER = "silver"  # 5-14 referrals
    GOLD = "gold"  # 15-49 referrals
    PLATINUM = "platinum"  # 50+ referrals


class BalanceTransactionType(str, Enum):
    """Balance transaction types"""

    EARN = "earn"  # Revenue share earned
    WITHDRAW = "withdraw"  # Withdrawal to crypto
    SPEND = "spend"  # Spent on subscription
    REFUND = "refund"  # Refund of previous transaction


# ===========================
# MODELS
# ===========================


class User(Base):
    """
    User model - stores Telegram user information

    Tracks:
    - Basic user info (telegram_id, username)
    - Subscription status
    - Last activity timestamp
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False, comment="Telegram user ID"
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Telegram username (without @)"
    )
    first_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="User first name"
    )
    last_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="User last name"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="User registration timestamp",
    )
    is_subscribed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Is user subscribed to required channel",
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        comment="Last user activity timestamp",
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="Is user an admin"
    )
    language: Mapped[str] = mapped_column(
        String(10),
        default="ru",
        nullable=False,
        comment="User language preference (ru, en)",
    )

    # Referral fields
    referral_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=True,
        comment="Unique referral code for this user",
    )

    referred_by_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
        comment="ID of user who referred this user",
    )

    # Relationships
    chat_history = relationship(
        "ChatHistory", back_populates="user", cascade="all, delete-orphan"
    )
    request_limits = relationship(
        "RequestLimit", back_populates="user", cascade="all, delete-orphan"
    )
    cost_tracking = relationship(
        "CostTracking", back_populates="user", cascade="all, delete-orphan"
    )
    subscription = relationship(
        "Subscription",
        back_populates="user",
        uselist=False,  # One-to-one relationship
        cascade="all, delete-orphan",
    )
    payments = relationship(
        "Payment", back_populates="user", cascade="all, delete-orphan"
    )

    # Referral relationships
    referrals_made = relationship(
        "Referral",
        foreign_keys="Referral.referrer_id",
        back_populates="referrer",
        cascade="all, delete-orphan",
    )
    referrals_received = relationship(
        "Referral",
        foreign_keys="Referral.referee_id",
        back_populates="referee",
        cascade="all, delete-orphan",
    )
    referred_by = relationship(
        "User",
        remote_side="User.id",
        foreign_keys=[referred_by_id],
    )
    bonus_requests = relationship(
        "BonusRequest", back_populates="user", cascade="all, delete-orphan"
    )
    referral_tier = relationship(
        "ReferralTier",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    referral_balance = relationship(
        "ReferralBalance",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    watchlist = relationship(
        "Watchlist", back_populates="user", cascade="all, delete-orphan"
    )

    def get_request_limit(self) -> int:
        """
        Get user's daily request limit based on subscription tier

        Returns:
            int: Daily request limit
        """
        if not self.subscription or not self.subscription.is_active:
            return 5  # FREE tier default

        tier_limits = {
            SubscriptionTier.FREE: 5,
            SubscriptionTier.BASIC: 20,
            SubscriptionTier.PREMIUM: 100,
            SubscriptionTier.VIP: 999999,  # Unlimited (practical limit)
        }

        return tier_limits.get(self.subscription.tier, 5)

    def get_total_requests_limit(self, session) -> int:
        """
        Get user's total daily request limit including bonuses

        Includes:
        - Base tier limit
        - Bonus requests (non-expired)
        - Monthly bonus from referral tier

        Args:
            session: SQLAlchemy session for querying bonuses

        Returns:
            int: Total daily request limit
        """
        from sqlalchemy import func, or_

        # Base limit from subscription
        base_limit = self.get_request_limit()

        # Calculate total bonus requests (non-expired)
        bonus_total = (
            session.query(func.sum(BonusRequest.amount))
            .filter(BonusRequest.user_id == self.id)
            .filter(
                or_(
                    BonusRequest.expires_at.is_(None),
                    BonusRequest.expires_at > datetime.now(UTC),
                )
            )
            .scalar()
            or 0
        )

        # Add monthly bonus from referral tier
        if self.referral_tier:
            bonus_total += self.referral_tier.monthly_bonus

        return base_limit + int(bonus_total)

    @property
    def is_premium(self) -> bool:
        """
        Check if user has active premium subscription

        Returns:
            bool: True if user has active subscription, False otherwise
        """
        return bool(self.subscription and self.subscription.is_active)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class ChatHistory(Base):
    """
    Chat history model - stores conversation context

    Used for:
    - Maintaining conversation context for AI
    - Analytics and debugging
    - Token usage tracking
    """

    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="User ID (foreign key)",
    )
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Message role: user, assistant, system"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Message content"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
        comment="Message timestamp",
    )
    tokens_used: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Tokens used (for AI responses)"
    )
    model: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="AI model used (gpt-4o, gpt-4o-mini, etc.)"
    )

    # Relationship
    user = relationship("User", back_populates="chat_history")

    def __repr__(self) -> str:
        return f"<ChatHistory(id={self.id}, user_id={self.user_id}, role={self.role})>"


class RequestLimit(Base):
    """
    Request limits model - tracks daily request limits (5/day)

    Each user gets 5 free requests per day
    Counter resets at 00:00 UTC
    """

    __tablename__ = "request_limits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="User ID (foreign key)",
    )
    date: Mapped[date] = mapped_column(
        Date,
        default=date.today,
        nullable=False,
        index=True,
        comment="Date for this limit count",
    )
    count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="Number of requests made today"
    )
    limit: Mapped[int] = mapped_column(
        Integer, default=5, nullable=False, comment="Request limit (default 5)"
    )

    # Relationship
    user = relationship("User", back_populates="request_limits")

    # Unique constraint: one record per user per day
    __table_args__ = (UniqueConstraint("user_id", "date", name="uix_user_date"),)

    def __repr__(self) -> str:
        return f"<RequestLimit(user_id={self.user_id}, date={self.date}, count={self.count}/{self.limit})>"


class CostTracking(Base):
    """
    Cost tracking model - monitors API usage and costs

    Tracks:
    - Tokens used per service (OpenAI, Together)
    - Calculated costs
    - Per-user expenses
    """

    __tablename__ = "cost_tracking"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="User ID (foreign key)",
    )
    service: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Service name: openai, together, coingecko, etc.",
    )
    model: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Specific model used"
    )
    tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Tokens used (if applicable)"
    )
    cost: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Calculated cost in USD"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
        comment="Timestamp of the request",
    )
    request_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Type of request: chat, vision, price, etc."
    )

    # Relationship
    user = relationship("User", back_populates="cost_tracking")

    def __repr__(self) -> str:
        return f"<CostTracking(id={self.id}, service={self.service}, cost=${self.cost:.4f})>"


class AdminLog(Base):
    """
    Admin log model - tracks admin actions

    Used for:
    - Audit trail
    - Monitoring admin activities
    - Security
    """

    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True, comment="Admin telegram ID"
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Action performed (e.g., reset_limits, ban_user)",
    )
    target_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, index=True, comment="Target user ID (if applicable)"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
        comment="Action timestamp",
    )
    details: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Additional details (JSON or text)"
    )
    success: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="Was the action successful"
    )

    def __repr__(self) -> str:
        return (
            f"<AdminLog(id={self.id}, admin_id={self.admin_id}, action={self.action})>"
        )


# Create indexes for frequently queried columns
# These are created automatically via index=True in mapped_column, but we document them here:

# Users:
# - users.telegram_id (unique index)

# ChatHistory:
# - chat_history.user_id (index)
# - chat_history.timestamp (index)

# RequestLimit:
# - request_limits.user_id (index)
# - request_limits.date (index)
# - request_limits.user_id + date (unique constraint)

# CostTracking:
# - cost_tracking.user_id (index)
# - cost_tracking.service (index)
# - cost_tracking.timestamp (index)

# AdminLog:
# - admin_logs.admin_id (index)
# - admin_logs.action (index)
# - admin_logs.target_user_id (index)
# - admin_logs.timestamp (index)


class HistoricalPrice(Base):
    """
    Historical OHLCV price data model

    Stores historical candlestick data for technical analysis
    and long-term price comparisons
    """

    __tablename__ = "historical_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    coin_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="CoinGecko coin ID (bitcoin, ethereum, etc.)"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Candlestick timestamp"
    )
    timeframe: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Timeframe: 1h, 4h, 1d, 1w"
    )
    open: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Opening price"
    )
    high: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Highest price"
    )
    low: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Lowest price"
    )
    close: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Closing price"
    )
    volume: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Trading volume"
    )
    market_cap: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Market capitalization"
    )

    # Unique constraint: one record per coin per timestamp per timeframe
    __table_args__ = (
        UniqueConstraint("coin_id", "timestamp", "timeframe", name="uix_coin_timestamp_timeframe"),
    )

    def __repr__(self) -> str:
        return f"<HistoricalPrice(coin_id={self.coin_id}, timestamp={self.timestamp}, close={self.close})>"


class OnChainMetric(Base):
    """
    On-chain metrics model - stores blockchain metrics from CoinMetrics

    Tracks:
    - Network health (active addresses, transaction volume)
    - Market indicators (exchange flows, whale movements)
    - Profitability metrics (SOPR, NUPL)
    """

    __tablename__ = "onchain_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    coin_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Asset ID (btc, eth, sol, etc.)"
    )
    metric_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Metric name (active_addresses, txn_count, etc.)"
    )
    value: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Metric value"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Metric timestamp"
    )

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("coin_id", "metric_name", "timestamp", name="uix_coin_metric_timestamp"),
    )

    def __repr__(self) -> str:
        return f"<OnChainMetric(coin_id={self.coin_id}, metric={self.metric_name}, value={self.value})>"


class FundingRate(Base):
    """
    Funding rate model - stores perpetual futures funding rates

    Funding rates indicate market sentiment:
    - Positive rate: Longs pay shorts (bullish sentiment)
    - Negative rate: Shorts pay longs (bearish sentiment)
    """

    __tablename__ = "funding_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Trading symbol (BTCUSDT, ETHUSDT, etc.)"
    )
    exchange: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="binance",
        comment="Exchange name (binance, bybit, etc.)"
    )
    funding_rate: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Funding rate (e.g., 0.0001 = 0.01%)"
    )
    funding_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Funding interval timestamp"
    )
    mark_price: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Mark price at funding time"
    )

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("symbol", "exchange", "funding_time", name="uix_symbol_exchange_time"),
    )

    def __repr__(self) -> str:
        return f"<FundingRate(symbol={self.symbol}, rate={self.funding_rate}, time={self.funding_time})>"


class Subscription(Base):
    """
    User subscription model

    Tracks:
    - Current tier (FREE/BASIC/PREMIUM/VIP)
    - Subscription period (start/end dates)
    - Auto-renewal status
    - Trial status
    """

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,  # One subscription per user
        index=True,
        nullable=False,
        comment="User ID (foreign key)",
    )

    # Subscription tier
    tier: Mapped[str] = mapped_column(
        String(20),
        default=SubscriptionTier.FREE.value,
        nullable=False,
        index=True,
        comment="Subscription tier: free, basic, premium, vip",
    )

    # Subscription period
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="Subscription start date",
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Subscription expiration date (NULL for FREE)",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Is subscription currently active",
    )

    auto_renew: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Auto-renew subscription",
    )

    # Trial
    is_trial: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Is this a trial subscription",
    )

    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Trial end date",
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="subscription")
    payments = relationship(
        "Payment", back_populates="subscription", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, user_id={self.user_id}, tier={self.tier})>"


class Payment(Base):
    """
    Payment transactions model

    Tracks all payment transactions for subscriptions
    """

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Relations
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="User ID (foreign key)",
    )

    subscription_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
        comment="Subscription ID (foreign key) - nullable until payment is completed",
    )

    # Payment details
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Payment provider: telegram_stars, ton_connect, crypto_bot",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=PaymentStatus.PENDING.value,
        nullable=False,
        index=True,
        comment="Payment status: pending, completed, failed, refunded, cancelled",
    )

    amount: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Payment amount in USD"
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="USD",
        nullable=False,
        comment="Currency: USD, STARS, TON, USDT",
    )

    # Subscription details
    tier: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Purchased tier"
    )

    duration_months: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Subscription duration in months (1, 3, 12)"
    )

    # Provider-specific data
    provider_payment_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="External payment ID from provider",
    )

    provider_data: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Additional provider data (JSON)"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
        comment="Payment creation timestamp",
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Payment completion timestamp",
    )

    # Relationships
    user = relationship("User", back_populates="payments")
    subscription = relationship("Subscription", back_populates="payments")

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, user_id={self.user_id}, status={self.status}, amount=${self.amount})>"


# Additional indexes documentation:
# HistoricalPrice:
# - historical_prices.coin_id (index)
# - historical_prices.timestamp (index)

# OnChainMetric:
# - onchain_metrics.coin_id (index)
# - onchain_metrics.metric_name (index)
# - onchain_metrics.timestamp (index)

# FundingRate:
# - funding_rates.symbol (index)
# - funding_rates.funding_time (index)

# Subscription:
# - subscriptions.user_id (unique index)
# - subscriptions.tier (index)
# - subscriptions.expires_at (index)
# - subscriptions.is_active (index)

# Payment:
# - payments.user_id (index)
# - payments.subscription_id (index)
# - payments.provider (index)
# - payments.status (index)
# - payments.provider_payment_id (unique index)
# - payments.created_at (index)


class Referral(Base):
    """
    Referral model - tracks referrer-referee relationships

    Tracks:
    - Who referred whom
    - Referral status (pending/active/churned)
    - Rewards granted
    """

    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Relations
    referrer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="User ID who referred (foreign key)",
    )

    referee_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="User ID who was referred (foreign key)",
    )

    # Referral details
    referral_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Referral code used",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=ReferralStatus.PENDING.value,
        nullable=False,
        index=True,
        comment="Status: pending, active, churned",
    )

    # Rewards tracking
    trial_granted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Has trial been granted to referee",
    )

    bonus_granted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Has bonus been granted to referrer",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="Referral creation timestamp",
    )

    activated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When referral became active",
    )

    # Relationships
    referrer = relationship(
        "User",
        foreign_keys=[referrer_id],
        back_populates="referrals_made",
    )
    referee = relationship(
        "User",
        foreign_keys=[referee_id],
        back_populates="referrals_received",
    )

    # Unique constraint: one referral per referrer-referee pair
    __table_args__ = (UniqueConstraint("referrer_id", "referee_id", name="uq_referrer_referee"),)

    def __repr__(self) -> str:
        return f"<Referral(id={self.id}, referrer_id={self.referrer_id}, referee_id={self.referee_id}, status={self.status})>"


class BonusRequest(Base):
    """
    Bonus requests model - tracks bonus requests granted to users

    Sources:
    - Referral signup
    - Monthly tier bonus
    - Challenges/achievements
    - Admin grants
    """

    __tablename__ = "bonus_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="User ID (foreign key)",
    )

    amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of bonus requests",
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Source: referral_signup, tier_monthly, challenge, achievement, admin_grant",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Description of bonus",
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Expiration date (NULL = never expires)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="Bonus creation timestamp",
    )

    # Relationship
    user = relationship("User", back_populates="bonus_requests")

    def __repr__(self) -> str:
        return f"<BonusRequest(id={self.id}, user_id={self.user_id}, amount={self.amount}, source={self.source})>"


class ReferralTier(Base):
    """
    Referral tier model - tracks user's referral tier and benefits

    Tiers:
    - Bronze: 0-4 referrals
    - Silver: 5-14 referrals (monthly bonus, discount)
    - Gold: 15-49 referrals (better bonus, discount, revenue share)
    - Platinum: 50+ referrals (best bonus, discount, revenue share)
    """

    __tablename__ = "referral_tiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
        comment="User ID (foreign key)",
    )

    # Tier info
    tier: Mapped[str] = mapped_column(
        String(20),
        default=ReferralTierLevel.BRONZE.value,
        nullable=False,
        index=True,
        comment="Tier: bronze, silver, gold, platinum",
    )

    total_referrals: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total number of referrals (all time)",
    )

    active_referrals: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        index=True,
        comment="Number of active referrals",
    )

    # Benefits
    monthly_bonus: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Monthly bonus requests for this tier",
    )

    discount_percent: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Discount percentage on subscriptions",
    )

    revenue_share_percent: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Revenue share percentage (0-100)",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="Tier creation timestamp",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        comment="Tier last update timestamp",
    )

    # Relationship
    user = relationship("User", back_populates="referral_tier")

    def __repr__(self) -> str:
        return f"<ReferralTier(id={self.id}, user_id={self.user_id}, tier={self.tier}, active={self.active_referrals})>"


class ReferralBalance(Base):
    """
    Referral balance model - tracks user's revenue share balance

    Tracks:
    - Current balance (USD)
    - Lifetime earnings
    - Withdrawals and spending
    """

    __tablename__ = "referral_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
        comment="User ID (foreign key)",
    )

    # Balance tracking
    balance_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal('0.00'),
        nullable=False,
        comment="Current balance in USD",
    )

    earned_total_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal('0.00'),
        nullable=False,
        comment="Total earned (all time)",
    )

    withdrawn_total_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal('0.00'),
        nullable=False,
        comment="Total withdrawn (all time)",
    )

    spent_total_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal('0.00'),
        nullable=False,
        comment="Total spent on subscriptions (all time)",
    )

    # Payout tracking
    last_payout_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last revenue share payout timestamp",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="Balance creation timestamp",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        comment="Balance last update timestamp",
    )

    # Relationships
    user = relationship("User", back_populates="referral_balance")
    transactions = relationship(
        "BalanceTransaction",
        back_populates="balance",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ReferralBalance(id={self.id}, user_id={self.user_id}, balance=${self.balance_usd:.2f})>"


class BalanceTransaction(Base):
    """
    Balance transaction model - tracks all balance operations

    Types:
    - earn: Revenue share earned
    - withdraw: Withdrawal to crypto wallet
    - spend: Spent on subscription purchase
    - refund: Refund of previous transaction
    """

    __tablename__ = "balance_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    balance_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("referral_balances.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="Balance ID (foreign key)",
    )

    # Transaction details
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Type: earn, withdraw, spend, refund",
    )

    amount_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Transaction amount in USD",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Transaction description",
    )

    # Withdrawal-specific fields
    withdrawal_address: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="TON wallet address for withdrawals",
    )

    withdrawal_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Blockchain transaction hash",
    )

    withdrawal_status: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="Withdrawal status: pending, completed, failed",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="Transaction creation timestamp",
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Transaction completion timestamp",
    )

    # Relationship
    balance = relationship("ReferralBalance", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<BalanceTransaction(id={self.id}, type={self.type}, amount=${self.amount_usd:.2f}, status={self.withdrawal_status})>"


# Referral system indexes:
# Referral:
# - referrals.referrer_id (index)
# - referrals.referee_id (index)
# - referrals.status (index)
# - referrals.referral_code (index)
# - referrals (referrer_id, referee_id) unique constraint

# BonusRequest:
# - bonus_requests.user_id (index)
# - bonus_requests.source (index)
# - bonus_requests.expires_at (index)

# ReferralTier:
# - referral_tiers.user_id (unique index)
# - referral_tiers.tier (index)
# - referral_tiers.active_referrals (index)

# ReferralBalance:
# - referral_balances.user_id (unique index)

class Watchlist(Base):
    """
    Watchlist model - tracks user's favorite cryptocurrencies

    Allows users to save and quickly access their favorite coins
    """

    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="User ID (foreign key)",
    )

    # Coin details
    coin_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="CoinGecko coin ID (e.g., 'bitcoin', 'ethereum')",
    )

    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Coin symbol (e.g., 'BTC', 'ETH')",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Coin name (e.g., 'Bitcoin', 'Ethereum')",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="Added to watchlist timestamp",
    )

    # Relationship
    user = relationship("User", back_populates="watchlist")

    # Unique constraint: one coin per user
    __table_args__ = (UniqueConstraint("user_id", "coin_id", name="uq_user_coin"),)

    def __repr__(self) -> str:
        return f"<Watchlist(id={self.id}, user_id={self.user_id}, symbol={self.symbol})>"


# Watchlist indexes:
# - watchlists.user_id (index)
# - watchlists.coin_id (index)
# - watchlists (user_id, coin_id) unique constraint

# BalanceTransaction:
# - balance_transactions.balance_id (index)
# - balance_transactions.type (index)
# - balance_transactions.withdrawal_status (index)
