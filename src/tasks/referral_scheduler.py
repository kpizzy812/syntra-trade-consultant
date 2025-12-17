"""
Referral Activation Scheduler

Background task that periodically checks and activates pending referrals
"""

import asyncio
from datetime import datetime
from loguru import logger

from src.database.engine import get_session
from src.database.crud import process_pending_referrals


async def check_and_activate_referrals():
    """
    Check all pending referrals and activate those that meet criteria

    Criteria for activation:
    - Registered > 24 hours ago
    - Made at least 5 requests
    - Not banned

    When activated:
    - Referrer receives +30 bonus requests
    - Referral status changes from PENDING to ACTIVE
    - Referrer's tier is updated
    """
    try:
        logger.info("Starting referral activation check")
        start_time = datetime.now()

        # Get database session
        async for session in get_session():
            try:
                # Process all pending referrals
                stats = await process_pending_referrals(session)

                # Log results
                duration = (datetime.now() - start_time).total_seconds()
                logger.info(
                    f"Referral activation check completed in {duration:.2f}s: "
                    f"{stats['activated']} activated, {stats['failed']} failed, "
                    f"{stats['checked']} total pending"
                )

                # Only need one session
                break
            except Exception as e:
                logger.error(f"Error in referral activation check: {e}", exc_info=True)
            finally:
                await session.close()

    except Exception as e:
        logger.error(f"Fatal error in referral activation scheduler: {e}", exc_info=True)


def schedule_referral_tasks(scheduler):
    """
    Schedule referral-related background tasks

    Args:
        scheduler: APScheduler instance
    """
    # Check and activate pending referrals every 30 minutes
    scheduler.add_job(
        check_and_activate_referrals,
        trigger='interval',
        minutes=30,
        id='check_referrals',
        name='Check and activate pending referrals',
        replace_existing=True,
        max_instances=1,  # Prevent overlapping runs
    )

    logger.info("Referral activation scheduler configured: checking every 30 minutes")
