# coding: utf-8
"""
Task Review Handlers for Telegram Bot

Handles inline button callbacks for approving/rejecting task screenshots.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from loguru import logger

from config.config import ADMIN_IDS
from src.database.engine import get_session_maker
from src.services.social_tasks_service import SocialTasksService

router = Router(name="task_review")


@router.callback_query(F.data.startswith("task_approve:"))
async def handle_task_approve(callback: CallbackQuery):
    """Handle task approval from inline button"""
    user_id = callback.from_user.id

    # Check admin permission
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Только для админов", show_alert=True)
        return

    # Extract completion_id
    try:
        completion_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return

    # Process approval
    SessionLocal = get_session_maker()
    async with SessionLocal() as session:
        try:
            success, message, completion = await SocialTasksService.approve_screenshot(
                session=session,
                completion_id=completion_id,
                admin_telegram_id=user_id,
                notes="Approved via Telegram",
            )

            if success:
                # Update message to show it's processed
                await callback.message.edit_text(
                    callback.message.html_text + "\n\n"
                    f"✅ <b>Одобрено</b> админом {callback.from_user.first_name}\n"
                    f"💰 Начислено: +{completion.points_awarded} $SYNTRA",
                    parse_mode="HTML",
                    reply_markup=None,  # Remove buttons
                )
                await callback.answer("✅ Задание одобрено!", show_alert=False)
            else:
                await callback.answer(f"❌ Ошибка: {message}", show_alert=True)

        except Exception as e:
            logger.exception(f"Error approving task: {e}")
            await callback.answer("❌ Ошибка при одобрении", show_alert=True)


@router.callback_query(F.data.startswith("task_reject:"))
async def handle_task_reject(callback: CallbackQuery):
    """Handle task rejection from inline button"""
    user_id = callback.from_user.id

    # Check admin permission
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Только для админов", show_alert=True)
        return

    # Extract completion_id
    try:
        completion_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return

    # Process rejection
    SessionLocal = get_session_maker()
    async with SessionLocal() as session:
        try:
            success, message, completion = await SocialTasksService.reject_screenshot(
                session=session,
                completion_id=completion_id,
                admin_telegram_id=user_id,
                reason="Rejected via Telegram",
            )

            if success:
                # Update message to show it's processed
                await callback.message.edit_text(
                    callback.message.html_text + "\n\n"
                    f"❌ <b>Отклонено</b> админом {callback.from_user.first_name}",
                    parse_mode="HTML",
                    reply_markup=None,  # Remove buttons
                )
                await callback.answer("❌ Задание отклонено", show_alert=False)
            else:
                await callback.answer(f"❌ Ошибка: {message}", show_alert=True)

        except Exception as e:
            logger.exception(f"Error rejecting task: {e}")
            await callback.answer("❌ Ошибка при отклонении", show_alert=True)
