"""
Fix missing referral codes for existing users

This script generates referral codes for all users that don't have one.
Safe to run multiple times - only updates users with NULL referral_code.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from loguru import logger

from src.database.engine import get_session_maker
from src.database.models import User
from src.database.crud import generate_referral_code


async def fix_missing_referral_codes():
    """Generate referral codes for users that don't have one"""

    logger.info("🔍 Checking for users without referral codes...")

    session_maker = get_session_maker()
    async with session_maker() as session:
        # Get users without referral_code
        stmt = select(User).where(User.referral_code.is_(None))
        result = await session.execute(stmt)
        users_without_code = list(result.scalars().all())

        if not users_without_code:
            logger.info("✅ All users already have referral codes!")
            return

        logger.info(f"📝 Found {len(users_without_code)} users without referral code")

        # Generate codes for each user
        updated_count = 0
        for user in users_without_code:
            try:
                # Generate unique code
                code = await generate_referral_code(session, user.id)
                user.referral_code = code

                # Identify user for logging
                identifier = (
                    f"telegram_id={user.telegram_id}" if user.telegram_id
                    else f"email={user.email}"
                )

                logger.info(
                    f"✅ Generated referral code {code} for user {user.id} "
                    f"({identifier}, username=@{user.username or 'N/A'})"
                )

                updated_count += 1

            except Exception as e:
                logger.error(f"❌ Failed to generate code for user {user.id}: {e}")
                continue

        # Commit all changes
        await session.commit()

        logger.info(f"\n🎉 Successfully generated {updated_count} referral codes!")

        # Verify results
        stmt = select(User).where(User.referral_code.is_(None))
        result = await session.execute(stmt)
        remaining = len(list(result.scalars().all()))

        if remaining > 0:
            logger.warning(f"⚠️  {remaining} users still without referral code")
        else:
            logger.info("✅ All users now have referral codes!")


async def main():
    """Main entry point"""
    try:
        await fix_missing_referral_codes()
    except Exception as e:
        logger.error(f"❌ Script failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
