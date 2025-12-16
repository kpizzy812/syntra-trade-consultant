"""
Feedback Service

Обработка и сохранение trade feedback.
UPSERT логика с partial updates.
"""
from datetime import datetime, UTC
from typing import Optional, Dict, Any, List

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    TradeOutcome,
    ConfidenceBucket,
    ArchetypeStats,
    TradeOutcomeLabel,
)


class FeedbackService:
    """
    Сервис обработки trade feedback.

    Поддерживает:
    - UPSERT по trade_id
    - Partial updates (execution, outcome, attribution отправляются отдельно)
    - Idempotency по idempotency_key
    - Триггер learning при достижении порогов
    """

    # Порог для триггера пересчёта
    LEARNING_TRIGGER_THRESHOLD = 10  # каждые N новых записей

    async def submit_feedback(
        self,
        session: AsyncSession,
        trade_id: str,
        analysis_id: str,
        scenario_local_id: int,
        scenario_hash: str,
        idempotency_key: str,
        user_id: int,
        symbol: str,
        side: str,
        timeframe: str,
        is_testnet: bool,
        confidence_raw: float,
        execution: Optional[Dict[str, Any]] = None,
        outcome: Optional[Dict[str, Any]] = None,
        attribution: Optional[Dict[str, Any]] = None,
        scenario_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Submit trade feedback with UPSERT logic.

        Args:
            trade_id: UUID from bot
            analysis_id: UUID from Syntra
            scenario_local_id: 1..N within analysis
            scenario_hash: sha256 of scenario snapshot
            idempotency_key: {trade_id}:{event_type}
            user_id: Telegram user ID
            symbol: Trading pair
            side: Long/Short
            timeframe: e.g., 4h
            is_testnet: Testnet flag
            confidence_raw: Original AI confidence
            execution: Execution report dict
            outcome: Outcome report dict
            attribution: Attribution dict
            scenario_snapshot: Full scenario snapshot

        Returns:
            Dict with success, duplicate, fields_updated, learning_triggered
        """
        fields_updated = []
        duplicate = False

        # Check if record exists by trade_id
        existing = await self._get_by_trade_id(session, trade_id)

        if existing:
            # Check idempotency
            if existing.idempotency_key == idempotency_key:
                logger.info(f"Duplicate feedback: trade_id={trade_id}")
                return {
                    "success": True,
                    "duplicate": True,
                    "fields_updated": [],
                    "learning_triggered": False,
                }

            # Update existing record (merge data)
            fields_updated = await self._update_outcome(
                session, existing,
                execution=execution,
                outcome=outcome,
                attribution=attribution,
                scenario_snapshot=scenario_snapshot,
                idempotency_key=idempotency_key,
            )

        else:
            # Create new record
            outcome_record = TradeOutcome(
                trade_id=trade_id,
                analysis_id=analysis_id,
                scenario_local_id=scenario_local_id,
                scenario_hash=scenario_hash,
                idempotency_key=idempotency_key,
                user_id=user_id,
                symbol=symbol,
                side=side,
                timeframe=timeframe,
                is_testnet=is_testnet,
                confidence_raw=confidence_raw,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

            # Set execution data
            if execution:
                outcome_record.execution_data = execution
                fields_updated.append("execution")

            # Set outcome data
            if outcome:
                self._apply_outcome_data(outcome_record, outcome)
                fields_updated.append("outcome")

            # Set attribution data
            if attribution:
                self._apply_attribution_data(outcome_record, attribution)
                fields_updated.append("attribution")

            # Set scenario snapshot
            if scenario_snapshot:
                outcome_record.scenario_snapshot = scenario_snapshot
                fields_updated.append("scenario_snapshot")

            session.add(outcome_record)

        await session.commit()

        # Check if learning should be triggered
        learning_triggered = await self._check_learning_trigger(session, is_testnet)

        return {
            "success": True,
            "duplicate": duplicate,
            "fields_updated": fields_updated,
            "learning_triggered": learning_triggered,
        }

    async def _get_by_trade_id(
        self,
        session: AsyncSession,
        trade_id: str
    ) -> Optional[TradeOutcome]:
        """Get TradeOutcome by trade_id."""
        stmt = select(TradeOutcome).where(TradeOutcome.trade_id == trade_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _update_outcome(
        self,
        session: AsyncSession,
        outcome: TradeOutcome,
        execution: Optional[Dict[str, Any]],
        outcome_data: Optional[Dict[str, Any]],
        attribution: Optional[Dict[str, Any]],
        scenario_snapshot: Optional[Dict[str, Any]],
        idempotency_key: str,
    ) -> List[str]:
        """Update existing outcome with new data (merge)."""
        fields_updated = []

        # Update idempotency key
        outcome.idempotency_key = idempotency_key
        outcome.updated_at = datetime.now(UTC)

        # Merge execution
        if execution:
            if outcome.execution_data:
                outcome.execution_data = {**outcome.execution_data, **execution}
            else:
                outcome.execution_data = execution
            fields_updated.append("execution")

        # Merge outcome
        if outcome_data:
            self._apply_outcome_data(outcome, outcome_data)
            fields_updated.append("outcome")

        # Merge attribution
        if attribution:
            self._apply_attribution_data(outcome, attribution)
            fields_updated.append("attribution")

        # Merge scenario snapshot
        if scenario_snapshot:
            if outcome.scenario_snapshot:
                outcome.scenario_snapshot = {**outcome.scenario_snapshot, **scenario_snapshot}
            else:
                outcome.scenario_snapshot = scenario_snapshot
            fields_updated.append("scenario_snapshot")

        return fields_updated

    def _apply_outcome_data(
        self,
        outcome: TradeOutcome,
        data: Dict[str, Any]
    ):
        """Apply outcome report data to TradeOutcome model."""
        outcome.exit_reason = data.get("exit_reason")
        outcome.exit_price = data.get("exit_price")

        # Parse exit_timestamp
        exit_ts = data.get("exit_timestamp")
        if exit_ts:
            try:
                if isinstance(exit_ts, str):
                    outcome.exit_timestamp = datetime.fromisoformat(
                        exit_ts.replace("Z", "+00:00")
                    )
                else:
                    outcome.exit_timestamp = exit_ts
            except Exception:
                pass

        outcome.pnl_usd = data.get("pnl_usd", 0)
        outcome.pnl_r = data.get("pnl_r", 0)
        outcome.roe_pct = data.get("roe_pct", 0)
        outcome.mae_r = data.get("mae_r", 0)
        outcome.mfe_r = data.get("mfe_r", 0)
        outcome.mae_usd = data.get("mae_usd", 0)
        outcome.mfe_usd = data.get("mfe_usd", 0)
        outcome.capture_efficiency = data.get("capture_efficiency", 0)
        outcome.time_in_trade_min = data.get("time_in_trade_min", 0)
        outcome.time_to_mfe_min = data.get("time_to_mfe_min")
        outcome.time_to_mae_min = data.get("time_to_mae_min")
        outcome.post_sl_mfe_r = data.get("post_sl_mfe_r")

        # Map label
        label = data.get("label", "breakeven")
        if hasattr(TradeOutcomeLabel, label.upper()):
            outcome.label = getattr(TradeOutcomeLabel, label.upper())
        else:
            outcome.label = TradeOutcomeLabel.BREAKEVEN

    def _apply_attribution_data(
        self,
        outcome: TradeOutcome,
        data: Dict[str, Any]
    ):
        """Apply attribution data to TradeOutcome model."""
        outcome.primary_archetype = data.get("primary_archetype", "unknown")
        outcome.tags = data.get("tags", [])
        outcome.attribution_data = data

        # Map label
        label = data.get("label", "breakeven")
        if hasattr(TradeOutcomeLabel, label.upper()):
            outcome.label = getattr(TradeOutcomeLabel, label.upper())

    async def _check_learning_trigger(
        self,
        session: AsyncSession,
        is_testnet: bool
    ) -> bool:
        """
        Check if learning recalculation should be triggered.

        Returns True if new trades count crosses threshold.
        """
        if is_testnet:
            return False  # Don't trigger for testnet

        # Count non-testnet trades
        from sqlalchemy import func
        stmt = select(func.count()).select_from(TradeOutcome).where(
            TradeOutcome.is_testnet == False
        )
        result = await session.execute(stmt)
        count = result.scalar() or 0

        # Trigger every N trades
        return count > 0 and count % self.LEARNING_TRIGGER_THRESHOLD == 0

    async def get_confidence_buckets(
        self,
        session: AsyncSession
    ) -> List[ConfidenceBucket]:
        """Get all confidence buckets."""
        stmt = select(ConfidenceBucket).order_by(ConfidenceBucket.confidence_min)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_archetype_stats(
        self,
        session: AsyncSession,
        min_trades: int = 10,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> List[ArchetypeStats]:
        """Get archetype statistics with optional filters."""
        conditions = [ArchetypeStats.total_trades >= min_trades]

        if symbol:
            conditions.append(ArchetypeStats.symbol == symbol)
        if timeframe:
            conditions.append(ArchetypeStats.timeframe == timeframe)

        stmt = select(ArchetypeStats).where(
            and_(*conditions)
        ).order_by(ArchetypeStats.profit_factor.desc())

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_trade_outcomes(
        self,
        session: AsyncSession,
        user_id: Optional[int] = None,
        symbol: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TradeOutcome]:
        """Get trade outcomes with filters."""
        conditions = []

        if user_id:
            conditions.append(TradeOutcome.user_id == user_id)
        if symbol:
            conditions.append(TradeOutcome.symbol == symbol)

        stmt = select(TradeOutcome)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(
            TradeOutcome.created_at.desc()
        ).limit(limit).offset(offset)

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_calibration_offset(
        self,
        session: AsyncSession,
        confidence_raw: float
    ) -> float:
        """
        Get calibration offset for a given raw confidence.

        Returns offset to apply: calibrated = raw + offset
        """
        # Find the bucket
        stmt = select(ConfidenceBucket).where(
            and_(
                ConfidenceBucket.confidence_min <= confidence_raw,
                ConfidenceBucket.confidence_max > confidence_raw
            )
        )
        result = await session.execute(stmt)
        bucket = result.scalar_one_or_none()

        if bucket and bucket.sample_size >= 20:  # Minimum sample size
            return bucket.calibration_offset

        return 0.0  # No calibration if insufficient data


# Singleton instance
feedback_service = FeedbackService()
