"""
Database models for Syntra Trade Consultant Bot

SQLAlchemy 2.0 models with full type hints
"""

from datetime import datetime, date
from typing import Optional

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
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models"""

    pass


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
        DateTime,
        default=datetime.utcnow,
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
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
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
        DateTime,
        default=datetime.utcnow,
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
        DateTime,
        default=datetime.utcnow,
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
        Integer, nullable=False, index=True, comment="Admin telegram ID"
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Action performed (e.g., reset_limits, ban_user)",
    )
    target_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True, comment="Target user ID (if applicable)"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
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
