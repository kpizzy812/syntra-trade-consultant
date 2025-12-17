"""
Chat Management API Endpoints
Provides CRUD operations for multiple chat sessions (like ChatGPT)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from pydantic import BaseModel
from loguru import logger

from src.database.models import User
from src.database.engine import get_session
from src.api.auth import get_current_user
from src.database.crud import (
    create_chat,
    get_user_chats,
    get_chat_by_id,
    update_chat_title,
    delete_chat,
    get_chat_messages,
    get_or_create_default_chat,
)

# Create router
router = APIRouter(prefix="/chats", tags=["chats"])


# ==================== Request/Response Models ====================

class CreateChatRequest(BaseModel):
    """Request model for creating a new chat"""
    title: str = "New Chat"


class UpdateChatTitleRequest(BaseModel):
    """Request model for updating chat title"""
    title: str


class ChatResponse(BaseModel):
    """Response model for a single chat"""
    id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0

    class Config:
        from_attributes = True


class ChatMessageResponse(BaseModel):
    """Response model for a chat message"""
    id: int
    role: str
    content: str
    timestamp: str
    tokens_used: int | None = None
    model: str | None = None

    class Config:
        from_attributes = True


class ChatListResponse(BaseModel):
    """Response model for list of chats"""
    chats: List[ChatResponse]
    total: int


class ChatMessagesResponse(BaseModel):
    """Response model for chat messages"""
    chat_id: int
    chat_title: str
    messages: List[ChatMessageResponse]
    total: int


# ==================== Endpoints ====================

@router.get("", response_model=ChatListResponse)
async def list_user_chats(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get list of user's chats (sorted by last update, newest first)

    Args:
        limit: Maximum number of chats to return (default: 50, max: 100)
        offset: Number of chats to skip for pagination (default: 0)
        user: Authenticated user
        session: Database session

    Returns:
        {
            "chats": [
                {
                    "id": 1,
                    "title": "Bitcoin Analysis",
                    "created_at": "2025-01-25T10:00:00Z",
                    "updated_at": "2025-01-25T12:30:00Z",
                    "message_count": 10
                }
            ],
            "total": 15
        }
    """
    # Validate limit
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1

    logger.info(f"Fetching chats for user {user.id} (limit={limit}, offset={offset})")

    # Get user's chats
    chats = await get_user_chats(session, user.id, limit=limit, offset=offset)

    # Convert to response format
    chat_responses = []
    for chat in chats:
        # Count messages in chat
        message_count = len(chat.messages) if hasattr(chat, 'messages') else 0

        chat_responses.append(ChatResponse(
            id=chat.id,
            title=chat.title,
            created_at=chat.created_at.isoformat(),
            updated_at=chat.updated_at.isoformat(),
            message_count=message_count,
        ))

    return ChatListResponse(
        chats=chat_responses,
        total=len(chats),
    )


@router.post("", response_model=ChatResponse)
async def create_new_chat(
    request: CreateChatRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new chat session

    Args:
        request: Chat creation request with optional title
        user: Authenticated user
        session: Database session

    Returns:
        {
            "id": 1,
            "title": "New Chat",
            "created_at": "2025-01-25T10:00:00Z",
            "updated_at": "2025-01-25T10:00:00Z",
            "message_count": 0
        }
    """
    logger.info(f"Creating new chat for user {user.id} with title '{request.title}'")

    # Create chat
    chat = await create_chat(session, user.id, title=request.title)

    return ChatResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at.isoformat(),
        updated_at=chat.updated_at.isoformat(),
        message_count=0,
    )


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    chat_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get specific chat by ID

    Args:
        chat_id: Chat ID
        user: Authenticated user
        session: Database session

    Returns:
        {
            "id": 1,
            "title": "Bitcoin Analysis",
            "created_at": "2025-01-25T10:00:00Z",
            "updated_at": "2025-01-25T12:30:00Z",
            "message_count": 10
        }

    Raises:
        404: Chat not found or user doesn't have access
    """
    logger.info(f"Fetching chat {chat_id} for user {user.id}")

    # Get chat (with ownership check)
    chat = await get_chat_by_id(session, chat_id, user.id)

    if not chat:
        raise HTTPException(
            status_code=404,
            detail=f"Chat not found or access denied (chat_id: {chat_id})"
        )

    # Count messages
    message_count = len(chat.messages) if hasattr(chat, 'messages') else 0

    return ChatResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at.isoformat(),
        updated_at=chat.updated_at.isoformat(),
        message_count=message_count,
    )


@router.get("/{chat_id}/messages", response_model=ChatMessagesResponse)
async def get_chat_messages_endpoint(
    chat_id: int,
    limit: int | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get messages from specific chat

    Args:
        chat_id: Chat ID
        limit: Optional limit for number of messages (default: all messages)
        user: Authenticated user
        session: Database session

    Returns:
        {
            "chat_id": 1,
            "chat_title": "Bitcoin Analysis",
            "messages": [
                {
                    "id": 1,
                    "role": "user",
                    "content": "What's the price of Bitcoin?",
                    "timestamp": "2025-01-25T10:00:00Z",
                    "tokens_used": null,
                    "model": null
                },
                {
                    "id": 2,
                    "role": "assistant",
                    "content": "Bitcoin is currently trading at $50,000...",
                    "timestamp": "2025-01-25T10:00:05Z",
                    "tokens_used": 150,
                    "model": "gpt-4o"
                }
            ],
            "total": 2
        }

    Raises:
        404: Chat not found or user doesn't have access
    """
    logger.info(f"Fetching messages for chat {chat_id}, user {user.id} (limit={limit})")

    # Verify chat exists and user has access
    chat = await get_chat_by_id(session, chat_id, user.id)
    if not chat:
        raise HTTPException(
            status_code=404,
            detail=f"Chat not found or access denied (chat_id: {chat_id})"
        )

    # Get messages
    messages = await get_chat_messages(session, chat_id, limit=limit)

    # Convert to response format
    message_responses = [
        ChatMessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            timestamp=msg.timestamp.isoformat(),
            tokens_used=msg.tokens_used,
            model=msg.model,
        )
        for msg in messages
    ]

    return ChatMessagesResponse(
        chat_id=chat.id,
        chat_title=chat.title,
        messages=message_responses,
        total=len(message_responses),
    )


@router.put("/{chat_id}/title", response_model=ChatResponse)
async def update_chat_title_endpoint(
    chat_id: int,
    request: UpdateChatTitleRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Update chat title (rename chat)

    Args:
        chat_id: Chat ID
        request: Update request with new title
        user: Authenticated user
        session: Database session

    Returns:
        {
            "id": 1,
            "title": "Updated Title",
            "created_at": "2025-01-25T10:00:00Z",
            "updated_at": "2025-01-25T12:30:00Z",
            "message_count": 10
        }

    Raises:
        404: Chat not found or user doesn't have access
    """
    logger.info(f"Updating title for chat {chat_id}, user {user.id}: '{request.title}'")

    # Update title
    chat = await update_chat_title(session, chat_id, user.id, request.title)

    if not chat:
        raise HTTPException(
            status_code=404,
            detail=f"Chat not found or access denied (chat_id: {chat_id})"
        )

    # Count messages
    message_count = len(chat.messages) if hasattr(chat, 'messages') else 0

    return ChatResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at.isoformat(),
        updated_at=chat.updated_at.isoformat(),
        message_count=message_count,
    )


@router.delete("/{chat_id}")
async def delete_chat_endpoint(
    chat_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Delete chat and all its messages (cascade delete)

    Args:
        chat_id: Chat ID
        user: Authenticated user
        session: Database session

    Returns:
        {
            "success": true,
            "message": "Chat deleted successfully",
            "chat_id": 1
        }

    Raises:
        404: Chat not found or user doesn't have access
    """
    logger.info(f"Deleting chat {chat_id} for user {user.id}")

    # Delete chat
    success = await delete_chat(session, chat_id, user.id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Chat not found or access denied (chat_id: {chat_id})"
        )

    return {
        "success": True,
        "message": "Chat deleted successfully",
        "chat_id": chat_id,
    }


@router.get("/default/active", response_model=ChatResponse)
async def get_or_create_default_chat_endpoint(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get user's most recent chat or create new one if none exists

    This is useful for the initial chat view - always returns a chat to work with.

    Args:
        user: Authenticated user
        session: Database session

    Returns:
        {
            "id": 1,
            "title": "New Chat",
            "created_at": "2025-01-25T10:00:00Z",
            "updated_at": "2025-01-25T10:00:00Z",
            "message_count": 0
        }
    """
    logger.info(f"Getting or creating default chat for user {user.id}")

    # Get or create default chat
    chat = await get_or_create_default_chat(session, user.id)

    # Count messages
    message_count = len(chat.messages) if hasattr(chat, 'messages') else 0

    return ChatResponse(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at.isoformat(),
        updated_at=chat.updated_at.isoformat(),
        message_count=message_count,
    )
