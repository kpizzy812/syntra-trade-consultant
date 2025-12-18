# coding: utf-8
"""
Futures Signals Handler for Telegram Bot

Provides /futures command for Premium/VIP users to generate trading scenarios.

Flow:
1. /futures → Show guide + limits info + waiting for input
2. User sends ticker request → Validate via GPT-4o-mini router
3. If clarification needed → Ask questions
4. If OK → Generate scenarios via FuturesAnalysisService
5. Limit incremented ONLY after successful generation

FSM States:
- waiting_for_input: Main state, waiting for user's signal request
- generating: Generating scenarios (transient state)
"""
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.chat_action import ChatActionSender
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud import get_or_create_user
from src.database.models import User, SubscriptionTier
from src.database.limit_manager import (
    RequestType,
    check_limit,
    increment_limit,
    get_usage_stats,
)
from src.services.futures_request_router import futures_request_router
from src.services.futures_analysis_service import futures_analysis_service
from src.utils.i18n import i18n


# ==============================================================================
# FSM STATES
# ==============================================================================


class FuturesStates(StatesGroup):
    """FSM states for futures signals flow"""
    waiting_for_input = State()  # Waiting for user's signal request
    generating = State()         # Generation in progress


# ==============================================================================
# ROUTER
# ==============================================================================


router = Router(name="futures")


# ==============================================================================
# HELPERS
# ==============================================================================


def get_cancel_keyboard(language: str) -> InlineKeyboardMarkup:
    """Get keyboard with cancel button"""
    cancel_text = "❌ Отмена" if language == "ru" else "❌ Cancel"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=cancel_text, callback_data="futures_cancel")]
        ]
    )


def format_scenario_message(scenario: dict, idx: int, language: str) -> str:
    """Format single scenario for Telegram message"""
    bias_emoji = "🟢" if scenario.get("bias") == "long" else "🔴"
    bias_text = "LONG" if scenario.get("bias") == "long" else "SHORT"

    confidence = scenario.get("confidence", 0) * 100

    # Entry plan
    entry_plan = scenario.get("entry_plan", {})
    orders = entry_plan.get("orders", [])

    # Stop loss
    sl = scenario.get("stop_loss", {}).get("recommended", 0)

    # Targets
    targets = scenario.get("targets", [])

    # Leverage
    leverage = scenario.get("leverage", {})

    # Build message
    lines = [
        f"\n{bias_emoji} <b>Сценарий {idx}: {scenario.get('name', bias_text)}</b>",
        f"📊 Направление: <b>{bias_text}</b>",
        f"🎯 Уверенность: <b>{confidence:.0f}%</b>",
        "",
        "<b>📍 Точки входа:</b>",
    ]

    for order in orders[:3]:
        lines.append(f"  • ${order.get('price', 0):,.2f} ({order.get('size_pct', 0)}%)")

    lines.extend([
        "",
        f"<b>🛑 Стоп-лосс:</b> ${sl:,.2f}",
        "",
        "<b>🎯 Тейк-профиты:</b>",
    ])

    for tp in targets[:3]:
        lines.append(
            f"  • TP{tp.get('level', 0)}: ${tp.get('price', 0):,.2f} "
            f"(RR {tp.get('rr', 0):.1f}x, {tp.get('partial_close_pct', 0)}%)"
        )

    lines.extend([
        "",
        f"<b>📈 Плечо:</b> {leverage.get('recommended', 'N/A')}",
    ])

    # Why section
    why = scenario.get("why", {})
    factors = why.get("bullish_factors") or why.get("bearish_factors") or []
    if factors:
        lines.append("")
        lines.append("<b>💡 Почему:</b>")
        for factor in factors[:2]:
            lines.append(f"  • {factor}")

    return "\n".join(lines)


def format_full_response(
    ticker: str,
    timeframe: str,
    current_price: float,
    scenarios: list,
    market_context: dict,
    limits_remaining: int,
    language: str
) -> str:
    """Format full response with all scenarios"""

    # Header
    header = f"""📊 <b>Торговые сценарии: {ticker}</b>
⏱ Таймфрейм: {timeframe.upper()}
💵 Текущая цена: ${current_price:,.2f}

<b>📈 Контекст рынка:</b>
• Тренд: {market_context.get('trend', 'N/A')}
• Фаза: {market_context.get('phase', 'N/A')}
• Настроение: {market_context.get('sentiment', 'N/A')}
• Волатильность: {market_context.get('volatility', 'N/A')}
"""

    # Scenarios
    scenarios_text = ""
    for idx, scenario in enumerate(scenarios, 1):
        scenarios_text += format_scenario_message(scenario, idx, language)

    # Footer
    footer = f"""

━━━━━━━━━━━━━━━━━━━━━━━
📌 Сигналов осталось сегодня: <b>{limits_remaining}</b>

⚠️ <i>Это не финансовый совет. Всегда используй риск-менеджмент.</i>
"""

    return header + scenarios_text + footer


def validate_scenario_output(result: dict) -> tuple[bool, str | None]:
    """Validate scenario output before incrementing limit"""
    if not result.get("success"):
        return False, "Generation failed"

    scenarios = result.get("scenarios", [])
    if not scenarios:
        return False, "No scenarios generated"

    for idx, s in enumerate(scenarios):
        entry_plan = s.get("entry_plan")
        if not entry_plan or not entry_plan.get("orders"):
            return False, f"Scenario {idx+1}: Missing entry plan"

        sl = s.get("stop_loss", {}).get("recommended")
        if not sl or sl <= 0:
            return False, f"Scenario {idx+1}: Invalid stop-loss"

        targets = s.get("targets")
        if not targets:
            return False, f"Scenario {idx+1}: No targets"

    return True, None


# ==============================================================================
# HANDLERS
# ==============================================================================


@router.message(Command("futures"))
async def cmd_futures(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user_language: str = "ru"
) -> None:
    """
    /futures command - Show guide and start futures flow

    Args:
        message: Telegram message
        state: FSM context
        session: Database session
        user_language: User's language
    """
    user = message.from_user

    # Get or create database user
    db_user, _ = await get_or_create_user(
        session,
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    # Check tier (Premium/VIP only)
    if not db_user.subscription:
        tier = SubscriptionTier.FREE
    else:
        tier = SubscriptionTier(db_user.subscription.tier)

    if tier not in (SubscriptionTier.PREMIUM, SubscriptionTier.VIP):
        await message.answer(
            i18n.get("futures.premium_required", user_language),
            parse_mode="HTML"
        )
        return

    # Check limit
    has_remaining, current_count, limit = await check_limit(
        session, db_user, RequestType.FUTURES
    )

    if not has_remaining:
        await message.answer(
            i18n.get(
                "futures.limit_reached",
                user_language,
                used=current_count,
                limit=limit
            ),
            parse_mode="HTML"
        )
        return

    # Show guide
    remaining = limit - current_count
    guide_text = i18n.get(
        "futures.guide",
        user_language,
        remaining=remaining,
        limit=limit
    )

    keyboard = get_cancel_keyboard(user_language)

    await message.answer(guide_text, parse_mode="HTML", reply_markup=keyboard)

    # Set state
    await state.set_state(FuturesStates.waiting_for_input)
    await state.update_data(user_id=db_user.id, language=user_language)

    logger.info(f"[Futures] User {user.id} entered futures mode (remaining: {remaining})")


@router.message(StateFilter(FuturesStates.waiting_for_input), F.text)
async def process_futures_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user_language: str = "ru"
) -> None:
    """
    Process user input in futures mode

    Validates request and generates scenarios if appropriate.
    """
    user = message.from_user
    user_text = message.text

    # Ignore commands
    if user_text.startswith("/"):
        await state.clear()
        return

    # Get state data
    state_data = await state.get_data()
    db_user_id = state_data.get("user_id")
    language = state_data.get("language", user_language)

    # Get database user
    db_user, _ = await get_or_create_user(
        session,
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    # Re-check limit (could have changed)
    has_remaining, current_count, limit = await check_limit(
        session, db_user, RequestType.FUTURES
    )

    if not has_remaining:
        await message.answer(
            i18n.get(
                "futures.limit_reached",
                language,
                used=current_count,
                limit=limit
            ),
            parse_mode="HTML"
        )
        await state.clear()
        return

    # Send "analyzing" message
    thinking_msg = await message.answer(
        i18n.get("futures.analyzing", language),
        parse_mode="HTML"
    )

    try:
        # Validate request via GPT-4o-mini router
        validation = await futures_request_router.validate_request(
            user_text, language=language
        )

        # Not a futures request
        if not validation.is_futures_request:
            await thinking_msg.edit_text(
                i18n.get("futures.not_signal_request", language),
                parse_mode="HTML"
            )
            # Don't clear state - let user try again
            return

        # Needs clarification
        if futures_request_router.should_ask_clarification(validation):
            questions = validation.clarifying_questions or []
            questions_text = "\n".join([f"• {q}" for q in questions])

            await thinking_msg.edit_text(
                i18n.get(
                    "futures.need_clarification",
                    language,
                    questions=questions_text
                ),
                parse_mode="HTML"
            )
            # Don't clear state - wait for clarified input
            return

        # Ready to generate
        await state.set_state(FuturesStates.generating)

        ticker = validation.ticker
        timeframe = validation.timeframe or "4h"
        mode = validation.mode or "standard"

        # Show default message if applicable
        if validation.timeframe_was_default:
            default_msg = futures_request_router.get_default_message(validation, language)
            if default_msg:
                await thinking_msg.edit_text(
                    f"{i18n.get('futures.generating', language)}\n\n{default_msg}",
                    parse_mode="HTML"
                )
            else:
                await thinking_msg.edit_text(
                    i18n.get("futures.generating", language),
                    parse_mode="HTML"
                )
        else:
            await thinking_msg.edit_text(
                i18n.get("futures.generating", language),
                parse_mode="HTML"
            )

        logger.info(f"[Futures] Generating: {ticker} {timeframe} {mode} for user {user.id}")

        # Generate scenarios
        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            result = await futures_analysis_service.analyze_symbol(
                symbol=ticker,
                timeframe=timeframe,
                max_scenarios=3,
                mode=mode
            )

        # Validate output
        is_valid, validation_error = validate_scenario_output(result)

        if not is_valid:
            logger.error(f"[Futures] Validation failed: {validation_error}")
            await thinking_msg.edit_text(
                i18n.get(
                    "futures.generation_failed",
                    language,
                    error=validation_error
                ),
                parse_mode="HTML"
            )
            await state.set_state(FuturesStates.waiting_for_input)
            return

        # Increment limit ONLY after successful validation
        await increment_limit(session, db_user.id, RequestType.FUTURES)
        limits_remaining = limit - current_count - 1

        # Format and send response
        response_text = format_full_response(
            ticker=ticker,
            timeframe=timeframe,
            current_price=result.get("current_price", 0),
            scenarios=result.get("scenarios", []),
            market_context=result.get("market_context", {}),
            limits_remaining=limits_remaining,
            language=language
        )

        await thinking_msg.edit_text(response_text, parse_mode="HTML")

        logger.info(
            f"[Futures] Success! User {user.id}: {ticker} {timeframe}, "
            f"scenarios={len(result.get('scenarios', []))}, remaining={limits_remaining}"
        )

        # Clear state
        await state.clear()

    except Exception as e:
        logger.exception(f"[Futures] Error processing request: {e}")
        await thinking_msg.edit_text(
            i18n.get("futures.error", language),
            parse_mode="HTML"
        )
        await state.set_state(FuturesStates.waiting_for_input)


@router.callback_query(F.data == "futures_cancel")
async def callback_futures_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    user_language: str = "ru"
) -> None:
    """Handle cancel button in futures mode"""
    await state.clear()

    language = user_language

    await callback.message.edit_text(
        i18n.get("futures.cancelled", language),
        parse_mode="HTML"
    )
    await callback.answer()

    logger.info(f"[Futures] User {callback.from_user.id} cancelled futures mode")
