"""
Add social task: Subscribe to @web3_moves Telegram channel

Reward: 200 points
Verification: Automatic (Telegram API)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from loguru import logger

from src.database.engine import get_session_maker
from src.database.models import SocialTask, TaskType, TaskStatus, VerificationType


async def add_web3_moves_task():
    """Add task for subscribing to @web3_moves channel"""

    logger.info("Adding @web3_moves subscription task...")

    session_maker = get_session_maker()
    async with session_maker() as session:
        # Check if task already exists
        stmt = select(SocialTask).where(
            SocialTask.telegram_channel_id == "@web3_moves"
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            logger.warning(f"Task already exists (id={existing.id}), skipping...")
            return

        # Create new task
        task = SocialTask(
            title_ru="Подпишись на Web3 Moves",
            title_en="Subscribe to Web3 Moves",
            description_ru="Подпишись на канал @web3_moves и получи 200 очков!",
            description_en="Subscribe to @web3_moves channel and get 200 points!",
            icon="🚀",
            task_type=TaskType.TELEGRAM_SUBSCRIBE_CHANNEL.value,
            telegram_channel_id="@web3_moves",
            telegram_channel_url="https://t.me/web3_moves",
            verification_type=VerificationType.AUTO_TELEGRAM.value,
            reward_points=200,
            unsubscribe_penalty=100,
            status=TaskStatus.ACTIVE.value,
            priority=100,
            created_by=0,  # System created
        )

        session.add(task)
        await session.commit()
        await session.refresh(task)

        logger.info(f"Task created successfully! ID: {task.id}")
        logger.info(f"  Title: {task.title_ru}")
        logger.info(f"  Channel: {task.telegram_channel_id}")
        logger.info(f"  Reward: {task.reward_points} points")
        logger.info(f"  Penalty: {task.unsubscribe_penalty} points")
        logger.info(f"  Status: {task.status}")


async def main():
    try:
        await add_web3_moves_task()
    except Exception as e:
        logger.error(f"Script failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
