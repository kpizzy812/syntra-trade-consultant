"""
Stats API Schemas - Pydantic модели для Stats System.

Определяет response schemas для всех Stats API endpoints.
Следует контракту из плана ancient-shimmying-pizza.md.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# =============================================================================
# Common Types
# =============================================================================


class ConfidenceInterval(BaseModel):
    """95% confidence interval."""

    lower: float
    upper: float


class FiltersApplied(BaseModel):
    """Примененные фильтры в запросе."""

    symbol: Optional[str] = None
    archetype: Optional[str] = None
    origin: Optional[str] = None


class StreaksInfo(BaseModel):
    """Информация о сериях."""

    max_win: int = 0
    max_loss: int = 0
    current: int = 0  # Положительное = win streak, отрицательное = loss streak


class OriginStats(BaseModel):
    """Статистика по origin (AI vs Manual)."""

    count: int
    winrate: float
    expectancy_r: float


class ByOriginStats(BaseModel):
    """Breakdown по AI vs Manual."""

    ai_scenario: Optional[OriginStats] = None
    manual: Optional[OriginStats] = None
    copy_trade: Optional[OriginStats] = None
    forward_test: Optional[OriginStats] = None


class DefinitionsContract(BaseModel):
    """Определения метрик для UI."""

    winrate: str = "trades with r_result > 0 / total trades"
    winrate_ci: str = "Wilson score 95% interval (null if n<30 or min(W,L)<5)"
    expectancy_r: str = "mean(r_result) across all closed trades"
    expectancy_ci: str = "t-distribution 95% interval (null if n<30)"
    sharpe_ratio: str = "mean(R) / std(R) per trade, NOT annualized"
    profit_factor: str = "sum(positive_r) / abs(sum(negative_r))"
    max_drawdown_r: str = "max peak-to-trough in cumulative R"


# =============================================================================
# Trading Overview
# =============================================================================


class TradingOverviewResponse(BaseModel):
    """Response для GET /api/stats/trading/overview."""

    # Period Boundaries
    period: str
    from_ts: int  # Unix timestamp начала
    to_ts: int  # Unix timestamp конца

    # Sample Info
    sample_size: int
    filters_applied: FiltersApplied

    # Key Metrics
    winrate: float
    winrate_ci: Optional[ConfidenceInterval] = None  # null если n < 30
    expectancy_r: float
    profit_factor: Optional[float] = None  # null если нет losses
    net_pnl_usd: float
    fees_usd: float

    # Risk Metrics
    avg_mae_r: Optional[float] = None
    avg_mfe_r: Optional[float] = None
    max_drawdown_r: float
    sharpe_ratio: Optional[float] = None  # null если n < 30

    # Streaks
    streaks: StreaksInfo

    # AI vs Manual
    by_origin: ByOriginStats

    # Definition Contract
    definitions: DefinitionsContract = Field(default_factory=DefinitionsContract)

    # API Versioning
    schema_version: int = 1
    generated_at_ts: int

    # Sharpe Basis
    sharpe_basis: str = "per_trade_r"

    # Warnings
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Outcomes Distribution
# =============================================================================


class OutcomeTypeStats(BaseModel):
    """Статистика по одному outcome type."""

    count: int
    pct: float
    avg_r: Optional[float] = None  # null если count == 0


class OutcomesDistribution(BaseModel):
    """Распределение по OutcomeType."""

    sl_early: OutcomeTypeStats
    be_after_tp1: OutcomeTypeStats
    stop_in_profit: OutcomeTypeStats
    tp1_final: OutcomeTypeStats
    tp2_final: OutcomeTypeStats
    tp3_final: OutcomeTypeStats
    manual_close: OutcomeTypeStats
    liquidation: OutcomeTypeStats
    other: OutcomeTypeStats


class HitRates(BaseModel):
    """TP hit rates."""

    tp1: Optional[float] = None  # % сделок дошедших до TP1
    tp2: Optional[float] = None
    tp3: Optional[float] = None


class CategoryStats(BaseModel):
    """Статистика по категории."""

    count: int
    pct: float


class ByCategory(BaseModel):
    """Агрегация по категориям."""

    losses: CategoryStats  # sl_early + liquidation
    breakeven: CategoryStats  # be_after_tp1
    wins: CategoryStats  # всё остальное с r > 0


class OutcomesDistributionResponse(BaseModel):
    """Response для GET /api/stats/trading/outcomes."""

    # Period Boundaries
    period: str
    from_ts: int
    to_ts: int
    sample_size: int

    # Distribution by OutcomeType
    distribution: OutcomesDistribution

    # TP Hit Rates
    hit_rates: HitRates

    # Aggregated by Category
    by_category: ByCategory

    # API Versioning
    schema_version: int = 1
    generated_at_ts: int

    # Warnings
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Archetype Stats
# =============================================================================


class PaperComparison(BaseModel):
    """Сравнение с paper trading."""

    sample_size: int
    winrate: float
    expectancy_r: float


class OutcomesBreakdown(BaseModel):
    """Breakdown outcomes в процентах."""

    sl_early: float
    tp1_final: float
    tp2_final: float
    tp3_final: float
    other: float


class ArchetypeListItem(BaseModel):
    """Элемент списка архетипов."""

    archetype: str
    sample_size: int
    winrate: float
    expectancy_r: float
    profit_factor: Optional[float] = None
    gate_status: str  # enabled, warning, disabled


class ArchetypeListResponse(BaseModel):
    """Response для GET /api/stats/learning/archetypes."""

    period: str
    from_ts: int
    to_ts: int

    archetypes: list[ArchetypeListItem]
    total_count: int
    page: int
    page_size: int

    schema_version: int = 1
    generated_at_ts: int
    warnings: list[str] = Field(default_factory=list)


class ArchetypeDetailResponse(BaseModel):
    """Response для GET /api/stats/learning/archetypes/{archetype}."""

    archetype: str

    # Period Boundaries
    period: str
    from_ts: int
    to_ts: int

    # Sample
    sample_size: int

    # Metrics
    winrate: float
    winrate_ci: Optional[ConfidenceInterval] = None
    expectancy_r: float
    expectancy_ci: Optional[ConfidenceInterval] = None
    profit_factor: Optional[float] = None
    max_drawdown_r: float

    # Gate Status
    gate_status: str  # enabled, warning, disabled
    gate_reason: Optional[str] = None

    # Paper Trading Comparison
    paper: Optional[PaperComparison] = None

    # Conversion
    conversion_rate: Optional[float] = None  # placed / viewed

    # Outcomes Breakdown
    outcomes: OutcomesBreakdown

    schema_version: int = 1
    generated_at_ts: int
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Gates Status
# =============================================================================


class GateStatusResponse(BaseModel):
    """Статус одного gate."""

    archetype: str
    gate_status: str  # enabled, warning, disabled
    gate_reason: Optional[str] = None
    sample_size: int
    winrate: float
    expectancy_r: float
    disabled_until: Optional[datetime] = None


# =============================================================================
# Conversion Funnel
# =============================================================================


class FunnelStageStats(BaseModel):
    """Статистика одной стадии воронки."""

    count: int
    pct: float
    breakdown: Optional[dict[str, int]] = None  # Для suppressed/viewed


class FunnelStages(BaseModel):
    """Все стадии воронки."""

    generated: FunnelStageStats
    suppressed: Optional[FunnelStageStats] = None
    viewed: FunnelStageStats
    selected: FunnelStageStats
    placed: FunnelStageStats
    closed: FunnelStageStats


class ConversionRates(BaseModel):
    """Rates конверсии между стадиями."""

    generated_to_viewed: float
    viewed_to_selected: float
    selected_to_placed: float
    placed_to_closed: float


class ArchetypeConversion(BaseModel):
    """Конверсия по архетипу."""

    archetype: str
    generated: int
    placed: int
    conversion_rate: float


class SuppressionAnalysis(BaseModel):
    """Анализ suppression."""

    total_suppressed: int
    suppression_rate: float
    top_reason: Optional[str] = None
    actionable_insight: Optional[str] = None


class ConversionFunnelResponse(BaseModel):
    """Response для GET /api/stats/conversion."""

    # Period Boundaries
    period: str
    from_ts: int
    to_ts: int

    # Funnel Stages
    stages: FunnelStages

    # Conversion Rates
    conversion_rates: ConversionRates

    # By Archetype (top converters)
    by_archetype: list[ArchetypeConversion]

    # Suppression Analysis
    suppression_analysis: Optional[SuppressionAnalysis] = None

    schema_version: int = 1
    generated_at_ts: int
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Symbols Stats
# =============================================================================


class SymbolStats(BaseModel):
    """Статистика по символу."""

    symbol: str
    count: int
    winrate: float
    expectancy_r: float
    net_pnl_usd: float


class SymbolsStatsResponse(BaseModel):
    """Response для GET /api/stats/trading/symbols."""

    period: str
    from_ts: int
    to_ts: int

    symbols: list[SymbolStats]
    total_count: int

    schema_version: int = 1
    generated_at_ts: int
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Paper Trading Stats
# =============================================================================


class PaperRealComparison(BaseModel):
    """Сравнение paper vs real для одного архетипа."""

    sample_size: int
    winrate: float
    expectancy_r: float


class PaperRealDelta(BaseModel):
    """Разница между paper и real."""

    winrate: float
    expectancy_r: float


class PaperArchetypeStats(BaseModel):
    """Статистика архетипа с paper vs real сравнением."""

    archetype: str
    paper: PaperRealComparison
    real: PaperRealComparison
    delta: PaperRealDelta


class PaperArchetypesResponse(BaseModel):
    """Response для GET /api/stats/paper/archetypes."""

    period: str
    from_ts: int
    to_ts: int

    archetypes: list[PaperArchetypeStats]
    total_count: int

    schema_version: int = 1
    generated_at_ts: int
    warnings: list[str] = Field(default_factory=list)
