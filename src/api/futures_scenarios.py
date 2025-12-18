# coding: utf-8
"""
Futures Scenarios API

API endpoint для получения структурированных торговых сценариев
для автоматизированного трейдинга.

Endpoint:
    POST /api/futures-scenarios

Request:
    {
        "symbol": "BTCUSDT",
        "timeframe": "4h",  // optional, default: "4h"
        "max_scenarios": 3   // optional, default: 3
    }

Response:
    {
        "success": true,
        "symbol": "BTCUSDT",
        "analysis_timestamp": "2025-01-15T12:00:00Z",
        "current_price": 95234.5,
        "market_context": {...},
        "scenarios": [...],
        "key_levels": {...},
        "data_quality": {...}
    }
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from loguru import logger

from src.services.futures_analysis_service import futures_analysis_service
from src.api.api_key_auth import verify_api_key


router = APIRouter()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class FuturesScenariosRequest(BaseModel):
    """Request model for futures scenarios"""

    symbol: str = Field(
        ...,
        description="Trading pair symbol (e.g., 'BTCUSDT', 'ETHUSDT')",
        example="BTCUSDT"
    )
    timeframe: Optional[str] = Field(
        default="4h",
        description="Primary timeframe for analysis",
        pattern="^(1h|4h|1d)$",
        example="4h"
    )
    max_scenarios: Optional[int] = Field(
        default=3,
        description="Maximum number of scenarios to generate",
        ge=1,
        le=5,
        example=3
    )
    mode: Optional[str] = Field(
        default="standard",
        description="Trading mode: conservative, standard, high_risk, meme",
        pattern="^(conservative|standard|high_risk|meme)$",
        example="standard"
    )

    class Config:
        schema_extra = {
            "example": {
                "symbol": "BTCUSDT",
                "timeframe": "4h",
                "max_scenarios": 3,
                "mode": "standard"
            }
        }


class ScenarioTarget(BaseModel):
    """Target model for scenario"""
    level: int
    price: float
    partial_close_pct: int
    rr: float
    reason: str


class ScenarioEntry(BaseModel):
    """Entry model for scenario (legacy, kept for backwards compatibility)"""
    price_min: float
    price_max: float
    type: str
    reason: str


# ============================================================================
# 🔥 NEW: ENTRY PLAN MODELS (Execution Plan instead of simple zone)
# ============================================================================


class EntryOrder(BaseModel):
    """
    Individual order in the entry plan ladder

    Each order references a specific technical level (not made up prices!)
    """
    price: float = Field(..., description="Order price (must reference a candidate level)")
    size_pct: int = Field(
        ...,
        ge=1,
        le=100,
        description="Position size percentage for this order (1-100)"
    )
    type: str = Field(
        default="limit",
        description="Order type: 'limit' or 'stop_limit'"
    )
    tag: str = Field(
        ...,
        description="Human-readable tag (e.g., 'E1_zone_top', 'E2_support')"
    )
    source_level: str = Field(
        ...,
        description="Source of this price (e.g., 'swing_low_1', 'ema_20', 'support_1')"
    )


class EntryActivation(BaseModel):
    """
    Activation conditions - when to start placing orders

    Prevents placing limit orders in vacuum when price is far away
    """
    type: str = Field(
        ...,
        description="Activation type: 'touch', 'break', 'close_above', 'close_below'"
    )
    level: float = Field(..., description="Price level that triggers activation")
    max_distance_pct: float = Field(
        default=0.5,
        ge=0.1,
        le=5.0,
        description="Max distance from current price to activate (0.1-5%)"
    )


class EntryPlan(BaseModel):
    """
    🔥 Execution Plan: How exactly to enter the position

    Instead of a simple "entry zone", this provides:
    - Ladder of limit orders with specific prices
    - Activation trigger (when to start placing orders)
    - Cancel conditions (when to abort the plan)
    - Time validity (how long the plan is valid)

    Example:
        {
            "mode": "ladder",
            "orders": [
                {"price": 3046.23, "size_pct": 30, "type": "limit", "tag": "E1_zone_top", "source_level": "swing_high_1"},
                {"price": 2973.64, "size_pct": 40, "type": "limit", "tag": "E2_mid", "source_level": "ema_50"},
                {"price": 2901.05, "size_pct": 30, "type": "limit", "tag": "E3_support", "source_level": "support_1"}
            ],
            "activation": {"type": "touch", "level": 3046.23, "max_distance_pct": 0.25},
            "cancel_if": ["break_below 2836.70", "time_valid_hours exceeded"],
            "time_valid_hours": 48
        }
    """
    mode: str = Field(
        default="ladder",
        description="Entry mode: 'ladder' (multiple limits), 'single' (one entry), 'dca' (dollar cost avg)"
    )
    orders: List[EntryOrder] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="List of entry orders (1-5)"
    )
    activation: EntryActivation = Field(
        ...,
        description="When to activate this plan"
    )
    cancel_if: List[str] = Field(
        default_factory=list,
        description="Conditions that invalidate this plan"
    )
    time_valid_hours: int = Field(
        default=48,
        ge=1,
        le=336,
        description="Plan validity in hours (1-336, i.e. up to 2 weeks)"
    )


class ScenarioStopLoss(BaseModel):
    """Stop-loss model for scenario"""
    conservative: float
    aggressive: float
    recommended: float
    reason: str


class ScenarioLeverage(BaseModel):
    """Leverage recommendation model"""
    recommended: str
    max_safe: str
    volatility_adjusted: bool
    atr_pct: Optional[float] = None


class ScenarioInvalidation(BaseModel):
    """Invalidation model for scenario"""
    price: float
    condition: str


class ScenarioWhy(BaseModel):
    """Why model explaining scenario logic"""
    bullish_factors: Optional[List[str]] = None
    bearish_factors: Optional[List[str]] = None
    risks: List[str]


class LearningSuggestions(BaseModel):
    """Learning system suggestions for SL/TP optimization"""
    sl_atr_mult: float = Field(..., description="Suggested SL as ATR multiple")
    tp1_r: float = Field(..., description="Suggested TP1 as R multiple")
    tp2_r: float = Field(..., description="Suggested TP2 as R multiple")
    based_on_trades: int = Field(..., description="Number of trades used for suggestion")
    confidence: float = Field(..., description="Confidence in suggestion (0-1)")


# =============================================================================
# EV (EXPECTED VALUE) MODELS
# =============================================================================


class OutcomeProbsAPI(BaseModel):
    """Terminal outcome probabilities for EV calculation"""
    sl: float = Field(..., description="P(stop loss) - не дошли ни до одного TP")
    tp1: float = Field(..., description="P(exit at TP1)")
    tp2: Optional[float] = Field(default=None, description="P(exit at TP2) — если 2+ targets")
    tp3: Optional[float] = Field(default=None, description="P(exit at TP3) — если 3 targets")
    other: float = Field(..., description="P(manual/timeout/breakeven)")
    source: str = Field(..., description="learning | llm | default")
    sample_size: Optional[int] = Field(default=None, description="Количество сделок в выборке")
    n_targets: int = Field(default=3, description="Количество TP уровней (1-3)")


class EVMetricsAPI(BaseModel):
    """Expected Value metrics for scenario scoring"""
    ev_r: float = Field(..., description="Expected Value в R (с учётом fees)")
    ev_r_gross: float = Field(..., description="EV до вычета fees (для дебага)")
    fees_r: float = Field(..., description="Комиссии в R")
    ev_grade: str = Field(..., description="A (>=0.5), B (>=0.2), C (>=0), D (<0)")
    scenario_score: float = Field(..., description="Нормализованный скор для ранжирования")
    n_targets: int = Field(..., description="Количество TP уровней (1-3)")
    flags: Optional[List[str]] = Field(default=None, description="Санити-чек флаги")


# =============================================================================
# NO-TRADE SIGNAL (first-class citizen)
# =============================================================================


# =============================================================================
# CLASS STATS (Context Gates)
# =============================================================================


class ClassStatsAPI(BaseModel):
    """
    Class Stats - статистика класса сценария для context gates.

    Класс = archetype + side + timeframe + [trend + vol + funding + sentiment]
    Используется для kill switch / boost.
    """
    # Идентификация
    class_key: str = Field(
        ...,
        description="ARCHETYPE|SIDE|TF|TREND|VOL|FUND|SENT"
    )
    class_key_hash: str = Field(
        ...,
        description="SHA1 hash для дебага"
    )
    class_level: str = Field(
        ...,
        description="L1 (coarse) or L2 (fine)"
    )

    # Sample info
    sample_size: int = Field(
        ...,
        description="Количество trades в статистике"
    )
    sample_status: str = Field(
        ...,
        description="insufficient / preliminary / reliable"
    )
    window_days: int = Field(
        default=90,
        description="Rolling window в днях"
    )

    # Fallback metadata
    fallback_used: bool = Field(
        default=False,
        description="True если использован L1 fallback"
    )
    fallback_from: Optional[str] = Field(
        default=None,
        description="L2 если fallback с L2 на L1"
    )
    fallback_reason: Optional[str] = Field(
        default=None,
        description="insufficient_sample / not_found"
    )

    # Gates
    is_enabled: bool = Field(
        default=True,
        description="False = kill switch активен"
    )
    disable_reason: Optional[str] = Field(
        default=None,
        description="Причина kill switch"
    )
    preliminary_warning: Optional[str] = Field(
        default=None,
        description="Warning для 20-49 trades"
    )

    # Метрики
    winrate: float = Field(..., description="Win rate (0-1)")
    winrate_lower_ci: float = Field(..., description="Wilson 95% CI lower bound")
    avg_pnl_r: float = Field(..., description="Средний PnL в R")
    avg_ev_r: float = Field(..., description="Средний EV в R")
    ev_lower_ci: float = Field(..., description="EV 95% CI lower bound")
    max_drawdown_r: float = Field(..., description="Max drawdown в R")
    conversion_rate: float = Field(
        default=0,
        description="traded_count / generated_count"
    )
    confidence_modifier: float = Field(
        default=0,
        description="+/- к confidence"
    )


class NoTradeSignal(BaseModel):
    """
    NO-TRADE как first-class сценарий.

    Рынок часто говорит "не лезь, брат, сегодня не день".
    Это режет овертрейдинг и поднимает winrate.
    """
    should_not_trade: bool = Field(
        default=True,
        description="True = рекомендуется НЕ торговать"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Уверенность в рекомендации (0-1)"
    )
    reasons: List[str] = Field(
        ...,
        description="Причины не торговать"
    )
    category: str = Field(
        ...,
        description="Категория: 'chop' | 'extreme_sentiment' | 'low_liquidity' | 'news_risk' | 'technical_conflict'"
    )
    wait_for: Optional[List[str]] = Field(
        default=None,
        description="Что ждать для возобновления торговли"
    )
    estimated_wait_hours: Optional[int] = Field(
        default=None,
        description="Примерное время ожидания (часы)"
    )


class TradingScenario(BaseModel):
    """Trading scenario model with execution plan"""
    id: int
    name: str
    bias: str
    confidence: float = Field(..., description="Calibrated confidence (0-1)")
    confidence_raw: Optional[float] = Field(
        default=None,
        description="Original AI confidence before calibration"
    )
    primary_archetype: Optional[str] = Field(
        default=None,
        description="Rule-based trade archetype classification"
    )
    learning_suggestions: Optional[LearningSuggestions] = Field(
        default=None,
        description="SL/TP suggestions from learning system"
    )

    # 🔥 NEW: Entry Plan (ladder of orders with activation & cancel conditions)
    entry_plan: EntryPlan = Field(
        ...,
        description="Execution plan with ladder entries, activation, and cancel conditions"
    )

    # Legacy entry field (for backwards compatibility)
    entry: Optional[ScenarioEntry] = Field(
        default=None,
        description="Legacy entry zone (deprecated, use entry_plan)"
    )

    stop_loss: ScenarioStopLoss
    targets: List[ScenarioTarget]
    leverage: ScenarioLeverage
    invalidation: ScenarioInvalidation
    why: ScenarioWhy
    conditions: List[str]

    # 🆕 Additional fields
    stop_pct_of_entry: Optional[float] = Field(
        default=None,
        description="Stop loss as % of entry price"
    )
    atr_multiple_stop: Optional[float] = Field(
        default=None,
        description="Stop loss as ATR multiple"
    )
    time_valid_hours: Optional[int] = Field(
        default=None,
        description="How long this scenario is valid (hours)"
    )
    entry_trigger: Optional[str] = Field(
        default=None,
        description="Primary trigger for entry"
    )
    no_trade_conditions: Optional[List[str]] = Field(
        default=None,
        description="Conditions when NOT to enter"
    )
    validation_status: Optional[str] = Field(
        default=None,
        description="Validation result: 'valid', 'fixed:field', 'warning'"
    )

    # 🆕 Trading mode notes (how AI applied mode parameters)
    mode_notes: Optional[List[str]] = Field(
        default=None,
        description="Notes explaining how the scenario reflects trading mode parameters"
    )

    # EV (Expected Value) metrics
    outcome_probs: Optional[OutcomeProbsAPI] = Field(
        default=None,
        description="Terminal outcome probabilities for EV calculation"
    )
    ev_metrics: Optional[EVMetricsAPI] = Field(
        default=None,
        description="Expected Value metrics and scenario score"
    )

    # Class Stats (Context Gates)
    class_stats: Optional[ClassStatsAPI] = Field(
        default=None,
        description="Class statistics for context gates (kill switch / boost)"
    )
    class_warning: Optional[str] = Field(
        default=None,
        description="Warning from class stats (disabled / preliminary negative)"
    )


class MarketContext(BaseModel):
    """Market context model"""
    trend: str
    phase: str
    sentiment: str
    volatility: str
    bias: str
    strength: float
    rsi: Optional[float] = None
    funding_rate_pct: Optional[float] = None
    long_short_ratio: Optional[float] = None


class KeyLevels(BaseModel):
    """Key levels model"""
    support: List[float]
    resistance: List[float]
    ema_levels: dict
    vwap: Optional[dict] = None
    bollinger_bands: Optional[dict] = None


class DataQuality(BaseModel):
    """Data quality assessment model"""
    completeness: int
    sources: List[str]
    warnings: Optional[List[str]] = None


class FuturesScenariosResponse(BaseModel):
    """Response model for futures scenarios"""

    success: bool
    symbol: str
    timeframe: str
    analysis_timestamp: str
    analysis_id: str = Field(
        ...,
        description="Unique ID for this analysis (for feedback tracking)"
    )
    current_price: float
    market_context: MarketContext
    scenarios: List[TradingScenario]
    key_levels: KeyLevels
    data_quality: DataQuality
    metadata: dict

    # 🆕 NO-TRADE signal (first-class citizen)
    no_trade: Optional[NoTradeSignal] = Field(
        default=None,
        description="Сигнал НЕ торговать (если есть - рекомендуется воздержаться)"
    )

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "symbol": "BTCUSDT",
                "timeframe": "4h",
                "analysis_timestamp": "2025-01-15T12:00:00Z",
                "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
                "current_price": 95234.5,
                "market_context": {
                    "trend": "bullish",
                    "phase": "continuation",
                    "sentiment": "greed",
                    "volatility": "medium",
                    "bias": "long",
                    "strength": 0.7,
                    "rsi": 65.2,
                    "funding_rate_pct": -0.015,
                    "long_short_ratio": 1.85
                },
                "scenarios": [
                    {
                        "id": 1,
                        "name": "Long Breakout",
                        "bias": "long",
                        "confidence": 0.75,
                        "entry_plan": {
                            "mode": "ladder",
                            "orders": [
                                {
                                    "price": 95200.0,
                                    "size_pct": 40,
                                    "type": "limit",
                                    "tag": "E1_ema20",
                                    "source_level": "ema_20"
                                },
                                {
                                    "price": 94800.0,
                                    "size_pct": 35,
                                    "type": "limit",
                                    "tag": "E2_support",
                                    "source_level": "support_1"
                                },
                                {
                                    "price": 94400.0,
                                    "size_pct": 25,
                                    "type": "limit",
                                    "tag": "E3_swing_low",
                                    "source_level": "swing_low_1"
                                }
                            ],
                            "activation": {
                                "type": "touch",
                                "level": 95200.0,
                                "max_distance_pct": 0.5
                            },
                            "cancel_if": [
                                "break_below 94000",
                                "time_valid_hours exceeded"
                            ],
                            "time_valid_hours": 48
                        },
                        "entry": {
                            "price_min": 94400.0,
                            "price_max": 95200.0,
                            "type": "ladder_limit",
                            "reason": "Entry plan with 3 order(s)"
                        },
                        "stop_loss": {
                            "conservative": 94200.0,
                            "aggressive": 94500.0,
                            "recommended": 94300.0,
                            "reason": "Below EMA50 support"
                        },
                        "targets": [
                            {
                                "level": 1,
                                "price": 96500.0,
                                "partial_close_pct": 30,
                                "rr": 2.1,
                                "reason": "First resistance"
                            },
                            {
                                "level": 2,
                                "price": 98000.0,
                                "partial_close_pct": 40,
                                "rr": 4.2,
                                "reason": "Major resistance"
                            },
                            {
                                "level": 3,
                                "price": 100000.0,
                                "partial_close_pct": 30,
                                "rr": 6.5,
                                "reason": "Psychological level"
                            }
                        ],
                        "leverage": {
                            "recommended": "5x-8x",
                            "max_safe": "10x",
                            "volatility_adjusted": True,
                            "atr_pct": 1.8
                        },
                        "invalidation": {
                            "price": 93800.0,
                            "condition": "Break below $93800.00"
                        },
                        "why": {
                            "bullish_factors": [
                                "Uptrend confirmed",
                                "Funding negative"
                            ],
                            "risks": ["Resistance at 96k"]
                        },
                        "conditions": [
                            "Price holds above $94.8k",
                            "Volume increases"
                        ],
                        "stop_pct_of_entry": 1.05,
                        "atr_multiple_stop": 0.8,
                        "time_valid_hours": 48,
                        "entry_trigger": "Price holds above $94.8k",
                        "no_trade_conditions": [
                            "Avoid if resistance at 96k"
                        ],
                        "validation_status": "valid"
                    }
                ],
                "key_levels": {
                    "support": [94200.0, 93500.0],
                    "resistance": [96000.0, 98000.0],
                    "ema_levels": {
                        "ema_20": {
                            "price": 94800.0,
                            "distance_pct": 0.45
                        }
                    }
                },
                "data_quality": {
                    "completeness": 95,
                    "sources": [
                        "candlestick_data",
                        "technical_indicators",
                        "funding_rates"
                    ]
                },
                "metadata": {
                    "has_liquidation_data": True,
                    "funding_available": True,
                    "candles_analyzed": 200
                }
            }
        }


# ============================================================================
# API ENDPOINTS
# ============================================================================


@router.post(
    "/futures-scenarios",
    response_model=FuturesScenariosResponse,
    summary="Get Futures Trading Scenarios",
    description=(
        "Получить структурированные торговые сценарии для фьючерсов с конкретными "
        "уровнями входа, стоп-лосса и целей. Используется для автоматизации трейдинга.\n\n"
        "**🔐 ТРЕБУЕТСЯ API KEY** - добавь заголовок `X-API-Key: your-secret-key`\n\n"
        "**Возвращает:**\n"
        "- 2-3 торговых сценария с confidence scoring\n"
        "- Конкретные уровни: entry, stop-loss, targets (TP1, TP2, TP3)\n"
        "- RR calculation для каждого сценария\n"
        "- Leverage recommendations на основе ATR volatility\n"
        "- Structured reasoning (почему этот сценарий валидный)\n"
        "- Market context (trend, phase, sentiment, volatility)\n\n"
        "**Data sources:**\n"
        "- Binance Futures (OHLCV, funding, OI, liquidations)\n"
        "- Technical indicators (RSI, MACD, EMA, ATR, VWAP, etc.)\n"
        "- Fear & Greed Index\n"
        "- Multi-timeframe analysis\n\n"
        "**Note:** Для получения liquidation data требуются Binance API keys."
    ),
    tags=["Futures Trading"]
)
async def get_futures_scenarios(
    request: FuturesScenariosRequest,
    api_key: str = Depends(verify_api_key)
) -> FuturesScenariosResponse:
    """
    Get structured trading scenarios for futures

    **🔐 ТРЕБУЕТСЯ API KEY** - добавь заголовок `X-API-Key: your-secret-key`

    **Example request:**
    ```bash
    curl -X POST "http://localhost:8000/api/futures-scenarios" \
         -H "Content-Type: application/json" \
         -H "X-API-Key: your-secret-key" \
         -d '{
           "symbol": "BTCUSDT",
           "timeframe": "4h",
           "max_scenarios": 3
         }'
    ```
    """
    try:
        logger.info(
            f"Futures scenarios request: {request.symbol}, "
            f"timeframe={request.timeframe}"
        )

        # Validate symbol format
        symbol = request.symbol.upper()
        if not symbol.endswith("USDT"):
            raise HTTPException(
                status_code=400,
                detail="Invalid symbol. Must be a USDT perpetual pair (e.g., BTCUSDT)"
            )

        # Validate timeframe
        if request.timeframe not in ["1h", "4h", "1d"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid timeframe. Allowed: 1h, 4h, 1d"
            )

        # Call analysis service
        result = await futures_analysis_service.analyze_symbol(
            symbol=symbol,
            timeframe=request.timeframe,
            max_scenarios=request.max_scenarios,
            mode=request.mode  # 🆕 Trading mode
        )

        # Check if analysis was successful
        if not result.get("success"):
            error_msg = result.get("error", "Unknown error occurred")
            logger.error(f"Analysis failed for {symbol}: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to analyze {symbol}: {error_msg}"
            )

        # Log successful analysis
        logger.info(
            f"Analysis complete for {symbol}: "
            f"{len(result['scenarios'])} scenarios, "
            f"quality={result['data_quality']['completeness']}%"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in futures scenarios endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/futures-scenarios/supported-symbols",
    summary="Get Supported Futures Symbols",
    description="Получить список поддерживаемых фьючерсных пар",
    tags=["Futures Trading"]
)
async def get_supported_symbols():
    """
    Get list of supported futures symbols

    Returns list of USDT perpetual pairs available for analysis
    """
    # Основные USDT perpetual пары на Binance
    supported_symbols = [
        # Top by volume
        "BTCUSDT",
        "ETHUSDT",
        # Layer 1
        "SOLUSDT",
        "BNBUSDT",
        "XRPUSDT",
        "ADAUSDT",
        "AVAXUSDT",
        "DOTUSDT",
        "MATICUSDT",
        "LINKUSDT",
        # DeFi
        "UNIUSDT",
        "AAVEUSDT",
        "SUSHIUSDT",
        # Layer 2
        "ARBUSDT",
        "OPUSDT",
        # AI/ML
        "RENDERUSDT",
        "FETUSDT",
        # Memes
        "DOGEUSDT",
        "SHIBUSDT",
        "PEPEUSDT",
        # Other popular
        "LTCUSDT",
        "ATOMUSDT",
        "NEARUSDT",
        "APTUSDT",
        "INJUSDT",
    ]

    return {
        "success": True,
        "symbols": supported_symbols,
        "count": len(supported_symbols),
        "note": "Любая USDT perpetual пара на Binance Futures поддерживается"
    }


@router.get(
    "/futures-scenarios/health",
    summary="Health Check",
    description="Проверить доступность futures analysis service",
    tags=["Futures Trading"]
)
async def health_check():
    """
    Health check for futures analysis service

    Returns service status and available data sources
    """
    try:
        # Check if Binance service is accessible
        test_price = await futures_analysis_service.binance.get_current_price("BTCUSDT")

        return {
            "success": True,
            "status": "healthy",
            "binance_api": "connected" if test_price else "error",
            "has_api_keys": futures_analysis_service.binance.has_credentials,
            "available_features": {
                "basic_analysis": True,
                "funding_rates": True,
                "open_interest": True,
                "liquidation_data": futures_analysis_service.binance.has_credentials
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }


# ============================================================================
# POSITION SIZE CALCULATION ENDPOINT
# ============================================================================


class CalculatePositionSizeRequest(BaseModel):
    """Request model for position size calculation"""

    # Symbol
    symbol: str = Field(
        ...,
        description="Trading pair symbol (e.g., 'BTCUSDT')",
        example="BTCUSDT"
    )

    # Side
    side: str = Field(
        ...,
        description="Position side",
        pattern="^(long|short)$",
        example="long"
    )

    # Entry/Stop
    entry_price: float = Field(
        ...,
        description="Entry price",
        gt=0,
        example=95250.0
    )

    stop_loss: float = Field(
        ...,
        description="Stop loss price",
        gt=0,
        example=94300.0
    )

    # Risk params (CRITICAL!)
    risk_usd: float = Field(
        ...,
        description="How much USD you're willing to lose on this trade",
        gt=0,
        example=10.0
    )

    leverage: int = Field(
        ...,
        description="Desired leverage",
        ge=1,
        le=125,
        example=5
    )

    # Optional safety limits
    account_balance: Optional[float] = Field(
        default=None,
        description="Current account balance (for validation)",
        gt=0,
        example=500.0
    )

    max_margin: Optional[float] = Field(
        default=None,
        description="Maximum margin per trade (safety limit)",
        gt=0,
        example=150.0
    )

    max_risk: Optional[float] = Field(
        default=None,
        description="Maximum risk per trade (safety limit)",
        gt=0,
        example=20.0
    )


@router.post(
    "/calculate-position-size",
    summary="Calculate Position Size",
    description=(
        "Рассчитать размер позиции на основе пользовательского риска и баланса "
        "с точным округлением до qtyStep биржи.\n\n"
        "**КРИТИЧНО для quick-execute интеграции!**\n\n"
        "**🔐 ТРЕБУЕТСЯ API KEY** - добавь заголовок `X-API-Key: your-secret-key`\n\n"
        "**Возвращает:**\n"
        "- Точное количество монет (qty) с округлением до qtyStep\n"
        "- Требуемую маржу в USDT\n"
        "- Фактический риск после округления\n"
        "- Валидацию на соответствие балансу и safety limits\n\n"
        "**Формула:**\n"
        "```\n"
        "qty = risk_usd / abs(entry_price - stop_loss)\n"
        "margin = (qty * entry_price) / leverage\n"
        "```"
    ),
    tags=["Futures Trading"]
)
async def calculate_position_size(
    request: CalculatePositionSizeRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Calculate position size for quick trade execution

    **Example request:**
    ```bash
    curl -X POST "http://localhost:8000/api/calculate-position-size" \
         -H "Content-Type: application/json" \
         -d '{
           "symbol": "BTCUSDT",
           "side": "long",
           "entry_price": 95250.0,
           "stop_loss": 94300.0,
           "risk_usd": 10.0,
           "leverage": 5,
           "account_balance": 500.0
         }'
    ```
    """
    try:
        from src.services.position_size_calculator import (
            position_size_calculator,
            PositionParams,
            InstrumentInfo
        )

        logger.info(
            f"Position size calculation: {request.symbol} {request.side}, "
            f"risk=${request.risk_usd}, leverage={request.leverage}x"
        )

        # 1. Get instrument info from Binance
        instrument_data = await futures_analysis_service.binance.get_instrument_info(
            request.symbol
        )

        if not instrument_data:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get instrument info for {request.symbol}"
            )

        # 2. Create InstrumentInfo object
        instrument = InstrumentInfo(
            symbol=instrument_data["symbol"],
            qty_step=instrument_data["qty_step"],
            tick_size=instrument_data["tick_size"],
            min_order_qty=instrument_data["min_order_qty"],
            max_order_qty=instrument_data["max_order_qty"],
            min_notional=instrument_data["min_notional"],
            max_leverage=instrument_data["max_leverage"]
        )

        # 3. Create PositionParams
        params = PositionParams(
            symbol=request.symbol,
            side=request.side,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            risk_usd=request.risk_usd,
            leverage=request.leverage,
            account_balance=request.account_balance,
            max_margin=request.max_margin,
            max_risk=request.max_risk
        )

        # 4. Calculate position size
        result = position_size_calculator.calculate(params, instrument)

        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Position size calculation failed")
            )

        logger.info(
            f"Position calculated: qty={result['position']['qty']}, "
            f"margin=${result['position']['margin_required']:.2f}, "
            f"valid={result['validation']['is_valid']}"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in position size calculation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
