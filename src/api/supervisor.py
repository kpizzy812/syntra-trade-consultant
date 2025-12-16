"""
Syntra Supervisor API

API endpoints for position supervision and recommendations.

Endpoints:
    POST /api/supervisor/sync           - Sync positions and get advice
    POST /api/supervisor/register       - Register new trade with scenario
    POST /api/supervisor/action-result  - Log action execution result
    POST /api/supervisor/deactivate     - Deactivate scenario
    GET  /api/supervisor/scenarios      - Get active scenarios
    GET  /api/supervisor/health         - Health check
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.engine import get_session
from src.api.api_key_auth import verify_api_key
from src.services.supervisor_service import supervisor_service


router = APIRouter(prefix="/supervisor", tags=["Supervisor"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class PositionSnapshotModel(BaseModel):
    """Position snapshot from trading bot"""
    trade_id: str = Field(..., description="Unique trade ID")
    symbol: str = Field(..., description="Trading pair (e.g., BTCUSDT)")
    side: str = Field(..., description="Position side (Long/Short)")
    qty: float = Field(..., description="Position size")
    entry_price: float = Field(..., description="Average entry price")
    mark_price: float = Field(..., description="Current mark price")
    unrealized_pnl: float = Field(..., description="Unrealized PnL in USD")
    pnl_pct: float = Field(..., description="PnL percentage")
    leverage: int = Field(..., description="Position leverage")
    liq_price: Optional[float] = Field(None, description="Liquidation price")
    sl_current: Optional[float] = Field(None, description="Current stop loss")
    tp_current: Optional[List[Dict]] = Field(None, description="Current take profits")
    updated_at: str = Field(..., description="Timestamp ISO format")


class SyncRequest(BaseModel):
    """Request for position sync"""
    user_id: int = Field(..., description="Telegram user ID")
    positions: List[PositionSnapshotModel] = Field(
        ...,
        description="List of position snapshots"
    )


class RegisterRequest(BaseModel):
    """Request to register new trade with scenario"""
    trade_id: str = Field(..., description="Unique trade ID")
    user_id: int = Field(..., description="Telegram user ID")
    symbol: str = Field(..., description="Trading pair")
    timeframe: str = Field(..., description="Timeframe (1h, 4h, 1d)")
    side: str = Field(..., description="Position side (Long/Short)")
    scenario_data: Dict[str, Any] = Field(
        ...,
        description="Full scenario from futures-scenarios API"
    )


class ActionResultRequest(BaseModel):
    """Request to log action result"""
    trade_id: str = Field(..., description="Trade ID")
    action_id: str = Field(..., description="Action ID from recommendation")
    status: str = Field(
        ...,
        description="Result status (applied/rejected/failed)"
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Execution details (order_id, error, etc.)"
    )


class DeactivateRequest(BaseModel):
    """Request to deactivate scenario"""
    trade_id: str = Field(..., description="Trade ID")
    reason: str = Field(
        default="position_closed",
        description="Deactivation reason"
    )


class RecommendationModel(BaseModel):
    """Single recommendation"""
    action_id: str
    type: str
    params: Dict[str, Any]
    urgency: str
    confidence: int
    reason_bullets: List[str]
    guards: List[str]
    expires_at: str


class AdvicePackModel(BaseModel):
    """Advice pack response"""
    pack_id: str
    trade_id: str
    user_id: int
    symbol: str
    market_summary: str
    scenario_valid: bool
    time_valid_left_min: int
    risk_state: str
    recommendations: List[Dict[str, Any]]
    cooldown_until: Optional[str]
    price_at_creation: float
    created_at: str
    expires_at: str


class SyncResponse(BaseModel):
    """Response for position sync"""
    success: bool
    advices: List[AdvicePackModel]
    synced_count: int
    timestamp: str


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.post(
    "/sync",
    response_model=SyncResponse,
    summary="Sync Positions",
    description=(
        "Sync open positions from trading bot and get advice packs.\n\n"
        "**Flow:**\n"
        "1. Bot sends all open positions\n"
        "2. Supervisor evaluates each against its scenario\n"
        "3. Returns advice packs for positions needing attention\n\n"
        "**Cooldown:** Each trade has ~15 min cooldown between advices."
    )
)
async def sync_positions(
    request: SyncRequest,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(verify_api_key)
) -> SyncResponse:
    """
    Sync positions and get advice packs.

    This is the main endpoint called periodically by the trading bot.
    """
    try:
        logger.info(
            f"Supervisor sync: user={request.user_id}, "
            f"positions={len(request.positions)}"
        )

        # Convert to dicts for service
        positions_data = [p.model_dump() for p in request.positions]

        # Get advice packs
        advice_packs = await supervisor_service.sync_positions(
            session, request.user_id, positions_data
        )

        # Convert to response models
        advices = []
        for pack in advice_packs:
            advices.append(AdvicePackModel(
                pack_id=pack.pack_id,
                trade_id=pack.trade_id,
                user_id=pack.user_id,
                symbol=pack.symbol,
                market_summary=pack.market_summary,
                scenario_valid=pack.scenario_valid,
                time_valid_left_min=pack.time_valid_left_min,
                risk_state=pack.risk_state,
                recommendations=pack.recommendations,
                cooldown_until=pack.cooldown_until,
                price_at_creation=pack.price_at_creation,
                created_at=pack.created_at,
                expires_at=pack.expires_at,
            ))

        logger.info(
            f"Supervisor sync complete: {len(advices)} advice packs"
        )

        return SyncResponse(
            success=True,
            advices=advices,
            synced_count=len(request.positions),
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

    except Exception as e:
        logger.exception(f"Error in supervisor sync: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Sync failed: {str(e)}"
        )


@router.post(
    "/register",
    summary="Register Trade",
    description=(
        "Register a new trade with its scenario snapshot.\n\n"
        "Call this when opening a position via AI scenario.\n"
        "The scenario data is stored for future evaluation."
    )
)
async def register_trade(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Register new trade with scenario snapshot."""
    try:
        logger.info(
            f"Registering trade: {request.trade_id}, "
            f"{request.symbol} {request.side}"
        )

        snapshot = await supervisor_service.register_scenario(
            session=session,
            trade_id=request.trade_id,
            user_id=request.user_id,
            symbol=request.symbol,
            timeframe=request.timeframe,
            side=request.side,
            scenario_data=request.scenario_data,
        )

        return {
            "success": True,
            "scenario_id": snapshot.id,
            "trade_id": snapshot.trade_id,
            "invalidation_price": snapshot.invalidation_price,
            "valid_until": snapshot.valid_until.isoformat(),
        }

    except Exception as e:
        logger.exception(f"Error registering trade: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Registration failed: {str(e)}"
        )


@router.post(
    "/action-result",
    summary="Log Action Result",
    description=(
        "Log the result of executing a recommendation.\n\n"
        "Call this after the trading bot executes (or rejects) an action."
    )
)
async def log_action_result(
    request: ActionResultRequest,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Log result of action execution."""
    try:
        logger.info(
            f"Action result: trade={request.trade_id}, "
            f"action={request.action_id}, status={request.status}"
        )

        success = await supervisor_service.log_action_result(
            session=session,
            trade_id=request.trade_id,
            action_id=request.action_id,
            status=request.status,
            result=request.details,
        )

        return {
            "success": success,
            "trade_id": request.trade_id,
            "action_id": request.action_id,
            "status": request.status,
        }

    except Exception as e:
        logger.exception(f"Error logging action result: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to log action: {str(e)}"
        )


@router.post(
    "/deactivate",
    summary="Deactivate Scenario",
    description=(
        "Deactivate a scenario when position is closed.\n\n"
        "Call this when a position is fully closed."
    )
)
async def deactivate_scenario(
    request: DeactivateRequest,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Deactivate scenario for closed position."""
    try:
        logger.info(
            f"Deactivating scenario: trade={request.trade_id}, "
            f"reason={request.reason}"
        )

        success = await supervisor_service.deactivate_scenario(
            session=session,
            trade_id=request.trade_id,
            reason=request.reason,
        )

        return {
            "success": success,
            "trade_id": request.trade_id,
            "reason": request.reason,
        }

    except Exception as e:
        logger.exception(f"Error deactivating scenario: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Deactivation failed: {str(e)}"
        )


@router.get(
    "/scenarios",
    summary="Get Active Scenarios",
    description="Get all active scenarios for a user."
)
async def get_active_scenarios(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(verify_api_key)
):
    """Get active scenarios for user."""
    try:
        scenarios = await supervisor_service.get_active_scenarios(
            session, user_id
        )

        return {
            "success": True,
            "user_id": user_id,
            "count": len(scenarios),
            "scenarios": [
                {
                    "id": s.id,
                    "trade_id": s.trade_id,
                    "symbol": s.symbol,
                    "side": s.side,
                    "timeframe": s.timeframe,
                    "invalidation_price": s.invalidation_price,
                    "valid_until": s.valid_until.isoformat(),
                    "created_at": s.created_at.isoformat(),
                }
                for s in scenarios
            ]
        }

    except Exception as e:
        logger.exception(f"Error getting scenarios: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scenarios: {str(e)}"
        )


@router.get(
    "/health",
    summary="Health Check",
    description="Check supervisor service health."
)
async def health_check():
    """Health check endpoint."""
    return {
        "success": True,
        "service": "Syntra Supervisor",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
