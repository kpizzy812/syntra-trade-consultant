"""
Test that trial users get PREMIUM tier access and limits
"""
import asyncio
from datetime import datetime, timedelta, UTC

from src.database.engine import get_session_maker
from src.database.crud import create_user, get_subscription, get_daily_limit_info
from src.database.models import User, Subscription, SubscriptionTier
from config.limits import get_text_limit, get_vision_limit


async def test_trial_premium_access():
    """Test that trial users have PREMIUM tier access and limits"""
    session_maker = get_session_maker()

    async with session_maker() as session:
        # Clean up test user if exists
        test_telegram_id = 999999998

        from sqlalchemy import select
        stmt = select(User).where(User.telegram_id == test_telegram_id)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            await session.delete(existing_user)
            await session.commit()
            print(f"✓ Cleaned up existing test user {test_telegram_id}")

        # Create new user (should get 7-day trial)
        print(f"\n🔄 Creating test user with telegram_id={test_telegram_id}...")
        user = await create_user(
            session,
            telegram_id=test_telegram_id,
            username="test_trial_premium",
            first_name="Trial",
            last_name="User",
            language="en"
        )

        print(f"✓ User created: ID={user.id}")

        # Get subscription
        subscription = await get_subscription(session, user.id)

        if not subscription:
            print("❌ ERROR: No subscription found!")
            return False

        print(f"\n📊 Subscription info:")
        print(f"  - Tier: {subscription.tier}")
        print(f"  - Is trial: {subscription.is_trial}")
        print(f"  - Is active: {subscription.is_active}")

        # Check tier and limits
        errors = []

        # 1. Check tier is PREMIUM
        if subscription.tier != SubscriptionTier.PREMIUM.value:
            errors.append(f"❌ Trial tier should be 'premium', got '{subscription.tier}'")
        else:
            print(f"✓ Trial tier is PREMIUM")

        # 2. Check daily limits match PREMIUM tier
        premium_text_limit = get_text_limit(SubscriptionTier.PREMIUM)
        premium_vision_limit = get_vision_limit(SubscriptionTier.PREMIUM)

        tier_text_limit = get_text_limit(subscription.tier)
        tier_vision_limit = get_vision_limit(subscription.tier)

        print(f"\n📈 Limits comparison:")
        print(f"  PREMIUM tier limits:")
        print(f"    - Text requests: {premium_text_limit}/day")
        print(f"    - Vision requests: {premium_vision_limit}/day")
        print(f"  Trial user limits:")
        print(f"    - Text requests: {tier_text_limit}/day")
        print(f"    - Vision requests: {tier_vision_limit}/day")

        if tier_text_limit != premium_text_limit:
            errors.append(
                f"❌ Text limit mismatch: trial={tier_text_limit}, premium={premium_text_limit}"
            )
        else:
            print(f"✓ Text limit matches PREMIUM ({tier_text_limit}/day)")

        if tier_vision_limit != premium_vision_limit:
            errors.append(
                f"❌ Vision limit mismatch: trial={tier_vision_limit}, premium={premium_vision_limit}"
            )
        else:
            print(f"✓ Vision limit matches PREMIUM ({tier_vision_limit}/day)")

        # 3. Check daily limit info
        limit_info = await get_daily_limit_info(session, user.id)
        print(f"\n📊 Current usage:")
        print(f"  - Used today: {limit_info.get('used', 0)}")
        print(f"  - Remaining: {tier_text_limit - limit_info.get('used', 0)}")

        # 4. Verify is_trial flag
        if not subscription.is_trial:
            errors.append("❌ is_trial should be True")
        else:
            print(f"✓ is_trial flag is set")

        # 5. Verify is_active
        if not subscription.is_active:
            errors.append("❌ is_active should be True")
        else:
            print(f"✓ Subscription is active")

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
            print("✅ TEST PASSED - Trial users have full PREMIUM access!")
            print(f"   Trial users get {premium_text_limit} text requests and {premium_vision_limit} vision requests per day")
            return True


if __name__ == "__main__":
    success = asyncio.run(test_trial_premium_access())
    exit(0 if success else 1)
