"""
Stats API - REST endpoints для статистики.

Endpoints:
    GET /api/stats/trading/overview     - Trading overview
    GET /api/stats/trading/outcomes     - Outcomes distribution
    GET /api/stats/trading/symbols      - Per-symbol stats
    GET /api/stats/learning/archetypes  - Archetypes list
    GET /api/stats/learning/archetypes/{archetype} - Archetype detail
    GET /api/stats/learning/gates       - EV gates status
    GET /api/stats/paper/overview       - Paper trading overview
    GET /api/stats/paper/archetypes     - Paper vs real comparison
    GET /api/stats/conversion           - Conversion funnel

Auth: X-API-Key header (SYNTRA_STATS_API_KEY)
"""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.database.engine import get_session
from src.services.stats import StatsService
from src.services.stats.schemas import (
    TradingOverviewResponse,
    OutcomesDistributionResponse,
    SymbolsStatsResponse,
    ArchetypeListResponse,
    ArchetypeDetailResponse,
    GateStatusResponse,
    ConversionFunnelResponse,
    PaperArchetypesResponse,
)


router = APIRouter(prefix="/stats", tags=["Stats"])

# Stats API Key (read-only)
SYNTRA_STATS_API_KEY = os.getenv("SYNTRA_STATS_API_KEY", "")


# =============================================================================
# Auth
# =============================================================================


async def verify_stats_api_key(
    x_api_key: Optional[str] = Header(None, description="Stats API key")
) -> str:
    """Verify Stats API key (read-only access)."""
    if not x_api_key:
        logger.warning("Stats API key missing in request")
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide X-API-Key header."
        )

    if not SYNTRA_STATS_API_KEY:
        logger.error("SYNTRA_STATS_API_KEY not configured")
        raise HTTPException(
            status_code=500,
            detail="Stats API key not configured"
        )

    if x_api_key != SYNTRA_STATS_API_KEY:
        logger.warning("Invalid stats API key")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return x_api_key


# =============================================================================
# Trading Stats
# =============================================================================


@router.get(
    "/trading/overview",
    response_model=TradingOverviewResponse,
    summary="Get trading overview",
    description="Returns key trading metrics: winrate, expectancy, PF, drawdown, streaks"
)
async def get_trading_overview(
    period: str = Query("90d", description="Period: 7d, 30d, 90d, 180d, 365d, all"),
    from_ts: Optional[int] = Query(None, description="Start timestamp (overrides period)"),
    to_ts: Optional[int] = Query(None, description="End timestamp (overrides period)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    archetype: Optional[str] = Query(None, description="Filter by archetype"),
    origin: Optional[str] = Query(None, description="Filter by origin: ai_scenario, manual"),
    session: AsyncSession = Depends(get_session),
    _api_key: str = Depends(verify_stats_api_key),
):
    """Get trading overview statistics."""
    try:
        stats = StatsService(session)
        return await stats.get_trading_overview(
            period=period,
            from_ts=from_ts,
            to_ts=to_ts,
            symbol=symbol,
            archetype=archetype,
            origin=origin,
        )
    except Exception as e:
        logger.error(f"Error getting trading overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/trading/outcomes",
    response_model=OutcomesDistributionResponse,
    summary="Get outcomes distribution",
    description="Returns exit types breakdown and TP hit rates"
)
async def get_outcomes_distribution(
    period: str = Query("90d", description="Period"),
    from_ts: Optional[int] = Query(None),
    to_ts: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
    _api_key: str = Depends(verify_stats_api_key),
):
    """Get outcomes distribution."""
    try:
        stats = StatsService(session)
        return await stats.get_outcomes_distribution(
            period=period,
            from_ts=from_ts,
            to_ts=to_ts,
        )
    except Exception as e:
        logger.error(f"Error getting outcomes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/trading/symbols",
    response_model=SymbolsStatsResponse,
    summary="Get per-symbol stats",
    description="Returns performance breakdown by trading symbol"
)
async def get_symbols_stats(
    period: str = Query("90d", description="Period"),
    from_ts: Optional[int] = Query(None),
    to_ts: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
    _api_key: str = Depends(verify_stats_api_key),
):
    """Get per-symbol statistics."""
    try:
        stats = StatsService(session)
        return await stats.get_symbols_stats(
            period=period,
            from_ts=from_ts,
            to_ts=to_ts,
        )
    except Exception as e:
        logger.error(f"Error getting symbols stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Learning Stats
# =============================================================================


@router.get(
    "/learning/archetypes",
    response_model=ArchetypeListResponse,
    summary="Get archetypes list",
    description="Returns paginated list of archetypes with stats"
)
async def get_archetypes_list(
    period: str = Query("90d", description="Period"),
    from_ts: Optional[int] = Query(None),
    to_ts: Optional[int] = Query(None),
    min_sample: int = Query(10, description="Minimum sample size"),
    page: int = Query(0, ge=0, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_session),
    _api_key: str = Depends(verify_stats_api_key),
):
    """Get list of archetypes with stats."""
    try:
        stats = StatsService(session)
        return await stats.get_archetypes(
            period=period,
            from_ts=from_ts,
            to_ts=to_ts,
            min_sample=min_sample,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        logger.error(f"Error getting archetypes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/learning/archetypes/{archetype}",
    response_model=ArchetypeDetailResponse,
    summary="Get archetype detail",
    description="Returns detailed stats for a specific archetype"
)
async def get_archetype_detail(
    archetype: str,
    period: str = Query("90d", description="Period"),
    from_ts: Optional[int] = Query(None),
    to_ts: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
    _api_key: str = Depends(verify_stats_api_key),
):
    """Get detailed stats for an archetype."""
    try:
        stats = StatsService(session)
        result = await stats.get_archetype_detail(
            archetype=archetype,
            period=period,
            from_ts=from_ts,
            to_ts=to_ts,
        )
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Archetype '{archetype}' not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting archetype detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/learning/gates",
    response_model=list[GateStatusResponse],
    summary="Get EV gates status",
    description="Returns status of all EV gates (enabled/warning/disabled)"
)
async def get_gates_status(
    session: AsyncSession = Depends(get_session),
    _api_key: str = Depends(verify_stats_api_key),
):
    """Get status of all EV gates."""
    try:
        stats = StatsService(session)
        return await stats.get_gates_status()
    except Exception as e:
        logger.error(f"Error getting gates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Paper Trading Stats
# =============================================================================


@router.get(
    "/paper/overview",
    response_model=TradingOverviewResponse,
    summary="Get paper trading overview",
    description="Returns paper trading (forward test) statistics"
)
async def get_paper_overview(
    period: str = Query("90d", description="Period"),
    from_ts: Optional[int] = Query(None),
    to_ts: Optional[int] = Query(None),
    archetype: Optional[str] = Query(None, description="Filter by archetype"),
    session: AsyncSession = Depends(get_session),
    _api_key: str = Depends(verify_stats_api_key),
):
    """Get paper trading overview."""
    try:
        stats = StatsService(session)
        return await stats.get_paper_overview(
            period=period,
            from_ts=from_ts,
            to_ts=to_ts,
            archetype=archetype,
        )
    except Exception as e:
        logger.error(f"Error getting paper overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/paper/archetypes",
    summary="Get paper vs real comparison",
    description="Returns paper vs real trading comparison by archetype"
)
async def get_paper_archetypes(
    period: str = Query("90d", description="Period"),
    from_ts: Optional[int] = Query(None),
    to_ts: Optional[int] = Query(None),
    min_sample: int = Query(10, description="Minimum paper trades"),
    session: AsyncSession = Depends(get_session),
    _api_key: str = Depends(verify_stats_api_key),
):
    """Get paper vs real comparison by archetype."""
    try:
        stats = StatsService(session)
        return await stats.get_paper_archetypes(
            period=period,
            from_ts=from_ts,
            to_ts=to_ts,
            min_sample=min_sample,
        )
    except Exception as e:
        logger.error(f"Error getting paper archetypes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Conversion Funnel
# =============================================================================


@router.get(
    "/conversion",
    response_model=ConversionFunnelResponse,
    summary="Get conversion funnel",
    description="Returns conversion funnel: GENERATED → VIEWED → SELECTED → PLACED → CLOSED"
)
async def get_conversion_funnel(
    period: str = Query("90d", description="Period"),
    from_ts: Optional[int] = Query(None),
    to_ts: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
    _api_key: str = Depends(verify_stats_api_key),
):
    """Get conversion funnel statistics."""
    try:
        stats = StatsService(session)
        return await stats.get_conversion_funnel(
            period=period,
            from_ts=from_ts,
            to_ts=to_ts,
        )
    except Exception as e:
        logger.error(f"Error getting funnel: {e}")
        raise HTTPException(status_code=500, detail=str(e))
