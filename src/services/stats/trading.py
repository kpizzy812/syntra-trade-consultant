"""
Trading Stats - агрегации из TradeOutcome для Stats API.

Реализует:
- Trading Overview (winrate, expectancy, PF, drawdown, etc.)
- Outcomes Distribution (exit types breakdown)
- Symbols Stats (per-symbol performance)

Следует формулам из плана ancient-shimmying-pizza.md.
"""

import math
import statistics
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import TradeOutcome
from src.services.stats.schemas import (
    TradingOverviewResponse,
    OutcomesDistributionResponse,
    SymbolsStatsResponse,
    ConfidenceInterval,
    FiltersApplied,
    StreaksInfo,
    OriginStats,
    ByOriginStats,
    DefinitionsContract,
    OutcomeTypeStats,
    OutcomesDistribution,
    HitRates,
    CategoryStats,
    ByCategory,
    SymbolStats,
)


# =============================================================================
# Period Parsing
# =============================================================================


def parse_period(
    period: Optional[str],
    from_ts: Optional[int],
    to_ts: Optional[int],
) -> tuple[datetime, datetime]:
    """Parse period params into UTC datetime range.

    Returns: (from_dt, to_dt) where to_dt is EXCLUSIVE.
    Query: from_dt <= closed_at < to_dt
    """
    now = datetime.now(timezone.utc)

    # Explicit timestamps override period
    if from_ts is not None and to_ts is not None:
        from_dt = datetime.fromtimestamp(from_ts, tz=timezone.utc)
        to_dt = datetime.fromtimestamp(to_ts, tz=timezone.utc)
        return from_dt, to_dt

    # Period shorthand
    period_map = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "180d": timedelta(days=180),
        "365d": timedelta(days=365),
        "all": None,  # No lower bound
    }

    if period not in period_map:
        period = "90d"  # Default

    delta = period_map[period]
    if delta is None:
        from_dt = datetime(2020, 1, 1, tzinfo=timezone.utc)
    else:
        from_dt = now - delta

    # to_ts is NOW (exclusive, будущие сделки не попадут)
    to_dt = now

    return from_dt, to_dt


# =============================================================================
# Statistical Calculations
# =============================================================================


def calculate_winrate_ci(
    wins: int,
    total: int,
    confidence: float = 0.95
) -> Optional[ConfidenceInterval]:
    """Wilson score interval для биномиальной доли.

    Returns None если:
    - total < 30
    - min(wins, losses) < 5 (слишком skewed)
    """
    if total < 30:
        return None

    losses = total - wins
    if min(wins, losses) < 5:
        return None  # Слишком skewed

    try:
        from scipy import stats as scipy_stats
        p = wins / total
        z = scipy_stats.norm.ppf((1 + confidence) / 2)
        z2 = z * z

        # Wilson score formula
        denominator = 1 + z2 / total
        center = (p + z2 / (2 * total)) / denominator
        margin = (z / denominator) * math.sqrt(
            p * (1 - p) / total + z2 / (4 * total * total)
        )

        return ConfidenceInterval(
            lower=round(max(0, center - margin), 4),
            upper=round(min(1, center + margin), 4)
        )
    except ImportError:
        # scipy not available, skip CI
        return None


def calculate_expectancy_ci(
    r_values: list[float],
    confidence: float = 0.95
) -> Optional[ConfidenceInterval]:
    """t-interval для среднего R per trade."""
    n = len(r_values)
    if n < 30:
        return None

    try:
        from scipy import stats as scipy_stats
        mean = statistics.mean(r_values)
        std = statistics.stdev(r_values)

        t_val = scipy_stats.t.ppf((1 + confidence) / 2, n - 1)
        margin = t_val * (std / math.sqrt(n))

        return ConfidenceInterval(
            lower=round(mean - margin, 4),
            upper=round(mean + margin, 4)
        )
    except ImportError:
        return None


def calculate_sharpe(r_values: list[float]) -> Optional[float]:
    """Sharpe ratio по R per trade (без annualization).

    Definition: sharpe = mean(R) / std(R)
    НЕ annualized — это "per trade" Sharpe.
    """
    if len(r_values) < 30:
        return None

    try:
        mean_r = statistics.mean(r_values)
        std_r = statistics.stdev(r_values)

        if std_r == 0:
            return None  # Все сделки одинаковые

        return round(mean_r / std_r, 3)
    except (statistics.StatisticsError, ZeroDivisionError):
        return None


def calculate_profit_factor(r_values: list[float]) -> Optional[float]:
    """Profit Factor с правильной обработкой edge cases.

    Returns None если нет losses (division by zero).
    """
    wins = [r for r in r_values if r > 0]  # Строго > 0
    losses = [r for r in r_values if r < 0]  # Строго < 0 (не включаем 0!)

    sum_wins = sum(wins)
    sum_losses = abs(sum(losses))

    if sum_losses == 0:
        return None  # Нет лоссов → PF undefined

    return round(sum_wins / sum_losses, 2)


def calculate_max_drawdown_r(outcomes: list[TradeOutcome]) -> float:
    """Max drawdown по cumulative R.

    КРИТИЧНО: порядок по closed_at ASC!
    """
    if not outcomes:
        return 0.0

    # Сортируем по времени закрытия
    sorted_outcomes = sorted(outcomes, key=lambda o: o.closed_at or o.created_at)

    cumulative_r = 0.0
    peak = 0.0
    max_dd = 0.0

    for outcome in sorted_outcomes:
        r = outcome.pnl_r or 0.0
        cumulative_r += r
        peak = max(peak, cumulative_r)
        dd = peak - cumulative_r
        max_dd = max(max_dd, dd)

    return round(max_dd, 2)


def calculate_streaks(outcomes: list[TradeOutcome]) -> StreaksInfo:
    """Вычисляем win/loss streaks."""
    if not outcomes:
        return StreaksInfo()

    sorted_outcomes = sorted(outcomes, key=lambda o: o.closed_at or o.created_at)

    max_win = 0
    max_loss = 0
    current = 0
    current_type = None  # 'win' or 'loss'

    for outcome in sorted_outcomes:
        r = outcome.pnl_r or 0.0
        is_win = r > 0

        if is_win:
            if current_type == 'win':
                current += 1
            else:
                current = 1
                current_type = 'win'
            max_win = max(max_win, current)
        else:
            if current_type == 'loss':
                current += 1
            else:
                current = 1
                current_type = 'loss'
            max_loss = max(max_loss, current)

    # Current streak: positive for win, negative for loss
    final_current = current if current_type == 'win' else -current

    return StreaksInfo(
        max_win=max_win,
        max_loss=max_loss,
        current=final_current
    )


# =============================================================================
# Trading Overview
# =============================================================================


async def get_trading_overview(
    session: AsyncSession,
    period: str = "90d",
    from_ts: Optional[int] = None,
    to_ts: Optional[int] = None,
    symbol: Optional[str] = None,
    archetype: Optional[str] = None,
    origin: Optional[str] = None,
) -> TradingOverviewResponse:
    """Get trading overview statistics."""

    from_dt, to_dt = parse_period(period, from_ts, to_ts)
    warnings: list[str] = []

    # Build query
    conditions = [
        TradeOutcome.closed_at >= from_dt,
        TradeOutcome.closed_at < to_dt,
        TradeOutcome.invalidated == False,  # noqa: E712
        TradeOutcome.is_testnet == False,  # noqa: E712
    ]

    if symbol:
        conditions.append(TradeOutcome.symbol == symbol)
    if archetype:
        conditions.append(TradeOutcome.primary_archetype == archetype)
    if origin:
        conditions.append(TradeOutcome.origin == origin)

    # Fetch outcomes
    stmt = select(TradeOutcome).where(and_(*conditions))
    result = await session.execute(stmt)
    outcomes = list(result.scalars().all())

    sample_size = len(outcomes)
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # Empty result handling
    if sample_size == 0:
        warnings.append("filter_empty")
        return TradingOverviewResponse(
            period=period,
            from_ts=int(from_dt.timestamp()),
            to_ts=int(to_dt.timestamp()),
            sample_size=0,
            filters_applied=FiltersApplied(symbol=symbol, archetype=archetype, origin=origin),
            winrate=0.0,
            expectancy_r=0.0,
            net_pnl_usd=0.0,
            fees_usd=0.0,
            max_drawdown_r=0.0,
            streaks=StreaksInfo(),
            by_origin=ByOriginStats(),
            generated_at_ts=now_ts,
            warnings=warnings,
        )

    # Extract R values
    r_values = [o.pnl_r for o in outcomes if o.pnl_r is not None]
    pnl_values = [o.pnl_usd for o in outcomes if o.pnl_usd is not None]
    fees_values = [o.fees_usd for o in outcomes if o.fees_usd is not None]
    mae_values = [o.mae_r for o in outcomes if o.mae_r is not None]
    mfe_values = [o.mfe_r for o in outcomes if o.mfe_r is not None]

    # Core metrics
    wins = sum(1 for r in r_values if r > 0)
    winrate = wins / len(r_values) if r_values else 0.0
    expectancy_r = statistics.mean(r_values) if r_values else 0.0
    net_pnl_usd = sum(pnl_values)
    total_fees = sum(fees_values)

    # CI calculations
    winrate_ci = calculate_winrate_ci(wins, len(r_values))
    if winrate_ci is None and sample_size >= 30:
        warnings.append("ci_unavailable_skewed")
    elif winrate_ci is None:
        warnings.append("ci_unavailable_sample_lt_30")

    # Risk metrics
    avg_mae_r = statistics.mean(mae_values) if mae_values else None
    avg_mfe_r = statistics.mean(mfe_values) if mfe_values else None
    max_drawdown_r = calculate_max_drawdown_r(outcomes)
    sharpe = calculate_sharpe(r_values)
    profit_factor = calculate_profit_factor(r_values)

    # Streaks
    streaks = calculate_streaks(outcomes)

    # By origin breakdown
    by_origin = ByOriginStats()
    for origin_val in ['ai_scenario', 'manual', 'copy_trade', 'forward_test']:
        origin_outcomes = [o for o in outcomes if o.origin == origin_val]
        if origin_outcomes:
            origin_r_values = [o.pnl_r for o in origin_outcomes if o.pnl_r is not None]
            if origin_r_values:
                origin_wins = sum(1 for r in origin_r_values if r > 0)
                origin_stats = OriginStats(
                    count=len(origin_outcomes),
                    winrate=round(origin_wins / len(origin_r_values), 4),
                    expectancy_r=round(statistics.mean(origin_r_values), 4)
                )
                setattr(by_origin, origin_val, origin_stats)

    return TradingOverviewResponse(
        period=period,
        from_ts=int(from_dt.timestamp()),
        to_ts=int(to_dt.timestamp()),
        sample_size=sample_size,
        filters_applied=FiltersApplied(symbol=symbol, archetype=archetype, origin=origin),
        winrate=round(winrate, 4),
        winrate_ci=winrate_ci,
        expectancy_r=round(expectancy_r, 4),
        profit_factor=profit_factor,
        net_pnl_usd=round(net_pnl_usd, 2),
        fees_usd=round(total_fees, 2),
        avg_mae_r=round(avg_mae_r, 4) if avg_mae_r else None,
        avg_mfe_r=round(avg_mfe_r, 4) if avg_mfe_r else None,
        max_drawdown_r=max_drawdown_r,
        sharpe_ratio=sharpe,
        streaks=streaks,
        by_origin=by_origin,
        generated_at_ts=now_ts,
        warnings=warnings,
    )


# =============================================================================
# Outcomes Distribution
# =============================================================================


async def get_outcomes_distribution(
    session: AsyncSession,
    period: str = "90d",
    from_ts: Optional[int] = None,
    to_ts: Optional[int] = None,
) -> OutcomesDistributionResponse:
    """Get outcomes distribution (exit types breakdown)."""

    from_dt, to_dt = parse_period(period, from_ts, to_ts)
    warnings: list[str] = []

    # Fetch outcomes
    stmt = select(TradeOutcome).where(
        and_(
            TradeOutcome.closed_at >= from_dt,
            TradeOutcome.closed_at < to_dt,
            TradeOutcome.invalidated == False,  # noqa: E712
            TradeOutcome.is_testnet == False,  # noqa: E712
        )
    )
    result = await session.execute(stmt)
    outcomes = list(result.scalars().all())

    sample_size = len(outcomes)
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # Helper to get stats for outcome type
    def get_outcome_stats(outcome_type: str) -> OutcomeTypeStats:
        filtered = [o for o in outcomes if o.terminal_outcome == outcome_type]
        count = len(filtered)
        pct = count / sample_size if sample_size > 0 else 0.0
        r_values = [o.pnl_r for o in filtered if o.pnl_r is not None]
        avg_r = round(statistics.mean(r_values), 2) if r_values else None
        return OutcomeTypeStats(count=count, pct=round(pct, 4), avg_r=avg_r)

    # Build distribution
    distribution = OutcomesDistribution(
        sl_early=get_outcome_stats("sl"),
        be_after_tp1=get_outcome_stats("be"),
        stop_in_profit=get_outcome_stats("stop_profit"),
        tp1_final=get_outcome_stats("tp1"),
        tp2_final=get_outcome_stats("tp2"),
        tp3_final=get_outcome_stats("tp3"),
        manual_close=get_outcome_stats("manual"),
        liquidation=get_outcome_stats("liquidation"),
        other=get_outcome_stats("other"),
    )

    # TP Hit Rates (from boolean fields)
    hit_tp1_count = sum(1 for o in outcomes if o.hit_tp1)
    hit_tp2_count = sum(1 for o in outcomes if o.hit_tp2)
    hit_tp3_count = sum(1 for o in outcomes if o.hit_tp3)

    hit_rates = HitRates(
        tp1=round(hit_tp1_count / sample_size, 4) if sample_size > 0 else None,
        tp2=round(hit_tp2_count / sample_size, 4) if sample_size > 0 else None,
        tp3=round(hit_tp3_count / sample_size, 4) if sample_size > 0 else None,
    )

    # By category
    loss_outcomes = [o for o in outcomes if o.terminal_outcome in ("sl", "liquidation")]
    be_outcomes = [o for o in outcomes if o.terminal_outcome == "be"]
    win_outcomes = [o for o in outcomes if o.pnl_r and o.pnl_r > 0 and o.terminal_outcome not in ("sl", "liquidation", "be")]

    by_category = ByCategory(
        losses=CategoryStats(
            count=len(loss_outcomes),
            pct=round(len(loss_outcomes) / sample_size, 4) if sample_size > 0 else 0.0
        ),
        breakeven=CategoryStats(
            count=len(be_outcomes),
            pct=round(len(be_outcomes) / sample_size, 4) if sample_size > 0 else 0.0
        ),
        wins=CategoryStats(
            count=len(win_outcomes),
            pct=round(len(win_outcomes) / sample_size, 4) if sample_size > 0 else 0.0
        ),
    )

    return OutcomesDistributionResponse(
        period=period,
        from_ts=int(from_dt.timestamp()),
        to_ts=int(to_dt.timestamp()),
        sample_size=sample_size,
        distribution=distribution,
        hit_rates=hit_rates,
        by_category=by_category,
        generated_at_ts=now_ts,
        warnings=warnings,
    )


# =============================================================================
# Symbols Stats
# =============================================================================


async def get_symbols_stats(
    session: AsyncSession,
    period: str = "90d",
    from_ts: Optional[int] = None,
    to_ts: Optional[int] = None,
) -> SymbolsStatsResponse:
    """Get per-symbol statistics."""

    from_dt, to_dt = parse_period(period, from_ts, to_ts)
    warnings: list[str] = []

    # Aggregate by symbol
    stmt = (
        select(
            TradeOutcome.symbol,
            func.count().label('count'),
            func.sum(case((TradeOutcome.pnl_r > 0, 1), else_=0)).label('wins'),
            func.avg(TradeOutcome.pnl_r).label('avg_r'),
            func.sum(TradeOutcome.pnl_usd).label('net_pnl'),
        )
        .where(
            and_(
                TradeOutcome.closed_at >= from_dt,
                TradeOutcome.closed_at < to_dt,
                TradeOutcome.invalidated == False,  # noqa: E712
                TradeOutcome.is_testnet == False,  # noqa: E712
            )
        )
        .group_by(TradeOutcome.symbol)
        .order_by(func.count().desc())
    )

    result = await session.execute(stmt)
    rows = result.all()

    symbols = []
    for row in rows:
        winrate = row.wins / row.count if row.count > 0 else 0.0
        symbols.append(SymbolStats(
            symbol=row.symbol,
            count=row.count,
            winrate=round(winrate, 4),
            expectancy_r=round(row.avg_r or 0.0, 4),
            net_pnl_usd=round(row.net_pnl or 0.0, 2),
        ))

    now_ts = int(datetime.now(timezone.utc).timestamp())

    return SymbolsStatsResponse(
        period=period,
        from_ts=int(from_dt.timestamp()),
        to_ts=int(to_dt.timestamp()),
        symbols=symbols,
        total_count=len(symbols),
        generated_at_ts=now_ts,
        warnings=warnings,
    )
