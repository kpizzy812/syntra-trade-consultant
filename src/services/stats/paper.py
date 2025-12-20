"""
Paper Trading Stats - статистика forward test / paper trading.

Использует данные из:
- ForwardTestOutcome (если есть)
- ScenarioClassStats.paper_* поля

Следует контракту из плана ancient-shimmying-pizza.md.
"""

import statistics
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ScenarioClassStats
from src.services.stats.schemas import (
    TradingOverviewResponse,
    ConfidenceInterval,
    FiltersApplied,
    StreaksInfo,
    ByOriginStats,
    OriginStats,
)
from src.services.stats.trading import (
    parse_period,
    calculate_winrate_ci,
)


# =============================================================================
# Paper Trading Overview
# =============================================================================


async def get_paper_overview(
    session: AsyncSession,
    period: str = "90d",
    from_ts: Optional[int] = None,
    to_ts: Optional[int] = None,
    archetype: Optional[str] = None,
) -> TradingOverviewResponse:
    """Get paper trading overview statistics.

    Aggregates from ScenarioClassStats.paper_* fields.
    """

    from_dt, to_dt = parse_period(period, from_ts, to_ts)
    warnings: list[str] = []

    # Build query for ScenarioClassStats with paper data
    conditions = [
        ScenarioClassStats.last_calculated_at >= from_dt,
        ScenarioClassStats.paper_entered > 0,  # Has paper trades
    ]

    if archetype:
        conditions.append(ScenarioClassStats.archetype == archetype)

    stmt = select(ScenarioClassStats).where(and_(*conditions))
    result = await session.execute(stmt)
    stats_list = list(result.scalars().all())

    now_ts = int(datetime.now(timezone.utc).timestamp())

    # Aggregate paper stats
    total_entered = sum(s.paper_entered or 0 for s in stats_list)
    total_wins = sum(s.paper_wins or 0 for s in stats_list)
    total_losses = sum(s.paper_losses or 0 for s in stats_list)

    if total_entered == 0:
        warnings.append("filter_empty")
        return TradingOverviewResponse(
            period=period,
            from_ts=int(from_dt.timestamp()),
            to_ts=int(to_dt.timestamp()),
            sample_size=0,
            filters_applied=FiltersApplied(archetype=archetype, origin="forward_test"),
            winrate=0.0,
            expectancy_r=0.0,
            net_pnl_usd=0.0,
            fees_usd=0.0,
            max_drawdown_r=0.0,
            streaks=StreaksInfo(),
            by_origin=ByOriginStats(
                forward_test=OriginStats(count=0, winrate=0.0, expectancy_r=0.0)
            ),
            generated_at_ts=now_ts,
            warnings=warnings,
        )

    # Calculate metrics
    winrate = total_wins / total_entered if total_entered > 0 else 0.0

    # Weighted average expectancy
    weighted_ev_sum = sum(
        (s.paper_avg_pnl_r or 0.0) * (s.paper_entered or 0)
        for s in stats_list
    )
    expectancy_r = weighted_ev_sum / total_entered if total_entered > 0 else 0.0

    # CI
    winrate_ci = calculate_winrate_ci(total_wins, total_entered)
    if winrate_ci is None and total_entered >= 30:
        warnings.append("ci_unavailable_skewed")
    elif winrate_ci is None:
        warnings.append("ci_unavailable_sample_lt_30")

    # Profit factor from aggregated stats
    # Estimate from win/loss ratio and typical R values
    if total_losses > 0:
        # Assuming avg win = 1.5R, avg loss = -1R
        profit_factor = round((total_wins * 1.5) / (total_losses * 1.0), 2)
    else:
        profit_factor = None

    return TradingOverviewResponse(
        period=period,
        from_ts=int(from_dt.timestamp()),
        to_ts=int(to_dt.timestamp()),
        sample_size=total_entered,
        filters_applied=FiltersApplied(archetype=archetype, origin="forward_test"),
        winrate=round(winrate, 4),
        winrate_ci=winrate_ci,
        expectancy_r=round(expectancy_r, 4),
        profit_factor=profit_factor,
        net_pnl_usd=0.0,  # Paper trading - no real PnL
        fees_usd=0.0,
        avg_mae_r=None,  # Not tracked in paper
        avg_mfe_r=None,
        max_drawdown_r=0.0,  # Would need trade-by-trade data
        sharpe_ratio=None,
        streaks=StreaksInfo(),  # Would need trade-by-trade data
        by_origin=ByOriginStats(
            forward_test=OriginStats(
                count=total_entered,
                winrate=round(winrate, 4),
                expectancy_r=round(expectancy_r, 4),
            )
        ),
        generated_at_ts=now_ts,
        warnings=warnings,
    )


# =============================================================================
# Paper Archetypes Comparison
# =============================================================================


async def get_paper_archetypes(
    session: AsyncSession,
    period: str = "90d",
    from_ts: Optional[int] = None,
    to_ts: Optional[int] = None,
    min_sample: int = 10,
) -> list[dict]:
    """Get paper trading stats per archetype.

    Returns list of archetypes with paper vs real comparison.
    """

    from_dt, to_dt = parse_period(period, from_ts, to_ts)

    # Get stats with paper data
    stmt = (
        select(ScenarioClassStats)
        .where(
            and_(
                ScenarioClassStats.last_calculated_at >= from_dt,
                ScenarioClassStats.paper_entered >= min_sample,
            )
        )
        .order_by(ScenarioClassStats.paper_entered.desc())
    )

    result = await session.execute(stmt)
    stats_list = result.scalars().all()

    archetypes = []
    for stats in stats_list:
        paper_wr = stats.paper_wins / stats.paper_entered if stats.paper_entered > 0 else 0
        real_wr = stats.winrate if stats.total_trades > 0 else 0

        archetypes.append({
            "archetype": stats.archetype,
            "paper": {
                "sample_size": stats.paper_entered,
                "winrate": round(paper_wr, 4),
                "expectancy_r": round(stats.paper_avg_pnl_r or 0.0, 4),
            },
            "real": {
                "sample_size": stats.total_trades,
                "winrate": round(real_wr, 4),
                "expectancy_r": round(stats.avg_pnl_r or 0.0, 4),
            },
            "delta": {
                "winrate": round(real_wr - paper_wr, 4),
                "expectancy_r": round((stats.avg_pnl_r or 0.0) - (stats.paper_avg_pnl_r or 0.0), 4),
            },
        })

    return archetypes
