"""
Test trial creation for new users
"""
import asyncio
from datetime import datetime, timedelta, UTC
from sqlalchemy import select, delete

from src.database.engine import get_session_maker
from src.database.crud import create_user, get_subscription
from src.database.models import User, Subscription


async def test_trial_creation():
    """Test that new users get 7-day Premium trial"""
    session_maker = get_session_maker()

    async with session_maker() as session:
        # Clean up test user if exists
        test_telegram_id = 999999999

        stmt = select(User).where(User.telegram_id == test_telegram_id)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            # Delete test user and their subscription
            await session.delete(existing_user)
            await session.commit()
            print(f"✓ Cleaned up existing test user {test_telegram_id}")

        # Create new user
        print(f"\n🔄 Creating test user with telegram_id={test_telegram_id}...")
        user = await create_user(
            session,
            telegram_id=test_telegram_id,
            username="test_user_trial",
            first_name="Test",
            last_name="User",
            language="en"
        )

        print(f"✓ User created: ID={user.id}, telegram_id={user.telegram_id}")

        # Get subscription
        subscription = await get_subscription(session, user.id)

        if not subscription:
            print("❌ ERROR: No subscription found for new user!")
            return False

        print(f"\n📊 Subscription details:")
        print(f"  - ID: {subscription.id}")
        print(f"  - Tier: {subscription.tier}")
        print(f"  - Is trial: {subscription.is_trial}")
        print(f"  - Is active: {subscription.is_active}")
        print(f"  - Trial start: {subscription.trial_start}")
        print(f"  - Trial end: {subscription.trial_end}")
        print(f"  - Expires at: {subscription.expires_at}")

        # Validate trial subscription
        errors = []

        if subscription.tier != "premium":
            errors.append(f"❌ Tier should be 'premium', got '{subscription.tier}'")
        else:
            print("✓ Tier is PREMIUM")

        if not subscription.is_trial:
            errors.append("❌ is_trial should be True")
        else:
            print("✓ is_trial is True")

        if not subscription.is_active:
            errors.append("❌ is_active should be True")
        else:
            print("✓ is_active is True")

        if not subscription.trial_start:
            errors.append("❌ trial_start should be set")
        else:
            print(f"✓ trial_start is set: {subscription.trial_start.isoformat()}")

        if not subscription.trial_end:
            errors.append("❌ trial_end should be set")
        else:
            # Check that trial_end is approximately 7 days from now
            now = datetime.now(UTC)
            expected_end = now + timedelta(days=7)
            time_diff = abs((subscription.trial_end - expected_end).total_seconds())

            if time_diff > 60:  # Allow 1 minute difference
                errors.append(
                    f"❌ trial_end should be ~7 days from now. "
                    f"Expected: {expected_end.isoformat()}, "
                    f"Got: {subscription.trial_end.isoformat()}"
                )
            else:
                days_remaining = (subscription.trial_end - now).days
                print(f"✓ trial_end is set correctly: {subscription.trial_end.isoformat()}")
                print(f"✓ Trial duration: {days_remaining} days remaining")

        if not subscription.expires_at:
            errors.append("❌ expires_at should be set")
        else:
            print(f"✓ expires_at is set: {subscription.expires_at.isoformat()}")

        # Clean up
        await session.delete(user)
        await session.commit()
        print(f"\n✓ Cleaned up test user {test_telegram_id}")

        # Print results
        print("\n" + "="*60)
        if errors:
            print("❌ TEST FAILED")
            for error in errors:
                print(error)
            return False
        else:
            print("✅ TEST PASSED - New users receive 7-day Premium trial!")
            return True


if __name__ == "__main__":
    success = asyncio.run(test_trial_creation())
    exit(0 if success else 1)
