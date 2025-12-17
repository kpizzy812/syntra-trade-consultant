# coding: utf-8
"""
Chat handler with intelligent AI function calling

AI automatically decides when to:
- Fetch crypto prices
- Get latest news
- Compare cryptocurrencies
- Get market overview

No manual parsing needed! OpenAI Function Calling handles everything.
"""
from datetime import datetime
from loguru import logger

from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.openai_service_two_step import two_step_service
from src.services.ads_service import enhance_response_with_ad
from src.services.points_service import PointsService
from src.database.crud import get_or_create_user
from src.database.models import PointsTransactionType
from src.utils.i18n import i18n
from src.utils.markdown_converter import convert_to_telegram_html
from config.prompts import enhance_response_with_character


router = Router(name="chat")

# Streaming configuration
STREAM_UPDATE_INTERVAL = 1.5  # Update message every 1.5 seconds
MIN_CHARS_FOR_UPDATE = 100  # Or every 100 characters


@router.message(F.text & ~F.text.startswith("/") & (F.chat.type == "private"))
async def handle_text_message(
    message: Message, session: AsyncSession, user_language: str = "ru"
):
    """
    Handle text messages with intelligent AI function calling

    The AI automatically decides when to call tools:
    - User: "Как дела у Bitcoin?" → AI calls get_crypto_price('bitcoin')
    - User: "ETH или SOL?" → AI calls compare_cryptos(['ethereum', 'solana'])
    - User: "Последние новости BTC?" → AI calls get_crypto_news('BTC')
    - User: "Что происходит на рынке?" → AI calls get_market_overview()

    Features:
    - ✅ Natural language - no commands needed
    - ✅ AI decides what data to fetch
    - ✅ Automatic tool execution
    - ✅ Streaming responses
    - ✅ Cost tracking
    - ✅ Multi-language support

    Args:
        message: Incoming message
        session: Database session (from middleware)
        user_language: User language (from LanguageMiddleware)
    """
    user = message.from_user
    user_text = message.text

    logger.info(
        f"[TOOLS] Processing message from user {user.id} (lang: {user_language}): {user_text[:50]}..."
    )

    # Ensure user exists in database
    db_user, _ = await get_or_create_user(
        session,
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        telegram_language=user.language_code,
    )

    # Get user's tier (with fallback to FREE)
    user_tier = "free"
    if hasattr(db_user, 'subscription') and db_user.subscription:
        user_tier = db_user.subscription.tier

    # Send initial "thinking" message
    thinking_msg = await message.answer(i18n.get("chat.thinking", user_language))

    try:
        # Stream AI response with intelligent tool calling
        # AI will automatically decide if it needs to:
        # - Get prices
        # - Fetch news
        # - Compare coins
        # - Get market data
        full_response = ""
        last_update_time = datetime.now()
        last_update_length = 0

        async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
            # Use two-step service for better personality (tier-aware)
            async for chunk in two_step_service.stream_two_step_completion(
                session=session,
                user_id=db_user.id,
                user_message=user_text,
                user_language=user_language,
                user_tier=user_tier,  # 🚨 Pass tier for context/memory
            ):
                full_response += chunk

                # Update message periodically
                now = datetime.now()
                time_since_update = (now - last_update_time).total_seconds()
                chars_since_update = len(full_response) - last_update_length

                should_update = (
                    time_since_update >= STREAM_UPDATE_INTERVAL
                    or chars_since_update >= MIN_CHARS_FOR_UPDATE
                )

                if should_update and full_response.strip():
                    try:
                        # Convert markdown to Telegram HTML
                        html_response = convert_to_telegram_html(full_response)
                        await thinking_msg.edit_text(
                            html_response, parse_mode="HTML"
                        )
                        last_update_time = now
                        last_update_length = len(full_response)
                    except Exception as e:
                        # Ignore edit errors (message not modified, rate limits, etc.)
                        logger.debug(f"Message edit error (ignored): {e}")

        # Final update with complete response
        if full_response.strip():
            # Apply post-processing to enhance character
            enhanced_response = enhance_response_with_character(full_response)
            # Add native ad if appropriate (based on context and frequency)
            # Умная стратегия: первые 24ч и 7 сообщений — без рекламы
            enhanced_response = enhance_response_with_ad(
                response=enhanced_response,
                user_id=db_user.id,
                user_message=user_text,
                user_language=user_language,
                user_tier=user_tier,
                user_created_at=db_user.created_at,
            )
            # Convert to Telegram HTML
            html_response = convert_to_telegram_html(enhanced_response)

            try:
                await thinking_msg.edit_text(html_response, parse_mode="HTML")
                logger.info(
                    f"[TOOLS] Response sent to user {user.id} "
                    f"({len(html_response)} chars, enhanced: {enhanced_response != full_response})"
                )

                # 💎 Award points for successful text request
                try:
                    points_transaction = await PointsService.earn_points(
                        session=session,
                        user_id=db_user.id,
                        transaction_type=PointsTransactionType.EARN_TEXT_REQUEST,
                        description=f"Анализ: {user_text[:50]}...",
                        metadata={"message_id": message.message_id, "language": user_language},
                        transaction_id=f"text_req:{db_user.id}:{message.message_id}",
                    )
                    if points_transaction:
                        logger.info(
                            f"💎 Awarded {points_transaction.amount} points to user {db_user.id} "
                            f"for text request (balance: {points_transaction.balance_after})"
                        )
                except Exception as points_error:
                    # Don't fail the request if points fail
                    logger.error(f"Failed to award points: {points_error}")

            except Exception as e:
                logger.error(f"Failed to send final response: {e}")
                await thinking_msg.edit_text(
                    i18n.get("chat.error_sending", user_language)
                )
        else:
            await thinking_msg.edit_text(i18n.get("chat.no_response", user_language))

    except Exception as e:
        logger.exception(f"[TOOLS] Error handling message from user {user.id}: {e}")
        try:
            await thinking_msg.edit_text(i18n.get("chat.critical_error", user_language))
        except Exception:
            pass
