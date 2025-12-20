"""
Stats Service Module - unified statistics API for trading outcomes.

Provides:
- StatsService: main service class with caching
- StatsCacheLayer: Redis caching with versioning
- Response schemas for all endpoints

Usage:
    from src.services.stats import StatsService

    async with async_session() as session:
        stats = StatsService(session, redis=redis_client)
        overview = await stats.get_trading_overview(period="90d")
"""

from src.services.stats.service import StatsService
from src.services.stats.cache import StatsCacheLayer, on_trade_outcome_received
from src.services.stats.schemas import (
    # Trading
    TradingOverviewResponse,
    OutcomesDistributionResponse,
    SymbolsStatsResponse,
    # Learning
    ArchetypeListResponse,
    ArchetypeDetailResponse,
    GateStatusResponse,
    # Funnel
    ConversionFunnelResponse,
    # Paper
    PaperArchetypesResponse,
    # Common
    ConfidenceInterval,
    FiltersApplied,
    StreaksInfo,
)

__all__ = [
    # Service
    "StatsService",
    "StatsCacheLayer",
    "on_trade_outcome_received",
    # Trading Responses
    "TradingOverviewResponse",
    "OutcomesDistributionResponse",
    "SymbolsStatsResponse",
    # Learning Responses
    "ArchetypeListResponse",
    "ArchetypeDetailResponse",
    "GateStatusResponse",
    # Funnel Responses
    "ConversionFunnelResponse",
    # Paper Responses
    "PaperArchetypesResponse",
    # Common Types
    "ConfidenceInterval",
    "FiltersApplied",
    "StreaksInfo",
]
