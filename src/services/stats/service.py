"""
Stats Service - главный сервис для Stats API.

Объединяет все модули:
- trading.py - агрегации из TradeOutcome
- learning.py - статистика архетипов
- paper.py - forward test stats
- funnel.py - воронка конверсии
- cache.py - Redis caching

Следует контракту из плана ancient-shimmying-pizza.md.
"""

from typing import Optional

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.stats.cache import StatsCacheLayer
from src.services.stats.schemas import (
    TradingOverviewResponse,
    OutcomesDistributionResponse,
    SymbolsStatsResponse,
    ArchetypeListResponse,
    ArchetypeDetailResponse,
    GateStatusResponse,
    ConversionFunnelResponse,
)
from src.services.stats import trading, learning, paper, funnel


class StatsService:
    """Unified stats service с caching."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Optional[Redis] = None,
    ):
        self.session = session
        self.redis = redis
        self.cache = StatsCacheLayer(redis)

    # =========================================================================
    # Trading Stats
    # =========================================================================

    async def get_trading_overview(
        self,
        period: str = "90d",
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
        symbol: Optional[str] = None,
        archetype: Optional[str] = None,
        origin: Optional[str] = None,
    ) -> TradingOverviewResponse:
        """Get trading overview statistics."""

        # Try cache first
        cache_params = {
            "period": period,
            "from_ts": from_ts,
            "to_ts": to_ts,
            "symbol": symbol,
            "archetype": archetype,
            "origin": origin,
        }
        cached = await self.cache.get("overview", **cache_params)
        if cached:
            return TradingOverviewResponse(**cached)

        # Compute
        result = await trading.get_trading_overview(
            session=self.session,
            period=period,
            from_ts=from_ts,
            to_ts=to_ts,
            symbol=symbol,
            archetype=archetype,
            origin=origin,
        )

        # Cache result
        await self.cache.set("overview", result.model_dump(), **cache_params)

        return result

    async def get_outcomes_distribution(
        self,
        period: str = "90d",
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
    ) -> OutcomesDistributionResponse:
        """Get outcomes distribution (exit types breakdown)."""

        cache_params = {"period": period, "from_ts": from_ts, "to_ts": to_ts}
        cached = await self.cache.get("outcomes", **cache_params)
        if cached:
            return OutcomesDistributionResponse(**cached)

        result = await trading.get_outcomes_distribution(
            session=self.session,
            period=period,
            from_ts=from_ts,
            to_ts=to_ts,
        )

        await self.cache.set("outcomes", result.model_dump(), **cache_params)
        return result

    async def get_symbols_stats(
        self,
        period: str = "90d",
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
    ) -> SymbolsStatsResponse:
        """Get per-symbol statistics."""

        cache_params = {"period": period, "from_ts": from_ts, "to_ts": to_ts}
        cached = await self.cache.get("symbols", **cache_params)
        if cached:
            return SymbolsStatsResponse(**cached)

        result = await trading.get_symbols_stats(
            session=self.session,
            period=period,
            from_ts=from_ts,
            to_ts=to_ts,
        )

        await self.cache.set("symbols", result.model_dump(), **cache_params)
        return result

    # =========================================================================
    # Learning Stats
    # =========================================================================

    async def get_archetypes(
        self,
        period: str = "90d",
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
        min_sample: int = 10,
        page: int = 0,
        page_size: int = 20,
    ) -> ArchetypeListResponse:
        """Get list of archetypes with stats."""

        cache_params = {
            "period": period,
            "from_ts": from_ts,
            "to_ts": to_ts,
            "min_sample": min_sample,
            "page": page,
            "page_size": page_size,
        }
        cached = await self.cache.get("archetypes", **cache_params)
        if cached:
            return ArchetypeListResponse(**cached)

        result = await learning.get_archetypes_list(
            session=self.session,
            period=period,
            from_ts=from_ts,
            to_ts=to_ts,
            min_sample=min_sample,
            page=page,
            page_size=page_size,
        )

        await self.cache.set("archetypes", result.model_dump(), **cache_params)
        return result

    async def get_archetype_detail(
        self,
        archetype: str,
        period: str = "90d",
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
    ) -> Optional[ArchetypeDetailResponse]:
        """Get detailed stats for a specific archetype."""

        cache_params = {"period": period, "from_ts": from_ts, "to_ts": to_ts}
        cached = await self.cache.get_archetype_detail(archetype, **cache_params)
        if cached:
            return ArchetypeDetailResponse(**cached)

        result = await learning.get_archetype_detail(
            session=self.session,
            archetype=archetype,
            period=period,
            from_ts=from_ts,
            to_ts=to_ts,
        )

        if result:
            await self.cache.set_archetype_detail(
                archetype, result.model_dump(), **cache_params
            )

        return result

    async def get_gates_status(self) -> list[GateStatusResponse]:
        """Get status of all EV gates."""

        cached = await self.cache.get("gates")
        if cached:
            return [GateStatusResponse(**g) for g in cached]

        result = await learning.get_gates_status(session=self.session)

        await self.cache.set("gates", [g.model_dump() for g in result])
        return result

    # =========================================================================
    # Paper Stats
    # =========================================================================

    async def get_paper_overview(
        self,
        period: str = "90d",
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
        archetype: Optional[str] = None,
    ) -> TradingOverviewResponse:
        """Get paper trading overview statistics."""

        return await paper.get_paper_overview(
            session=self.session,
            period=period,
            from_ts=from_ts,
            to_ts=to_ts,
            archetype=archetype,
        )

    async def get_paper_archetypes(
        self,
        period: str = "90d",
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
        min_sample: int = 10,
    ) -> list[dict]:
        """Get paper trading stats per archetype."""

        return await paper.get_paper_archetypes(
            session=self.session,
            period=period,
            from_ts=from_ts,
            to_ts=to_ts,
            min_sample=min_sample,
        )

    # =========================================================================
    # Conversion Funnel
    # =========================================================================

    async def get_conversion_funnel(
        self,
        period: str = "90d",
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
    ) -> ConversionFunnelResponse:
        """Get conversion funnel statistics."""

        cache_params = {"period": period, "from_ts": from_ts, "to_ts": to_ts}
        cached = await self.cache.get("funnel", **cache_params)
        if cached:
            return ConversionFunnelResponse(**cached)

        result = await funnel.get_conversion_funnel(
            session=self.session,
            period=period,
            from_ts=from_ts,
            to_ts=to_ts,
        )

        await self.cache.set("funnel", result.model_dump(), **cache_params)
        return result

    # =========================================================================
    # Cache Management
    # =========================================================================

    async def invalidate_trading_cache(self) -> None:
        """Invalidate all trading-related caches."""
        await self.cache.invalidate_all_trading()

    async def invalidate_archetype_cache(self, archetype: str) -> None:
        """Invalidate cache for specific archetype."""
        await self.cache.invalidate_archetype(archetype)
        await self.cache.invalidate("archetypes")
