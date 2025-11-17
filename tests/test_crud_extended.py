"""
Extended unit tests for CRUD operations
Tests for chat history, cost tracking, and admin functions
"""
import pytest
from datetime import datetime

from src.database.crud import (
    create_user,
    add_chat_message,
    get_chat_history,
    clear_chat_history,
    track_cost,
    log_admin_action,
    get_admin_logs,
    update_user_subscription,
    update_user_language,
    get_user_by_telegram_id,
)


@pytest.mark.asyncio
async def test_add_chat_message(db_session):
    """Test adding chat messages"""
    # Create user first
    user = await create_user(
        session=db_session,
        telegram_id=123456789
    )

    # Add user message
    user_msg = await add_chat_message(
        session=db_session,
        user_id=user.id,
        role="user",
        content="Hello, bot!"
    )

    assert user_msg.role == "user"
    assert user_msg.content == "Hello, bot!"
    assert user_msg.user_id == user.id

    # Add assistant message
    assistant_msg = await add_chat_message(
        session=db_session,
        user_id=user.id,
        role="assistant",
        content="Hello! How can I help?",
        tokens_used=25,
        model="gpt-4o-mini"
    )

    assert assistant_msg.role == "assistant"
    assert assistant_msg.tokens_used == 25
    assert assistant_msg.model == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_get_chat_history(db_session):
    """Test retrieving chat history"""
    # Create user
    user = await create_user(
        session=db_session,
        telegram_id=123456789
    )

    # Add multiple messages
    await add_chat_message(db_session, user.id, "user", "Message 1")
    await add_chat_message(db_session, user.id, "assistant", "Response 1")
    await add_chat_message(db_session, user.id, "user", "Message 2")
    await add_chat_message(db_session, user.id, "assistant", "Response 2")

    # Get history
    history = await get_chat_history(db_session, user.id, limit=10)

    assert len(history) == 4
    assert history[0].content == "Message 1"  # Ordered by timestamp
    assert history[-1].content == "Response 2"


@pytest.mark.asyncio
async def test_get_chat_history_limit(db_session):
    """Test chat history with limit"""
    user = await create_user(db_session, telegram_id=123456789)

    # Add 10 messages
    for i in range(10):
        await add_chat_message(db_session, user.id, "user", f"Message {i}")

    # Get only last 5
    history = await get_chat_history(db_session, user.id, limit=5)

    assert len(history) == 5


@pytest.mark.asyncio
async def test_clear_chat_history(db_session):
    """Test clearing chat history"""
    user = await create_user(db_session, telegram_id=123456789)

    # Add messages
    await add_chat_message(db_session, user.id, "user", "Message 1")
    await add_chat_message(db_session, user.id, "assistant", "Response 1")

    # Verify they exist
    history = await get_chat_history(db_session, user.id)
    assert len(history) == 2

    # Clear history
    await clear_chat_history(db_session, user.id)

    # Verify cleared
    history = await get_chat_history(db_session, user.id)
    assert len(history) == 0


@pytest.mark.asyncio
async def test_track_cost(db_session):
    """Test cost tracking"""
    user = await create_user(db_session, telegram_id=123456789)

    # Track OpenAI cost
    cost_entry = await track_cost(
        session=db_session,
        user_id=user.id,
        service="openai",
        model="gpt-4o",
        tokens=1000,
        cost=0.025,
        request_type="chat"
    )

    assert cost_entry.service == "openai"
    assert cost_entry.model == "gpt-4o"
    assert cost_entry.tokens == 1000
    assert cost_entry.cost == 0.025
    assert cost_entry.request_type == "chat"


@pytest.mark.asyncio
async def test_log_admin_action(db_session):
    """Test logging admin actions"""
    # Log successful action
    log = await log_admin_action(
        session=db_session,
        admin_id=987654321,
        action="reset_limits",
        target_user_id=123456789,
        details="Reset daily limits",
        success=True
    )

    assert log.admin_id == 987654321
    assert log.action == "reset_limits"
    assert log.target_user_id == 123456789
    assert log.success is True


@pytest.mark.asyncio
async def test_get_admin_logs(db_session):
    """Test retrieving admin logs"""
    # Create multiple admin logs
    await log_admin_action(db_session, 111, "action1", success=True)
    await log_admin_action(db_session, 111, "action2", success=True)
    await log_admin_action(db_session, 222, "action3", success=False)

    # Get all logs
    logs = await get_admin_logs(db_session, limit=10)
    assert len(logs) == 3

    # Get logs with limit
    logs = await get_admin_logs(db_session, limit=2)
    assert len(logs) == 2


@pytest.mark.asyncio
async def test_update_user_subscription(db_session):
    """Test updating user subscription status"""
    user = await create_user(db_session, telegram_id=123456789)

    # Initially not subscribed
    assert user.is_subscribed is False

    # Update to subscribed (using telegram_id, not user.id)
    await update_user_subscription(db_session, telegram_id=123456789, is_subscribed=True)

    # Verify updated
    updated_user = await get_user_by_telegram_id(db_session, 123456789)
    assert updated_user.is_subscribed is True


@pytest.mark.asyncio
async def test_update_user_language(db_session):
    """Test updating user language"""
    user = await create_user(db_session, telegram_id=123456789, language="ru")

    # Initially Russian
    assert user.language == "ru"

    # Update to English (using telegram_id, not user.id)
    await update_user_language(db_session, telegram_id=123456789, language="en")

    # Verify updated
    updated_user = await get_user_by_telegram_id(db_session, 123456789)
    assert updated_user.language == "en"


@pytest.mark.asyncio
async def test_chat_history_ordering(db_session):
    """Test that chat history is ordered by timestamp"""
    user = await create_user(db_session, telegram_id=123456789)

    # Add messages in specific order
    msg1 = await add_chat_message(db_session, user.id, "user", "First")
    msg2 = await add_chat_message(db_session, user.id, "assistant", "Second")
    msg3 = await add_chat_message(db_session, user.id, "user", "Third")

    # Get history
    history = await get_chat_history(db_session, user.id)

    # Should be in chronological order
    assert history[0].id == msg1.id
    assert history[1].id == msg2.id
    assert history[2].id == msg3.id


@pytest.mark.asyncio
async def test_multiple_users_chat_isolation(db_session):
    """Test that chat histories are isolated per user"""
    user1 = await create_user(db_session, telegram_id=111111111)
    user2 = await create_user(db_session, telegram_id=222222222)

    # Add messages for user1
    await add_chat_message(db_session, user1.id, "user", "User1 message")

    # Add messages for user2
    await add_chat_message(db_session, user2.id, "user", "User2 message")

    # Get histories
    history1 = await get_chat_history(db_session, user1.id)
    history2 = await get_chat_history(db_session, user2.id)

    # Each user should only see their own messages
    assert len(history1) == 1
    assert len(history2) == 1
    assert history1[0].content == "User1 message"
    assert history2[0].content == "User2 message"


@pytest.mark.asyncio
async def test_cost_tracking_multiple_services(db_session):
    """Test tracking costs for multiple services"""
    user = await create_user(db_session, telegram_id=123456789)

    # Track different services (tokens must not be None or 0.0 - must be int)
    await track_cost(db_session, user.id, "openai", "gpt-4o", 1000, 0.025)
    await track_cost(db_session, user.id, "coingecko", "api", 1, 0.0)  # 1 API call = 1 "token"
    await track_cost(db_session, user.id, "openai", "gpt-4o-mini", 500, 0.005)

    # All should be tracked (we'd need a get function to verify, but the add should succeed)
    # This is a basic test that the operations complete without error
    assert True
