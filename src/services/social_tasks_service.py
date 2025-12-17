# coding: utf-8
"""
Social Tasks Service

Manages social tasks (Telegram subscriptions, Twitter follows) for earning points.

Features:
- Telegram subscription verification via Telegram API
- Twitter follow verification via screenshot (manual)
- Points reward on completion
- Penalty on unsubscription
- Periodic subscription rechecking
"""

import json
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, List, Tuple, Any

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from loguru import logger

from config.config import ADMIN_IDS
from src.database.models import (
    User,
    SocialTask,
    TaskCompletion,
    TaskType,
    TaskStatus,
    TaskCompletionStatus,
    VerificationType,
    PointsTransactionType,
    SubscriptionTier,
)
from src.services.points_service import PointsService


class SocialTasksService:
    """Service for managing social tasks"""

    # =====================
    # ADMIN NOTIFICATIONS
    # =====================

    @staticmethod
    async def notify_admins_new_screenshot(
        bot: Bot,
        user: User,
        task: SocialTask,
        screenshot_url: str,
        completion_id: int,
    ) -> None:
        """
        Notify admins about new screenshot pending review

        Args:
            bot: Telegram bot instance
            user: User who submitted screenshot
            task: Task being completed
            screenshot_url: URL of the screenshot
            completion_id: Task completion ID for inline buttons
        """
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        if not ADMIN_IDS:
            logger.warning("No ADMIN_IDS configured for notifications")
            return

        message = (
            "📸 <b>Новый скриншот на проверку</b>\n\n"
            f"👤 Пользователь: {user.first_name or 'Unknown'}"
            f"{f' (@{user.username})' if user.username else ''}\n"
            f"📋 Задание: {task.title_ru}\n"
            f"💰 Награда: +{task.reward_points} $SYNTRA\n\n"
            f"🔗 <a href='{screenshot_url}'>Открыть скриншот</a>"
        )

        # Inline keyboard for quick approve/reject
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Одобрить",
                    callback_data=f"task_approve:{completion_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"task_reject:{completion_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔗 Скриншот",
                    url=screenshot_url
                ),
            ],
        ])

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    message,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                    disable_web_page_preview=False,
                )
                logger.info(f"Notified admin {admin_id} about new screenshot")
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

    # =====================
    # TASK RETRIEVAL
    # =====================

    @staticmethod
    async def get_available_tasks(
        session: AsyncSession,
        user_id: int,
        language: str = "en",
        include_completed: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get available tasks for user with their completion status

        Args:
            session: Database session
            user_id: User ID
            language: Language code (ru/en)
            include_completed: Include already completed tasks

        Returns:
            List of task dicts with status
        """
        # Get user for level/premium checks
        user_stmt = select(User).where(User.id == user_id)
        user_result = await session.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if not user:
            return []

        # Get user's points balance for level
        from src.services.points_service import PointsService
        balance = await PointsService.get_or_create_balance(session, user_id)
        user_level = balance.level

        # Check if user is premium
        is_premium = False
        if user.subscription:
            is_premium = user.subscription.tier != SubscriptionTier.FREE.value

        now = datetime.now(UTC)

        # Build query for active tasks
        stmt = (
            select(SocialTask)
            .where(
                and_(
                    SocialTask.status == TaskStatus.ACTIVE.value,
                    SocialTask.min_level <= user_level,
                    or_(
                        SocialTask.starts_at.is_(None),
                        SocialTask.starts_at <= now,
                    ),
                    or_(
                        SocialTask.expires_at.is_(None),
                        SocialTask.expires_at > now,
                    ),
                    or_(
                        SocialTask.max_completions.is_(None),
                        SocialTask.current_completions < SocialTask.max_completions,
                    ),
                )
            )
            .order_by(SocialTask.priority.desc(), SocialTask.created_at.desc())
        )

        result = await session.execute(stmt)
        tasks = result.scalars().all()

        # Get user's completions for these tasks
        task_ids = [t.id for t in tasks]
        completions_stmt = (
            select(TaskCompletion)
            .where(
                and_(
                    TaskCompletion.user_id == user_id,
                    TaskCompletion.task_id.in_(task_ids),
                )
            )
        )
        completions_result = await session.execute(completions_stmt)
        completions = {c.task_id: c for c in completions_result.scalars().all()}

        result_list = []
        for task in tasks:
            # Skip premium-only tasks for free users
            if task.requires_premium and not is_premium:
                continue

            completion = completions.get(task.id)

            # Skip completed tasks if not requested
            if completion and completion.status == TaskCompletionStatus.COMPLETED.value:
                if not include_completed and not task.is_repeatable:
                    continue

            task_dict = {
                "id": task.id,
                "title": task.get_title(language),
                "description": task.get_description(language),
                "icon": task.icon,
                "task_type": task.task_type,
                "reward_points": task.reward_points,
                "unsubscribe_penalty": task.unsubscribe_penalty,
                "verification_type": task.verification_type,
                "is_repeatable": task.is_repeatable,
                "requires_premium": task.requires_premium,
                # Target info
                "telegram_channel_id": task.telegram_channel_id,
                "telegram_channel_url": task.telegram_channel_url,
                "twitter_target_username": task.twitter_target_username,
                # User completion status
                "completion_status": completion.status if completion else None,
                "points_awarded": completion.points_awarded if completion else 0,
                "completed_at": (
                    completion.completed_at.isoformat()
                    if completion and completion.completed_at else None
                ),
            }
            result_list.append(task_dict)

        return result_list

    @staticmethod
    async def get_task_by_id(
        session: AsyncSession,
        task_id: int,
    ) -> Optional[SocialTask]:
        """Get task by ID"""
        stmt = select(SocialTask).where(SocialTask.id == task_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    # =====================
    # TASK EXECUTION
    # =====================

    @staticmethod
    async def start_task(
        session: AsyncSession,
        user_id: int,
        task_id: int,
    ) -> Tuple[Optional[TaskCompletion], str]:
        """
        Start a task for user (create pending completion)

        Args:
            session: Database session
            user_id: User ID
            task_id: Task ID

        Returns:
            Tuple of (TaskCompletion or None, error message)
        """
        # Get task
        task = await SocialTasksService.get_task_by_id(session, task_id)
        if not task:
            return None, "task_not_found"

        if task.status != TaskStatus.ACTIVE.value:
            return None, "task_not_active"

        # Check if already started/completed
        existing_stmt = select(TaskCompletion).where(
            and_(
                TaskCompletion.user_id == user_id,
                TaskCompletion.task_id == task_id,
            )
        )
        result = await session.execute(existing_stmt)
        existing = result.scalar_one_or_none()

        if existing:
            if existing.status == TaskCompletionStatus.COMPLETED.value:
                if not task.is_repeatable:
                    return None, "already_completed"
                # For repeatable tasks, create new completion
                existing.completion_count += 1
                existing.status = TaskCompletionStatus.PENDING.value
                existing.started_at = datetime.now(UTC)
                existing.completed_at = None
                existing.verified_at = None
                existing.points_awarded = 0
                await session.commit()
                await session.refresh(existing)
                return existing, "ok"
            else:
                # Already in progress
                return existing, "already_started"

        # Create new completion
        completion = TaskCompletion(
            task_id=task_id,
            user_id=user_id,
            status=TaskCompletionStatus.PENDING.value,
            completion_count=1,
        )
        session.add(completion)
        await session.commit()
        await session.refresh(completion)

        logger.info(f"User {user_id} started task {task_id}")
        return completion, "ok"

    @staticmethod
    async def verify_task(
        session: AsyncSession,
        user_id: int,
        task_id: int,
        bot: Optional[Bot] = None,
        telegram_user_id: Optional[int] = None,
    ) -> Tuple[bool, str, Optional[TaskCompletion]]:
        """
        Verify task completion

        Args:
            session: Database session
            user_id: User ID
            task_id: Task ID
            bot: Bot instance (for Telegram verification)
            telegram_user_id: User's Telegram ID (for verification)

        Returns:
            Tuple of (success, message, completion)
        """
        # Get task
        task = await SocialTasksService.get_task_by_id(session, task_id)
        if not task:
            return False, "task_not_found", None

        # Get or create completion
        completion_stmt = select(TaskCompletion).where(
            and_(
                TaskCompletion.user_id == user_id,
                TaskCompletion.task_id == task_id,
            )
        )
        result = await session.execute(completion_stmt)
        completion = result.scalar_one_or_none()

        if not completion:
            # Auto-start task
            completion, msg = await SocialTasksService.start_task(
                session, user_id, task_id
            )
            if not completion:
                return False, msg, None

        if completion.status == TaskCompletionStatus.COMPLETED.value:
            return True, "already_completed", completion

        # Verify based on task type
        if task.verification_type == VerificationType.AUTO_TELEGRAM.value:
            if not bot or not telegram_user_id:
                return False, "bot_required", completion

            result = await SocialTasksService.verify_telegram_subscription(
                bot=bot,
                telegram_user_id=telegram_user_id,
                channel_id=task.telegram_channel_id,
            )
            is_verified, verification_data = result

            if is_verified:
                completion.status = TaskCompletionStatus.VERIFIED.value
                completion.verified_at = datetime.now(UTC)
                completion.verification_data = json.dumps(verification_data)
                await session.commit()

                # Complete task and award points
                return await SocialTasksService.complete_task(session, completion)
            else:
                return False, "not_subscribed", completion

        elif task.verification_type == VerificationType.MANUAL_SCREENSHOT.value:
            # Manual verification - just mark as pending review
            if completion.status == TaskCompletionStatus.PENDING.value:
                return False, "screenshot_required", completion
            elif completion.status == TaskCompletionStatus.PENDING_REVIEW.value:
                return False, "awaiting_review", completion

        return False, "unknown_verification_type", completion

    @staticmethod
    async def verify_telegram_subscription(
        bot: Bot,
        telegram_user_id: int,
        channel_id: str,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify Telegram channel/chat subscription

        Args:
            bot: Bot instance
            telegram_user_id: User's Telegram ID
            channel_id: Channel/chat ID (@username or -100xxx)

        Returns:
            Tuple of (is_subscribed, verification_data)
        """
        try:
            # Normalize channel_id: add @ for usernames, keep numeric IDs as-is
            is_username = channel_id and not channel_id.startswith(("-", "@"))
            if is_username:
                channel_id = f"@{channel_id}"

            member = await bot.get_chat_member(
                chat_id=channel_id,
                user_id=telegram_user_id,
            )

            is_member = member.status in {
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.CREATOR,
            }

            status_val = (
                member.status.value
                if hasattr(member.status, 'value')
                else str(member.status)
            )
            return is_member, {
                "status": status_val,
                "channel_id": channel_id,
                "checked_at": datetime.now(UTC).isoformat(),
            }

        except TelegramBadRequest as e:
            logger.warning(f"Telegram error checking subscription: {e}")
            return False, {"error": str(e)}
        except Exception as e:
            logger.exception(f"Error verifying Telegram subscription: {e}")
            return False, {"error": str(e)}

    @staticmethod
    async def complete_task(
        session: AsyncSession,
        completion: TaskCompletion,
    ) -> Tuple[bool, str, TaskCompletion]:
        """
        Complete task and award points

        Args:
            session: Database session
            completion: TaskCompletion to complete

        Returns:
            Tuple of (success, message, completion)
        """
        if completion.status == TaskCompletionStatus.COMPLETED.value:
            return True, "already_completed", completion

        # Get task for reward amount
        task = await SocialTasksService.get_task_by_id(session, completion.task_id)
        if not task:
            return False, "task_not_found", completion

        # Award points
        transaction = await PointsService.earn_points(
            session=session,
            user_id=completion.user_id,
            transaction_type=PointsTransactionType.EARN_SOCIAL_TASK.value,
            amount=task.reward_points,
            description=f"Task completed: {task.title_en}",
            metadata={
                "task_id": task.id,
                "task_type": task.task_type,
                "completion_id": completion.id,
            },
            transaction_id=f"task_{task.id}_user_{completion.user_id}_count_{completion.completion_count}",
        )

        if transaction:
            completion.status = TaskCompletionStatus.COMPLETED.value
            completion.completed_at = datetime.now(UTC)
            completion.points_awarded = task.reward_points
            completion.points_transaction_id = transaction.id

            # Increment task completion counter
            task.current_completions += 1

            # Check if task is fully completed
            max_reached = (
                task.max_completions
                and task.current_completions >= task.max_completions
            )
            if max_reached:
                task.status = TaskStatus.COMPLETED.value

            await session.commit()
            await session.refresh(completion)

            logger.info(
                f"User {completion.user_id} completed task {task.id}, "
                f"awarded {task.reward_points} points"
            )
            return True, "completed", completion
        else:
            return False, "points_award_failed", completion

    # =====================
    # SCREENSHOT VERIFICATION (Twitter)
    # =====================

    @staticmethod
    async def submit_screenshot(
        session: AsyncSession,
        user_id: int,
        task_id: int,
        screenshot_url: str,
    ) -> Tuple[bool, str, Optional[TaskCompletion]]:
        """
        Submit screenshot for manual verification

        Args:
            session: Database session
            user_id: User ID
            task_id: Task ID
            screenshot_url: URL of uploaded screenshot

        Returns:
            Tuple of (success, message, completion)
        """
        # Get or create completion
        completion_stmt = select(TaskCompletion).where(
            and_(
                TaskCompletion.user_id == user_id,
                TaskCompletion.task_id == task_id,
            )
        )
        result = await session.execute(completion_stmt)
        completion = result.scalar_one_or_none()

        if not completion:
            completion, msg = await SocialTasksService.start_task(
                session, user_id, task_id
            )
            if not completion:
                return False, msg, None

        if completion.status == TaskCompletionStatus.COMPLETED.value:
            return False, "already_completed", completion

        # Update with screenshot
        completion.screenshot_url = screenshot_url
        completion.status = TaskCompletionStatus.PENDING_REVIEW.value
        await session.commit()
        await session.refresh(completion)

        logger.info(f"User {user_id} submitted screenshot for task {task_id}")
        return True, "submitted_for_review", completion

    @staticmethod
    async def approve_screenshot(
        session: AsyncSession,
        completion_id: int,
        admin_telegram_id: int,
        notes: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[TaskCompletion]]:
        """
        Approve screenshot verification (admin)

        Args:
            session: Database session
            completion_id: TaskCompletion ID
            admin_telegram_id: Admin's Telegram ID
            notes: Admin notes

        Returns:
            Tuple of (success, message, completion)
        """
        stmt = select(TaskCompletion).where(TaskCompletion.id == completion_id)
        result = await session.execute(stmt)
        completion = result.scalar_one_or_none()

        if not completion:
            return False, "completion_not_found", None

        if completion.status != TaskCompletionStatus.PENDING_REVIEW.value:
            return False, "not_pending_review", completion

        # Mark as verified
        completion.status = TaskCompletionStatus.VERIFIED.value
        completion.verified_at = datetime.now(UTC)
        completion.reviewed_by = admin_telegram_id
        completion.reviewed_at = datetime.now(UTC)
        completion.review_notes = notes
        await session.commit()

        # Complete task
        return await SocialTasksService.complete_task(session, completion)

    @staticmethod
    async def reject_screenshot(
        session: AsyncSession,
        completion_id: int,
        admin_telegram_id: int,
        reason: str,
    ) -> Tuple[bool, str, Optional[TaskCompletion]]:
        """
        Reject screenshot verification (admin)

        Args:
            session: Database session
            completion_id: TaskCompletion ID
            admin_telegram_id: Admin's Telegram ID
            reason: Rejection reason

        Returns:
            Tuple of (success, message, completion)
        """
        stmt = select(TaskCompletion).where(TaskCompletion.id == completion_id)
        result = await session.execute(stmt)
        completion = result.scalar_one_or_none()

        if not completion:
            return False, "completion_not_found", None

        if completion.status != TaskCompletionStatus.PENDING_REVIEW.value:
            return False, "not_pending_review", completion

        completion.status = TaskCompletionStatus.FAILED.value
        completion.reviewed_by = admin_telegram_id
        completion.reviewed_at = datetime.now(UTC)
        completion.review_notes = reason
        await session.commit()
        await session.refresh(completion)

        logger.info(
            f"Admin {admin_telegram_id} rejected screenshot {completion_id}"
        )
        return True, "rejected", completion

    # =====================
    # SUBSCRIPTION RECHECKING
    # =====================

    @staticmethod
    async def recheck_subscriptions(
        session: AsyncSession,
        bot: Bot,
        hours_since_check: int = 6,
    ) -> Dict[str, Any]:
        """
        Recheck all completed Telegram subscriptions

        Args:
            session: Database session
            bot: Bot instance
            hours_since_check: Only check if not checked recently

        Returns:
            Dict with stats (total_checked, still_subscribed, revoked, etc.)
        """
        stats = {
            "total_checked": 0,
            "still_subscribed": 0,
            "revoked": 0,
            "total_penalty": 0,
            "errors": 0,
            "revoked_details": [],
        }

        cutoff_time = datetime.now(UTC) - timedelta(hours=hours_since_check)

        # Get completions to recheck
        stmt = (
            select(TaskCompletion)
            .join(SocialTask)
            .join(User)
            .where(
                and_(
                    TaskCompletion.status == TaskCompletionStatus.COMPLETED.value,
                    SocialTask.task_type.in_([
                        TaskType.TELEGRAM_SUBSCRIBE_CHANNEL.value,
                        TaskType.TELEGRAM_SUBSCRIBE_CHAT.value,
                    ]),
                    or_(
                        TaskCompletion.last_recheck_at.is_(None),
                        TaskCompletion.last_recheck_at < cutoff_time,
                    ),
                )
            )
            .options(
                selectinload(TaskCompletion.task),
                selectinload(TaskCompletion.user),
            )
        )

        result = await session.execute(stmt)
        completions = result.scalars().all()

        for completion in completions:
            stats["total_checked"] += 1

            try:
                # Get user's telegram_id
                if not completion.user.telegram_id:
                    continue

                sub_result = await SocialTasksService.verify_telegram_subscription(
                    bot=bot,
                    telegram_user_id=completion.user.telegram_id,
                    channel_id=completion.task.telegram_channel_id,
                )
                is_subscribed = sub_result[0]

                completion.last_recheck_at = datetime.now(UTC)

                if is_subscribed:
                    stats["still_subscribed"] += 1
                else:
                    stats["revoked"] += 1
                    # Revoke reward
                    penalty = completion.task.unsubscribe_penalty
                    stats["total_penalty"] += penalty
                    stats["revoked_details"].append({
                        "user_id": completion.user_id,
                        "task_id": completion.task_id,
                        "penalty": penalty,
                    })

                    await SocialTasksService.revoke_reward(
                        session=session,
                        completion=completion,
                        apply_penalty=True,
                    )

            except Exception as e:
                stats["errors"] += 1
                logger.exception(f"Error rechecking completion {completion.id}: {e}")

        await session.commit()
        logger.info(f"Subscription recheck completed: {stats}")
        return stats

    @staticmethod
    async def revoke_reward(
        session: AsyncSession,
        completion: TaskCompletion,
        apply_penalty: bool = True,
    ) -> Tuple[bool, str]:
        """
        Revoke reward for unsubscription

        Args:
            session: Database session
            completion: TaskCompletion to revoke
            apply_penalty: Apply penalty points

        Returns:
            Tuple of (success, message)
        """
        if completion.status == TaskCompletionStatus.REVOKED.value:
            return False, "already_revoked"

        task = await SocialTasksService.get_task_by_id(session, completion.task_id)
        if not task:
            return False, "task_not_found"

        # Apply penalty
        penalty_amount = task.unsubscribe_penalty if apply_penalty else 0

        if penalty_amount > 0:
            penalty_tx = await PointsService.earn_points(
                session=session,
                user_id=completion.user_id,
                transaction_type=PointsTransactionType.SPEND_TASK_PENALTY.value,
                amount=-penalty_amount,  # Negative for deduction
                description=f"Penalty for unsubscribing: {task.title_en}",
                metadata={
                    "task_id": task.id,
                    "completion_id": completion.id,
                    "original_reward": completion.points_awarded,
                },
                transaction_id=f"penalty_task_{task.id}_user_{completion.user_id}_count_{completion.completion_count}",
            )

            if penalty_tx:
                completion.penalty_transaction_id = penalty_tx.id
                completion.penalty_applied = penalty_amount

        completion.status = TaskCompletionStatus.REVOKED.value
        completion.revoked_at = datetime.now(UTC)
        await session.commit()

        logger.warning(
            f"Revoked reward for user {completion.user_id} task {task.id}, "
            f"penalty: {penalty_amount} points"
        )
        return True, "revoked"

    # =====================
    # ADMIN OPERATIONS
    # =====================

    @staticmethod
    async def get_all_tasks(
        session: AsyncSession,
        status_filter: Optional[str] = None,
    ) -> List[SocialTask]:
        """Get all tasks for admin"""
        stmt = select(SocialTask).order_by(SocialTask.created_at.desc())
        if status_filter:
            stmt = stmt.where(SocialTask.status == status_filter)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_task(
        session: AsyncSession,
        admin_telegram_id: int,
        task_data: Dict[str, Any],
    ) -> SocialTask:
        """Create new task"""
        task = SocialTask(
            created_by=admin_telegram_id,
            **task_data,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        logger.info(f"Admin {admin_telegram_id} created task {task.id}")
        return task

    @staticmethod
    async def update_task(
        session: AsyncSession,
        task_id: int,
        updates: Dict[str, Any],
    ) -> Optional[SocialTask]:
        """Update task"""
        task = await SocialTasksService.get_task_by_id(session, task_id)
        if not task:
            return None

        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)

        task.updated_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(task)
        logger.info(f"Task {task_id} updated")
        return task

    @staticmethod
    async def toggle_task_status(
        session: AsyncSession,
        task_id: int,
        new_status: str,
    ) -> Optional[SocialTask]:
        """Change task status"""
        return await SocialTasksService.update_task(
            session, task_id, {"status": new_status}
        )

    @staticmethod
    async def delete_task(
        session: AsyncSession,
        task_id: int,
    ) -> bool:
        """Delete task"""
        task = await SocialTasksService.get_task_by_id(session, task_id)
        if not task:
            return False

        await session.delete(task)
        await session.commit()
        logger.info(f"Task {task_id} deleted")
        return True

    @staticmethod
    async def get_pending_reviews(
        session: AsyncSession,
    ) -> List[TaskCompletion]:
        """Get completions pending manual review"""
        stmt = (
            select(TaskCompletion)
            .where(TaskCompletion.status == TaskCompletionStatus.PENDING_REVIEW.value)
            .options(
                selectinload(TaskCompletion.task),
                selectinload(TaskCompletion.user),
            )
            .order_by(TaskCompletion.started_at.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_task_analytics(
        session: AsyncSession,
        task_id: int,
    ) -> Dict[str, Any]:
        """Get analytics for task"""
        task = await SocialTasksService.get_task_by_id(session, task_id)
        if not task:
            return {}

        # Count completions by status
        completions_stmt = (
            select(TaskCompletion.status, func.count(TaskCompletion.id))
            .where(TaskCompletion.task_id == task_id)
            .group_by(TaskCompletion.status)
        )
        result = await session.execute(completions_stmt)
        status_counts = dict(result.all())

        # Total points awarded
        points_stmt = (
            select(func.sum(TaskCompletion.points_awarded))
            .where(
                and_(
                    TaskCompletion.task_id == task_id,
                    TaskCompletion.status == TaskCompletionStatus.COMPLETED.value,
                )
            )
        )
        points_result = await session.execute(points_stmt)
        total_points = points_result.scalar() or 0

        return {
            "task_id": task_id,
            "title": task.title_en,
            "status": task.status,
            "current_completions": task.current_completions,
            "max_completions": task.max_completions,
            "reward_points": task.reward_points,
            "completions_by_status": status_counts,
            "total_points_awarded": total_points,
        }

    @staticmethod
    async def get_user_task_history(
        session: AsyncSession,
        user_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get user's task completion history"""
        stmt = (
            select(TaskCompletion)
            .where(TaskCompletion.user_id == user_id)
            .options(selectinload(TaskCompletion.task))
            .order_by(TaskCompletion.started_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        completions = result.scalars().all()

        return [
            {
                "completion_id": c.id,
                "task_id": c.task_id,
                "task_title": c.task.title_en if c.task else "Unknown",
                "task_icon": c.task.icon if c.task else "📋",
                "status": c.status,
                "points_awarded": c.points_awarded,
                "penalty_applied": c.penalty_applied,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "completed_at": c.completed_at.isoformat() if c.completed_at else None,
                "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
            }
            for c in completions
        ]
