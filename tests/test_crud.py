"""
Unit tests for CRUD operations
"""

import pytest
from datetime import datetime

from src.database.crud import (
    create_user,
    get_user_by_telegram_id,
    get_or_create_user,
    check_request_limit,
    increment_request_count,
    reset_request_limit,
)


@pytest.mark.asyncio
async def test_create_user(db_session):
    """Test user creation"""
    user = await create_user(
        session=db_session,
        telegram_id=123456789,
        username="test_user",
        first_name="Test",
        last_name="User",
    )

    assert user.telegram_id == 123456789
    assert user.username == "test_user"
    assert user.first_name == "Test"
    assert user.last_name == "User"
    assert not user.is_admin
    assert user.language == "ru"  # default


@pytest.mark.asyncio
async def test_get_user_by_telegram_id(db_session):
    """Test getting user by Telegram ID"""
    # Create user first
    created_user = await create_user(
        session=db_session, telegram_id=123456789, username="test_user"
    )

    # Get user
    user = await get_user_by_telegram_id(db_session, 123456789)

    assert user is not None
    assert user.id == created_user.id
    assert user.telegram_id == 123456789

    # Try non-existent user
    non_existent = await get_user_by_telegram_id(db_session, 999999999)
    assert non_existent is None


@pytest.mark.asyncio
async def test_get_or_create_user(db_session):
    """Test get_or_create_user function"""
    # Create new user
    user1, created1 = await get_or_create_user(
        session=db_session, telegram_id=123456789, username="new_user"
    )

    assert created1 is True
    assert user1.telegram_id == 123456789

    # Get existing user
    user2, created2 = await get_or_create_user(
        session=db_session, telegram_id=123456789, username="new_user"
    )

    assert created2 is False
    assert user2.id == user1.id


@pytest.mark.asyncio
async def test_request_limits(db_session):
    """Test request limit operations"""
    # Create user
    user = await create_user(session=db_session, telegram_id=123456789)

    # Check initial limits
    has_remaining, count, limit = await check_request_limit(db_session, user.id)
    assert has_remaining is True
    assert count == 0
    assert limit == 5  # default limit

    # Increment count
    await increment_request_count(db_session, user.id)
    has_remaining, count, limit = await check_request_limit(db_session, user.id)
    assert count == 1
    assert has_remaining is True

    # Increment to limit
    for _ in range(4):
        await increment_request_count(db_session, user.id)

    has_remaining, count, limit = await check_request_limit(db_session, user.id)
    assert count == 5
    assert has_remaining is False

    # Reset limits
    await reset_request_limit(db_session, user.id)
    has_remaining, count, limit = await check_request_limit(db_session, user.id)
    assert count == 0
    assert has_remaining is True
