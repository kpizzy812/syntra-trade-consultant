"""
Forward Test Scheduler

APScheduler jobs для forward testing:
- Генерация batch: каждые 6 часов (00/06/12/18 UTC)
- Мониторинг: каждые 60 сек
- Aggregation: раз в день 23:55 UTC
- Telegram report: раз в день 23:58 UTC
- Cleanup: раз в день 04:00 UTC
"""
from datetime import datetime, timedelta, UTC
from typing import Optional

from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import delete, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.engine import get_session_maker
from src.services.forward_test.config import get_config
from src.services.forward_test.models import (
    ForwardTestSnapshot,
    ForwardTestEvent,
    ForwardTestOutcome,
)
from src.services.forward_test.snapshot_service import snapshot_service
from src.services.forward_test.monitor_service import monitor_service
from src.services.forward_test.telegram_reporter import TelegramReporter
from src.learning.class_stats_analyzer import ClassStatsAnalyzer


class ForwardTestScheduler:
    """
    APScheduler для forward testing jobs.

    Jobs:
    - forward_test_generate: генерация сценариев
    - forward_test_monitor: мониторинг по 1m OHLC
    - forward_test_aggregate: агрегация метрик
    - forward_test_telegram: Telegram report
    - forward_test_cleanup: cleanup старых данных
    """

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._running = False
        self.config = get_config()

    def start(self):
        """Запустить scheduler."""
        if self._running:
            logger.warning("Forward test scheduler already running")
            return

        self.scheduler = AsyncIOScheduler()

        schedule = self.config.schedule

        # 1. Generation: 00/06/12/18 UTC
        hours = ",".join(str(h) for h in schedule.generation_hours)
        self.scheduler.add_job(
            self._job_generate,
            CronTrigger(hour=hours, minute=0),
            id="forward_test_generate",
            name="Forward Test Generation",
            replace_existing=True
        )

        # 2. Monitor: каждые 60 сек
        self.scheduler.add_job(
            self._job_monitor,
            IntervalTrigger(seconds=self.config.monitor.interval_sec),
            id="forward_test_monitor",
            name="Forward Test Monitor",
            replace_existing=True
        )

        # 3. Aggregation: 23:55 UTC
        self.scheduler.add_job(
            self._job_aggregate,
            CronTrigger(
                hour=schedule.aggregation_hour,
                minute=schedule.aggregation_minute
            ),
            id="forward_test_aggregate",
            name="Forward Test Aggregation",
            replace_existing=True
        )

        # 4. Telegram report: 23:58 UTC
        self.scheduler.add_job(
            self._job_telegram_report,
            CronTrigger(
                hour=schedule.telegram_report_hour,
                minute=schedule.telegram_report_minute
            ),
            id="forward_test_telegram",
            name="Forward Test Telegram Report",
            replace_existing=True
        )

        # 5. Cleanup: 04:00 UTC
        self.scheduler.add_job(
            self._job_cleanup,
            CronTrigger(
                hour=schedule.cleanup_hour,
                minute=schedule.cleanup_minute
            ),
            id="forward_test_cleanup",
            name="Forward Test Cleanup",
            replace_existing=True
        )

        # 6. Mark-to-market: hourly at :30 min (Portfolio Mode)
        if self.config.portfolio.enabled:
            self.scheduler.add_job(
                self._job_mark_to_market,
                CronTrigger(minute=30),  # Every hour at :30
                id="forward_test_mark_to_market",
                name="Forward Test Mark-to-Market",
                replace_existing=True
            )

        self.scheduler.start()
        self._running = True

        logger.info(
            f"Forward test scheduler started: "
            f"generation at {hours}:00 UTC, "
            f"monitor every {self.config.monitor.interval_sec}s, "
            f"report at {schedule.telegram_report_hour}:{schedule.telegram_report_minute:02d} UTC"
        )

    def stop(self):
        """Остановить scheduler."""
        if self.scheduler:
            self.scheduler.shutdown()
            self._running = False
            logger.info("Forward test scheduler stopped")

    async def trigger_generate_now(self) -> dict:
        """Ручной запуск генерации (для тестов)."""
        logger.info("Manual generation triggered")
        return await self._job_generate()

    async def trigger_monitor_now(self) -> dict:
        """Ручной запуск мониторинга."""
        logger.info("Manual monitor triggered")
        transitions = await self._job_monitor()
        return {"transitions": len(transitions)}

    async def trigger_aggregate_now(self) -> dict:
        """Ручной запуск агрегации."""
        logger.info("Manual aggregation triggered")
        await self._job_aggregate()
        return {"status": "completed"}

    async def trigger_telegram_now(self) -> dict:
        """Ручной запуск Telegram report."""
        logger.info("Manual telegram report triggered")
        await self._job_telegram_report()
        return {"status": "completed"}

    def set_enabled(self, enabled: bool):
        """Включить/выключить forward testing."""
        self.config.enabled = enabled
        logger.info(f"Forward test {'enabled' if enabled else 'disabled'}")

    def is_enabled(self) -> bool:
        """Проверить включен ли forward testing."""
        return self.config.enabled

    async def _job_generate(self) -> dict:
        """Job: генерация batch."""
        if not self.config.enabled:
            logger.debug("Forward test disabled, skipping generation")
            return {"skipped": True, "reason": "disabled"}
        try:
            async with get_session_maker()() as session:
                result = await snapshot_service.generate_batch(session)
                logger.info(
                    f"Generation complete: {result.total_generated} snapshots, "
                    f"{len(result.errors)} errors"
                )
                return {
                    "batch_id": result.batch_id,
                    "total": result.total_generated,
                    "by_symbol": result.by_symbol,
                    "errors": result.errors
                }
        except Exception as e:
            logger.error(f"Generation job failed: {e}")
            return {"error": str(e)}

    async def _job_monitor(self) -> list:
        """Job: мониторинг."""
        if not self.config.enabled:
            return []
        try:
            async with get_session_maker()() as session:
                transitions = await monitor_service.tick(session)
                if transitions:
                    logger.debug(f"Monitor tick: {len(transitions)} transitions")
                return transitions
        except Exception as e:
            logger.error(f"Monitor job failed: {e}")
            return []

    async def _job_aggregate(self):
        """Job: агрегация метрик + apply paper outcomes к learning."""
        try:
            async with get_session_maker()() as session:
                from datetime import date

                today = date.today()
                start_dt = datetime.combine(today, datetime.min.time())
                end_dt = datetime.combine(today, datetime.max.time())

                # Получить outcomes за сегодня
                outcomes_q = select(ForwardTestOutcome, ForwardTestSnapshot).join(
                    ForwardTestSnapshot,
                    ForwardTestOutcome.snapshot_id == ForwardTestSnapshot.snapshot_id
                ).where(
                    and_(
                        ForwardTestSnapshot.generated_at >= start_dt,
                        ForwardTestSnapshot.generated_at <= end_dt
                    )
                )
                result = await session.execute(outcomes_q)
                rows = result.all()

                if rows:
                    # Подготовить данные для apply_paper_outcomes
                    outcomes_data = []
                    for outcome, snapshot in rows:
                        outcomes_data.append({
                            "archetype": snapshot.archetype,
                            "side": snapshot.bias,
                            "timeframe": snapshot.timeframe,
                            "result": outcome.result,
                            "total_r": outcome.total_r,
                            "mae_r": outcome.mae_r,
                            "mfe_r": outcome.mfe_r,
                        })

                    # Apply к learning
                    analyzer = ClassStatsAnalyzer(session)
                    await analyzer.apply_paper_outcomes(outcomes_data, weight=0.3)

                    logger.info(f"Aggregation complete: {len(rows)} outcomes applied to learning")
                else:
                    logger.info("Aggregation: no outcomes for today")

        except Exception as e:
            logger.error(f"Aggregation job failed: {e}")

    async def _job_telegram_report(self):
        """Job: Telegram daily report."""
        try:
            reporter = TelegramReporter()
            try:
                async with get_session_maker()() as session:
                    result = await reporter.send_daily_report(session)
                    logger.info(
                        f"Telegram report sent: {result['sent']} success, "
                        f"{result['failed']} failed"
                    )
            finally:
                await reporter.close()
        except Exception as e:
            logger.error(f"Telegram report job failed: {e}")

    async def _job_cleanup(self):
        """
        Job: cleanup старых данных.

        Retention (0 = keep forever):
        - events: 30 дней
        - snapshots: 90 дней
        - outcomes: 0 (хранить всегда для all-time stats)
        """
        try:
            retention = self.config.retention
            now = datetime.now(UTC)
            events_deleted_count = 0
            outcomes_deleted_count = 0
            snapshots_deleted_count = 0

            async with get_session_maker()() as session:
                # Cleanup events
                if retention.events_days > 0:
                    events_cutoff = now - timedelta(days=retention.events_days)
                    events_deleted = await session.execute(
                        delete(ForwardTestEvent).where(
                            ForwardTestEvent.ts < events_cutoff
                        )
                    )
                    events_deleted_count = events_deleted.rowcount

                # Cleanup outcomes (0 = хранить всегда)
                if retention.outcomes_days > 0:
                    outcomes_cutoff = now - timedelta(days=retention.outcomes_days)
                    outcomes_deleted = await session.execute(
                        delete(ForwardTestOutcome).where(
                            ForwardTestOutcome.created_at < outcomes_cutoff
                        )
                    )
                    outcomes_deleted_count = outcomes_deleted.rowcount

                # Cleanup snapshots
                if retention.snapshots_days > 0:
                    snapshots_cutoff = now - timedelta(days=retention.snapshots_days)
                    snapshots_deleted = await session.execute(
                        delete(ForwardTestSnapshot).where(
                            ForwardTestSnapshot.generated_at < snapshots_cutoff
                        )
                    )
                    snapshots_deleted_count = snapshots_deleted.rowcount

                await session.commit()

                logger.info(
                    f"Cleanup complete: "
                    f"events={events_deleted_count}, "
                    f"outcomes={outcomes_deleted_count}, "
                    f"snapshots={snapshots_deleted_count}"
                )

        except Exception as e:
            logger.error(f"Cleanup job failed: {e}")

    async def _job_mark_to_market(self):
        """
        Job: hourly mark-to-market for portfolio positions.

        Обновляет unrealized_r для всех open positions.
        """
        if not self.config.enabled or not self.config.portfolio.enabled:
            return

        try:
            async with get_session_maker()() as session:
                updated = await monitor_service.update_unrealized_pnl(session)
                await session.commit()
                logger.debug(f"Mark-to-market: updated {updated} positions")
        except Exception as e:
            logger.error(f"Mark-to-market job failed: {e}")

    def get_status(self) -> dict:
        """Получить статус scheduler."""
        if not self.scheduler or not self._running:
            return {
                "running": False,
                "enabled": self.config.enabled,
                "jobs": []
            }

        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            })

        return {
            "running": True,
            "enabled": self.config.enabled,
            "jobs": jobs
        }


# Singleton
forward_test_scheduler = ForwardTestScheduler()
