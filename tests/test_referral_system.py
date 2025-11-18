"""
Comprehensive tests for referral system
Tests CRUD operations, tier upgrades, balance operations, and revenue sharing
"""

import pytest
from datetime import datetime, UTC, timedelta
from decimal import Decimal

from src.database.crud import (
    create_user,
    generate_referral_code,
    create_referral,
    grant_referral_rewards,
    is_referral_active,
    update_referral_tier,
    get_referral_stats,
    add_bonus_requests,
    get_active_bonuses,
    get_or_create_balance,
    add_to_balance,
    withdraw_balance,
    spend_balance,
    get_leaderboard,
    get_leaderboard_rank,
    calculate_revenue_share,
    increment_request_count,
)
from src.database.models import (
    User,
    Referral,
    ReferralStatus,
    BonusSource,
    ReferralTierLevel,
    BalanceTransactionType,
)
from sqlalchemy import select


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


async def make_user_requests(session, user_id: int, count: int = 5):
    """Helper to simulate user making multiple requests"""
    for _ in range(count):
        await increment_request_count(session, user_id)


# ============================================================================
# REFERRAL CODE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_generate_referral_code(db_session):
    """Test referral code generation"""
    user = await create_user(db_session, telegram_id=123456789)

    # Generate code
    code = await generate_referral_code(db_session, user.id)

    assert code is not None
    assert len(code) == 8
    assert code.isupper()
    assert code.isalnum()

    # Save code to user
    user.referral_code = code
    await db_session.commit()
    await db_session.refresh(user)
    assert user.referral_code == code


@pytest.mark.asyncio
async def test_referral_code_uniqueness(db_session):
    """Test that referral codes are unique"""
    user1 = await create_user(db_session, telegram_id=111111111)
    user2 = await create_user(db_session, telegram_id=222222222)

    code1 = await generate_referral_code(db_session, user1.id)
    code2 = await generate_referral_code(db_session, user2.id)

    assert code1 != code2


# ============================================================================
# REFERRAL CREATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_create_referral(db_session):
    """Test creating a referral relationship"""
    referrer = await create_user(db_session, telegram_id=111111111, username="referrer")
    referee = await create_user(db_session, telegram_id=222222222, username="referee")

    code = await generate_referral_code(db_session, referrer.id)

    # Create referral
    referral = await create_referral(
        db_session,
        referrer_id=referrer.id,
        referee_id=referee.id,
        referral_code=code
    )

    assert referral is not None
    assert referral.referrer_id == referrer.id
    assert referral.referee_id == referee.id
    assert referral.referral_code == code
    assert referral.status == ReferralStatus.PENDING.value
    assert referral.trial_granted is False
    assert referral.bonus_granted is False


@pytest.mark.asyncio
async def test_create_referral_self_referral_blocked(db_session):
    """Test that self-referrals are blocked"""
    user = await create_user(db_session, telegram_id=111111111)
    code = await generate_referral_code(db_session, user.id)

    # Try to refer self
    referral = await create_referral(
        db_session,
        referrer_id=user.id,
        referee_id=user.id,
        referral_code=code
    )

    assert referral is None


@pytest.mark.asyncio
async def test_create_referral_duplicate_blocked(db_session):
    """Test that duplicate referrals are blocked"""
    referrer = await create_user(db_session, telegram_id=111111111)
    referee = await create_user(db_session, telegram_id=222222222)
    code = await generate_referral_code(db_session, referrer.id)

    # Create first referral
    referral1 = await create_referral(db_session, referrer.id, referee.id, code)
    assert referral1 is not None

    # Try to create duplicate
    referral2 = await create_referral(db_session, referrer.id, referee.id, code)
    assert referral2 is None


# ============================================================================
# BONUS REWARDS TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_grant_referral_rewards(db_session):
    """Test that referral rewards are granted correctly"""
    referrer = await create_user(db_session, telegram_id=111111111, username="referrer")
    referee = await create_user(db_session, telegram_id=222222222, username="referee")
    code = await generate_referral_code(db_session, referrer.id)

    referral = await create_referral(db_session, referrer.id, referee.id, code)

    # Grant rewards
    await grant_referral_rewards(db_session, referral.id)

    # Check referee got +15 bonus requests
    referee_bonuses = await get_active_bonuses(db_session, referee.id)
    assert referee_bonuses == 15

    # Check referrer got +30 bonus requests
    referrer_bonuses = await get_active_bonuses(db_session, referrer.id)
    assert referrer_bonuses == 30

    # Check referral is marked as rewarded
    await db_session.refresh(referral)
    assert referral.bonus_granted is True


@pytest.mark.asyncio
async def test_grant_referral_rewards_only_once(db_session):
    """Test that rewards are only granted once"""
    referrer = await create_user(db_session, telegram_id=111111111)
    referee = await create_user(db_session, telegram_id=222222222)
    code = await generate_referral_code(db_session, referrer.id)

    referral = await create_referral(db_session, referrer.id, referee.id, code)

    # Grant rewards first time
    await grant_referral_rewards(db_session, referral.id)
    referrer_bonuses = await get_active_bonuses(db_session, referrer.id)
    assert referrer_bonuses == 30

    # Try to grant again
    await grant_referral_rewards(db_session, referral.id)
    referrer_bonuses = await get_active_bonuses(db_session, referrer.id)
    assert referrer_bonuses == 30  # Still 30, not 60


# ============================================================================
# REFERRAL ACTIVATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_referral_activation_criteria(db_session):
    """Test referral activation criteria: 24h + 5 requests + username + not banned"""
    referrer = await create_user(db_session, telegram_id=111111111)

    # Create referee with username
    referee = await create_user(db_session, telegram_id=222222222, username="referee_user")
    code = await generate_referral_code(db_session, referrer.id)
    referral = await create_referral(db_session, referrer.id, referee.id, code)

    # Initially not active (just registered)
    is_active = await is_referral_active(db_session, referee.id)
    assert is_active is False

    # Make 5 requests
    await make_user_requests(db_session, referee.id, count=5)

    # Move registration time back 25 hours
    referee.created_at = datetime.now(UTC) - timedelta(hours=25)
    await db_session.commit()

    # Now should be active
    is_active = await is_referral_active(db_session, referee.id)
    assert is_active is True

    # Check referral status updated
    await db_session.refresh(referral)
    assert referral.status == ReferralStatus.ACTIVE.value
    assert referral.activated_at is not None


@pytest.mark.asyncio
async def test_referral_not_active_without_username(db_session):
    """Test that referrals without username don't activate"""
    referrer = await create_user(db_session, telegram_id=111111111)
    referee = await create_user(db_session, telegram_id=222222222, username=None)
    code = await generate_referral_code(db_session, referrer.id)
    referral = await create_referral(db_session, referrer.id, referee.id, code)

    # Make requirements (5 requests, 24h+)
    await make_user_requests(db_session, referee.id, count=5)
    referee.created_at = datetime.now(UTC) - timedelta(hours=25)
    await db_session.commit()

    # Should NOT be active (no username)
    is_active = await is_referral_active(db_session, referral.id)
    assert is_active is False


@pytest.mark.asyncio
async def test_referral_not_active_if_banned(db_session):
    """Test that banned users' referrals don't activate"""
    referrer = await create_user(db_session, telegram_id=111111111)
    referee = await create_user(db_session, telegram_id=222222222, username="referee")
    code = await generate_referral_code(db_session, referrer.id)
    referral = await create_referral(db_session, referrer.id, referee.id, code)

    # Ban user
    referee.is_banned = True
    await db_session.commit()

    # Make other requirements
    await make_user_requests(db_session, referee.id, count=5)
    referee.created_at = datetime.now(UTC) - timedelta(hours=25)
    await db_session.commit()

    # Should NOT be active (banned)
    is_active = await is_referral_active(db_session, referral.id)
    assert is_active is False


# ============================================================================
# TIER SYSTEM TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_tier_upgrade_to_silver(db_session):
    """Test tier upgrade to Silver (5 active referrals)"""
    referrer = await create_user(db_session, telegram_id=111111111, username="referrer")
    code = await generate_referral_code(db_session, referrer.id)

    # Create 5 active referrals
    for i in range(5):
        referee = await create_user(db_session, telegram_id=222222220 + i, username=f"referee_{i}")
        referee.created_at = datetime.now(UTC) - timedelta(hours=25)
        await make_user_requests(db_session, referee.id, count=5)
        await db_session.commit()

        referral = await create_referral(db_session, referrer.id, referee.id, code)
        await is_referral_active(db_session, referee.id)  # Mark as active

    # Update tier
    tier = await update_referral_tier(db_session, referrer.id)

    assert tier is not None
    assert tier.tier == ReferralTierLevel.SILVER.value
    assert tier.active_referrals == 5
    assert tier.monthly_bonus == 50
    assert tier.discount_percent == 10
    assert tier.revenue_share_percent == Decimal('0.00')


@pytest.mark.asyncio
async def test_tier_upgrade_to_gold(db_session):
    """Test tier upgrade to Gold (15 active referrals)"""
    referrer = await create_user(db_session, telegram_id=111111111, username="referrer")
    code = await generate_referral_code(db_session, referrer.id)

    # Create 15 active referrals
    for i in range(15):
        referee = await create_user(db_session, telegram_id=222222200 + i, username=f"referee_{i}")
        referee.created_at = datetime.now(UTC) - timedelta(hours=25)
        await make_user_requests(db_session, referee.id, count=5)
        await db_session.commit()

        referral = await create_referral(db_session, referrer.id, referee.id, code)
        await is_referral_active(db_session, referee.id)

    tier = await update_referral_tier(db_session, referrer.id)

    assert tier.tier == ReferralTierLevel.GOLD.value
    assert tier.active_referrals == 15
    assert tier.monthly_bonus == 150
    assert tier.discount_percent == 20
    assert tier.revenue_share_percent == Decimal('10.00')


@pytest.mark.asyncio
async def test_tier_upgrade_to_platinum(db_session):
    """Test tier upgrade to Platinum (50+ active referrals)"""
    referrer = await create_user(db_session, telegram_id=111111111, username="referrer")
    code = await generate_referral_code(db_session, referrer.id)

    # Create 50 active referrals
    for i in range(50):
        referee = await create_user(db_session, telegram_id=222220000 + i, username=f"referee_{i}")
        referee.created_at = datetime.now(UTC) - timedelta(hours=25)
        await make_user_requests(db_session, referee.id, count=5)
        await db_session.commit()

        referral = await create_referral(db_session, referrer.id, referee.id, code)
        await is_referral_active(db_session, referee.id)

    tier = await update_referral_tier(db_session, referrer.id)

    assert tier.tier == ReferralTierLevel.PLATINUM.value
    assert tier.active_referrals == 50
    assert tier.monthly_bonus == 500
    assert tier.discount_percent == 30
    assert tier.revenue_share_percent == Decimal('15.00')


# ============================================================================
# REFERRAL STATS TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_get_referral_stats(db_session):
    """Test getting referral statistics"""
    referrer = await create_user(db_session, telegram_id=111111111, username="referrer")
    code = await generate_referral_code(db_session, referrer.id)

    # Create 3 referrals: 2 active, 1 pending
    for i in range(3):
        referee = await create_user(db_session, telegram_id=222222220 + i, username=f"referee_{i}")

        if i < 2:  # Make first 2 active
            referee.created_at = datetime.now(UTC) - timedelta(hours=25)
            await make_user_requests(db_session, referee.id, count=5)

        await db_session.commit()
        referral = await create_referral(db_session, referrer.id, referee.id, code)

        if i < 2:
            await is_referral_active(db_session, referee.id)

    # Get stats
    stats = await get_referral_stats(db_session, referrer.id)

    assert stats['total_referrals'] == 3
    assert stats['active_referrals'] == 2
    assert stats['tier'] == ReferralTierLevel.BRONZE.value  # 2 active < 5


# ============================================================================
# BALANCE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_create_balance(db_session):
    """Test balance creation"""
    user = await create_user(db_session, telegram_id=111111111)

    balance = await get_or_create_balance(db_session, user.id)

    assert balance is not None
    assert balance.user_id == user.id
    assert balance.balance_usd == Decimal('0.00')
    assert balance.earned_total_usd == Decimal('0.00')
    assert balance.withdrawn_total_usd == Decimal('0.00')


@pytest.mark.asyncio
async def test_add_to_balance(db_session):
    """Test adding funds to balance"""
    user = await create_user(db_session, telegram_id=111111111)

    # Add $10.50
    transaction = await add_to_balance(
        db_session,
        user.id,
        amount_usd=Decimal('10.50'),
        description="Test credit"
    )

    assert transaction is not None
    assert transaction.type == BalanceTransactionType.EARN.value
    assert transaction.amount_usd == Decimal('10.50')

    # Check balance updated
    balance = await get_or_create_balance(db_session, user.id)
    assert balance.balance_usd == Decimal('10.50')
    assert balance.earned_total_usd == Decimal('10.50')


@pytest.mark.asyncio
async def test_withdraw_balance(db_session):
    """Test withdrawing from balance"""
    user = await create_user(db_session, telegram_id=111111111)

    # Add $20
    await add_to_balance(db_session, user.id, Decimal('20.00'), "Initial")

    # Withdraw $10 (5% fee = $0.50)
    transaction = await withdraw_balance(
        db_session,
        user.id,
        amount_usd=Decimal('10.00'),
        wallet_address="TON_WALLET_ADDRESS_123"
    )

    assert transaction is not None
    assert transaction.type == BalanceTransactionType.WITHDRAW.value
    assert transaction.amount_usd == Decimal('10.50')  # Including fee
    assert transaction.withdrawal_address == "TON_WALLET_ADDRESS_123"

    # Check balance
    balance = await get_or_create_balance(db_session, user.id)
    assert balance.balance_usd == Decimal('9.50')  # 20 - 10.50
    assert balance.withdrawn_total_usd == Decimal('10.50')


@pytest.mark.asyncio
async def test_withdraw_insufficient_funds(db_session):
    """Test withdrawal with insufficient funds"""
    user = await create_user(db_session, telegram_id=111111111)

    # Add only $5
    await add_to_balance(db_session, user.id, Decimal('5.00'), "Initial")

    # Try to withdraw $10
    transaction = await withdraw_balance(
        db_session,
        user.id,
        amount_usd=Decimal('10.00'),
        wallet_address="TON_WALLET"
    )

    assert transaction is None  # Should fail


@pytest.mark.asyncio
async def test_spend_balance(db_session):
    """Test spending balance on subscription"""
    user = await create_user(db_session, telegram_id=111111111)

    # Add $50
    await add_to_balance(db_session, user.id, Decimal('50.00'), "Initial")

    # Spend $24.99 on subscription
    transaction = await spend_balance(
        db_session,
        user.id,
        amount_usd=Decimal('24.99'),
        description="PREMIUM subscription (1 month)"
    )

    assert transaction is not None
    assert transaction.type == BalanceTransactionType.SPEND.value
    assert transaction.amount_usd == Decimal('24.99')

    # Check balance
    balance = await get_or_create_balance(db_session, user.id)
    assert balance.balance_usd == Decimal('25.01')
    assert balance.spent_total_usd == Decimal('24.99')


# ============================================================================
# LEADERBOARD TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_get_leaderboard(db_session):
    """Test getting leaderboard"""
    # Create 3 referrers with different numbers of active referrals
    referrers = []
    for r in range(3):
        referrer = await create_user(db_session, telegram_id=111111110 + r, username=f"referrer_{r}")
        code = await generate_referral_code(db_session, referrer.id)

        # Create different numbers of active referrals (5, 10, 15)
        num_refs = (r + 1) * 5
        for i in range(num_refs):
            referee = await create_user(db_session, telegram_id=222220000 + r * 100 + i, username=f"ref_{r}_{i}")
            referee.created_at = datetime.now(UTC) - timedelta(hours=25)
            await make_user_requests(db_session, referee.id, count=5)
            await db_session.commit()

            referral = await create_referral(db_session, referrer.id, referee.id, code)
            await is_referral_active(db_session, referee.id)

        await update_referral_tier(db_session, referrer.id)
        referrers.append(referrer)

    # Get leaderboard
    leaderboard = await get_leaderboard(db_session, limit=10)

    assert len(leaderboard) == 3
    # Should be sorted by active_referrals desc
    assert leaderboard[0]['active_referrals'] == 15
    assert leaderboard[1]['active_referrals'] == 10
    assert leaderboard[2]['active_referrals'] == 5


@pytest.mark.asyncio
async def test_get_leaderboard_rank(db_session):
    """Test getting user's leaderboard rank"""
    # Create 3 referrers
    referrers = []
    for r in range(3):
        referrer = await create_user(db_session, telegram_id=111111110 + r, username=f"referrer_{r}")
        code = await generate_referral_code(db_session, referrer.id)

        num_refs = (r + 1) * 5  # 5, 10, 15
        for i in range(num_refs):
            referee = await create_user(db_session, telegram_id=222220000 + r * 100 + i, username=f"ref_{r}_{i}")
            referee.created_at = datetime.now(UTC) - timedelta(hours=25)
            await make_user_requests(db_session, referee.id, count=5)
            await db_session.commit()

            referral = await create_referral(db_session, referrer.id, referee.id, code)
            await is_referral_active(db_session, referee.id)

        await update_referral_tier(db_session, referrer.id)
        referrers.append(referrer)

    # Get rank for middle referrer (10 active refs)
    rank = await get_leaderboard_rank(db_session, referrers[1].id)
    assert rank == 2  # Should be 2nd place


# ============================================================================
# REVENUE SHARE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_calculate_revenue_share(db_session):
    """Test revenue share calculation"""
    # Create referrer with Gold tier (15 active referrals, 10% share)
    referrer = await create_user(db_session, telegram_id=111111111, username="referrer")
    code = await generate_referral_code(db_session, referrer.id)

    # Create 15 active referrals
    for i in range(15):
        referee = await create_user(db_session, telegram_id=222222200 + i, username=f"referee_{i}")
        referee.created_at = datetime.now(UTC) - timedelta(hours=25)
        await make_user_requests(db_session, referee.id, count=5)
        await db_session.commit()

        referral = await create_referral(db_session, referrer.id, referee.id, code)
        await is_referral_active(db_session, referee.id)

    tier = await update_referral_tier(db_session, referrer.id)
    assert tier.tier == ReferralTierLevel.GOLD.value

    # Simulate payments from referrals
    # TODO: This test needs payment tracking implementation
    # For now, just verify the calculation logic exists

    start_date = datetime.now(UTC) - timedelta(days=30)
    end_date = datetime.now(UTC)

    revenue_share = await calculate_revenue_share(
        db_session,
        referrer.id,
        start_date,
        end_date
    )

    # Without payments, should be 0
    assert revenue_share['revenue_share_amount'] == 0
    assert revenue_share['total_revenue'] == 0
    assert revenue_share['revenue_share_percent'] == 10.0  # Gold tier = 10%


# ============================================================================
# BONUS EXPIRY TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_bonus_requests_with_expiry(db_session):
    """Test bonus requests with expiration"""
    user = await create_user(db_session, telegram_id=111111111)

    # Add bonus that expires in 1 hour
    expires = datetime.now(UTC) + timedelta(hours=1)
    await add_bonus_requests(
        db_session,
        user.id,
        amount=50,
        source=BonusSource.CHALLENGE.value,
        description="Challenge bonus",
        expires_at=expires
    )

    # Should be active
    active = await get_active_bonuses(db_session, user.id)
    assert active == 50

    # Add expired bonus
    expired = datetime.now(UTC) - timedelta(hours=1)
    await add_bonus_requests(
        db_session,
        user.id,
        amount=100,
        source=BonusSource.CHALLENGE.value,
        description="Expired bonus",
        expires_at=expired
    )

    # Should still be 50 (expired bonus not counted)
    active = await get_active_bonuses(db_session, user.id)
    assert active == 50
