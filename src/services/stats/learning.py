"""
Learning Stats - статистика по архетипам и gates.

Использует данные из:
- TradeOutcome (агрегация по primary_archetype)
- ScenarioClassStats (если есть)
- ArchetypeStats (если есть)

Следует контракту из плана ancient-shimmying-pizza.md.
"""

import statistics
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import TradeOutcome, ArchetypeStats, ScenarioClassStats
from src.services.stats.schemas import (
    ArchetypeListResponse,
    ArchetypeDetailResponse,
    GateStatusResponse,
    ArchetypeListItem,
    ConfidenceInterval,
    PaperComparison,
    OutcomesBreakdown,
)
from src.services.stats.trading import (
    parse_period,
    calculate_winrate_ci,
    calculate_expectancy_ci,
    calculate_profit_factor,
    calculate_max_drawdown_r,
)


# =============================================================================
# Archetype List
# =============================================================================


async def get_archetypes_list(
    session: AsyncSession,
    period: str = "90d",
    from_ts: Optional[int] = None,
    to_ts: Optional[int] = None,
    min_sample: int = 10,
    page: int = 0,
    page_size: int = 20,
) -> ArchetypeListResponse:
    """Get list of archetypes with basic stats."""

    from_dt, to_dt = parse_period(period, from_ts, to_ts)
    warnings: list[str] = []

    # Aggregate by archetype
    stmt = (
        select(
            TradeOutcome.primary_archetype,
            func.count().label('count'),
            func.sum(func.cast(TradeOutcome.pnl_r > 0, type_=func.INTEGER())).label('wins'),
            func.avg(TradeOutcome.pnl_r).label('avg_r'),
        )
        .where(
            and_(
                TradeOutcome.closed_at >= from_dt,
                TradeOutcome.closed_at < to_dt,
                TradeOutcome.invalidated == False,  # noqa: E712
                TradeOutcome.is_testnet == False,  # noqa: E712
                TradeOutcome.primary_archetype.isnot(None),
            )
        )
        .group_by(TradeOutcome.primary_archetype)
        .having(func.count() >= min_sample)
        .order_by(func.count().desc())
    )

    result = await session.execute(stmt)
    rows = result.all()

    # Build list items
    archetypes: list[ArchetypeListItem] = []
    for row in rows:
        winrate = (row.wins or 0) / row.count if row.count > 0 else 0.0
        expectancy = row.avg_r or 0.0

        # Determine gate status based on metrics
        gate_status = "enabled"
        if winrate < 0.4 or expectancy < -0.2:
            gate_status = "disabled"
        elif winrate < 0.5 or expectancy < 0:
            gate_status = "warning"

        archetypes.append(ArchetypeListItem(
            archetype=row.primary_archetype,
            sample_size=row.count,
            winrate=round(winrate, 4),
            expectancy_r=round(expectancy, 4),
            profit_factor=None,  # Computed in detail view
            gate_status=gate_status,
        ))

    # Pagination
    total_count = len(archetypes)
    start_idx = page * page_size
    end_idx = start_idx + page_size
    paginated = archetypes[start_idx:end_idx]

    now_ts = int(datetime.now(timezone.utc).timestamp())

    return ArchetypeListResponse(
        period=period,
        from_ts=int(from_dt.timestamp()),
        to_ts=int(to_dt.timestamp()),
        archetypes=paginated,
        total_count=total_count,
        page=page,
        page_size=page_size,
        generated_at_ts=now_ts,
        warnings=warnings,
    )


# =============================================================================
# Archetype Detail
# =============================================================================


async def get_archetype_detail(
    session: AsyncSession,
    archetype: str,
    period: str = "90d",
    from_ts: Optional[int] = None,
    to_ts: Optional[int] = None,
) -> Optional[ArchetypeDetailResponse]:
    """Get detailed stats for a specific archetype."""

    from_dt, to_dt = parse_period(period, from_ts, to_ts)
    warnings: list[str] = []

    # Fetch outcomes for this archetype
    stmt = select(TradeOutcome).where(
        and_(
            TradeOutcome.closed_at >= from_dt,
            TradeOutcome.closed_at < to_dt,
            TradeOutcome.invalidated == False,  # noqa: E712
            TradeOutcome.is_testnet == False,  # noqa: E712
            TradeOutcome.primary_archetype == archetype,
        )
    )
    result = await session.execute(stmt)
    outcomes = list(result.scalars().all())

    if not outcomes:
        return None

    sample_size = len(outcomes)
    r_values = [o.pnl_r for o in outcomes if o.pnl_r is not None]

    # Core metrics
    wins = sum(1 for r in r_values if r > 0)
    winrate = wins / len(r_values) if r_values else 0.0
    expectancy = statistics.mean(r_values) if r_values else 0.0

    # CI
    winrate_ci = calculate_winrate_ci(wins, len(r_values))
    expectancy_ci = calculate_expectancy_ci(r_values)

    if winrate_ci is None and sample_size >= 30:
        warnings.append("ci_unavailable_skewed")

    # Risk metrics
    profit_factor = calculate_profit_factor(r_values)
    max_drawdown = calculate_max_drawdown_r(outcomes)

    # Gate status
    gate_status = "enabled"
    gate_reason = None
    if winrate < 0.4:
        gate_status = "disabled"
        gate_reason = f"Low winrate: {winrate:.1%}"
    elif expectancy < -0.2:
        gate_status = "disabled"
        gate_reason = f"Negative expectancy: {expectancy:.2f}R"
    elif winrate < 0.5 or expectancy < 0:
        gate_status = "warning"
        gate_reason = "Borderline performance"

    # Outcomes breakdown
    def get_pct(outcome_type: str) -> float:
        count = sum(1 for o in outcomes if o.terminal_outcome == outcome_type)
        return round(count / sample_size, 4) if sample_size > 0 else 0.0

    outcomes_breakdown = OutcomesBreakdown(
        sl_early=get_pct("sl"),
        tp1_final=get_pct("tp1"),
        tp2_final=get_pct("tp2"),
        tp3_final=get_pct("tp3"),
        other=round(1.0 - get_pct("sl") - get_pct("tp1") - get_pct("tp2") - get_pct("tp3"), 4),
    )

    # Try to get paper comparison from ScenarioClassStats
    paper = None
    try:
        paper_stmt = select(ScenarioClassStats).where(
            ScenarioClassStats.archetype == archetype
        ).order_by(ScenarioClassStats.last_calculated_at.desc()).limit(1)
        paper_result = await session.execute(paper_stmt)
        paper_stats = paper_result.scalar_one_or_none()

        if paper_stats and paper_stats.paper_entered and paper_stats.paper_entered > 0:
            paper_wr = paper_stats.paper_wins / paper_stats.paper_entered if paper_stats.paper_entered > 0 else 0
            paper_ev = paper_stats.paper_avg_pnl_r or 0.0
            paper = PaperComparison(
                sample_size=paper_stats.paper_entered,
                winrate=round(paper_wr, 4),
                expectancy_r=round(paper_ev, 4),
            )
    except Exception:
        pass  # Paper stats not available

    now_ts = int(datetime.now(timezone.utc).timestamp())

    return ArchetypeDetailResponse(
        archetype=archetype,
        period=period,
        from_ts=int(from_dt.timestamp()),
        to_ts=int(to_dt.timestamp()),
        sample_size=sample_size,
        winrate=round(winrate, 4),
        winrate_ci=winrate_ci,
        expectancy_r=round(expectancy, 4),
        expectancy_ci=expectancy_ci,
        profit_factor=profit_factor,
        max_drawdown_r=max_drawdown,
        gate_status=gate_status,
        gate_reason=gate_reason,
        paper=paper,
        conversion_rate=None,  # Computed from funnel data
        outcomes=outcomes_breakdown,
        generated_at_ts=now_ts,
        warnings=warnings,
    )


# =============================================================================
# Gates Status
# =============================================================================


async def get_gates_status(
    session: AsyncSession,
) -> list[GateStatusResponse]:
    """Get status of all EV gates."""

    # Get latest ScenarioClassStats for each archetype
    subquery = (
        select(
            ScenarioClassStats.archetype,
            func.max(ScenarioClassStats.last_calculated_at).label('latest')
        )
        .group_by(ScenarioClassStats.archetype)
        .subquery()
    )

    stmt = (
        select(ScenarioClassStats)
        .join(
            subquery,
            and_(
                ScenarioClassStats.archetype == subquery.c.archetype,
                ScenarioClassStats.last_calculated_at == subquery.c.latest
            )
        )
        .order_by(ScenarioClassStats.archetype)
    )

    result = await session.execute(stmt)
    stats_list = result.scalars().all()

    gates: list[GateStatusResponse] = []
    for stats in stats_list:
        gate_status = "enabled" if stats.is_enabled else "disabled"
        if stats.preliminary_warning:
            gate_status = "warning"

        gates.append(GateStatusResponse(
            archetype=stats.archetype,
            gate_status=gate_status,
            gate_reason=stats.disable_reason or stats.preliminary_warning,
            sample_size=stats.total_trades,
            winrate=round(stats.winrate, 4),
            expectancy_r=round(stats.avg_ev_r, 4),
            disabled_until=stats.disabled_until,
        ))

    return gates
