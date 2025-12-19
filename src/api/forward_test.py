"""
Forward Test API Endpoints

REST API для forward testing системы - paper trading с симуляцией.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from pydantic import BaseModel

from src.database.engine import get_session
from src.api.api_key_auth import verify_api_key
from src.services.forward_test.models import (
    ForwardTestSnapshot,
    ForwardTestMonitorState,
    ForwardTestEvent,
    ForwardTestOutcome,
)
from src.services.forward_test.enums import ScenarioState, OutcomeResult, PnLClass
from src.services.forward_test.config import get_config

router = APIRouter(prefix="/forward-test", tags=["Forward Testing"])


# =============================================================================
# Pydantic Models (Response Schemas)
# =============================================================================

class FunnelStats(BaseModel):
    """Conversion funnel статистика."""
    generated: int
    triggered: int
    entered: int
    finished: int
    trigger_rate: float
    entry_rate: float
    finish_rate: float


class PerformanceStats(BaseModel):
    """Performance метрики."""
    total_trades: int
    wins: int
    losses: int
    breakeven: int
    expired: int
    winrate: float
    avg_r: float
    total_r: float
    profit_factor: Optional[float]
    median_hold_time_sec: Optional[int]


class EVAccuracyStats(BaseModel):
    """EV accuracy метрики."""
    correlation: Optional[float]
    avg_predicted_ev: Optional[float]
    avg_realized_r: Optional[float]
    ev_delta: Optional[float]
    sample_size: int


class AlertItem(BaseModel):
    """Один алерт."""
    severity: str  # warning, critical
    type: str
    message: str
    value: Optional[float] = None


class DailyReportResponse(BaseModel):
    """Response для daily report."""
    date: str
    funnel: FunnelStats
    performance: PerformanceStats
    ev_accuracy: EVAccuracyStats
    best_archetype: Optional[Dict[str, Any]]
    worst_archetype: Optional[Dict[str, Any]]
    alerts: List[AlertItem]
    mae_p90: Optional[float]
    mfe_p90: Optional[float]
    max_dd_r: Optional[float]


class ScenarioListItem(BaseModel):
    """Элемент списка сценариев."""
    snapshot_id: str
    symbol: str
    timeframe: str
    bias: str
    archetype: str
    state: str
    confidence: float
    generated_at: str
    total_r: Optional[float] = None


class ScenarioDetailResponse(BaseModel):
    """Детали сценария."""
    snapshot: Dict[str, Any]
    monitor_state: Optional[Dict[str, Any]]
    events: List[Dict[str, Any]]
    outcome: Optional[Dict[str, Any]]


class BatchTriggerResponse(BaseModel):
    """Response для ручного batch."""
    batch_id: str
    symbols: List[str]
    snapshots_created: int
    started_at: str


# =============================================================================
# Helper Functions
# =============================================================================

async def _get_date_range(
    session: AsyncSession,
    target_date: Optional[date] = None,
    days: int = 1
) -> tuple[datetime, datetime]:
    """Получить datetime range для фильтрации."""
    if target_date is None:
        target_date = date.today()

    start_dt = datetime.combine(target_date - timedelta(days=days - 1), datetime.min.time())
    end_dt = datetime.combine(target_date, datetime.max.time())
    return start_dt, end_dt


async def _calculate_funnel(
    session: AsyncSession,
    start_dt: datetime,
    end_dt: datetime
) -> FunnelStats:
    """Рассчитать conversion funnel."""
    # Generated (all snapshots in period)
    generated_q = select(func.count()).select_from(ForwardTestSnapshot).where(
        and_(
            ForwardTestSnapshot.generated_at >= start_dt,
            ForwardTestSnapshot.generated_at <= end_dt
        )
    )
    generated = (await session.execute(generated_q)).scalar() or 0

    # Triggered (state >= triggered)
    triggered_q = select(func.count()).select_from(ForwardTestMonitorState).join(
        ForwardTestSnapshot,
        ForwardTestMonitorState.snapshot_id == ForwardTestSnapshot.snapshot_id
    ).where(
        and_(
            ForwardTestSnapshot.generated_at >= start_dt,
            ForwardTestSnapshot.generated_at <= end_dt,
            ForwardTestMonitorState.triggered_at.isnot(None)
        )
    )
    triggered = (await session.execute(triggered_q)).scalar() or 0

    # Entered (state >= entered)
    entered_q = select(func.count()).select_from(ForwardTestMonitorState).join(
        ForwardTestSnapshot,
        ForwardTestMonitorState.snapshot_id == ForwardTestSnapshot.snapshot_id
    ).where(
        and_(
            ForwardTestSnapshot.generated_at >= start_dt,
            ForwardTestSnapshot.generated_at <= end_dt,
            ForwardTestMonitorState.entered_at.isnot(None)
        )
    )
    entered = (await session.execute(entered_q)).scalar() or 0

    # Finished (has outcome)
    finished_q = select(func.count()).select_from(ForwardTestOutcome).join(
        ForwardTestSnapshot,
        ForwardTestOutcome.snapshot_id == ForwardTestSnapshot.snapshot_id
    ).where(
        and_(
            ForwardTestSnapshot.generated_at >= start_dt,
            ForwardTestSnapshot.generated_at <= end_dt
        )
    )
    finished = (await session.execute(finished_q)).scalar() or 0

    return FunnelStats(
        generated=generated,
        triggered=triggered,
        entered=entered,
        finished=finished,
        trigger_rate=round(triggered / generated * 100, 1) if generated > 0 else 0,
        entry_rate=round(entered / generated * 100, 1) if generated > 0 else 0,
        finish_rate=round(finished / entered * 100, 1) if entered > 0 else 0
    )


async def _calculate_performance(
    session: AsyncSession,
    start_dt: datetime,
    end_dt: datetime
) -> PerformanceStats:
    """Рассчитать performance метрики."""
    # Get outcomes in period
    outcomes_q = select(ForwardTestOutcome).join(
        ForwardTestSnapshot,
        ForwardTestOutcome.snapshot_id == ForwardTestSnapshot.snapshot_id
    ).where(
        and_(
            ForwardTestSnapshot.generated_at >= start_dt,
            ForwardTestSnapshot.generated_at <= end_dt
        )
    )
    result = await session.execute(outcomes_q)
    outcomes = result.scalars().all()

    if not outcomes:
        return PerformanceStats(
            total_trades=0, wins=0, losses=0, breakeven=0, expired=0,
            winrate=0, avg_r=0, total_r=0, profit_factor=None,
            median_hold_time_sec=None
        )

    wins = sum(1 for o in outcomes if o.result == OutcomeResult.WIN.value)
    losses = sum(1 for o in outcomes if o.result == OutcomeResult.LOSS.value)
    breakeven = sum(1 for o in outcomes if o.result == OutcomeResult.BREAKEVEN.value)
    expired = sum(1 for o in outcomes if o.result == OutcomeResult.EXPIRED.value)

    total_r = sum(o.total_r for o in outcomes)
    avg_r = total_r / len(outcomes) if outcomes else 0

    # Profit factor
    gross_profit = sum(o.total_r for o in outcomes if o.total_r > 0)
    gross_loss = abs(sum(o.total_r for o in outcomes if o.total_r < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    # Median hold time
    hold_times = [o.hold_time_sec for o in outcomes if o.hold_time_sec]
    median_hold = sorted(hold_times)[len(hold_times) // 2] if hold_times else None

    # Winrate (excluding expired)
    tradable = wins + losses + breakeven
    winrate = wins / tradable * 100 if tradable > 0 else 0

    return PerformanceStats(
        total_trades=len(outcomes),
        wins=wins,
        losses=losses,
        breakeven=breakeven,
        expired=expired,
        winrate=round(winrate, 1),
        avg_r=round(avg_r, 3),
        total_r=round(total_r, 2),
        profit_factor=round(profit_factor, 2) if profit_factor else None,
        median_hold_time_sec=median_hold
    )


async def _calculate_ev_accuracy(
    session: AsyncSession,
    start_dt: datetime,
    end_dt: datetime
) -> EVAccuracyStats:
    """Рассчитать EV accuracy."""
    # Get outcomes with snapshots (for ev_r)
    q = select(ForwardTestSnapshot, ForwardTestOutcome).join(
        ForwardTestOutcome,
        ForwardTestSnapshot.snapshot_id == ForwardTestOutcome.snapshot_id
    ).where(
        and_(
            ForwardTestSnapshot.generated_at >= start_dt,
            ForwardTestSnapshot.generated_at <= end_dt,
            ForwardTestSnapshot.ev_r.isnot(None)
        )
    )
    result = await session.execute(q)
    rows = result.all()

    if len(rows) < 5:
        return EVAccuracyStats(
            correlation=None,
            avg_predicted_ev=None,
            avg_realized_r=None,
            ev_delta=None,
            sample_size=len(rows)
        )

    predicted = [r[0].ev_r for r in rows]
    realized = [r[1].total_r for r in rows]

    # Calculate correlation
    n = len(predicted)
    mean_p = sum(predicted) / n
    mean_r = sum(realized) / n

    cov = sum((p - mean_p) * (r - mean_r) for p, r in zip(predicted, realized)) / n
    std_p = (sum((p - mean_p) ** 2 for p in predicted) / n) ** 0.5
    std_r = (sum((r - mean_r) ** 2 for r in realized) / n) ** 0.5

    correlation = cov / (std_p * std_r) if std_p > 0 and std_r > 0 else None

    return EVAccuracyStats(
        correlation=round(correlation, 3) if correlation else None,
        avg_predicted_ev=round(mean_p, 3),
        avg_realized_r=round(mean_r, 3),
        ev_delta=round(mean_r - mean_p, 3),
        sample_size=n
    )


async def _get_archetype_stats(
    session: AsyncSession,
    start_dt: datetime,
    end_dt: datetime,
    best: bool = True
) -> Optional[Dict[str, Any]]:
    """Получить лучший/худший архетип по avg_r."""
    q = select(
        ForwardTestSnapshot.archetype,
        func.count().label('count'),
        func.avg(ForwardTestOutcome.total_r).label('avg_r')
    ).join(
        ForwardTestOutcome,
        ForwardTestSnapshot.snapshot_id == ForwardTestOutcome.snapshot_id
    ).where(
        and_(
            ForwardTestSnapshot.generated_at >= start_dt,
            ForwardTestSnapshot.generated_at <= end_dt
        )
    ).group_by(ForwardTestSnapshot.archetype).having(func.count() >= 3)

    if best:
        q = q.order_by(desc('avg_r'))
    else:
        q = q.order_by('avg_r')

    q = q.limit(1)

    result = await session.execute(q)
    row = result.first()

    if not row:
        return None

    return {
        "archetype": row[0],
        "count": row[1],
        "avg_r": round(row[2], 3)
    }


async def _generate_alerts(
    session: AsyncSession,
    start_dt: datetime,
    end_dt: datetime,
    performance: PerformanceStats,
    ev_accuracy: EVAccuracyStats
) -> List[AlertItem]:
    """Сгенерировать алерты на основе метрик."""
    alerts = []

    # Low winrate alert
    if performance.total_trades >= 10 and performance.winrate < 40:
        alerts.append(AlertItem(
            severity="warning",
            type="low_winrate",
            message=f"Low winrate: {performance.winrate}% (n={performance.total_trades})",
            value=performance.winrate
        ))

    # Negative avg R alert
    if performance.total_trades >= 10 and performance.avg_r < -0.1:
        alerts.append(AlertItem(
            severity="critical",
            type="negative_edge",
            message=f"Negative edge: avg_r={performance.avg_r}R",
            value=performance.avg_r
        ))

    # Poor EV correlation
    if ev_accuracy.correlation is not None and ev_accuracy.correlation < 0.1:
        alerts.append(AlertItem(
            severity="warning",
            type="ev_drift",
            message=f"Poor EV accuracy: corr={ev_accuracy.correlation}",
            value=ev_accuracy.correlation
        ))

    # High expiration rate
    if performance.total_trades > 0:
        exp_rate = performance.expired / performance.total_trades
        if exp_rate > 0.3:
            alerts.append(AlertItem(
                severity="warning",
                type="high_expiration",
                message=f"High expiration rate: {exp_rate * 100:.0f}%",
                value=exp_rate
            ))

    return alerts


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/report/daily")
async def get_daily_report(
    target_date: Optional[date] = Query(None, description="Target date (YYYY-MM-DD), defaults to today"),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key),
) -> DailyReportResponse:
    """
    Получить daily report для Telegram/UI.

    Включает:
    - Conversion funnel (generated → triggered → entered → finished)
    - Performance metrics (WR, avg_r, total_r, profit_factor)
    - EV accuracy (correlation, delta)
    - Best/worst archetypes
    - Alerts (low WR, negative edge, EV drift)
    """
    start_dt, end_dt = await _get_date_range(session, target_date)

    funnel = await _calculate_funnel(session, start_dt, end_dt)
    performance = await _calculate_performance(session, start_dt, end_dt)
    ev_accuracy = await _calculate_ev_accuracy(session, start_dt, end_dt)
    best_arch = await _get_archetype_stats(session, start_dt, end_dt, best=True)
    worst_arch = await _get_archetype_stats(session, start_dt, end_dt, best=False)
    alerts = await _generate_alerts(session, start_dt, end_dt, performance, ev_accuracy)

    # MAE/MFE p90
    outcomes_q = select(ForwardTestOutcome.mae_r, ForwardTestOutcome.mfe_r).join(
        ForwardTestSnapshot,
        ForwardTestOutcome.snapshot_id == ForwardTestSnapshot.snapshot_id
    ).where(
        and_(
            ForwardTestSnapshot.generated_at >= start_dt,
            ForwardTestSnapshot.generated_at <= end_dt
        )
    )
    result = await session.execute(outcomes_q)
    mae_mfe = result.all()

    mae_values = sorted([r[0] for r in mae_mfe if r[0] is not None])
    mfe_values = sorted([r[1] for r in mae_mfe if r[1] is not None])

    mae_p90 = mae_values[int(len(mae_values) * 0.9)] if mae_values else None
    mfe_p90 = mfe_values[int(len(mfe_values) * 0.9)] if mfe_values else None

    return DailyReportResponse(
        date=target_date.isoformat() if target_date else date.today().isoformat(),
        funnel=funnel,
        performance=performance,
        ev_accuracy=ev_accuracy,
        best_archetype=best_arch,
        worst_archetype=worst_arch,
        alerts=alerts,
        mae_p90=round(mae_p90, 3) if mae_p90 else None,
        mfe_p90=round(mfe_p90, 3) if mfe_p90 else None,
        max_dd_r=None  # TODO: implement cumulative DD
    )


@router.get("/dashboard")
async def get_dashboard(
    days: int = Query(7, ge=1, le=90, description="Number of days"),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Получить dashboard метрики за N дней.
    """
    start_dt, end_dt = await _get_date_range(session, days=days)

    funnel = await _calculate_funnel(session, start_dt, end_dt)
    performance = await _calculate_performance(session, start_dt, end_dt)
    ev_accuracy = await _calculate_ev_accuracy(session, start_dt, end_dt)

    return {
        "period_days": days,
        "funnel": funnel.model_dump(),
        "performance": performance.model_dump(),
        "ev_accuracy": ev_accuracy.model_dump(),
        "config": {
            "symbols": get_config().universe.symbols,
            "timeframes": get_config().universe.timeframes,
            "modes": get_config().universe.modes,
        }
    }


@router.get("/scenarios")
async def list_scenarios(
    state: Optional[str] = Query(None, description="Filter by state"),
    archetype: Optional[str] = Query(None, description="Filter by archetype"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    batch_id: Optional[str] = Query(None, description="Filter by batch_id"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Получить список сценариев с фильтрами.
    """
    q = select(ForwardTestSnapshot, ForwardTestMonitorState, ForwardTestOutcome).outerjoin(
        ForwardTestMonitorState,
        ForwardTestSnapshot.snapshot_id == ForwardTestMonitorState.snapshot_id
    ).outerjoin(
        ForwardTestOutcome,
        ForwardTestSnapshot.snapshot_id == ForwardTestOutcome.snapshot_id
    )

    # Apply filters
    conditions = []
    if archetype:
        conditions.append(ForwardTestSnapshot.archetype == archetype)
    if symbol:
        conditions.append(ForwardTestSnapshot.symbol == symbol)
    if batch_id:
        conditions.append(ForwardTestSnapshot.batch_id == batch_id)
    if state:
        conditions.append(ForwardTestMonitorState.state == state)

    if conditions:
        q = q.where(and_(*conditions))

    q = q.order_by(desc(ForwardTestSnapshot.generated_at)).offset(offset).limit(limit)

    result = await session.execute(q)
    rows = result.all()

    items = []
    for snapshot, monitor, outcome in rows:
        items.append(ScenarioListItem(
            snapshot_id=snapshot.snapshot_id,
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            bias=snapshot.bias,
            archetype=snapshot.archetype,
            state=monitor.state if monitor else "unknown",
            confidence=snapshot.confidence,
            generated_at=snapshot.generated_at.isoformat(),
            total_r=outcome.total_r if outcome else None
        ).model_dump())

    return {
        "items": items,
        "total": len(items),
        "limit": limit,
        "offset": offset
    }


@router.get("/scenarios/{snapshot_id}")
async def get_scenario_detail(
    snapshot_id: str,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key),
) -> ScenarioDetailResponse:
    """
    Получить детали сценария + события + outcome.
    """
    # Snapshot
    snapshot_q = select(ForwardTestSnapshot).where(
        ForwardTestSnapshot.snapshot_id == snapshot_id
    )
    snapshot_result = await session.execute(snapshot_q)
    snapshot = snapshot_result.scalar_one_or_none()

    if not snapshot:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Monitor state
    monitor_q = select(ForwardTestMonitorState).where(
        ForwardTestMonitorState.snapshot_id == snapshot_id
    )
    monitor_result = await session.execute(monitor_q)
    monitor = monitor_result.scalar_one_or_none()

    # Events
    events_q = select(ForwardTestEvent).where(
        ForwardTestEvent.snapshot_id == snapshot_id
    ).order_by(ForwardTestEvent.ts)
    events_result = await session.execute(events_q)
    events = events_result.scalars().all()

    # Outcome
    outcome_q = select(ForwardTestOutcome).where(
        ForwardTestOutcome.snapshot_id == snapshot_id
    )
    outcome_result = await session.execute(outcome_q)
    outcome = outcome_result.scalar_one_or_none()

    return ScenarioDetailResponse(
        snapshot={
            "snapshot_id": snapshot.snapshot_id,
            "batch_id": snapshot.batch_id,
            "symbol": snapshot.symbol,
            "timeframe": snapshot.timeframe,
            "mode": snapshot.mode,
            "bias": snapshot.bias,
            "archetype": snapshot.archetype,
            "confidence": snapshot.confidence,
            "ev_r": snapshot.ev_r,
            "entry_price_avg": snapshot.entry_price_avg,
            "stop_loss": snapshot.stop_loss,
            "tp1_price": snapshot.tp1_price,
            "tp2_price": snapshot.tp2_price,
            "tp3_price": snapshot.tp3_price,
            "be_after_tp1": snapshot.be_after_tp1,
            "current_price": snapshot.current_price,
            "generated_at": snapshot.generated_at.isoformat(),
            "expires_at": snapshot.expires_at.isoformat(),
            "version_hash": snapshot.version_hash,
            "prompt_version": snapshot.prompt_version,
        },
        monitor_state={
            "state": monitor.state,
            "state_updated_at": monitor.state_updated_at.isoformat(),
            "triggered_at": monitor.triggered_at.isoformat() if monitor.triggered_at else None,
            "entered_at": monitor.entered_at.isoformat() if monitor.entered_at else None,
            "tp1_hit_at": monitor.tp1_hit_at.isoformat() if monitor.tp1_hit_at else None,
            "exit_at": monitor.exit_at.isoformat() if monitor.exit_at else None,
            "avg_entry_price": monitor.avg_entry_price,
            "fill_pct": monitor.fill_pct,
            "initial_sl": monitor.initial_sl,
            "current_sl": monitor.current_sl,
            "sl_moved_to_be": monitor.sl_moved_to_be,
            "tp_progress": monitor.tp_progress,
            "realized_r_so_far": monitor.realized_r_so_far,
            "remaining_position_pct": monitor.remaining_position_pct,
            "mae_r": monitor.mae_r,
            "mfe_r": monitor.mfe_r,
        } if monitor else None,
        events=[
            {
                "ts": e.ts.isoformat(),
                "event_type": e.event_type,
                "price": e.price,
                "details": e.details_json
            }
            for e in events
        ],
        outcome={
            "result": outcome.result,
            "terminal_state": outcome.terminal_state,
            "is_profit": outcome.is_profit,
            "pnl_class": outcome.pnl_class,
            "total_r": outcome.total_r,
            "realized_r_from_tp1": outcome.realized_r_from_tp1,
            "remaining_r": outcome.remaining_r,
            "fill_pct_at_exit": outcome.fill_pct_at_exit,
            "mae_r": outcome.mae_r,
            "mfe_r": outcome.mfe_r,
            "time_to_trigger_sec": outcome.time_to_trigger_sec,
            "time_to_entry_sec": outcome.time_to_entry_sec,
            "hold_time_sec": outcome.hold_time_sec,
            "created_at": outcome.created_at.isoformat(),
        } if outcome else None
    )


@router.get("/performance")
async def get_performance_breakdown(
    days: int = Query(30, ge=1, le=180),
    group_by: str = Query("archetype", description="Group by: archetype, symbol, bias"),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Performance breakdown по группам.
    """
    start_dt, end_dt = await _get_date_range(session, days=days)

    # Determine grouping column
    if group_by == "symbol":
        group_col = ForwardTestSnapshot.symbol
    elif group_by == "bias":
        group_col = ForwardTestSnapshot.bias
    else:
        group_col = ForwardTestSnapshot.archetype

    q = select(
        group_col.label('group_key'),
        func.count().label('count'),
        func.avg(ForwardTestOutcome.total_r).label('avg_r'),
        func.sum(ForwardTestOutcome.total_r).label('total_r'),
        func.sum(
            func.cast(ForwardTestOutcome.result == OutcomeResult.WIN.value, sa.Integer)
        ).label('wins'),
    ).select_from(ForwardTestSnapshot).join(
        ForwardTestOutcome,
        ForwardTestSnapshot.snapshot_id == ForwardTestOutcome.snapshot_id
    ).where(
        and_(
            ForwardTestSnapshot.generated_at >= start_dt,
            ForwardTestSnapshot.generated_at <= end_dt
        )
    ).group_by(group_col).order_by(desc('avg_r'))

    # Need to import sa for cast
    import sqlalchemy as sa

    result = await session.execute(q)
    rows = result.all()

    breakdown = []
    for row in rows:
        count = row[1]
        wins = row[4] or 0
        breakdown.append({
            "key": row[0],
            "count": count,
            "avg_r": round(row[2], 3) if row[2] else 0,
            "total_r": round(row[3], 2) if row[3] else 0,
            "winrate": round(wins / count * 100, 1) if count > 0 else 0
        })

    return {
        "period_days": days,
        "group_by": group_by,
        "breakdown": breakdown
    }


@router.get("/ev-accuracy")
async def get_ev_accuracy_detail(
    days: int = Query(30, ge=1, le=180),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Детальный анализ EV accuracy.
    """
    start_dt, end_dt = await _get_date_range(session, days=days)

    overall = await _calculate_ev_accuracy(session, start_dt, end_dt)

    # By archetype
    archetypes_q = select(ForwardTestSnapshot.archetype).distinct()
    archetypes_result = await session.execute(archetypes_q)
    archetypes = [r[0] for r in archetypes_result.all()]

    by_archetype = {}
    for arch in archetypes[:10]:  # Limit to 10
        q = select(ForwardTestSnapshot.ev_r, ForwardTestOutcome.total_r).join(
            ForwardTestOutcome,
            ForwardTestSnapshot.snapshot_id == ForwardTestOutcome.snapshot_id
        ).where(
            and_(
                ForwardTestSnapshot.generated_at >= start_dt,
                ForwardTestSnapshot.generated_at <= end_dt,
                ForwardTestSnapshot.archetype == arch,
                ForwardTestSnapshot.ev_r.isnot(None)
            )
        )
        result = await session.execute(q)
        rows = result.all()

        if len(rows) >= 3:
            predicted = [r[0] for r in rows]
            realized = [r[1] for r in rows]
            by_archetype[arch] = {
                "sample_size": len(rows),
                "avg_predicted": round(sum(predicted) / len(predicted), 3),
                "avg_realized": round(sum(realized) / len(realized), 3),
            }

    return {
        "period_days": days,
        "overall": overall.model_dump(),
        "by_archetype": by_archetype
    }


@router.get("/alerts")
async def get_active_alerts(
    days: int = Query(7, ge=1, le=30),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Получить активные алерты.
    """
    start_dt, end_dt = await _get_date_range(session, days=days)

    performance = await _calculate_performance(session, start_dt, end_dt)
    ev_accuracy = await _calculate_ev_accuracy(session, start_dt, end_dt)
    alerts = await _generate_alerts(session, start_dt, end_dt, performance, ev_accuracy)

    return {
        "period_days": days,
        "alerts": [a.model_dump() for a in alerts],
        "total_alerts": len(alerts),
        "critical_count": sum(1 for a in alerts if a.severity == "critical"),
        "warning_count": sum(1 for a in alerts if a.severity == "warning")
    }


@router.post("/trigger-batch")
async def trigger_manual_batch(
    symbols: Optional[List[str]] = Query(None, description="Symbols to generate (default: all)"),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key),
) -> BatchTriggerResponse:
    """
    Ручной запуск генерации batch (для тестов).
    """
    from src.services.forward_test.snapshot_service import SnapshotService

    config = get_config()
    target_symbols = symbols or config.universe.symbols

    snapshot_service = SnapshotService()
    batch_result = await snapshot_service.generate_batch(session, symbols=target_symbols)

    return BatchTriggerResponse(
        batch_id=batch_result.batch_id,
        symbols=target_symbols,
        snapshots_created=batch_result.snapshots_created,
        started_at=batch_result.started_at.isoformat()
    )


@router.get("/batches")
async def list_batches(
    days: int = Query(7, ge=1, le=30),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """
    Список последних batch генераций.
    """
    start_dt, end_dt = await _get_date_range(session, days=days)

    q = select(
        ForwardTestSnapshot.batch_id,
        ForwardTestSnapshot.batch_ts,
        ForwardTestSnapshot.batch_scope,
        func.count().label('count')
    ).where(
        and_(
            ForwardTestSnapshot.generated_at >= start_dt,
            ForwardTestSnapshot.generated_at <= end_dt
        )
    ).group_by(
        ForwardTestSnapshot.batch_id,
        ForwardTestSnapshot.batch_ts,
        ForwardTestSnapshot.batch_scope
    ).order_by(desc(ForwardTestSnapshot.batch_ts))

    result = await session.execute(q)
    rows = result.all()

    batches = []
    for row in rows:
        batches.append({
            "batch_id": row[0],
            "batch_ts": row[1].isoformat(),
            "batch_scope": row[2],
            "scenarios_count": row[3]
        })

    return {
        "period_days": days,
        "batches": batches,
        "total_batches": len(batches)
    }
