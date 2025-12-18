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
    Index,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB


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
    NOWPAYMENTS = "nowpayments"  # NOWPayments (300+ crypto + fiat)


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
    User model - multi-platform support

    Tracks:
    - Basic user info (telegram_id OR email)
    - Registration platform (telegram/web/ios/android)
    - Subscription status
    - Last activity timestamp

    Note: Either telegram_id OR email must be set (not both nullable)
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Platform-specific identifiers (at least one required)
    telegram_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, index=True, nullable=True, comment="Telegram user ID (nullable for web users)"
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, index=True, nullable=True, comment="Email for web registration"
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="Email verification status"
    )

    # Registration source tracking
    registration_platform: Mapped[str] = mapped_column(
        String(20), default="telegram", nullable=False, comment="Platform where user registered (telegram/web/ios/android)"
    )

    # User profile (shared across platforms)
    username: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Username (Telegram username or display name)"
    )
    first_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="User first name"
    )
    last_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="User last name"
    )
    photo_url: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, comment="User avatar URL (from Telegram or uploaded)"
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
    is_banned: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="Is user banned from using the bot"
    )
    custom_daily_limit: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Custom daily request limit set by admin (overrides tier limit)"
    )
    language: Mapped[str] = mapped_column(
        String(10),
        default="ru",
        nullable=False,
        comment="User language preference (ru, en)",
    )
    privacy_policy_shown: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Flag indicating if privacy policy was shown to user",
    )

    # Referral fields
    referral_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=True,
        comment="Unique referral code for this user",
    )
    pending_referral_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Temporary storage for referral code until subscription verified",
    )

    startapp_param: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Startapp parameter from deep link (e.g., web3moves, telegram_channel)",
    )

    referred_by_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
        comment="ID of user who referred this user",
    )

    # Relationships
    chats = relationship(
        "Chat", back_populates="user", cascade="all, delete-orphan"
    )
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
        Get user's daily request limit based on subscription tier or custom limit

        Priority:
        1. custom_daily_limit (if set by admin)
        2. Tier-based limit from config/limits.py

        Returns:
            int: Daily request limit
        """
        # Custom limit takes priority
        if self.custom_daily_limit is not None:
            return self.custom_daily_limit

        from config.limits import get_text_limit

        if not self.subscription or not self.subscription.is_active:
            return get_text_limit(SubscriptionTier.FREE)

        return get_text_limit(self.subscription.tier)

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


class Chat(Base):
    """
    Chat model - represents individual chat sessions (like ChatGPT conversations)

    Features:
    - Multiple chats per user
    - Auto-generated titles from first message
    - Timestamps for creation and last update
    """

    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="User ID (foreign key)",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="New Chat",
        comment="Chat title (auto-generated from first message)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="Chat creation timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        comment="Last message timestamp",
    )

    # Relationships
    user = relationship("User", back_populates="chats")
    messages = relationship(
        "ChatMessage",
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="ChatMessage.timestamp",
    )

    def __repr__(self) -> str:
        return f"<Chat(id={self.id}, user_id={self.user_id}, title='{self.title}')>"


class ChatMessage(Base):
    """
    Chat message model - stores individual messages within a chat

    Replaces old ChatHistory model with chat-aware structure
    """

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chats.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="Chat ID (foreign key)",
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
    chat = relationship("Chat", back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, chat_id={self.chat_id}, role={self.role})>"


class ChatHistory(Base):
    """
    DEPRECATED: Old chat history model - kept for backward compatibility

    Use ChatMessage instead for new code
    This will be removed in future migration
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
    Request limits model - tracks daily request limits with separate counters

    Tracks three types of requests separately:
    - Text requests (AI chat analysis)
    - Chart requests (technical chart generation)
    - Vision requests (screenshot/image analysis)

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

    # Separate counters for each request type
    text_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="Number of text requests made today"
    )
    chart_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="Number of chart requests made today"
    )
    vision_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="Number of vision requests made today"
    )

    # Legacy field for backward compatibility (deprecated, use text_count)
    count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="DEPRECATED: Total requests (use text_count)"
    )
    limit: Mapped[int] = mapped_column(
        Integer, default=5, nullable=False, comment="DEPRECATED: Request limit (use tier-based limits)"
    )

    # Relationship
    user = relationship("User", back_populates="request_limits")

    # Unique constraint: one record per user per day
    __table_args__ = (UniqueConstraint("user_id", "date", name="uix_user_date"),)

    def __repr__(self) -> str:
        return f"<RequestLimit(user_id={self.user_id}, date={self.date}, text={self.text_count}, chart={self.chart_count}, vision={self.vision_count})>"


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

    trial_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Trial start date",
    )

    trial_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Trial end date",
    )

    # Post-trial discount tracking
    has_post_trial_discount: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="User is eligible for post-trial discount (-20%)",
    )

    discount_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Post-trial discount expiration (48h after trial ends)",
    )

    trial_notified_24h: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="24h trial ending notification sent",
    )

    trial_notified_end: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Trial ended notification sent",
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


class TonScannerState(Base):
    """
    TON Scanner state model - tracks last processed transaction for each address

    Prevents re-processing of already scanned transactions by storing
    the logical time (lt) of the last successfully scanned transaction
    """

    __tablename__ = "ton_scanner_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Address being monitored
    address: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        comment="TON address being monitored",
    )

    # Last processed transaction
    last_lt: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="Logical time of last processed transaction",
    )

    last_tx_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Hash of last processed transaction (for reference)",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="State creation timestamp",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        comment="State last update timestamp",
    )

    def __repr__(self) -> str:
        return f"<TonScannerState(address={self.address[:16]}..., last_lt={self.last_lt})>"


# TonScannerState indexes:
# - ton_scanner_states.address (unique index)


class MagicLink(Base):
    """
    Magic Link tokens для email авторизации

    Временные токены для passwordless authentication через email.
    Используется для web-платформы (не Telegram).
    """

    __tablename__ = "magic_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Email и token
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Email address for magic link"
    )

    token: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique magic link token (URL-safe random)"
    )

    # User (nullable пока пользователь не зарегистрирован)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User ID if already registered"
    )

    # Status tracking
    is_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Has this token been used (single-use enforcement)"
    )

    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When token was used"
    )

    # Expiration (15 minutes by default)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Token expiration time (15 minutes from creation)"
    )

    # IP tracking (security audit)
    request_ip: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
        comment="IP address that requested magic link"
    )

    used_ip: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address that used magic link"
    )

    # Referral tracking
    referral_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Referral code from URL if user arrived via referral link"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="Token creation timestamp"
    )

    def __repr__(self) -> str:
        return f"<MagicLink(email={self.email}, used={self.is_used}, expires={self.expires_at})>"


# MagicLink indexes:
# - magic_links.email (index) - быстрый поиск по email
# - magic_links.token (unique index) - верификация токена
# - magic_links.user_id (index) - связь с пользователем
# - magic_links.expires_at (index) - cleanup expired tokens


class CryptoInvoice(Base):
    """
    CryptoBot (Crypto Pay API) инвойсы для оплаты подписки

    Workflow:
    1. Пользователь выбирает тариф и способ оплаты (CryptoBot)
    2. Создается инвойс через Crypto Pay API
    3. Сохраняется в БД со статусом 'active'
    4. Пользователь оплачивает через @CryptoBot
    5. Webhook обновляет статус на 'paid'
    6. Активируется подписка пользователю
    """

    __tablename__ = "crypto_invoices"

    # Основные поля
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="User ID (foreign key)",
    )

    # Данные инвойса от CryptoBot API
    invoice_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
        comment="Invoice ID from CryptoBot API",
    )
    hash: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="Invoice hash from CryptoBot",
    )

    # Суммы и валюта
    amount_usd: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Amount in USD"
    )
    asset: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Cryptocurrency (USDT, TON, BTC, ETH, etc.)"
    )
    amount_crypto: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Amount in cryptocurrency"
    )

    # Информация о подписке
    tier: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Subscription tier: basic, premium, vip"
    )
    duration_months: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Subscription duration in months"
    )

    # Статус и даты
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
        index=True,
        comment="Invoice status: active, paid, expired, cancelled",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
        comment="Invoice creation timestamp",
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Invoice expiration timestamp",
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Payment timestamp",
    )

    # URL для оплаты
    bot_invoice_url: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="URL to pay via @CryptoBot"
    )
    mini_app_invoice_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="URL for Mini App payment (API 1.4+)"
    )
    web_app_invoice_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="URL for Web payment (API 1.4+)"
    )

    # Данные оплаты (заполняются после payment)
    paid_asset: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="Asset used for payment (may differ)"
    )
    paid_amount: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Actual paid amount"
    )
    paid_usd_rate: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="USD exchange rate at payment time"
    )
    fee_amount: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="CryptoBot fee amount"
    )
    fee_asset: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="Fee asset"
    )
    paid_anonymously: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="Paid anonymously (API 1.4)"
    )

    # Дополнительные данные
    payload: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Custom payload data (JSON string)"
    )
    comment: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="User comment from payment"
    )

    # Флаг обработки
    processed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether subscription was activated",
    )

    def __repr__(self) -> str:
        return f"<CryptoInvoice(id={self.id}, invoice_id={self.invoice_id}, user_id={self.user_id}, amount_usd={self.amount_usd}, status={self.status})>"


# CryptoInvoice indexes:
# - crypto_invoices.user_id (index)
# - crypto_invoices.invoice_id (unique index)
# - crypto_invoices.status (index)
# - crypto_invoices.created_at (index)
# - crypto_invoices.expires_at (index)
# - crypto_invoices.processed (index)


# ===========================
# BROADCAST SYSTEM
# ===========================


class BroadcastStatus(str, Enum):
    """Broadcast status"""

    DRAFT = "draft"  # Черновик
    SCHEDULED = "scheduled"  # Запланирована
    SENDING = "sending"  # Отправляется
    COMPLETED = "completed"  # Завершена
    PAUSED = "paused"  # Приостановлена
    CANCELLED = "cancelled"  # Отменена


class BroadcastTargetAudience(str, Enum):
    """Target audience for broadcast"""

    ALL = "all"  # Все пользователи
    PREMIUM = "premium"  # Только Premium
    FREE = "free"  # Только бесплатные
    BASIC = "basic"  # Basic подписка
    VIP = "vip"  # VIP подписка
    TRIAL = "trial"  # На триале
    INACTIVE_7D = "inactive_7d"  # Неактивные 7 дней
    INACTIVE_30D = "inactive_30d"  # Неактивные 30 дней
    NEW_24H = "new_24h"  # Новые за 24 часа
    NEW_7D = "new_7d"  # Новые за 7 дней


class BroadcastTemplate(Base):
    """
    Broadcast template model - шаблоны для рассылки

    Поддерживает:
    - Текст с форматированием (entities)
    - Медиа (фото, видео, документы)
    - Inline кнопки (URL)
    - Периодическую отправку
    """

    __tablename__ = "broadcast_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Название шаблона (для админки)
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Template name for admin panel",
    )

    # Контент сообщения
    text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Message text content",
    )

    # Entities для форматирования (JSON)
    entities_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Message entities as JSON (bold, italic, links, etc.)",
    )

    # Медиа
    media_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Media type: photo, video, document, animation",
    )

    media_file_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Telegram file_id for media",
    )

    # Inline кнопки (JSON array)
    buttons_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Inline buttons as JSON [[{text, url}], [{text, url}]]",
    )

    # Целевая аудитория
    target_audience: Mapped[str] = mapped_column(
        String(30),
        default=BroadcastTargetAudience.ALL.value,
        nullable=False,
        index=True,
        comment="Target audience: all, premium, free, etc.",
    )

    # Периодичность (для автоматической рассылки)
    is_periodic: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Is this a periodic template",
    )

    period_hours: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Period in hours for periodic broadcasts",
    )

    next_send_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Next scheduled send time",
    )

    last_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last send timestamp",
    )

    # Статус
    status: Mapped[str] = mapped_column(
        String(20),
        default=BroadcastStatus.DRAFT.value,
        nullable=False,
        index=True,
        comment="Template status: draft, scheduled, paused, etc.",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Is template active (for periodic)",
    )

    # Статистика
    total_sent: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total messages sent",
    )

    total_delivered: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total messages delivered",
    )

    total_failed: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total messages failed",
    )

    # Метаданные
    created_by: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Admin telegram_id who created template",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="Template creation timestamp",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        comment="Template last update timestamp",
    )

    # Relationships
    logs = relationship(
        "BroadcastLog",
        back_populates="template",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<BroadcastTemplate(id={self.id}, name='{self.name}', status={self.status})>"


class BroadcastLog(Base):
    """
    Broadcast log model - логи отправки рассылок

    Tracks:
    - Каждая отправка шаблона
    - Статистика по каждой рассылке
    - Ошибки отправки
    """

    __tablename__ = "broadcast_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("broadcast_templates.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="Template ID (foreign key)",
    )

    # Статистика рассылки
    total_recipients: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total recipients count",
    )

    sent_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Successfully sent count",
    )

    failed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Failed send count",
    )

    blocked_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Blocked by user count",
    )

    # Статус
    status: Mapped[str] = mapped_column(
        String(20),
        default=BroadcastStatus.SENDING.value,
        nullable=False,
        index=True,
        comment="Broadcast status: sending, completed, cancelled",
    )

    # Ошибки (JSON array)
    errors_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Errors as JSON array [{user_id, error}]",
    )

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
        comment="Broadcast start timestamp",
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Broadcast completion timestamp",
    )

    # Relationship
    template = relationship("BroadcastTemplate", back_populates="logs")

    def __repr__(self) -> str:
        return f"<BroadcastLog(id={self.id}, template_id={self.template_id}, sent={self.sent_count}/{self.total_recipients})>"


# Broadcast indexes:
# - broadcast_templates.target_audience (index)
# - broadcast_templates.next_send_at (index)
# - broadcast_templates.status (index)
# - broadcast_templates.is_active (index)
# - broadcast_logs.template_id (index)
# - broadcast_logs.status (index)
# - broadcast_logs.started_at (index)


# ===========================
# FRAUD DETECTION & FINGERPRINTING
# ===========================


class LinkedAccountStatus(str, Enum):
    """Status of linked account detection"""

    DETECTED = "detected"  # Автоматически обнаружено
    CONFIRMED_ABUSE = "confirmed_abuse"  # Подтверждённый абьюз админом
    FALSE_POSITIVE = "false_positive"  # Ложное срабатывание
    IGNORED = "ignored"  # Игнорируется (легитимно)


class LinkedAccountType(str, Enum):
    """Type of link between accounts"""

    IP_MATCH = "ip_match"  # Совпадение IP адреса
    FINGERPRINT_MATCH = "fingerprint_match"  # Совпадение browser fingerprint
    DEVICE_MATCH = "device_match"  # Совпадение устройства (Telegram)
    SELF_REFERRAL = "self_referral"  # Самореферал
    MULTI_TRIAL = "multi_trial"  # Двойной trial


class DeviceFingerprint(Base):
    """
    Device fingerprint model - tracks device/browser info for fraud detection

    Collects:
    - IP address and geolocation
    - Browser fingerprint (via FingerprintJS or custom)
    - Device info (user agent, platform)
    - Telegram device info (for Mini App)
    """

    __tablename__ = "device_fingerprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="User ID (foreign key)",
    )

    # IP tracking
    ip_address: Mapped[str] = mapped_column(
        String(45),  # IPv6 max length
        nullable=False,
        index=True,
        comment="Client IP address",
    )

    ip_country: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Country from IP geolocation",
    )

    ip_city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="City from IP geolocation",
    )

    ip_asn: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="ASN/ISP info",
    )

    # Browser fingerprint (FingerprintJS or custom)
    visitor_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="FingerprintJS visitor ID (persistent)",
    )

    request_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="FingerprintJS request ID (single request)",
    )

    fingerprint_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="Custom fingerprint hash (canvas, webgl, fonts)",
    )

    # Device info
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Full user agent string",
    )

    platform: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unknown",
        index=True,
        comment="Platform: telegram, web, ios, android, miniapp",
    )

    device_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Device type: desktop, mobile, tablet",
    )

    browser_name: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Browser name: Chrome, Safari, Firefox",
    )

    os_name: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="OS name: Windows, macOS, iOS, Android",
    )

    # Telegram-specific
    telegram_device_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Telegram device model (from initData)",
    )

    telegram_platform: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Telegram platform (ios, android, tdesktop)",
    )

    telegram_version: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Telegram app version",
    )

    # Screen/display info (fingerprint components)
    screen_resolution: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Screen resolution (1920x1080)",
    )

    timezone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Browser timezone",
    )

    language: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Browser language",
    )

    # Event tracking
    event_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="login",
        comment="Event type: registration, login, payment, referral_use",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
        comment="Fingerprint creation timestamp",
    )

    # Relationships
    user = relationship("User", backref="device_fingerprints")

    def __repr__(self) -> str:
        return f"<DeviceFingerprint(user_id={self.user_id}, ip={self.ip_address}, platform={self.platform})>"


class LinkedAccount(Base):
    """
    Linked accounts model - tracks suspected multi-account abuse

    Detects:
    - Same IP address used by multiple accounts
    - Same browser fingerprint
    - Self-referral patterns
    - Multi-trial abuse (telegram + email)
    """

    __tablename__ = "linked_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Linked users (always user_id_a < user_id_b for uniqueness)
    user_id_a: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="First user ID (always smaller)",
    )

    user_id_b: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="Second user ID (always larger)",
    )

    # Link details
    link_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="Link type: ip_match, fingerprint_match, device_match, self_referral, multi_trial",
    )

    confidence_score: Mapped[float] = mapped_column(
        Float,
        default=0.5,
        nullable=False,
        comment="Confidence score 0.0-1.0 (higher = more likely abuse)",
    )

    # Evidence (JSON)
    shared_ips: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON array of shared IP addresses",
    )

    shared_fingerprints: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON array of shared fingerprint hashes",
    )

    shared_visitor_ids: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON array of shared FingerprintJS visitor IDs",
    )

    evidence_details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON with additional evidence details",
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=LinkedAccountStatus.DETECTED.value,
        nullable=False,
        index=True,
        comment="Status: detected, confirmed_abuse, false_positive, ignored",
    )

    # Actions taken
    trial_blocked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Trial was blocked due to this link",
    )

    referral_blocked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Referral bonus was blocked due to this link",
    )

    accounts_banned: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Accounts were banned due to this link",
    )

    # Admin review
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When admin reviewed this link",
    )

    reviewed_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Admin user ID who reviewed",
    )

    admin_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Admin notes about this link",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
        comment="Link detection timestamp",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        comment="Last update timestamp",
    )

    # Relationships
    user_a = relationship("User", foreign_keys=[user_id_a], backref="links_as_a")
    user_b = relationship("User", foreign_keys=[user_id_b], backref="links_as_b")

    # Unique constraint: one record per user pair per link type
    __table_args__ = (
        UniqueConstraint("user_id_a", "user_id_b", "link_type", name="uq_linked_accounts"),
    )

    def __repr__(self) -> str:
        return f"<LinkedAccount(users={self.user_id_a}-{self.user_id_b}, type={self.link_type}, status={self.status})>"


# Fraud detection indexes:
# - device_fingerprints.user_id (index)
# - device_fingerprints.ip_address (index)
# - device_fingerprints.visitor_id (index)
# - device_fingerprints.fingerprint_hash (index)
# - device_fingerprints.platform (index)
# - device_fingerprints.created_at (index)
# - linked_accounts.user_id_a (index)
# - linked_accounts.user_id_b (index)
# - linked_accounts.link_type (index)
# - linked_accounts.status (index)
# - linked_accounts.created_at (index)


# ===========================
# $SYNTRA POINTS SYSTEM
# ===========================


class PointsTransactionType(str, Enum):
    """Types of points transactions"""

    # Earning points
    EARN_TEXT_REQUEST = "earn_text_request"  # За текстовый запрос
    EARN_CHART_REQUEST = "earn_chart_request"  # За график/technical analysis
    EARN_VISION_REQUEST = "earn_vision_request"  # За vision/screenshot анализ
    EARN_SUBSCRIPTION = "earn_subscription"  # За покупку подписки
    EARN_REFERRAL_SIGNUP = "earn_referral_signup"  # За регистрацию реферала
    EARN_REFERRAL_PURCHASE = "earn_referral_purchase"  # За покупку реферала
    EARN_DAILY_LOGIN = "earn_daily_login"  # За ежедневный вход (streak)
    EARN_ACHIEVEMENT = "earn_achievement"  # За достижение
    EARN_ADMIN_GRANT = "earn_admin_grant"  # Админ начислил вручную

    # Spending points
    SPEND_SUBSCRIPTION = "spend_subscription"  # Потрачено на подписку
    SPEND_BONUS_REQUESTS = "spend_bonus_requests"  # Потрачено на доп. запросы
    SPEND_ADMIN_DEDUCT = "spend_admin_deduct"  # Админ списал вручную

    # System
    REFUND = "refund"  # Возврат поинтов
    EXPIRE = "expire"  # Истечение срока действия

    # Social Tasks
    EARN_SOCIAL_TASK = "earn_social_task"  # За выполнение социального задания
    SPEND_TASK_PENALTY = "spend_task_penalty"  # Штраф за отписку


# ===========================
# SOCIAL TASKS ENUMS
# ===========================


class TaskType(str, Enum):
    """Types of social tasks"""

    TELEGRAM_SUBSCRIBE_CHANNEL = "telegram_subscribe_channel"  # Подписка на канал
    TELEGRAM_SUBSCRIBE_CHAT = "telegram_subscribe_chat"  # Вступление в чат
    TWITTER_FOLLOW = "twitter_follow"  # Подписка на Twitter (ручная проверка)


class TaskStatus(str, Enum):
    """Status of a social task"""

    DRAFT = "draft"  # Черновик
    ACTIVE = "active"  # Активно
    PAUSED = "paused"  # Скрыто/приостановлено
    COMPLETED = "completed"  # Завершено (лимит выполнений)
    EXPIRED = "expired"  # Истекло


class TaskCompletionStatus(str, Enum):
    """Status of task completion by user"""

    PENDING = "pending"  # Ожидает проверки
    PENDING_REVIEW = "pending_review"  # Ждёт ручной проверки (Twitter)
    VERIFIED = "verified"  # Проверено
    COMPLETED = "completed"  # Награда начислена
    FAILED = "failed"  # Не выполнено
    REVOKED = "revoked"  # Отозвано (отписался)


class VerificationType(str, Enum):
    """Type of task verification"""

    AUTO_TELEGRAM = "auto_telegram"  # Автоматическая через Telegram API
    MANUAL_SCREENSHOT = "manual_screenshot"  # Ручная через скриншот


class PointsBalance(Base):
    """
    Points balance model - stores user's $SYNTRA points balance

    Features:
    - Current balance
    - Lifetime earned/spent tracking
    - Level/tier based on total earned
    - Multiplier for earning bonuses
    """

    __tablename__ = "points_balances"

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
    balance: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Current $SYNTRA points balance",
    )

    lifetime_earned: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total points earned (all time)",
    )

    lifetime_spent: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total points spent (all time)",
    )

    # Gamification - уровень пользователя
    level: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="User level (based on lifetime_earned)",
    )

    # Множитель для начисления поинтов (бонус от уровня/подписки)
    earning_multiplier: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
        comment="Points earning multiplier (1.0 = 100%, 1.5 = 150%)",
    )

    # Streak tracking для daily login бонуса
    current_streak: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Current daily login streak",
    )

    longest_streak: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Longest daily login streak (all time)",
    )

    last_daily_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last daily login timestamp",
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
    user = relationship("User", backref="points_balance")
    transactions = relationship(
        "PointsTransaction",
        back_populates="balance",
        cascade="all, delete-orphan",
        order_by="PointsTransaction.created_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<PointsBalance(user_id={self.user_id}, balance={self.balance}, level={self.level})>"


class PointsTransaction(Base):
    """
    Points transaction model - tracks all points operations

    Features:
    - Detailed transaction history
    - Idempotency via unique transaction_id
    - Metadata for context (request_id, payment_id, etc.)
    - Expiration tracking
    """

    __tablename__ = "points_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    balance_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("points_balances.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="Points balance ID (foreign key)",
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="User ID (denormalized for fast queries)",
    )

    # Transaction details
    transaction_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Transaction type (earn_*/spend_*/refund/expire)",
    )

    amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Points amount (positive for earn, negative for spend)",
    )

    # Balance snapshots для аудита
    balance_before: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Balance before transaction",
    )

    balance_after: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Balance after transaction",
    )

    # Description and metadata
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable transaction description",
    )

    metadata_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional metadata (JSON): request_id, payment_id, referral_id, etc.",
    )

    # Idempotency - уникальный ID транзакции для предотвращения дублей
    transaction_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
        comment="Unique transaction ID for idempotency (type:entity_id)",
    )

    # Expiration для временных поинтов
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Expiration timestamp (NULL = never expires)",
    )

    is_expired: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Is transaction expired (auto-processed)",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
        comment="Transaction timestamp",
    )

    # Relationships
    balance = relationship("PointsBalance", back_populates="transactions")
    user = relationship("User", backref="points_transactions")

    def __repr__(self) -> str:
        return f"<PointsTransaction(id={self.id}, user_id={self.user_id}, type={self.transaction_type}, amount={self.amount})>"


class PointsLevel(Base):
    """
    Points level configuration - defines level thresholds and benefits

    This is a configuration table that defines:
    - Level requirements (points needed)
    - Level benefits (multipliers, badges, etc.)
    - Level names and icons
    """

    __tablename__ = "points_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Level info
    level: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        nullable=False,
        index=True,
        comment="Level number (1, 2, 3, ...)",
    )

    name_ru: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Level name in Russian",
    )

    name_en: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Level name in English",
    )

    icon: Mapped[str] = mapped_column(
        String(10),
        default="⭐",
        nullable=False,
        comment="Level icon (emoji)",
    )

    # Requirements
    points_required: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Minimum lifetime_earned points to reach this level",
    )

    # Benefits
    earning_multiplier: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
        comment="Points earning multiplier for this level",
    )

    description_ru: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Level description in Russian",
    )

    description_en: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Level description in English",
    )

    def __repr__(self) -> str:
        return f"<PointsLevel(level={self.level}, name={self.name_en}, required={self.points_required})>"


# Points system indexes:
# - points_balances.user_id (unique index)
# - points_transactions.balance_id (index)
# - points_transactions.user_id (index)
# - points_transactions.transaction_type (index)
# - points_transactions.transaction_id (unique index)
# - points_transactions.expires_at (index)
# - points_transactions.is_expired (index)
# - points_transactions.created_at (index)
# - points_levels.level (unique index)


# ===========================
# SOCIAL TASKS SYSTEM
# ===========================


class SocialTask(Base):
    """
    Social task model - represents tasks users can complete for rewards

    Features:
    - Telegram channel/chat subscriptions (auto-verified)
    - Twitter follows (manual screenshot verification)
    - Configurable rewards and penalties
    - Admin management
    """

    __tablename__ = "social_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Task info (localized)
    title_ru: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Task title in Russian",
    )
    title_en: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Task title in English",
    )
    description_ru: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Task description in Russian",
    )
    description_en: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Task description in English",
    )
    icon: Mapped[str] = mapped_column(
        String(10),
        default="📢",
        nullable=False,
        comment="Emoji icon for task",
    )

    # Task type and target
    task_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of task (TaskType enum)",
    )

    # Telegram specific
    telegram_channel_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Telegram channel/chat ID (@username or -100xxx)",
    )
    telegram_channel_url: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Telegram channel/chat URL for redirect",
    )

    # Twitter specific
    twitter_target_username: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Twitter username to follow (without @)",
    )

    # Verification settings
    verification_type: Mapped[str] = mapped_column(
        String(30),
        default=VerificationType.AUTO_TELEGRAM.value,
        nullable=False,
        comment="How to verify completion (VerificationType enum)",
    )

    # Rewards and penalties
    reward_points: Mapped[int] = mapped_column(
        Integer,
        default=100,
        nullable=False,
        comment="Points awarded for completion",
    )
    unsubscribe_penalty: Mapped[int] = mapped_column(
        Integer,
        default=50,
        nullable=False,
        comment="Penalty points if user unsubscribes",
    )

    # Limits
    max_completions: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum total completions allowed (null = unlimited)",
    )
    current_completions: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Current number of completions",
    )

    # Repeatable task settings
    is_repeatable: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Can user complete this task multiple times",
    )
    repeat_interval_hours: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Hours between repeated completions",
    )

    # Requirements
    requires_premium: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Requires premium subscription",
    )
    min_level: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Minimum user level required",
    )

    # Display
    priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        index=True,
        comment="Display priority (higher = shown first)",
    )

    # Status and timing
    status: Mapped[str] = mapped_column(
        String(20),
        default=TaskStatus.DRAFT.value,
        nullable=False,
        index=True,
        comment="Task status (TaskStatus enum)",
    )
    starts_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When task becomes available",
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When task expires",
    )

    # Audit
    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Admin telegram_id who created task",
    )
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
    completions: Mapped[list["TaskCompletion"]] = relationship(
        "TaskCompletion",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<SocialTask(id={self.id}, type={self.task_type}, status={self.status})>"

    def get_title(self, language: str = "en") -> str:
        """Get localized title"""
        return self.title_ru if language == "ru" else self.title_en

    def get_description(self, language: str = "en") -> Optional[str]:
        """Get localized description"""
        return self.description_ru if language == "ru" else self.description_en


class TaskCompletion(Base):
    """
    Task completion model - tracks user task completions

    Features:
    - Completion status tracking
    - Points award tracking
    - Screenshot storage for manual verification
    - Revocation support with penalties
    - Periodic recheck support
    """

    __tablename__ = "task_completions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Relations
    task_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("social_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Task ID",
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID",
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=TaskCompletionStatus.PENDING.value,
        nullable=False,
        index=True,
        comment="Completion status (TaskCompletionStatus enum)",
    )

    # Points tracking
    points_awarded: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Points awarded for this completion",
    )
    points_transaction_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("points_transactions.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to points transaction",
    )

    # Verification
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When verification was completed",
    )
    verification_data: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON data from verification (chat_member info, etc.)",
    )

    # For repeatable tasks
    completion_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Which completion number this is (for repeatable tasks)",
    )

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When user started the task",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When task was completed",
    )

    # Screenshot for manual verification (Twitter)
    screenshot_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to uploaded screenshot",
    )

    # Admin review (for manual verification)
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Admin telegram_id who reviewed",
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When admin reviewed",
    )
    review_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Admin notes on review",
    )

    # Revocation tracking
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When reward was revoked (user unsubscribed)",
    )
    penalty_applied: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Penalty points applied on revocation",
    )
    penalty_transaction_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("points_transactions.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to penalty transaction",
    )

    # Recheck tracking
    last_recheck_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last subscription recheck time",
    )

    # Relationships
    task: Mapped["SocialTask"] = relationship(
        "SocialTask",
        back_populates="completions",
    )
    user: Mapped["User"] = relationship(
        "User",
        backref="task_completions",
    )

    # Unique constraint: one completion per user per task (for non-repeatable)
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "user_id",
            "completion_count",
            name="uq_task_user_completion",
        ),
    )

    def __repr__(self) -> str:
        return f"<TaskCompletion(id={self.id}, task_id={self.task_id}, user_id={self.user_id}, status={self.status})>"


# Social tasks indexes:
# - social_tasks.task_type (index)
# - social_tasks.status (index)
# - social_tasks.priority (index)
# - task_completions.task_id (index)
# - task_completions.user_id (index)
# - task_completions.status (index)
# - task_completions (task_id, user_id, completion_count) unique


# ===========================
# SYNTRA SUPERVISOR MODELS
# ===========================


class SupervisorUrgency(str, Enum):
    """Urgency level for recommendations"""
    LOW = "low"
    MED = "med"
    HIGH = "high"
    CRITICAL = "critical"


class SupervisorRiskState(str, Enum):
    """Risk state of position"""
    SAFE = "safe"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecommendationType(str, Enum):
    """Types of supervisor recommendations"""
    HOLD = "hold"
    MOVE_SL = "move_sl"
    SET_BREAK_EVEN = "set_break_even"
    TAKE_PARTIAL = "take_partial"
    ADJUST_TP = "adjust_tp"
    CLOSE_POSITION = "close_position"
    REDUCE_POSITION = "reduce_position"


class RecommendationStatus(str, Enum):
    """Status of recommendation"""
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"


class SupervisorEvent(str, Enum):
    """Events that trigger LLM analysis"""
    # Critical events (always trigger LLM)
    INVALIDATION_HIT = "invalidation_hit"           # Price breached invalidation
    INVALIDATION_THREAT = "invalidation_threat"     # Price approaching invalidation (<2%)
    LIQ_CRITICAL = "liq_critical"                   # Liquidation proximity <8%
    LIQ_WARNING = "liq_warning"                     # Liquidation proximity <15%

    # High priority events
    TP1_HIT = "tp1_hit"                             # First TP zone reached
    TP2_HIT = "tp2_hit"                             # Second TP zone reached
    TP_NEAR = "tp_near"                             # Approaching TP zone (<1%)
    TIME_EXPIRED = "time_expired"                   # Scenario time validity expired
    TIME_WARNING = "time_warning"                   # <30 min left

    # Medium priority events
    PROFIT_MILESTONE = "profit_milestone"           # Crossed profit threshold (1%, 2%, 5%)
    STRUCTURE_BREAK = "structure_break"             # Market structure changed
    MOMENTUM_FADE = "momentum_fade"                 # Momentum weakening in profit
    VOLATILITY_SPIKE = "volatility_spike"          # Unusual volatility

    # Low priority / info
    POSITION_UPDATE = "position_update"             # Regular position sync
    HOLD_CHECK = "hold_check"                       # Periodic hold confirmation


class ScenarioSnapshot(Base):
    """
    Snapshot of trading scenario at position open time.

    Stores the original analysis to compare with current market state.
    """
    __tablename__ = "scenario_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Trade identification
    trade_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique trade ID from trading bot"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
        nullable=False,
        comment="User telegram_id"
    )

    # Symbol & timeframe
    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Trading pair (e.g., BTCUSDT)"
    )
    timeframe: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Timeframe (1h, 4h, 1d)"
    )
    side: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Position side (Long/Short)"
    )

    # Scenario bias
    bias: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Market bias (bull/bear/range)"
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Scenario confidence 0-1"
    )

    # Entry zone
    entry_zone_low: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Entry zone low price"
    )
    entry_zone_high: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Entry zone high price"
    )

    # Critical levels
    stop_loss: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Stop loss price"
    )
    invalidation_price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Price that invalidates scenario (KEY!)"
    )

    # Take profits (JSON array)
    take_profits_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="JSON array of TP levels [{price, pct, rr}, ...]"
    )

    # Conditions (JSON array)
    conditions_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON array of validity conditions"
    )

    # 🆕 Trading mode
    mode_id: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        default="standard",
        comment="Trading mode: conservative, standard, high_risk, meme"
    )
    mode_family: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        default="balanced",
        comment="Mode family: cautious, balanced, speculative"
    )

    # Validity
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Scenario valid until this time"
    )

    # Source
    source: Mapped[str] = mapped_column(
        String(20),
        default="syntra",
        nullable=False,
        comment="Scenario source (syntra/manual)"
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Is this scenario still being supervised"
    )
    deactivated_reason: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Reason for deactivation"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False
    )
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    def __repr__(self) -> str:
        return f"<ScenarioSnapshot(trade_id={self.trade_id}, symbol={self.symbol}, side={self.side})>"


class SupervisorAdvice(Base):
    """
    Advice pack generated by supervisor.

    Contains market summary, risk state, and list of recommendations.
    """
    __tablename__ = "supervisor_advices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Reference to scenario
    scenario_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("scenario_snapshots.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    trade_id: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
        nullable=False
    )

    # Market summary
    market_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="1-2 line market summary"
    )

    # State assessment
    scenario_valid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="Is scenario still valid"
    )
    time_valid_left_min: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Minutes left until scenario expires"
    )
    risk_state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Risk state (safe/medium/high/critical)"
    )

    # Price at creation
    price_at_creation: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Mark price when advice was created"
    )

    # Recommendations (JSON array)
    recommendations_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="JSON array of recommendations"
    )

    # Cooldown
    cooldown_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Don't create new advice until this time"
    )

    # Telegram message tracking
    telegram_message_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Telegram message ID for updating"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When this advice expires"
    )

    # Relationship
    scenario: Mapped["ScenarioSnapshot"] = relationship(
        "ScenarioSnapshot",
        backref="advices"
    )

    def __repr__(self) -> str:
        return f"<SupervisorAdvice(id={self.id}, trade_id={self.trade_id}, risk={self.risk_state})>"


class SupervisorAction(Base):
    """
    Log of actions taken on recommendations.

    Tracks what was applied, rejected, or expired.
    """
    __tablename__ = "supervisor_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Reference
    advice_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("supervisor_advices.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    trade_id: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
        nullable=False
    )

    # Action details
    action_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Unique action ID within advice"
    )
    action_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="Type of action (move_sl, take_partial, etc.)"
    )
    params_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="JSON params of the action"
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="pending/applied/rejected/expired"
    )

    # Execution result
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    execution_result: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON result from execution (order_id, error, etc.)"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False
    )

    # Relationship
    advice: Mapped["SupervisorAdvice"] = relationship(
        "SupervisorAdvice",
        backref="actions"
    )

    def __repr__(self) -> str:
        return f"<SupervisorAction(id={self.id}, type={self.action_type}, status={self.status})>"


# Supervisor indexes:
# - scenario_snapshots.trade_id (unique, index)
# - scenario_snapshots.user_id (index)
# - scenario_snapshots.is_active (for filtering active scenarios)
# - supervisor_advices.trade_id (index)
# - supervisor_advices.user_id (index)
# - supervisor_actions.trade_id (index)


# ===========================
# FEEDBACK LOOP & LEARNING MODELS
# ===========================


class TradeOutcomeLabel(str, Enum):
    """Результат сделки"""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    TIMEOUT = "timeout"


class ExitReasonType(str, Enum):
    """Причина закрытия"""
    TP1 = "tp1"
    TP2 = "tp2"
    TP3 = "tp3"
    SL = "sl"
    MANUAL = "manual"
    TIMEOUT = "timeout"
    CANCEL = "cancel"
    LIQUIDATION = "liquidation"
    BREAKEVEN = "breakeven"


class TradeOutcome(Base):
    """
    Trade Outcome - результаты закрытых сделок для learning системы.

    Хранит полную телеметрию:
    - Execution Report (JSONB)
    - Outcome metrics (PnL, MAE/MFE)
    - Attribution (архетип, факторы)

    Использует 4 ключа склейки с Futures Bot.
    """
    __tablename__ = "trade_outcomes"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # === 4 КЛЮЧА СКЛЕЙКИ ===
    trade_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="UUID от бота (unique)"
    )
    analysis_id: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
        comment="UUID от Syntra /futures-scenarios"
    )
    scenario_local_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="1..N в рамках analysis"
    )
    scenario_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="sha256 от scenario snapshot"
    )

    # === IDEMPOTENCY ===
    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        comment="{trade_id}:{event_type}"
    )

    # === CONTEXT ===
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
        nullable=False
    )
    symbol: Mapped[str] = mapped_column(
        String(20),
        index=True,
        nullable=False
    )
    side: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Long | Short"
    )
    timeframe: Mapped[str] = mapped_column(
        String(10),
        index=True,
        nullable=False
    )
    is_testnet: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
        nullable=False,
        comment="Фильтр для learning"
    )

    # === EXIT ===
    exit_reason: Mapped[str] = mapped_column(
        String(20),
        index=True,
        nullable=True,
        comment="tp1, tp2, sl, manual, etc."
    )
    exit_price: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    exit_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # === PNL ===
    pnl_usd: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    pnl_r: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="PnL / risk"
    )
    roe_pct: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="PnL / margin * 100"
    )

    # === MAE/MFE ===
    mae_r: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Max Adverse Excursion in R"
    )
    mfe_r: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Max Favorable Excursion in R"
    )
    capture_efficiency: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="pnl / mfe"
    )

    # === TIME METRICS ===
    time_in_trade_min: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    time_to_mfe_min: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Минут до макс profit"
    )
    time_to_mae_min: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Минут до макс drawdown"
    )
    post_sl_mfe_r: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="MFE после SL (если SL был неправильным)"
    )

    # === CONFIDENCE ===
    confidence_raw: Mapped[Optional[float]] = mapped_column(
        Float,
        index=True,
        nullable=True,
        comment="Оригинальный AI confidence"
    )
    confidence_calibrated: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Калиброванный confidence"
    )

    # === ARCHETYPE ===
    primary_archetype: Mapped[Optional[str]] = mapped_column(
        String(50),
        index=True,
        nullable=True
    )
    tags: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        comment='["tag1", "tag2"]'
    )
    label: Mapped[Optional[str]] = mapped_column(
        String(20),
        index=True,
        nullable=True,
        comment="win, loss, breakeven"
    )

    # === TERMINAL OUTCOME (для EV) ===
    terminal_outcome: Mapped[Optional[str]] = mapped_column(
        String(10),
        index=True,
        nullable=True,
        comment="sl/tp1/tp2/tp3/other — max TP hit"
    )
    max_tp_reached: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="0, 1, 2, или 3"
    )

    # === JSONB DATA ===
    execution_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Execution Report (слой B)"
    )
    attribution_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Attribution (слой D)"
    )
    scenario_snapshot: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Полный snapshot сценария"
    )

    # === TIMESTAMPS ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False
    )

    # === INDEXES ===
    __table_args__ = (
        Index('ix_outcomes_user_created', 'user_id', 'created_at'),
        Index('ix_outcomes_symbol_tf', 'symbol', 'timeframe', 'created_at'),
        Index('ix_outcomes_archetype_created', 'primary_archetype', 'created_at'),
    )

    def __repr__(self) -> str:
        return f"<TradeOutcome(id={self.id}, trade_id={self.trade_id}, label={self.label})>"


class ConfidenceBucket(Base):
    """
    Confidence Bucket - агрегированная статистика по корзинам confidence.

    Используется для калибровки AI confidence на основе реальных результатов.
    Применяется Laplace smoothing для малых выборок.
    """
    __tablename__ = "confidence_buckets"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # === BUCKET DEFINITION ===
    bucket_name: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        comment='e.g., "0.55-0.70"'
    )
    confidence_min: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    confidence_max: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    # === STATISTICS ===
    total_trades: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    wins: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    losses: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    breakevens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    # === WINRATE (raw + smoothed) ===
    actual_winrate_raw: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="wins / total"
    )
    actual_winrate_smoothed: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="Laplace: (wins + 1) / (total + 2)"
    )

    # === ADDITIONAL METRICS ===
    avg_pnl_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )
    avg_mae_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )
    avg_mfe_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )

    # === CALIBRATION ===
    calibration_offset: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="smoothed_winrate - bucket_midpoint"
    )

    # === META ===
    sample_size: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Размер выборки для расчёта"
    )
    last_calculated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    def __repr__(self) -> str:
        return f"<ConfidenceBucket(name={self.bucket_name}, winrate={self.actual_winrate_smoothed:.1%})>"


class ArchetypeStats(Base):
    """
    Archetype Stats - статистика по архетипам сетапов.

    Группируется по:
    - archetype (обязательно)
    - symbol (опционально)
    - timeframe (опционально)
    - volatility_regime (опционально)

    Используется для оптимизации SL/TP по типам сетапов.
    """
    __tablename__ = "archetype_stats"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # === GROUPING ===
    archetype: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False
    )
    side: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        index=True,
        comment="long/short — критично для EV!"
    )
    symbol: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="None = все символы"
    )
    timeframe: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="None = все TF"
    )
    volatility_regime: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="low/normal/high или None"
    )

    # === STATISTICS ===
    total_trades: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    wins: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    losses: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    winrate: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )
    avg_pnl_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )
    profit_factor: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="gross_profit / gross_loss"
    )

    # === TERMINAL OUTCOME COUNTS (для EV) ===
    exit_sl_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Не дошли ни до одного TP"
    )
    exit_tp1_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Дошли до TP1"
    )
    exit_tp2_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Дошли до TP2"
    )
    exit_tp3_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Дошли до TP3"
    )
    exit_other_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="manual/timeout/breakeven ДО любого TP"
    )
    avg_pnl_r_other: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="Средний PnL для OTHER исходов"
    )

    # === V2 PATH OUTCOME COUNTS (для EV v2) ===
    exit_sl_early_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        default=None,
        nullable=True,
        comment="SL до TP1 (полный лосс -1R)"
    )
    exit_be_after_tp1_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        default=None,
        nullable=True,
        comment="BE hit после TP1"
    )
    exit_stop_in_profit_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        default=None,
        nullable=True,
        comment="Trail/lock profit после TP1"
    )

    # === MAE/MFE ===
    avg_mae_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )
    avg_mfe_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )
    p75_mae_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="75th percentile MAE"
    )
    p90_mae_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="90th percentile MAE"
    )
    p50_mfe_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="median MFE"
    )

    # === OPTIMIZATION SUGGESTIONS ===
    suggested_sl_atr_mult: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
        comment="SL = X * ATR"
    )
    suggested_tp1_r: Mapped[float] = mapped_column(
        Float,
        default=1.5,
        nullable=False
    )
    suggested_tp2_r: Mapped[float] = mapped_column(
        Float,
        default=2.5,
        nullable=False
    )

    # === META ===
    last_calculated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # === UNIQUE CONSTRAINT ===
    __table_args__ = (
        UniqueConstraint(
            'archetype', 'side', 'symbol', 'timeframe', 'volatility_regime',
            name='uq_archetype_group_v2'
        ),
    )

    def __repr__(self) -> str:
        return f"<ArchetypeStats(archetype={self.archetype}, winrate={self.winrate:.1%})>"


# Feedback indexes:
# - trade_outcomes.trade_id (unique)
# - trade_outcomes.idempotency_key (unique)
# - trade_outcomes.user_id, created_at (composite)
# - trade_outcomes.symbol, timeframe, created_at (composite)
# - trade_outcomes.primary_archetype, created_at (composite)
# - trade_outcomes.confidence_raw (for bucket queries)
# - trade_outcomes.is_testnet (for filtering)
# - archetype_stats.archetype (index)
# - archetype_stats unique constraint on (archetype, symbol, timeframe, volatility_regime)


# =============================================================================
# SCENARIO CLASS STATS (Learning Module - Class Backtesting)
# =============================================================================

class ScenarioClassStats(Base):
    """
    Scenario Class Stats - статистика по классам сценариев с context gates.

    Класс = archetype + side + timeframe + [trend + vol + funding + sentiment]

    Hierarchical Fallback:
    - Level 1 (coarse): archetype + side + timeframe (buckets = '__any__')
    - Level 2 (fine): + все bucket dimensions

    Используется для:
    - Kill switch для мусорных классов (EV < 0 с CI)
    - Boost для топовых классов
    - Context gates (архетип разрешён только в правильном контексте)
    """
    __tablename__ = "scenario_class_stats"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # === CLASS KEY (для быстрого lookup) ===
    class_key_hash: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
        comment="SHA1 hash для быстрого lookup"
    )
    class_key_string: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="ARCHETYPE|SIDE|TF|TREND|VOL|FUND|SENT для дебага"
    )

    # === DECOMPOSED KEY (для UNIQUE + CHECK) ===
    archetype: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    side: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="long/short"
    )
    timeframe: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="1h/4h/1d"
    )
    trend_bucket: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="bullish/bearish/sideways/__any__"
    )
    vol_bucket: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="low/normal/high/__any__"
    )
    funding_bucket: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="strong_negative/negative/neutral/positive/__any__"
    )
    sentiment_bucket: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="fear/neutral/greed/__any__"
    )

    # === PROFITABILITY ===
    total_trades: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="= traded_count"
    )
    wins: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    losses: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    winrate: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )
    winrate_lower_ci: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="Wilson score 95% CI lower bound"
    )
    avg_pnl_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )
    avg_ev_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="Mean expected value per trade"
    )
    ev_lower_ci: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="EV 95% CI lower bound"
    )
    profit_factor: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="gross_profit / gross_loss"
    )

    # === CONVERSION ===
    generated_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="DISTINCT(analysis_id, scenario_local_id) из log"
    )
    traded_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="DISTINCT(trade_id)"
    )
    conversion_rate: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="traded_count / generated_count"
    )

    # === TERMINAL OUTCOMES ===
    exit_sl_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    exit_tp1_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    exit_tp2_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    exit_tp3_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    exit_other_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    avg_pnl_r_other: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="Средний PnL для OTHER исходов"
    )

    # === RISK ===
    max_drawdown_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="Max DD на equity curve (sorted by closed_at!)"
    )
    avg_mae_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )
    avg_mfe_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )
    p75_mae_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )
    p90_mae_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )
    avg_time_in_trade_min: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )

    # === EXECUTION ===
    fill_rate: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="opened_trades / selected_trades"
    )
    avg_slippage_r: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )
    other_exit_rate: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False
    )

    # === CONTEXT GATES ===
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="False = kill switch активен"
    )
    disable_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Причина kill switch"
    )
    preliminary_warning: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Warning для 20-49 trades"
    )
    confidence_modifier: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="+/- к confidence сценария"
    )
    ev_prior_boost: Mapped[float] = mapped_column(
        Float,
        default=0,
        nullable=False,
        comment="Boost для EV prior"
    )

    # === COOLDOWN ===
    disabled_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Cooldown: держим disabled до этого времени"
    )
    last_state_change_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда последний раз менялся is_enabled"
    )

    # === META ===
    window_days: Mapped[int] = mapped_column(
        Integer,
        default=90,
        nullable=False,
        comment="Rolling window в днях"
    )
    last_calculated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # === UNIQUE CONSTRAINT ===
    __table_args__ = (
        UniqueConstraint(
            'archetype', 'side', 'timeframe', 'trend_bucket', 'vol_bucket',
            'funding_bucket', 'sentiment_bucket',
            name='uq_scenario_class_key'
        ),
        # CHECK constraints добавлены в миграции
    )

    @property
    def class_level(self) -> int:
        """1 = coarse (__any__ во всех buckets), 2 = fine."""
        from src.learning.constants import ANY_BUCKET
        if all(
            b == ANY_BUCKET for b in [
                self.trend_bucket, self.vol_bucket,
                self.funding_bucket, self.sentiment_bucket
            ]
        ):
            return 1
        return 2

    def get_sample_status(self) -> str:
        """Вычисляемый статус sample size."""
        if self.total_trades >= 50:
            return "reliable"
        if self.total_trades >= 20:
            return "preliminary"
        return "insufficient"

    def __repr__(self) -> str:
        return (
            f"<ScenarioClassStats("
            f"archetype={self.archetype}, side={self.side}, "
            f"winrate={self.winrate:.1%}, is_enabled={self.is_enabled})>"
        )


class ScenarioGenerationLog(Base):
    """
    Scenario Generation Log - трекинг сгенерированных сценариев.

    Используется для:
    - Подсчёта generated_count (DISTINCT analysis_id + scenario_local_id)
    - Вычисления conversion_rate = traded_count / generated_count
    - Rolling window фильтрации (90 дней)

    Идемпотентность: UNIQUE(analysis_id, scenario_local_id)
    """
    __tablename__ = "scenario_generation_log"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # === ИДЕНТИФИКАЦИЯ ===
    analysis_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="UUID от Syntra анализа"
    )
    scenario_local_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="1..N в рамках analysis"
    )

    # === CONTEXT ===
    user_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )
    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )
    timeframe: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )

    # === CLASS KEY ===
    class_key_hash: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
        comment="SHA1 для быстрого lookup в class_stats"
    )
    archetype: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    side: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )

    # === META ===
    is_testnet: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="Для rolling window filter"
    )

    # === UNIQUE CONSTRAINT ===
    __table_args__ = (
        UniqueConstraint(
            'analysis_id', 'scenario_local_id',
            name='uq_scenario_generation'
        ),
        Index('ix_gen_log_class_hash_created', 'class_key_hash', 'created_at'),
    )

    def __repr__(self) -> str:
        return (
            f"<ScenarioGenerationLog("
            f"analysis={self.analysis_id}, scenario={self.scenario_local_id}, "
            f"archetype={self.archetype})>"
        )
