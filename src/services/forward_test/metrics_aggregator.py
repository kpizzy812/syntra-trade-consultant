"""
Metrics Aggregator

Расчёт агрегированных метрик для forward testing.
"""
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, UTC
from typing import List, Dict, Optional, Any
import statistics

from loguru import logger
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.forward_test.enums import OutcomeResult, PnLClass, TerminalState
from src.services.forward_test.models import (
    ForwardTestSnapshot,
    ForwardTestMonitorState,
    ForwardTestOutcome,
)
from src.services.forward_test.epoch_manager import get_current_epoch


@dataclass
class ConversionFunnel:
    """Conversion funnel метрики."""
    generated: int = 0
    triggered: int = 0
    entered: int = 0
    finished: int = 0

    @property
    def trigger_rate(self) -> float:
        return self.triggered / self.generated if self.generated > 0 else 0

    @property
    def entry_rate(self) -> float:
        return self.entered / self.generated if self.generated > 0 else 0

    @property
    def finish_rate(self) -> float:
        return self.finished / self.entered if self.entered > 0 else 0


@dataclass
class PerformanceMetrics:
    """Performance метрики."""
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    expired: int = 0
    total_r: float = 0.0
    avg_r: float = 0.0
    median_r: float = 0.0
    profit_factor: float = 0.0
    winrate: float = 0.0


@dataclass
class EVAccuracy:
    """EV accuracy метрики."""
    correlation: float = 0.0  # corr(predicted_ev, realized_r)
    mean_predicted_ev: float = 0.0
    mean_realized_r: float = 0.0
    delta: float = 0.0  # realized - predicted
    count: int = 0


@dataclass
class CalibrationBucket:
    """Один бакет calibration curve."""
    predicted_conf_low: float
    predicted_conf_high: float
    mean_predicted_conf: float = 0.0
    realized_winrate: float = 0.0
    count: int = 0


@dataclass
class CalibrationCurve:
    """Calibration curve метрики."""
    buckets: List[CalibrationBucket] = field(default_factory=list)
    ece: float = 0.0  # Expected Calibration Error
    mce: float = 0.0  # Max Calibration Error
    brier_score: float = 0.0


@dataclass
class EdgeDecomposition:
    """Edge decomposition метрики."""
    generation_contribution_r: float = 0.0
    levels_contribution_r: float = 0.0
    timing_contribution_r: float = 0.0
    execution_drag_r: float = 0.0
    total_edge_r: float = 0.0


@dataclass
class DrawdownMetrics:
    """Drawdown метрики."""
    max_dd_r: float = 0.0
    mae_p50: float = 0.0
    mae_p90: float = 0.0
    mfe_p50: float = 0.0
    mfe_p90: float = 0.0


@dataclass
class LoserReport:
    """Report по лузерам."""
    archetype: str
    avg_r: float
    count: int
    winrate: float


@dataclass
class DailyMetrics:
    """Дневные метрики."""
    date: date
    funnel: ConversionFunnel
    performance: PerformanceMetrics
    ev_accuracy: EVAccuracy
    calibration: CalibrationCurve
    edge: EdgeDecomposition
    drawdown: DrawdownMetrics
    top_archetypes: List[Dict[str, Any]] = field(default_factory=list)
    worst_archetypes: List[Dict[str, Any]] = field(default_factory=list)
    alerts: List[str] = field(default_factory=list)


class MetricsAggregator:
    """Расчёт агрегированных метрик."""

    async def calculate_daily(
        self,
        session: AsyncSession,
        target_date: Optional[date] = None
    ) -> DailyMetrics:
        """
        Рассчитать метрики за день.

        Args:
            session: DB session
            target_date: Дата для расчёта (по умолчанию - вчера)

        Returns:
            DailyMetrics
        """
        if target_date is None:
            target_date = (datetime.now(UTC) - timedelta(days=1)).date()

        current_epoch = await get_current_epoch()
        start_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=UTC)
        end_dt = start_dt + timedelta(days=1)

        # Получить snapshots за день (filter by current epoch)
        snapshots_query = select(ForwardTestSnapshot).where(
            and_(
                ForwardTestSnapshot.epoch == current_epoch,
                ForwardTestSnapshot.generated_at >= start_dt,
                ForwardTestSnapshot.generated_at < end_dt
            )
        )
        snapshots_result = await session.execute(snapshots_query)
        snapshots = list(snapshots_result.scalars().all())

        # Получить outcomes за день
        outcomes_query = select(ForwardTestOutcome).where(
            and_(
                ForwardTestOutcome.created_at >= start_dt,
                ForwardTestOutcome.created_at < end_dt
            )
        )
        outcomes_result = await session.execute(outcomes_query)
        outcomes = list(outcomes_result.scalars().all())

        # Получить monitor states для snapshots
        snapshot_ids = [s.snapshot_id for s in snapshots]
        states_query = select(ForwardTestMonitorState).where(
            ForwardTestMonitorState.snapshot_id.in_(snapshot_ids)
        ) if snapshot_ids else select(ForwardTestMonitorState).where(False)
        states_result = await session.execute(states_query)
        states = list(states_result.scalars().all())

        # Рассчитать метрики
        funnel = self._calculate_funnel(snapshots, states, outcomes)
        performance = self._calculate_performance(outcomes)
        ev_accuracy = await self._calculate_ev_accuracy(session, snapshots, outcomes)
        calibration = self._calculate_calibration(snapshots, outcomes)
        edge = self._calculate_edge_decomposition(snapshots, outcomes)
        drawdown = self._calculate_drawdown(outcomes)

        # Top/Worst archetypes
        top_archetypes, worst_archetypes = await self._get_archetype_performance(
            session, start_dt, end_dt
        )

        # Alerts
        alerts = self._generate_alerts(funnel, performance, ev_accuracy, outcomes)

        return DailyMetrics(
            date=target_date,
            funnel=funnel,
            performance=performance,
            ev_accuracy=ev_accuracy,
            calibration=calibration,
            edge=edge,
            drawdown=drawdown,
            top_archetypes=top_archetypes,
            worst_archetypes=worst_archetypes,
            alerts=alerts
        )

    def _calculate_funnel(
        self,
        snapshots: List[ForwardTestSnapshot],
        states: List[ForwardTestMonitorState],
        outcomes: List[ForwardTestOutcome]
    ) -> ConversionFunnel:
        """Рассчитать conversion funnel."""
        generated = len(snapshots)
        triggered = sum(1 for s in states if s.triggered_at is not None)
        entered = sum(1 for s in states if s.entered_at is not None)
        finished = len(outcomes)

        return ConversionFunnel(
            generated=generated,
            triggered=triggered,
            entered=entered,
            finished=finished
        )

    def _calculate_performance(
        self,
        outcomes: List[ForwardTestOutcome]
    ) -> PerformanceMetrics:
        """Рассчитать performance метрики."""
        if not outcomes:
            return PerformanceMetrics()

        total = len(outcomes)
        wins = sum(1 for o in outcomes if o.result == OutcomeResult.WIN)
        losses = sum(1 for o in outcomes if o.result == OutcomeResult.LOSS)
        breakeven = sum(1 for o in outcomes if o.result == OutcomeResult.BREAKEVEN)
        expired = sum(1 for o in outcomes if o.result == OutcomeResult.EXPIRED)

        r_values = [o.total_r for o in outcomes]
        total_r = sum(r_values)
        avg_r = statistics.mean(r_values) if r_values else 0
        median_r = statistics.median(r_values) if r_values else 0

        # Profit factor
        gross_profit = sum(o.total_r for o in outcomes if o.total_r > 0)
        gross_loss = abs(sum(o.total_r for o in outcomes if o.total_r < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Winrate (без expired)
        closed_trades = wins + losses + breakeven
        winrate = wins / closed_trades if closed_trades > 0 else 0

        return PerformanceMetrics(
            total_trades=total,
            wins=wins,
            losses=losses,
            breakeven=breakeven,
            expired=expired,
            total_r=total_r,
            avg_r=avg_r,
            median_r=median_r,
            profit_factor=profit_factor if profit_factor != float('inf') else 999.99,
            winrate=winrate
        )

    async def _calculate_ev_accuracy(
        self,
        session: AsyncSession,
        snapshots: List[ForwardTestSnapshot],
        outcomes: List[ForwardTestOutcome]
    ) -> EVAccuracy:
        """Рассчитать EV accuracy."""
        # Создать маппинг snapshot_id → ev_r
        ev_map = {s.snapshot_id: s.ev_r for s in snapshots if s.ev_r is not None}

        pairs = []
        for o in outcomes:
            predicted_ev = ev_map.get(o.snapshot_id)
            if predicted_ev is not None:
                pairs.append((predicted_ev, o.total_r))

        if len(pairs) < 5:
            return EVAccuracy(count=len(pairs))

        predicted = [p[0] for p in pairs]
        realized = [p[1] for p in pairs]

        mean_pred = statistics.mean(predicted)
        mean_real = statistics.mean(realized)

        # Pearson correlation
        try:
            n = len(pairs)
            sum_xy = sum(p * r for p, r in pairs)
            sum_x = sum(predicted)
            sum_y = sum(realized)
            sum_x2 = sum(p ** 2 for p in predicted)
            sum_y2 = sum(r ** 2 for r in realized)

            numerator = n * sum_xy - sum_x * sum_y
            denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5

            correlation = numerator / denominator if denominator > 0 else 0
        except Exception:
            correlation = 0

        return EVAccuracy(
            correlation=correlation,
            mean_predicted_ev=mean_pred,
            mean_realized_r=mean_real,
            delta=mean_real - mean_pred,
            count=len(pairs)
        )

    def _calculate_calibration(
        self,
        snapshots: List[ForwardTestSnapshot],
        outcomes: List[ForwardTestOutcome]
    ) -> CalibrationCurve:
        """Рассчитать calibration curve."""
        # Создать маппинг snapshot_id → confidence
        conf_map = {s.snapshot_id: s.confidence for s in snapshots}

        # Собрать пары (confidence, is_win)
        pairs = []
        for o in outcomes:
            conf = conf_map.get(o.snapshot_id)
            if conf is not None and o.result != OutcomeResult.EXPIRED:
                is_win = 1 if o.is_profit else 0
                pairs.append((conf, is_win))

        if not pairs:
            return CalibrationCurve()

        # Создать бакеты (0-0.2, 0.2-0.4, ...)
        bucket_edges = [(i * 0.2, (i + 1) * 0.2) for i in range(5)]
        buckets = []

        for low, high in bucket_edges:
            bucket_pairs = [(c, w) for c, w in pairs if low <= c < high]
            if bucket_pairs:
                mean_conf = statistics.mean([c for c, w in bucket_pairs])
                realized_wr = statistics.mean([w for c, w in bucket_pairs])
                buckets.append(CalibrationBucket(
                    predicted_conf_low=low,
                    predicted_conf_high=high,
                    mean_predicted_conf=mean_conf,
                    realized_winrate=realized_wr,
                    count=len(bucket_pairs)
                ))

        # ECE и MCE
        calibration_errors = []
        for b in buckets:
            error = abs(b.mean_predicted_conf - b.realized_winrate)
            calibration_errors.append((error, b.count))

        if calibration_errors:
            total_count = sum(c for _, c in calibration_errors)
            ece = sum(e * c for e, c in calibration_errors) / total_count if total_count > 0 else 0
            mce = max(e for e, _ in calibration_errors)
        else:
            ece = 0
            mce = 0

        # Brier score
        brier = statistics.mean((c - w) ** 2 for c, w in pairs) if pairs else 0

        return CalibrationCurve(
            buckets=buckets,
            ece=ece,
            mce=mce,
            brier_score=brier
        )

    def _calculate_edge_decomposition(
        self,
        snapshots: List[ForwardTestSnapshot],
        outcomes: List[ForwardTestOutcome]
    ) -> EdgeDecomposition:
        """Рассчитать edge decomposition."""
        if not outcomes:
            return EdgeDecomposition()

        # Создать маппинг
        snapshot_map = {s.snapshot_id: s for s in snapshots}

        # Группировка по архетипам
        by_archetype: Dict[str, List[float]] = {}
        for o in outcomes:
            s = snapshot_map.get(o.snapshot_id)
            if s:
                arch = s.archetype
                if arch not in by_archetype:
                    by_archetype[arch] = []
                by_archetype[arch].append(o.total_r)

        # Generation quality: variance explained by archetype
        archetype_means = {a: statistics.mean(rs) for a, rs in by_archetype.items() if rs}
        overall_mean = statistics.mean([o.total_r for o in outcomes])

        generation_contribution = sum(
            len(rs) * (archetype_means.get(a, 0) - overall_mean) ** 2
            for a, rs in by_archetype.items()
        ) / len(outcomes) if outcomes else 0

        # Simplified: total edge = avg R
        total_edge = overall_mean

        return EdgeDecomposition(
            generation_contribution_r=generation_contribution ** 0.5 if generation_contribution > 0 else 0,
            levels_contribution_r=0,  # TODO: implement
            timing_contribution_r=0,  # TODO: implement
            execution_drag_r=0,  # TODO: implement
            total_edge_r=total_edge
        )

    def _calculate_drawdown(
        self,
        outcomes: List[ForwardTestOutcome]
    ) -> DrawdownMetrics:
        """Рассчитать drawdown метрики."""
        if not outcomes:
            return DrawdownMetrics()

        # Cumulative R curve
        sorted_outcomes = sorted(outcomes, key=lambda o: o.created_at)
        cumulative = 0
        peak = 0
        max_dd = 0

        for o in sorted_outcomes:
            cumulative += o.total_r
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd

        # MAE/MFE percentiles
        mae_values = [o.mae_r for o in outcomes if o.mae_r is not None]
        mfe_values = [o.mfe_r for o in outcomes if o.mfe_r is not None]

        def percentile(values, p):
            if not values:
                return 0
            sorted_v = sorted(values)
            idx = int(len(sorted_v) * p / 100)
            return sorted_v[min(idx, len(sorted_v) - 1)]

        return DrawdownMetrics(
            max_dd_r=max_dd,
            mae_p50=percentile(mae_values, 50),
            mae_p90=percentile(mae_values, 90),
            mfe_p50=percentile(mfe_values, 50),
            mfe_p90=percentile(mfe_values, 90)
        )

    async def _get_archetype_performance(
        self,
        session: AsyncSession,
        start_dt: datetime,
        end_dt: datetime
    ) -> tuple:
        """Получить top/worst archetypes."""
        # Join outcomes с snapshots
        query = (
            select(
                ForwardTestSnapshot.archetype,
                func.count(ForwardTestOutcome.id).label("count"),
                func.avg(ForwardTestOutcome.total_r).label("avg_r"),
                func.sum(
                    func.cast(ForwardTestOutcome.is_profit, Integer)
                ).label("wins")
            )
            .join(
                ForwardTestOutcome,
                ForwardTestSnapshot.snapshot_id == ForwardTestOutcome.snapshot_id
            )
            .where(
                and_(
                    ForwardTestOutcome.created_at >= start_dt,
                    ForwardTestOutcome.created_at < end_dt
                )
            )
            .group_by(ForwardTestSnapshot.archetype)
            .having(func.count(ForwardTestOutcome.id) >= 3)
        )

        try:
            result = await session.execute(query)
            rows = result.all()
        except Exception as e:
            logger.error(f"Failed to get archetype performance: {e}")
            return [], []

        archetypes = []
        for row in rows:
            archetypes.append({
                "archetype": row.archetype,
                "count": row.count,
                "avg_r": float(row.avg_r) if row.avg_r else 0,
                "winrate": row.wins / row.count if row.count > 0 else 0
            })

        # Sort by avg_r
        sorted_archetypes = sorted(archetypes, key=lambda x: x["avg_r"], reverse=True)

        top_5 = sorted_archetypes[:5]
        worst_5 = sorted_archetypes[-5:][::-1] if len(sorted_archetypes) >= 5 else []

        return top_5, worst_5

    def _generate_alerts(
        self,
        funnel: ConversionFunnel,
        performance: PerformanceMetrics,
        ev_accuracy: EVAccuracy,
        outcomes: List[ForwardTestOutcome]
    ) -> List[str]:
        """Генерировать alerts."""
        alerts = []

        # Entry too far
        if funnel.entry_rate < 0.3:
            alerts.append(f"Entry too far: {funnel.entry_rate:.0%} entry rate")

        # SL too tight
        sl_hits_fast = sum(
            1 for o in outcomes
            if o.terminal_state == TerminalState.SL
            and o.hold_time_sec is not None
            and o.hold_time_sec < 1800  # 30 min
        )
        if sl_hits_fast > 5:
            alerts.append(f"SL too tight: {sl_hits_fast} SL hits < 30min")

        # EV drift
        if ev_accuracy.count >= 10 and ev_accuracy.correlation < 0.1:
            alerts.append(f"EV drift: correlation={ev_accuracy.correlation:.2f}")

        # Low winrate
        if performance.winrate < 0.4 and performance.total_trades >= 10:
            alerts.append(f"Low winrate: {performance.winrate:.0%}")

        return alerts


# Для совместимости с import Integer
from sqlalchemy import Integer

# Singleton
metrics_aggregator = MetricsAggregator()
