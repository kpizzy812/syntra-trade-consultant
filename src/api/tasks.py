# coding: utf-8
"""
Social Tasks API Endpoints
Provides task management for Mini App
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Header, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel
import base64
import uuid
import os
from pathlib import Path

from loguru import logger

from config.config import API_BASE_URL
from src.database.models import User
from src.database.engine import get_session
from src.api.auth import get_current_user
from src.services.social_tasks_service import SocialTasksService

# Create router
router = APIRouter(prefix="/tasks", tags=["tasks"])


# ===========================
# RESPONSE MODELS
# ===========================


class TaskResponse(BaseModel):
    """Task info for user"""

    id: int
    title: str
    description: Optional[str]
    icon: str
    task_type: str
    reward_points: int
    unsubscribe_penalty: int
    verification_type: str
    is_repeatable: bool
    requires_premium: bool
    # Target info
    telegram_channel_id: Optional[str]
    telegram_channel_url: Optional[str]
    twitter_target_username: Optional[str]
    # User completion status
    completion_status: Optional[str]
    points_awarded: int
    completed_at: Optional[str]


class TaskHistoryResponse(BaseModel):
    """Task completion history entry"""

    completion_id: int
    task_id: int
    task_title: str
    task_icon: str
    status: str
    points_awarded: int
    penalty_applied: int
    started_at: Optional[str]
    completed_at: Optional[str]
    revoked_at: Optional[str]


class VerifyTaskResponse(BaseModel):
    """Response for task verification"""

    success: bool
    message: str
    status: Optional[str]
    points_awarded: int


class ScreenshotSubmitResponse(BaseModel):
    """Response for screenshot submission"""

    success: bool
    message: str
    status: str


# ===========================
# ENDPOINTS
# ===========================


@router.get("/available", response_model=List[TaskResponse])
async def get_available_tasks(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    include_completed: bool = Query(False, description="Include completed tasks"),
    accept_language: str = Header("en", alias="Accept-Language"),
):
    """
    Get available tasks for user

    Returns list of tasks with their completion status
    """
    try:
        # Extract language code
        language = "ru" if accept_language.startswith("ru") else "en"

        tasks = await SocialTasksService.get_available_tasks(
            session=session,
            user_id=user.id,
            language=language,
            include_completed=include_completed,
        )

        return tasks

    except Exception as e:
        logger.exception(f"Error getting available tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to get tasks")


@router.post("/{task_id}/start")
async def start_task(
    task_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Start a task

    Creates a pending completion record
    """
    try:
        completion, message = await SocialTasksService.start_task(
            session=session,
            user_id=user.id,
            task_id=task_id,
        )

        if not completion:
            raise HTTPException(status_code=400, detail=message)

        return {
            "success": True,
            "message": message,
            "completion_id": completion.id,
            "status": completion.status,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error starting task: {e}")
        raise HTTPException(status_code=500, detail="Failed to start task")


@router.post("/{task_id}/verify", response_model=VerifyTaskResponse)
async def verify_task(
    task_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Verify task completion

    For Telegram tasks - checks subscription via API
    For Twitter tasks - requires screenshot submission first
    """
    # Create bot instance for Telegram verification
    from aiogram import Bot
    from config.config import BOT_TOKEN

    bot = Bot(token=BOT_TOKEN)
    try:
        success, message, completion = await SocialTasksService.verify_task(
            session=session,
            user_id=user.id,
            task_id=task_id,
            bot=bot,
            telegram_user_id=user.telegram_id,
        )

        return VerifyTaskResponse(
            success=success,
            message=message,
            status=completion.status if completion else None,
            points_awarded=completion.points_awarded if completion else 0,
        )

    except Exception as e:
        logger.exception(f"Error verifying task: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify task")
    finally:
        await bot.session.close()


class ScreenshotUploadRequest(BaseModel):
    """Request body for screenshot upload"""
    image_base64: str


@router.post("/{task_id}/screenshot", response_model=ScreenshotSubmitResponse)
async def submit_screenshot(
    task_id: int,
    request: ScreenshotUploadRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Submit screenshot for manual verification (Twitter tasks)

    Accepts base64 encoded image, saves to disk, and notifies admins

    🔒 SECURITY: Validates MIME type, magic bytes, file size
    """
    try:
        # Parse base64 image
        image_data = request.image_base64
        if "," in image_data:
            # Remove data URL prefix (data:image/png;base64,...)
            image_data = image_data.split(",", 1)[1]

        # Decode base64
        try:
            image_bytes = base64.b64decode(image_data)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 image")

        # 🔒 SECURITY: Validate image size (max 5MB)
        if len(image_bytes) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large (max 5MB)")

        # 🔒 SECURITY: Validate magic bytes (file signature)
        # PNG: 89 50 4E 47 0D 0A 1A 0A
        # JPEG: FF D8 FF
        # WebP: 52 49 46 46 ... 57 45 42 50
        is_png = image_bytes[:8] == b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a'
        is_jpeg = image_bytes[:3] == b'\xff\xd8\xff'
        is_webp = image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP'

        if not (is_png or is_jpeg or is_webp):
            logger.warning(f"🔒 SECURITY: Invalid file type from user {user.id}. Magic bytes: {image_bytes[:16].hex()}")
            raise HTTPException(status_code=400, detail="Only PNG, JPEG and WebP images are allowed")

        # Determine extension
        if is_png:
            ext = "png"
        elif is_jpeg:
            ext = "jpg"
        else:
            ext = "webp"

        # 🔒 SECURITY: Create screenshots directory with safe permissions
        screenshots_dir = Path("static/screenshots")
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        # Set secure permissions (owner only)
        os.chmod(screenshots_dir, 0o700)

        # 🔒 SECURITY: Generate cryptographically secure filename
        # Prevents path traversal and file overwrites
        secure_filename = f"{user.id}_{task_id}_{uuid.uuid4().hex}.{ext}"
        filepath = screenshots_dir / secure_filename

        # 🔒 SECURITY: Verify filepath is inside screenshots_dir (prevent path traversal)
        if not filepath.resolve().is_relative_to(screenshots_dir.resolve()):
            logger.error(f"🔒 SECURITY: Path traversal attempt from user {user.id}")
            raise HTTPException(status_code=400, detail="Invalid filename")

        # 🔒 SECURITY: Save with secure permissions (owner read-write only)
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        os.chmod(filepath, 0o600)

        # Generate full URL for the screenshot (Telegram requires absolute URLs)
        screenshot_url = f"{API_BASE_URL}/static/screenshots/{secure_filename}"

        success, message, completion = await SocialTasksService.submit_screenshot(
            session=session,
            user_id=user.id,
            task_id=task_id,
            screenshot_url=screenshot_url,
        )

        if not success:
            # Clean up saved file on failure
            if filepath.exists():
                filepath.unlink()
            raise HTTPException(status_code=400, detail=message)

        # Notify admins about new screenshot
        try:
            from aiogram import Bot
            from config.config import BOT_TOKEN

            bot = Bot(token=BOT_TOKEN)
            try:
                task = await SocialTasksService.get_task_by_id(session, task_id)
                if task and completion:
                    await SocialTasksService.notify_admins_new_screenshot(
                        bot=bot,
                        user=user,
                        task=task,
                        screenshot_url=screenshot_url,
                        completion_id=completion.id,
                    )
            finally:
                await bot.session.close()
        except Exception as notify_error:
            logger.warning(f"Failed to notify admins: {notify_error}")

        return ScreenshotSubmitResponse(
            success=True,
            message=message,
            status=completion.status,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error submitting screenshot: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit screenshot")


@router.get("/history", response_model=List[TaskHistoryResponse])
async def get_task_history(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(50, ge=1, le=100),
):
    """
    Get user's task completion history
    """
    try:
        history = await SocialTasksService.get_user_task_history(
            session=session,
            user_id=user.id,
            limit=limit,
        )

        return history

    except Exception as e:
        logger.exception(f"Error getting task history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get history")
