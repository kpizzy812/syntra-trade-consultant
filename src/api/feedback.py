"""
Syntra Feedback API

API endpoints for receiving trade feedback from the bot.

Endpoints:
    POST /api/feedback/submit     - Submit trade feedback (upsert)
    GET  /api/feedback/stats/confidence - Get confidence bucket stats
    GET  /api/feedback/stats/archetypes - Get archetype stats
    GET  /api/feedback/health     - Health check
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.engine import get_session
from src.api.api_key_auth import verify_api_key
from src.services.feedback_service import feedback_service
from src.cache.redis_manager import get_redis_manager
from src.services.stats.cache import StatsCacheLayer, on_trade_outcome_received


router = APIRouter(prefix="/feedback", tags=["Feedback"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class OrderFillModel(BaseModel):
    """Single order fill"""
    order_id: str = ""
    order_type: str = "market"
    side: str
    price: float
    qty: float
    fee_usd: float = 0
    timestamp: str
    is_entry: bool = True
    tag: Optional[str] = None


class ExecutionReportModel(BaseModel):
    """Layer B: Execution Report"""
    planned_entry_price: float
    planned_entry_qty: float
    planned_orders_count: int = 1
    actual_avg_entry: float
    actual_total_qty: float
    filled_orders_count: int = 1
    slippage_pct: float = 0
    slippage_usd: float = 0
    entry_fills: List[OrderFillModel] = Field(default_factory=list)
    exit_fills: List[OrderFillModel] = Field(default_factory=list)
    entry_start_ts: str
    entry_complete_ts: str
    execution_duration_sec: float = 0


class OutcomeReportModel(BaseModel):
    """Layer C: Outcome Report"""
    exit_reason: str
    exit_price: float
    exit_timestamp: str
    pnl_usd: float
    pnl_r: float
    roe_pct: float = 0
    mae_r: float = 0
    mfe_r: float = 0
    mae_usd: float = 0
    mfe_usd: float = 0
    capture_efficiency: float = 0
    time_in_trade_min: int = 0
    time_to_mfe_min: Optional[int] = None
    time_to_mae_min: Optional[int] = None
    post_sl_mfe_r: Optional[float] = None
    post_sl_was_correct: Optional[bool] = None
    label: str


class ScenarioFactorsModel(BaseModel):
    """Scenario factors for attribution"""
    trend: str = "sideways"
    bias: str = "neutral"
    fear_greed_index: Optional[int] = None
    funding_rate: Optional[float] = None
    long_short_ratio: Optional[float] = None
    adx: Optional[float] = None
    rsi: Optional[float] = None
    volatility_regime: Optional[str] = None
    atr_pct: Optional[float] = None
    support_levels: List[float] = Field(default_factory=list)
    resistance_levels: List[float] = Field(default_factory=list)
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    ema_200: Optional[float] = None


class AttributionModel(BaseModel):
    """Layer D: Attribution"""
    primary_archetype: str
    archetype_confidence: float = 0.5
    tags: List[str] = Field(default_factory=list)
    factors: Optional[ScenarioFactorsModel] = None
    label: str
    pnl_r: float = 0
    factor_contributions: Dict[str, float] = Field(default_factory=dict)


class FeedbackSubmitRequest(BaseModel):
    """Full feedback submission request"""
    # 4 keys
    trade_id: str = Field(..., description="UUID from bot")
    analysis_id: str = Field(..., description="UUID from Syntra")
    scenario_local_id: int = Field(..., description="1..N within analysis")
    scenario_hash: str = Field(..., description="sha256 of scenario snapshot")

    # Idempotency
    idempotency_key: str = Field(..., description="{trade_id}:{event_type}")

    # Context
    user_id: int = Field(...)
    symbol: str = Field(...)
    side: str = Field(...)
    timeframe: str = Field(default="4h")
    is_testnet: bool = Field(default=False)
    confidence_raw: float = Field(default=0.5)

    # Partial data (can send in parts)
    execution: Optional[ExecutionReportModel] = None
    outcome: Optional[OutcomeReportModel] = None
    attribution: Optional[AttributionModel] = None
    scenario_snapshot: Optional[Dict[str, Any]] = None


class FeedbackSubmitResponse(BaseModel):
    """Response for feedback submission"""
    success: bool
    trade_id: str
    duplicate: bool = False
    fields_updated: List[str] = Field(default_factory=list)
    learning_triggered: bool = False


class ConfidenceBucketModel(BaseModel):
    """Confidence bucket statistics"""
    name: str
    confidence_min: float
    confidence_max: float
    total_trades: int
    wins: int
    losses: int
    actual_winrate_raw: float
    actual_winrate_smoothed: float
    calibration_offset: float
    sample_size: int


class ArchetypeStatModel(BaseModel):
    """Archetype statistics"""
    archetype: str
    symbol: Optional[str]
    timeframe: Optional[str]
    total_trades: int
    wins: int
    losses: int
    winrate: float
    avg_pnl_r: float
    profit_factor: float
    avg_mae_r: float
    avg_mfe_r: float


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.post(
    "/submit",
    response_model=FeedbackSubmitResponse,
    summary="Submit Trade Feedback",
    description=(
        "Submit feedback for a completed trade.\n\n"
        "**Features:**\n"
        "- UPSERT: partial updates merge with existing data\n"
        "- Idempotency: duplicate requests are detected\n"
        "- Learning: triggers recalculation when thresholds met\n\n"
        "**Layers:**\n"
        "- execution: fills, slippage, timing\n"
        "- outcome: PnL, MAE/MFE, exit reason\n"
        "- attribution: archetype, factors, contributions"
    )
)
async def submit_feedback(
    request: FeedbackSubmitRequest,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(verify_api_key)
) -> FeedbackSubmitResponse:
    """Submit trade feedback with partial update support."""
    try:
        logger.info(
            f"Feedback submit: trade_id={request.trade_id}, "
            f"user={request.user_id}, symbol={request.symbol}"
        )

        result = await feedback_service.submit_feedback(
            session=session,
            trade_id=request.trade_id,
            analysis_id=request.analysis_id,
            scenario_local_id=request.scenario_local_id,
            scenario_hash=request.scenario_hash,
            idempotency_key=request.idempotency_key,
            user_id=request.user_id,
            symbol=request.symbol,
            side=request.side,
            timeframe=request.timeframe,
            is_testnet=request.is_testnet,
            confidence_raw=request.confidence_raw,
            execution=request.execution.model_dump() if request.execution else None,
            outcome=request.outcome.model_dump() if request.outcome else None,
            attribution=request.attribution.model_dump() if request.attribution else None,
            scenario_snapshot=request.scenario_snapshot,
        )

        logger.info(
            f"Feedback processed: trade_id={request.trade_id}, "
            f"duplicate={result.get('duplicate', False)}, "
            f"fields={result.get('fields_updated', [])}"
        )

        # Cache invalidation (Phase 7)
        # Инвалидируем кеш если это outcome данные (финальный submit)
        if request.outcome and not result.get("duplicate", False):
            try:
                redis_mgr = get_redis_manager()
                if redis_mgr.is_available():
                    cache = StatsCacheLayer(redis_mgr._client)
                    # Создаем простой объект для on_trade_outcome_received
                    class OutcomeContext:
                        primary_archetype = (
                            request.attribution.primary_archetype
                            if request.attribution else None
                        )
                    await on_trade_outcome_received(OutcomeContext(), cache)
                    logger.debug(f"Stats cache invalidated for trade {request.trade_id}")
            except Exception as e:
                # Fire-and-forget: не блокируем основной запрос
                logger.warning(f"Cache invalidation failed: {e}")

        return FeedbackSubmitResponse(
            success=True,
            trade_id=request.trade_id,
            duplicate=result.get("duplicate", False),
            fields_updated=result.get("fields_updated", []),
            learning_triggered=result.get("learning_triggered", False),
        )

    except Exception as e:
        logger.exception(f"Error submitting feedback: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Feedback submit failed: {str(e)}"
        )


@router.get(
    "/stats/confidence",
    summary="Get Confidence Stats",
    description="Get confidence bucket statistics for calibration."
)
async def get_confidence_stats(
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Get confidence calibration statistics."""
    try:
        buckets = await feedback_service.get_confidence_buckets(session)

        return {
            "success": True,
            "buckets": [
                {
                    "name": b.bucket_name,
                    "confidence_min": b.confidence_min,
                    "confidence_max": b.confidence_max,
                    "total_trades": b.total_trades,
                    "actual_winrate": b.actual_winrate_smoothed,
                    "calibration_offset": b.calibration_offset,
                    "sample_size": b.sample_size,
                }
                for b in buckets
            ],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.exception(f"Error getting confidence stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get confidence stats: {str(e)}"
        )


@router.get(
    "/stats/archetypes",
    summary="Get Archetype Stats",
    description="Get performance statistics by trade archetype."
)
async def get_archetype_stats(
    min_trades: int = 10,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Get archetype performance statistics."""
    try:
        archetypes = await feedback_service.get_archetype_stats(
            session,
            min_trades=min_trades,
            symbol=symbol,
            timeframe=timeframe,
        )

        # Sort by profit factor descending
        sorted_archetypes = sorted(
            archetypes,
            key=lambda x: x.profit_factor,
            reverse=True
        )

        return {
            "success": True,
            "archetypes": [
                {
                    "rank": i + 1,
                    "name": a.archetype,
                    "symbol": a.symbol,
                    "timeframe": a.timeframe,
                    "trades": a.total_trades,
                    "winrate": round(a.winrate * 100, 1),
                    "profit_factor": round(a.profit_factor, 2),
                    "avg_pnl_r": round(a.avg_pnl_r, 2),
                    "suggested_sl_atr_mult": a.suggested_sl_atr_mult,
                    "suggested_tp1_r": a.suggested_tp1_r,
                    "suggested_tp2_r": a.suggested_tp2_r,
                }
                for i, a in enumerate(sorted_archetypes)
            ],
            "filters": {
                "min_trades": min_trades,
                "symbol": symbol,
                "timeframe": timeframe,
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.exception(f"Error getting archetype stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get archetype stats: {str(e)}"
        )


@router.get(
    "/outcomes",
    summary="Get Trade Outcomes",
    description="Get recent trade outcomes with optional filters."
)
async def get_trade_outcomes(
    user_id: Optional[int] = None,
    symbol: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Get trade outcomes with filters."""
    try:
        outcomes = await feedback_service.get_trade_outcomes(
            session,
            user_id=user_id,
            symbol=symbol,
            limit=min(limit, 100),
            offset=offset,
        )

        return {
            "success": True,
            "count": len(outcomes),
            "outcomes": [
                {
                    "trade_id": o.trade_id,
                    "user_id": o.user_id,
                    "symbol": o.symbol,
                    "side": o.side,
                    "timeframe": o.timeframe,
                    "exit_reason": o.exit_reason,
                    "pnl_usd": o.pnl_usd,
                    "pnl_r": o.pnl_r,
                    "label": o.label,
                    "primary_archetype": o.primary_archetype,
                    "confidence_raw": o.confidence_raw,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in outcomes
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
            }
        }

    except Exception as e:
        logger.exception(f"Error getting trade outcomes: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get outcomes: {str(e)}"
        )


@router.get(
    "/health",
    summary="Health Check",
    description="Check feedback service health."
)
async def health_check():
    """Health check endpoint."""
    return {
        "success": True,
        "service": "Syntra Feedback",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
