# coding: utf-8
"""
Social Tasks Admin API Endpoints
Admin management for social tasks
"""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger

from src.database.engine import get_session
from src.database.models import User, TaskStatus, TaskType, VerificationType
from src.api.auth import get_current_user
from src.services.social_tasks_service import SocialTasksService


router = APIRouter(prefix="/admin/tasks", tags=["admin-tasks"])


# ===========================
# REQUEST/RESPONSE MODELS
# ===========================


class TaskResponse(BaseModel):
    """Task admin response"""

    id: int
    title_ru: str
    title_en: str
    description_ru: Optional[str]
    description_en: Optional[str]
    icon: str
    task_type: str
    telegram_channel_id: Optional[str]
    telegram_channel_url: Optional[str]
    twitter_target_username: Optional[str]
    verification_type: str
    reward_points: int
    unsubscribe_penalty: int
    max_completions: Optional[int]
    current_completions: int
    is_repeatable: bool
    requires_premium: bool
    min_level: int
    priority: int
    status: str
    starts_at: Optional[str]
    expires_at: Optional[str]
    created_by: Optional[int]
    created_at: str
    updated_at: str


class CreateTaskRequest(BaseModel):
    """Request to create task"""

    title_ru: str
    title_en: str
    description_ru: Optional[str] = None
    description_en: Optional[str] = None
    icon: str = "📢"
    task_type: str
    telegram_channel_id: Optional[str] = None
    telegram_channel_url: Optional[str] = None
    twitter_target_username: Optional[str] = None
    verification_type: str = VerificationType.AUTO_TELEGRAM.value
    reward_points: int = 100
    unsubscribe_penalty: int = 50
    max_completions: Optional[int] = None
    is_repeatable: bool = False
    repeat_interval_hours: Optional[int] = None
    requires_premium: bool = False
    min_level: int = 1
    priority: int = 0
    status: str = TaskStatus.DRAFT.value
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class UpdateTaskRequest(BaseModel):
    """Request to update task"""

    title_ru: Optional[str] = None
    title_en: Optional[str] = None
    description_ru: Optional[str] = None
    description_en: Optional[str] = None
    icon: Optional[str] = None
    telegram_channel_id: Optional[str] = None
    telegram_channel_url: Optional[str] = None
    twitter_target_username: Optional[str] = None
    reward_points: Optional[int] = None
    unsubscribe_penalty: Optional[int] = None
    max_completions: Optional[int] = None
    is_repeatable: Optional[bool] = None
    requires_premium: Optional[bool] = None
    min_level: Optional[int] = None
    priority: Optional[int] = None
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class PendingReviewResponse(BaseModel):
    """Pending review completion"""

    completion_id: int
    task_id: int
    task_title: str
    task_icon: str
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    screenshot_url: Optional[str]
    started_at: str


class ReviewRequest(BaseModel):
    """Request to review completion"""

    notes: Optional[str] = None


class RejectRequest(BaseModel):
    """Request to reject completion"""

    reason: str


class TaskAnalyticsResponse(BaseModel):
    """Task analytics"""

    task_id: int
    title: str
    status: str
    current_completions: int
    max_completions: Optional[int]
    reward_points: int
    completions_by_status: dict
    total_points_awarded: int


# ===========================
# HELPER FUNCTIONS
# ===========================


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency that requires admin privileges"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user


def task_to_response(task) -> TaskResponse:
    """Convert task model to response"""
    return TaskResponse(
        id=task.id,
        title_ru=task.title_ru,
        title_en=task.title_en,
        description_ru=task.description_ru,
        description_en=task.description_en,
        icon=task.icon,
        task_type=task.task_type,
        telegram_channel_id=task.telegram_channel_id,
        telegram_channel_url=task.telegram_channel_url,
        twitter_target_username=task.twitter_target_username,
        verification_type=task.verification_type,
        reward_points=task.reward_points,
        unsubscribe_penalty=task.unsubscribe_penalty,
        max_completions=task.max_completions,
        current_completions=task.current_completions,
        is_repeatable=task.is_repeatable,
        requires_premium=task.requires_premium,
        min_level=task.min_level,
        priority=task.priority,
        status=task.status,
        starts_at=task.starts_at.isoformat() if task.starts_at else None,
        expires_at=task.expires_at.isoformat() if task.expires_at else None,
        created_by=task.created_by,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
    )


# ===========================
# ENDPOINTS
# ===========================


@router.get("/", response_model=List[TaskResponse])
async def get_all_tasks(
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """
    Get all tasks (admin only)
    """
    try:
        tasks = await SocialTasksService.get_all_tasks(
            session=session,
            status_filter=status,
        )

        return [task_to_response(t) for t in tasks]

    except Exception as e:
        logger.exception(f"Error getting tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to get tasks")


@router.post("/", response_model=TaskResponse)
async def create_task(
    request: CreateTaskRequest,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Create new task (admin only)
    """
    try:
        # Validate task type
        valid_types = [t.value for t in TaskType]
        if request.task_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid task_type. Must be one of: {valid_types}",
            )

        # Validate verification type
        valid_verifications = [v.value for v in VerificationType]
        if request.verification_type not in valid_verifications:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid verification_type: {valid_verifications}",
            )

        task_data = request.model_dump(exclude_none=True)

        task = await SocialTasksService.create_task(
            session=session,
            admin_telegram_id=admin.telegram_id or 0,
            task_data=task_data,
        )

        return task_to_response(task)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail="Failed to create task")


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Get task by ID (admin only)
    """
    task = await SocialTasksService.get_task_by_id(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task_to_response(task)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    request: UpdateTaskRequest,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Update task (admin only)
    """
    try:
        updates = request.model_dump(exclude_none=True)

        task = await SocialTasksService.update_task(
            session=session,
            task_id=task_id,
            updates=updates,
        )

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        return task_to_response(task)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating task: {e}")
        raise HTTPException(status_code=500, detail="Failed to update task")


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Delete task (admin only)
    """
    try:
        success = await SocialTasksService.delete_task(session, task_id)

        if not success:
            raise HTTPException(status_code=404, detail="Task not found")

        return {"success": True, "message": "Task deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting task: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete task")


@router.post("/{task_id}/activate", response_model=TaskResponse)
async def activate_task(
    task_id: int,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Activate task (admin only)
    """
    task = await SocialTasksService.toggle_task_status(
        session, task_id, TaskStatus.ACTIVE.value
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task_to_response(task)


@router.post("/{task_id}/pause", response_model=TaskResponse)
async def pause_task(
    task_id: int,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Pause/hide task (admin only)
    """
    task = await SocialTasksService.toggle_task_status(
        session, task_id, TaskStatus.PAUSED.value
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task_to_response(task)


@router.get("/{task_id}/analytics", response_model=TaskAnalyticsResponse)
async def get_task_analytics(
    task_id: int,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Get task analytics (admin only)
    """
    analytics = await SocialTasksService.get_task_analytics(session, task_id)

    if not analytics:
        raise HTTPException(status_code=404, detail="Task not found")

    return analytics


# ===========================
# REVIEW ENDPOINTS
# ===========================


@router.get("/pending-reviews", response_model=List[PendingReviewResponse])
async def get_pending_reviews(
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Get completions pending manual review (admin only)
    """
    try:
        completions = await SocialTasksService.get_pending_reviews(session)

        return [
            PendingReviewResponse(
                completion_id=c.id,
                task_id=c.task_id,
                task_title=c.task.title_en if c.task else "Unknown",
                task_icon=c.task.icon if c.task else "📋",
                user_id=c.user_id,
                username=c.user.username if c.user else None,
                first_name=c.user.first_name if c.user else None,
                screenshot_url=c.screenshot_url,
                started_at=c.started_at.isoformat(),
            )
            for c in completions
        ]

    except Exception as e:
        logger.exception(f"Error getting pending reviews: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pending reviews")


@router.post("/completions/{completion_id}/approve")
async def approve_completion(
    completion_id: int,
    request: ReviewRequest,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Approve screenshot completion (admin only)
    """
    try:
        success, message, completion = await SocialTasksService.approve_screenshot(
            session=session,
            completion_id=completion_id,
            admin_telegram_id=admin.telegram_id or 0,
            notes=request.notes,
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {
            "success": True,
            "message": message,
            "points_awarded": completion.points_awarded if completion else 0,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error approving completion: {e}")
        raise HTTPException(status_code=500, detail="Failed to approve")


@router.post("/completions/{completion_id}/reject")
async def reject_completion(
    completion_id: int,
    request: RejectRequest,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Reject screenshot completion (admin only)
    """
    try:
        success, message, completion = await SocialTasksService.reject_screenshot(
            session=session,
            completion_id=completion_id,
            admin_telegram_id=admin.telegram_id or 0,
            reason=request.reason,
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {"success": True, "message": message}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error rejecting completion: {e}")
        raise HTTPException(status_code=500, detail="Failed to reject")
