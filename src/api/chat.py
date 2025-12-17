"""
Chat API Endpoints with SSE Streaming
Provides AI chat functionality for Mini App
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, AsyncGenerator
from pydantic import BaseModel
import json
import base64
from loguru import logger

from src.database.models import User, PointsTransactionType
from src.database.engine import get_session
from src.api.auth import get_current_user
from src.services.openai_service import OpenAIService
from src.services.ads_service import get_ads_service
from src.services.posthog_service import track_limit_hit
from src.services.points_service import PointsService
from src.utils.i18n import i18n
from src.database.crud import (
    get_chat_history,
    check_request_limit,
    increment_request_count,
    get_chat_message_by_id,
    delete_chat_message,
    get_previous_user_message,
    get_or_create_default_chat,
    get_chat_by_id,
    update_chat_title,
)

# Create router
router = APIRouter(prefix="/chat", tags=["chat"])

# Initialize OpenAI service
openai_service = OpenAIService()


def create_rate_limit_response(
    user: User,
    current_count: int,
    limit: int,
) -> dict:
    """
    Create informative rate limit response with upgrade CTA

    Returns:
        Dict with error details, message, and upgrade info
    """
    user_lang = user.language or "ru"
    user_tier = "free"
    if hasattr(user, "subscription") and user.subscription:
        user_tier = user.subscription.tier

    # Calculate reset time (next midnight UTC)
    now_utc = datetime.now(timezone.utc)
    next_midnight = (now_utc + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    hours_until_reset = int((next_midnight - now_utc).total_seconds() / 3600)

    # Get localized message
    message = i18n.get(
        "errors.rate_limit_with_cta",
        user_lang,
        limit=limit,
        hours=hours_until_reset,
    )

    return {
        "error": "rate_limit_exceeded",
        "error_code": "RATE_LIMIT_EXCEEDED",
        "message": message,
        "requests_used": current_count,
        "requests_limit": limit,
        "reset_hours": hours_until_reset,
        "reset_at": next_midnight.isoformat(),
        "current_tier": user_tier,
        "show_upgrade": user_tier == "free",  # Show upgrade CTA for free users
    }


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str
    context: str | None = None
    image: str | None = None  # Base64 encoded image
    chat_id: int | None = None  # Optional chat ID for multiple chats support


class ChatHistoryResponse(BaseModel):
    """Response model for chat history"""
    messages: list[Dict[str, Any]]


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Stream AI chat response using Server-Sent Events (SSE)

    Args:
        request: Chat request with message and optional context
        user: Authenticated user
        session: Database session

    Returns:
        StreamingResponse with SSE events

    Example Response (SSE format):
        data: {"type": "token", "content": "Hello"}
        data: {"type": "token", "content": " world"}
        data: {"type": "done"}
    """
    # Log incoming request
    logger.info(
        f"Chat stream request from user {user.id} (@{user.username}): "
        f"message='{request.message[:100]}{'...' if len(request.message) > 100 else ''}', "
        f"has_image={bool(request.image)}, chat_id={request.chat_id}"
    )

    try:
        # Get or create chat (if chat_id not provided, use default chat)
        if not request.chat_id:
            chat = await get_or_create_default_chat(session, user.id)
            chat_id = chat.id
            logger.debug(f"Using default chat {chat_id} for user {user.id}")
        else:
            chat_id = request.chat_id
            logger.debug(f"Using provided chat {chat_id} for user {user.id}")

        # Check rate limit
        can_send, current_count, limit = await check_request_limit(session, user)
        if not can_send:
            # 📊 Track limit hit
            user_tier = "free"
            if hasattr(user, 'subscription') and user.subscription:
                user_tier = user.subscription.tier
            track_limit_hit(user.id, user_tier, "text", current_count, limit)

            raise HTTPException(
                status_code=429,
                detail=create_rate_limit_response(user, current_count, limit),
            )

        async def event_generator() -> AsyncGenerator[str, None]:
            """
            Generator for SSE events

            Yields SSE-formatted messages:
            - data: {json}\n\n format
            """
            token_count = 0
            full_response = ""

            # Get user's tier (with fallback to FREE) - needed for ads and model routing
            user_tier = "free"
            if hasattr(user, 'subscription') and user.subscription:
                user_tier = user.subscription.tier

            try:
                # Check if image is provided
                if request.image:
                    # Decode base64 image
                    try:
                        # Remove data URL prefix if present (e.g., "data:image/png;base64,")
                        image_data = request.image
                        if "base64," in image_data:
                            image_data = image_data.split("base64,")[1]

                        image_bytes = base64.b64decode(image_data)
                    except Exception as e:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Invalid image data: {str(e)}"
                        )

                    # Stream image analysis
                    logger.info(f"Starting image analysis stream for user {user.id}")
                    async for chunk in openai_service.stream_image_analysis(
                        session=session,
                        user_id=user.id,
                        image_bytes=image_bytes,
                        user_language=user.language or "ru",
                        user_prompt=request.message if request.message else None,
                        detail="auto",  # Let OpenAI decide detail level
                    ):
                        # Format as SSE event
                        event_data = {
                            "type": "token",
                            "content": chunk
                        }
                        token_count += len(chunk)
                        yield f"data: {json.dumps(event_data)}\n\n"
                else:
                    # Stream regular text completion
                    logger.info(f"Starting text completion stream for user {user.id}")

                    async for chunk in openai_service.stream_completion(
                        session=session,
                        user_id=user.id,
                        user_message=request.message,
                        user_language=user.language or "ru",
                        user_tier=user_tier,  # 🚨 CRITICAL: Pass tier for model routing
                        use_tools=True,  # Enable crypto tools (price, analysis, etc.)
                        chat_id=chat_id,  # 🚨 Pass chat_id for multiple chats support
                    ):
                        # Format as SSE event
                        event_data = {
                            "type": "token",
                            "content": chunk
                        }
                        full_response += chunk
                        token_count += len(chunk)
                        yield f"data: {json.dumps(event_data)}\n\n"

                    # Auto-generate chat title if this is the first message in a new chat
                    if not request.image and full_response:
                        try:
                            chat_obj = await get_chat_by_id(session, chat_id, user.id)
                            if chat_obj and chat_obj.title in ("New Chat", "Новый чат"):
                                logger.info(f"Auto-generating title for chat {chat_id}")
                                new_title = await openai_service.generate_chat_title(
                                    user_message=request.message,
                                    assistant_response=full_response,
                                    user_language=user.language or "ru",
                                )
                                await update_chat_title(session, chat_id, user.id, new_title)
                                logger.info(f"Chat {chat_id} renamed to: '{new_title}'")
                        except Exception as title_error:
                            logger.error(f"Failed to auto-generate chat title: {title_error}")
                            # Don't fail the stream if title generation fails

                # Increment request count AFTER successful completion
                await increment_request_count(session, user.id)

                # 💎 Award $SYNTRA points for AI request
                transaction_type = (
                    PointsTransactionType.EARN_VISION_REQUEST
                    if request.image
                    else PointsTransactionType.EARN_TEXT_REQUEST
                )
                await PointsService.earn_points(
                    session=session,
                    user_id=user.id,
                    transaction_type=transaction_type,
                    description=f"Chat request ({transaction_type})",
                    metadata={
                        "chat_id": chat_id,
                        "has_image": bool(request.image),
                        "message_length": len(request.message),
                    },
                    transaction_id=f"chat:{user.id}:{chat_id}:{datetime.now(timezone.utc).timestamp()}",
                )
                logger.info(f"💎 Awarded points for {transaction_type} to user {user.id}")

                # Check if we should add native ad to response
                # Умная стратегия: первые 24ч и 7 сообщений — без рекламы
                ads_service = get_ads_service()
                should_add_ad, ad_text = ads_service.maybe_add_chat_ad(
                    user_id=user.id,
                    user_message=request.message,
                    user_language=user.language or "ru",
                    user_tier=user_tier,
                    user_created_at=user.created_at,
                )

                # Send ad as final token if appropriate
                if should_add_ad and ad_text:
                    ad_event = {
                        "type": "token",
                        "content": ad_text
                    }
                    yield f"data: {json.dumps(ad_event)}\n\n"
                    logger.info(f"Native ad added to response for user {user.id}")

                # Send completion event WITH chat_id (important for frontend state!)
                logger.info(
                    f"Chat stream completed for user {user.id}: ~{token_count} characters generated, chat_id={chat_id}"
                )
                yield f"data: {json.dumps({'type': 'done', 'chat_id': chat_id})}\n\n"

            except Exception as e:
                # Send error event
                logger.error(f"Error in chat stream for user {user.id}: {str(e)}")
                error_data = {
                    "type": "error",
                    "error": str(e)
                }
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat message: {str(e)}"
        )


@router.post("")
async def chat_message(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Send chat message and get full response (non-streaming)

    Args:
        request: Chat request with message and optional chat_id
        user: Authenticated user
        session: Database session

    Returns:
        {
            "response": "AI response text",
            "tokens_used": 150,
            "chat_id": 1
        }
    """
    try:
        # Get or create chat (if chat_id not provided, use default chat)
        if not request.chat_id:
            chat = await get_or_create_default_chat(session, user.id)
            chat_id = chat.id
            logger.debug(f"Using default chat {chat_id} for user {user.id}")
        else:
            chat_id = request.chat_id
            logger.debug(f"Using provided chat {chat_id} for user {user.id}")

        # Check rate limit
        can_send, current_count, limit = await check_request_limit(session, user)
        if not can_send:
            raise HTTPException(
                status_code=429,
                detail=create_rate_limit_response(user, current_count, limit),
            )

        # Get user's tier (with fallback to FREE)
        user_tier = "free"
        if hasattr(user, 'subscription') and user.subscription:
            user_tier = user.subscription.tier

        # Collect full response from stream
        full_response = ""
        async for chunk in openai_service.stream_completion(
            session=session,
            user_id=user.id,
            user_message=request.message,
            user_language=user.language or "ru",
            user_tier=user_tier,  # 🚨 Pass tier for context/memory
            use_tools=True,
            chat_id=chat_id,  # 🚨 Pass chat_id for multiple chats support
        ):
            full_response += chunk

        # Auto-generate chat title if this is the first message in a new chat
        try:
            chat_obj = await get_chat_by_id(session, chat_id, user.id)
            if chat_obj and chat_obj.title in ("New Chat", "Новый чат"):
                logger.info(f"Auto-generating title for chat {chat_id}")
                new_title = await openai_service.generate_chat_title(
                    user_message=request.message,
                    assistant_response=full_response,
                    user_language=user.language or "ru",
                )
                await update_chat_title(session, chat_id, user.id, new_title)
                logger.info(f"Chat {chat_id} renamed to: '{new_title}'")
        except Exception as e:
            logger.error(f"Failed to auto-generate chat title: {e}")
            # Don't fail the request if title generation fails

        # 💎 Award $SYNTRA points for AI request
        await PointsService.earn_points(
            session=session,
            user_id=user.id,
            transaction_type=PointsTransactionType.EARN_TEXT_REQUEST,
            description="Chat request (non-streaming)",
            metadata={
                "chat_id": chat_id,
                "message_length": len(request.message),
            },
            transaction_id=f"chat:{user.id}:{chat_id}:{datetime.now(timezone.utc).timestamp()}",
        )
        logger.info(f"💎 Awarded points for text request to user {user.id}")

        return {
            "response": full_response,
            "tokens_used": openai_service.count_tokens(full_response),
            "chat_id": chat_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat message: {str(e)}"
        )


@router.get("/history")
async def get_history(
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatHistoryResponse:
    """
    Get chat history for current user

    Args:
        limit: Maximum number of messages to return
        user: Authenticated user
        session: Database session

    Returns:
        {
            "messages": [
                {"role": "user", "content": "...", "timestamp": "..."},
                {"role": "assistant", "content": "...", "timestamp": "..."},
                ...
            ]
        }
    """
    try:
        messages = await get_chat_history(session, user.id, limit=limit)

        return ChatHistoryResponse(
            messages=[
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                }
                for msg in messages
            ]
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch chat history: {str(e)}"
        )


class RegenerateRequest(BaseModel):
    """Request model for regenerate endpoint"""
    message_id: int


@router.post("/regenerate")
async def regenerate_message(
    request: RegenerateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Regenerate AI response for a given message

    Flow:
    1. Verify message exists and belongs to user
    2. Find the previous user message
    3. Delete the old assistant response
    4. Generate new response with SSE streaming

    Args:
        request: Request with message_id to regenerate
        user: Authenticated user
        session: Database session

    Returns:
        StreamingResponse with SSE events

    Example Request:
        POST /api/chat/regenerate
        {
            "message_id": 123
        }

    Example Response (SSE format):
        data: {"type": "token", "content": "New"}
        data: {"type": "token", "content": " response"}
        data: {"type": "done"}

    Errors:
        404: Message not found or not owned by user
        400: Message is not an assistant message or no previous user message found
        429: Rate limit exceeded
    """
    # Log regenerate request
    logger.info(
        f"Regenerate request from user {user.id} (@{user.username}): message_id={request.message_id}"
    )

    try:
        # 1. Verify message exists and belongs to user
        message = await get_chat_message_by_id(session, request.message_id, user.id)
        if not message:
            raise HTTPException(
                status_code=404,
                detail="Message not found or you don't have permission to regenerate it"
            )

        # 2. Verify it's an assistant message
        if message.role != "assistant":
            raise HTTPException(
                status_code=400,
                detail="Can only regenerate assistant messages"
            )

        # 3. Find the previous user message
        user_message = await get_previous_user_message(session, request.message_id, user.id)
        if not user_message:
            raise HTTPException(
                status_code=400,
                detail="No previous user message found. Cannot regenerate."
            )

        # 4. Check rate limit
        can_send, current_count, limit = await check_request_limit(session, user)
        if not can_send:
            raise HTTPException(
                status_code=429,
                detail=create_rate_limit_response(user, current_count, limit),
            )

        # 5. Delete the old assistant response
        deleted = await delete_chat_message(session, request.message_id, user.id)
        if not deleted:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete old message"
            )

        # 6. Generate new response with SSE streaming
        async def event_generator() -> AsyncGenerator[str, None]:
            """
            Generator for SSE events

            Yields SSE-formatted messages:
            - data: {json}\n\n format
            """
            token_count = 0
            try:
                # Get or create default chat (for backward compatibility with old messages)
                chat = await get_or_create_default_chat(session, user.id)
                chat_id = chat.id

                # Get user's tier (with fallback to FREE)
                user_tier = "free"
                if hasattr(user, 'subscription') and user.subscription:
                    user_tier = user.subscription.tier

                # Stream new response from OpenAI
                logger.info(f"Starting regenerate stream for user {user.id}, original message: '{user_message.content[:100]}...', chat_id={chat_id}")
                async for chunk in openai_service.stream_completion(
                    session=session,
                    user_id=user.id,
                    user_message=user_message.content,
                    user_language=user.language or "ru",
                    user_tier=user_tier,  # 🚨 Pass tier for context/memory
                    use_tools=True,  # Enable crypto tools
                    chat_id=chat_id,  # 🚨 Pass chat_id for multiple chats support
                ):
                    # Format as SSE event
                    event_data = {
                        "type": "token",
                        "content": chunk
                    }
                    token_count += len(chunk)
                    yield f"data: {json.dumps(event_data)}\n\n"

                # Send completion event
                logger.info(
                    f"Regenerate stream completed for user {user.id}: ~{token_count} characters generated"
                )
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

            except Exception as e:
                # Send error event
                logger.error(f"Error in regenerate stream for user {user.id}: {str(e)}")
                error_data = {
                    "type": "error",
                    "error": str(e)
                }
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to regenerate message: {str(e)}"
        )
