# coding: utf-8
"""
Futures Signals API - User-facing endpoint for futures signals

Отличия от futures_scenarios.py (API Key auth для trading bot):
- Использует user auth (tma / JWT) для обычных пользователей
- Проверяет subscription tier (Premium/VIP only)
- Проверяет лимиты (futures_count)
- Валидирует запросы через GPT-4o-mini router
- Инкрементирует лимит ТОЛЬКО после успешной генерации

Flow:
1. Auth Check → get user from tma/JWT
2. Tier Check → Premium/VIP only (403 if FREE/BASIC)
3. Limit Check → check futures_count (429 if exceeded)
4. Router Check → GPT-4o-mini validates request
5. If confidence < 0.6 → return clarifying questions
6. If OK → generate scenarios via FuturesAnalysisService
7. Validate output (JSON valid, has scenarios, RR sane)
8. If valid → increment limit
9. Return response

Endpoints:
    POST /api/futures-signals/analyze - Analyze and generate signals
    GET /api/futures-signals/limits - Get current limits info
    POST /api/futures-signals/validate - Only validate request (no generation)
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.api.auth import get_current_user
from src.database.engine import get_session
from src.database.models import User, SubscriptionTier
from src.database.limit_manager import (
    RequestType,
    check_limit,
    increment_limit,
    get_usage_stats,
)
from src.services.futures_request_router import (
    futures_request_router,
    FuturesRequestValidation,
)
from src.services.futures_analysis_service import futures_analysis_service
from src.database.crud import (
    create_chat,
    get_chat_by_id,
    add_chat_message_to_chat,
    update_chat_title,
)


router = APIRouter(prefix="/futures-signals", tags=["Futures Signals"])


# ==============================================================================
# REQUEST/RESPONSE MODELS
# ==============================================================================


class FuturesSignalRequest(BaseModel):
    """Request for futures signal analysis"""
    message: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="User message (natural language)",
        example="сигнал по BTC 4h"
    )
    ticker: Optional[str] = Field(
        default=None,
        description="Override ticker (if already extracted)",
        example="BTCUSDT"
    )
    timeframe: Optional[str] = Field(
        default=None,
        description="Override timeframe (if already extracted)",
        pattern="^(15m|1h|4h|1d|1w)$",
        example="4h"
    )
    mode: Optional[str] = Field(
        default="standard",
        description="Trading mode: conservative, standard, high_risk, meme",
        pattern="^(conservative|standard|high_risk|meme)$",
        example="standard"
    )
    language: Optional[str] = Field(
        default="ru",
        description="Response language",
        example="ru"
    )
    chat_id: Optional[int] = Field(
        default=None,
        description="Chat ID to save messages to. If not provided, new chat will be created."
    )


class ClarifyingResponse(BaseModel):
    """Response when clarification needed"""
    status: str = "clarification_needed"
    confidence: float
    questions: List[str]
    detected_ticker: Optional[str] = None
    detected_timeframe: Optional[str] = None
    default_message: Optional[str] = None


class SignalGeneratedResponse(BaseModel):
    """Response with generated signal"""
    status: str = "success"
    analysis_id: str
    ticker: str
    timeframe: str
    timeframe_was_default: bool = False
    default_message: Optional[str] = None
    mode: str
    current_price: float
    scenarios: List[dict]
    market_context: dict
    key_levels: dict
    data_quality: dict
    limits_remaining: int
    limit_incremented: bool = True
    chat_id: Optional[int] = None
    chat_title: Optional[str] = None


class NotFuturesResponse(BaseModel):
    """Response when request is not about futures"""
    status: str = "not_futures_request"
    message: str
    suggestion: str


class LimitsResponse(BaseModel):
    """Response with limits info"""
    tier: str
    futures_available: bool
    futures_limit: int
    futures_used: int
    futures_remaining: int
    resets_at: str


class ValidationResponse(BaseModel):
    """Response from validation-only endpoint"""
    is_futures_request: bool
    confidence: float
    has_sufficient_data: bool
    ticker: Optional[str]
    timeframe: Optional[str]
    timeframe_was_default: bool
    mode: str
    clarifying_questions: Optional[List[str]]
    will_proceed: bool
    reason: str


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def validate_scenario_output(result: dict) -> tuple[bool, Optional[str]]:
    """
    Validate scenario output before incrementing limit.

    Returns:
        (is_valid, error_message)
    """
    # 1. Check success flag
    if not result.get("success"):
        return False, "Generation failed"

    scenarios = result.get("scenarios", [])
    if not scenarios:
        return False, "No scenarios generated"

    for idx, s in enumerate(scenarios):
        # 2. Entry plan exists
        entry_plan = s.get("entry_plan")
        if not entry_plan or not entry_plan.get("orders"):
            return False, f"Scenario {idx+1}: Missing entry plan"

        # 3. Stop loss exists and is sane
        sl = s.get("stop_loss", {}).get("recommended")
        if not sl or sl <= 0:
            return False, f"Scenario {idx+1}: Invalid stop-loss"

        # 4. At least one target
        targets = s.get("targets")
        if not targets:
            return False, f"Scenario {idx+1}: No take-profit targets"

        # 5. RR sanity check (> 0.5 for at least TP1)
        tp1_rr = targets[0].get("rr", 0) if targets else 0
        if tp1_rr < 0.5:
            return False, f"Scenario {idx+1}: RR too low ({tp1_rr})"

    return True, None


async def check_user_access(
    user: User,
    session: AsyncSession
) -> tuple[bool, int, int, Optional[str]]:
    """
    Check if user has access to futures signals.

    Returns:
        (has_access, current_count, limit, error_message)
    """
    # Get user tier
    if not user.subscription:
        tier = SubscriptionTier.FREE
    else:
        tier = SubscriptionTier(user.subscription.tier)

    # Check tier (Premium/VIP only)
    if tier not in (SubscriptionTier.PREMIUM, SubscriptionTier.VIP):
        return False, 0, 0, f"Futures signals available for Premium/VIP only (current: {tier.value})"

    # Check limit
    has_remaining, current_count, limit = await check_limit(
        session, user, RequestType.FUTURES
    )

    if not has_remaining:
        return False, current_count, limit, f"Daily limit reached ({current_count}/{limit})"

    return True, current_count, limit, None


# ==============================================================================
# ENDPOINTS
# ==============================================================================


@router.post(
    "/analyze",
    summary="Analyze and generate futures signal",
    description=(
        "Анализировать запрос и сгенерировать торговые сценарии.\n\n"
        "**Доступно только для Premium/VIP**\n\n"
        "**Flow:**\n"
        "1. Валидация запроса через GPT-4o-mini\n"
        "2. Если данных недостаточно → возврат уточняющих вопросов\n"
        "3. Если OK → генерация сценариев\n"
        "4. Лимит списывается ТОЛЬКО после успешной генерации\n\n"
        "**Possible responses:**\n"
        "- `status: success` - сценарии сгенерированы\n"
        "- `status: clarification_needed` - нужны уточнения\n"
        "- `status: not_futures_request` - это не запрос на сигнал"
    )
)
async def analyze_futures_signal(
    request: FuturesSignalRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Analyze user request and generate futures signal if appropriate.
    """
    logger.info(
        f"[Futures Signals] User {user.id} request: '{request.message[:50]}...'"
    )

    # 1. Check access (tier + limit)
    has_access, current_count, limit, error = await check_user_access(user, session)
    if not has_access:
        if "Premium/VIP only" in error:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "premium_required",
                    "message": error,
                    "upgrade_url": "/subscribe"
                }
            )
        else:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "limit_exceeded",
                    "message": error,
                    "limit": limit,
                    "used": current_count,
                    "resets_at": "00:00 UTC"
                }
            )

    # 2. Validate request via GPT-4o-mini router
    language = request.language or "ru"

    # If ticker/timeframe provided, skip validation
    if request.ticker and request.timeframe:
        validation = FuturesRequestValidation(
            is_futures_request=True,
            has_sufficient_data=True,
            confidence=1.0,
            ticker=futures_request_router.normalize_ticker(request.ticker),
            timeframe=request.timeframe,
            timeframe_was_default=False,
            mode=request.mode or "standard",
            clarifying_questions=None,
        )
    else:
        validation = await futures_request_router.validate_request(
            request.message,
            language=language
        )

    # 3. Handle non-futures request
    if not validation.is_futures_request:
        logger.info(f"[Futures Signals] Not a futures request: {request.message[:50]}...")
        return NotFuturesResponse(
            status="not_futures_request",
            message="Это не запрос на торговый сигнал." if language == "ru"
                    else "This is not a trading signal request.",
            suggestion="Используй команду /futures или режим Signals для получения торговых сценариев." if language == "ru"
                       else "Use /futures command or Signals mode to get trading scenarios."
        )

    # 4. Check if clarification needed
    if futures_request_router.should_ask_clarification(validation):
        logger.info(
            f"[Futures Signals] Clarification needed: confidence={validation.confidence:.2f}"
        )
        return ClarifyingResponse(
            status="clarification_needed",
            confidence=validation.confidence,
            questions=validation.clarifying_questions or [],
            detected_ticker=validation.ticker,
            detected_timeframe=validation.timeframe,
            default_message=futures_request_router.get_default_message(validation, language)
        )

    # 5. Generate scenarios
    try:
        ticker = validation.ticker
        timeframe = validation.timeframe or "4h"
        mode = validation.mode or "standard"

        logger.info(
            f"[Futures Signals] Generating scenarios: {ticker} {timeframe} {mode}"
        )

        result = await futures_analysis_service.analyze_symbol(
            symbol=ticker,
            timeframe=timeframe,
            max_scenarios=3,
            mode=mode
        )

        # 6. Validate output
        is_valid, validation_error = validate_scenario_output(result)

        if not is_valid:
            logger.error(f"[Futures Signals] Output validation failed: {validation_error}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "generation_failed",
                    "message": f"Сценарии не прошли валидацию: {validation_error}" if language == "ru"
                              else f"Scenarios failed validation: {validation_error}",
                    "limit_incremented": False
                }
            )

        # 7. Increment limit ONLY after successful validation
        await increment_limit(session, user.id, RequestType.FUTURES)
        limits_remaining = limit - current_count - 1

        logger.info(
            f"[Futures Signals] Success! User {user.id}: {ticker} {timeframe}, "
            f"scenarios={len(result['scenarios'])}, remaining={limits_remaining}"
        )

        # 8. Save to chat (create if needed)
        chat_id = request.chat_id
        chat_title = None

        try:
            if chat_id:
                # Get existing chat
                chat = await get_chat_by_id(session, chat_id)
                if not chat or chat.user_id != user.id:
                    # Chat not found or doesn't belong to user - create new
                    chat_id = None

            if not chat_id:
                # Create new chat with generated title
                chat_title = f"📊 {ticker} {timeframe.upper()}"
                chat = await create_chat(session, user.id, chat_title)
                chat_id = chat.id
                logger.info(f"[Futures Signals] Created chat {chat_id}: {chat_title}")
            else:
                chat_title = chat.title
                # Update title if it's still "New Chat"
                if chat_title == "New Chat":
                    chat_title = f"📊 {ticker} {timeframe.upper()}"
                    await update_chat_title(session, chat_id, chat_title)

            # Save user message
            await add_chat_message_to_chat(
                session,
                chat_id=chat_id,
                role="user",
                content=request.message
            )

            # Save AI response as JSON (frontend will parse and render it)
            import json
            ai_response = json.dumps({
                "type": "futures_signal",
                "analysis_id": result.get("analysis_id", ""),
                "ticker": ticker,
                "timeframe": timeframe,
                "mode": mode,
                "current_price": result.get("current_price", 0),
                "scenarios": result.get("scenarios", []),
                "market_context": result.get("market_context", {}),
                "key_levels": result.get("key_levels", {}),
                "data_quality": result.get("data_quality", {}),
            }, ensure_ascii=False)

            await add_chat_message_to_chat(
                session,
                chat_id=chat_id,
                role="assistant",
                content=ai_response,
                model="futures-signal"
            )

            await session.commit()
            logger.info(f"[Futures Signals] Saved messages to chat {chat_id}")

        except Exception as e:
            logger.warning(f"[Futures Signals] Failed to save chat: {e}")
            # Don't fail the request if chat save fails
            # Just log and continue with response

        # 9. Build response
        return SignalGeneratedResponse(
            status="success",
            analysis_id=result.get("analysis_id", ""),
            ticker=ticker,
            timeframe=timeframe,
            timeframe_was_default=validation.timeframe_was_default,
            default_message=futures_request_router.get_default_message(validation, language),
            mode=mode,
            current_price=result.get("current_price", 0),
            scenarios=result.get("scenarios", []),
            market_context=result.get("market_context", {}),
            key_levels=result.get("key_levels", {}),
            data_quality=result.get("data_quality", {}),
            limits_remaining=limits_remaining,
            limit_incremented=True,
            chat_id=chat_id,
            chat_title=chat_title
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[Futures Signals] Error generating scenarios: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Ошибка генерации: {str(e)}" if language == "ru"
                          else f"Generation error: {str(e)}",
                "limit_incremented": False
            }
        )


@router.get(
    "/limits",
    response_model=LimitsResponse,
    summary="Get futures signals limits",
    description="Получить информацию о лимитах futures signals для текущего пользователя"
)
async def get_futures_limits(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LimitsResponse:
    """Get current user's futures signals limits."""

    usage = await get_usage_stats(session, user)
    futures_stats = usage.get("futures", {})

    return LimitsResponse(
        tier=usage.get("tier", "free"),
        futures_available=futures_stats.get("available", False),
        futures_limit=futures_stats.get("limit", 0),
        futures_used=futures_stats.get("count", 0),
        futures_remaining=futures_stats.get("remaining", 0),
        resets_at="00:00 UTC"
    )


@router.post(
    "/validate",
    response_model=ValidationResponse,
    summary="Validate request without generation",
    description=(
        "Только валидация запроса через GPT-4o-mini без генерации сценариев.\n"
        "Полезно для UI: показать что будет сгенерировано перед подтверждением."
    )
)
async def validate_futures_request(
    request: FuturesSignalRequest,
    user: User = Depends(get_current_user),
) -> ValidationResponse:
    """
    Validate request without generating scenarios.
    Does NOT check or decrement limits.
    """
    language = request.language or "ru"

    validation = await futures_request_router.validate_request(
        request.message,
        language=language
    )

    will_proceed = futures_request_router.should_auto_proceed(validation)

    if not validation.is_futures_request:
        reason = "Not a futures signal request"
    elif will_proceed:
        reason = "Ready to generate"
    elif futures_request_router.should_ask_clarification(validation):
        reason = "Needs clarification"
    else:
        reason = "Insufficient data"

    return ValidationResponse(
        is_futures_request=validation.is_futures_request,
        confidence=validation.confidence,
        has_sufficient_data=validation.has_sufficient_data,
        ticker=validation.ticker,
        timeframe=validation.timeframe,
        timeframe_was_default=validation.timeframe_was_default,
        mode=validation.mode,
        clarifying_questions=validation.clarifying_questions,
        will_proceed=will_proceed,
        reason=reason
    )
