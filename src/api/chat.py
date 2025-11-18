"""
Chat API Endpoints with SSE Streaming
Provides AI chat functionality for Mini App
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, AsyncGenerator
from pydantic import BaseModel
import json

from src.database.models import User
from src.database.engine import get_session
from src.api.auth import get_current_user
from src.services.openai_service import OpenAIService
from src.database.crud import (
    get_chat_history,
    check_request_limit,
    get_chat_message_by_id,
    delete_chat_message,
    get_previous_user_message,
)

# Create router
router = APIRouter(prefix="/chat", tags=["chat"])

# Initialize OpenAI service
openai_service = OpenAIService()


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str
    context: str | None = None


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
    try:
        # Check rate limit
        can_send, limit_info = await check_request_limit(session, user.id)
        if not can_send:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "requests_used": limit_info.get("requests_used", 0),
                    "requests_limit": limit_info.get("requests_limit", 0),
                    "reset_at": limit_info.get("reset_at"),
                }
            )

        async def event_generator() -> AsyncGenerator[str, None]:
            """
            Generator for SSE events

            Yields SSE-formatted messages:
            - data: {json}\n\n format
            """
            try:
                # Stream response from OpenAI
                async for chunk in openai_service.stream_completion(
                    session=session,
                    user_id=user.id,
                    user_message=request.message,
                    user_language=user.language or "ru",
                    use_tools=True,  # Enable crypto tools (price, analysis, etc.)
                ):
                    # Format as SSE event
                    event_data = {
                        "type": "token",
                        "content": chunk
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"

                # Send completion event
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

            except Exception as e:
                # Send error event
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
        request: Chat request with message
        user: Authenticated user
        session: Database session

    Returns:
        {
            "response": "AI response text",
            "tokens_used": 150
        }
    """
    try:
        # Check rate limit
        can_send, limit_info = await check_request_limit(session, user.id)
        if not can_send:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "requests_used": limit_info.get("requests_used", 0),
                    "requests_limit": limit_info.get("requests_limit", 0),
                }
            )

        # Collect full response from stream
        full_response = ""
        async for chunk in openai_service.stream_completion(
            session=session,
            user_id=user.id,
            user_message=request.message,
            user_language=user.language or "ru",
            use_tools=True,
        ):
            full_response += chunk

        return {
            "response": full_response,
            "tokens_used": openai_service.count_tokens(full_response),
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
        can_send, limit_info = await check_request_limit(session, user.id)
        if not can_send:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "requests_used": limit_info.get("requests_used", 0),
                    "requests_limit": limit_info.get("requests_limit", 0),
                    "reset_at": limit_info.get("reset_at"),
                }
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
            try:
                # Stream new response from OpenAI
                async for chunk in openai_service.stream_completion(
                    session=session,
                    user_id=user.id,
                    user_message=user_message.content,
                    user_language=user.language or "ru",
                    use_tools=True,  # Enable crypto tools
                ):
                    # Format as SSE event
                    event_data = {
                        "type": "token",
                        "content": chunk
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"

                # Send completion event
                yield f"data: {json.dumps({'type': 'done'})}\n\n"

            except Exception as e:
                # Send error event
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
