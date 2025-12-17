"""
Learning Scheduler

Периодический пересчёт статистики для learning системы.
Использует APScheduler для фоновых задач.
"""
import asyncio
from datetime import datetime, UTC
from typing import Optional

from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.engine import get_session_maker
from src.learning.confidence_calibrator import confidence_calibrator
from src.learning.archetype_analyzer import archetype_analyzer
from src.learning.class_stats_analyzer import class_stats_analyzer


class LearningScheduler:
    """
    Scheduler для периодического пересчёта learning статистики.

    Jobs:
    - Confidence calibration: каждые 6 часов
    - Archetype stats: каждые 6 часов
    - Class stats: каждые 6 часов (context gates)
    """

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._running = False

    def start(
        self,
        confidence_interval_hours: int = 6,
        archetype_interval_hours: int = 6,
        class_stats_interval_hours: int = 6,
        include_testnet: bool = False,
    ):
        """
        Запустить scheduler.

        Args:
            confidence_interval_hours: Интервал пересчёта confidence buckets
            archetype_interval_hours: Интервал пересчёта archetype stats
            class_stats_interval_hours: Интервал пересчёта class stats
            include_testnet: Включать testnet сделки в learning
        """
        if self._running:
            logger.warning("Learning scheduler already running")
            return

        self.scheduler = AsyncIOScheduler()

        # Confidence calibration job
        self.scheduler.add_job(
            self._recalculate_confidence,
            trigger=IntervalTrigger(hours=confidence_interval_hours),
            id="confidence_calibration",
            name="Confidence Bucket Calibration",
            kwargs={"include_testnet": include_testnet},
            replace_existing=True,
        )

        # Archetype stats job
        self.scheduler.add_job(
            self._recalculate_archetypes,
            trigger=IntervalTrigger(hours=archetype_interval_hours),
            id="archetype_stats",
            name="Archetype Statistics",
            kwargs={"include_testnet": include_testnet},
            replace_existing=True,
        )

        # Class stats job (context gates)
        self.scheduler.add_job(
            self._recalculate_class_stats,
            trigger=IntervalTrigger(hours=class_stats_interval_hours),
            id="class_stats",
            name="Class Statistics (Context Gates)",
            kwargs={"include_testnet": include_testnet},
            replace_existing=True,
        )

        self.scheduler.start()
        self._running = True

        logger.info(
            f"Learning scheduler started: "
            f"confidence every {confidence_interval_hours}h, "
            f"archetypes every {archetype_interval_hours}h, "
            f"class_stats every {class_stats_interval_hours}h"
        )

    def stop(self):
        """Остановить scheduler."""
        if self.scheduler:
            self.scheduler.shutdown()
            self._running = False
            logger.info("Learning scheduler stopped")

    async def trigger_recalculation(
        self,
        include_testnet: bool = False
    ):
        """
        Немедленно запустить пересчёт всей статистики.

        Используется для ручного триггера после пакетного импорта.
        """
        logger.info("Manual learning recalculation triggered")

        await self._recalculate_confidence(include_testnet)
        await self._recalculate_archetypes(include_testnet)
        await self._recalculate_class_stats(include_testnet)

        logger.info("Manual learning recalculation complete")

    async def _recalculate_confidence(self, include_testnet: bool = False):
        """Пересчитать confidence buckets."""
        try:
            async with get_session_maker()() as session:
                stats = await confidence_calibrator.recalculate_buckets(
                    session,
                    include_testnet=include_testnet
                )
                logger.info(
                    f"Confidence recalculation complete: "
                    f"{stats.get('buckets_updated', 0)} buckets updated"
                )
        except Exception as e:
            logger.error(f"Confidence recalculation failed: {e}")

    async def _recalculate_archetypes(self, include_testnet: bool = False):
        """Пересчитать archetype stats."""
        try:
            async with get_session_maker()() as session:
                stats = await archetype_analyzer.recalculate_stats(
                    session,
                    include_testnet=include_testnet
                )
                logger.info(
                    f"Archetype recalculation complete: "
                    f"{stats.get('groups_updated', 0)} groups updated"
                )
        except Exception as e:
            logger.error(f"Archetype recalculation failed: {e}")

    async def _recalculate_class_stats(self, include_testnet: bool = False):
        """Пересчитать class stats (context gates)."""
        try:
            async with get_session_maker()() as session:
                stats = await class_stats_analyzer.recalculate_stats(
                    session,
                    include_testnet=include_testnet
                )
                logger.info(
                    f"Class stats recalculation complete: "
                    f"{stats.get('classes_updated', 0)} classes updated "
                    f"(L1: {stats.get('l1_classes', 0)}, L2: {stats.get('l2_classes', 0)})"
                )
        except Exception as e:
            logger.error(f"Class stats recalculation failed: {e}")

    def get_status(self) -> dict:
        """Получить статус scheduler."""
        if not self.scheduler or not self._running:
            return {
                "running": False,
                "jobs": [],
            }

        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            })

        return {
            "running": True,
            "jobs": jobs,
        }


# Singleton instance
learning_scheduler = LearningScheduler()
