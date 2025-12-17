# coding: utf-8
"""
Broadcast Scheduler - планировщик автоматических рассылок

Запускает периодические рассылки по расписанию
"""

import asyncio

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from src.database.engine import get_session_maker
from src.services.broadcast_service import (
    get_periodic_templates_due,
    execute_broadcast,
    update_template,
)
from src.database.models import BroadcastStatus


async def check_and_send_periodic_broadcasts(bot: Bot) -> None:
    """
    Проверить и отправить периодические рассылки

    Вызывается планировщиком каждые N минут
    """
    logger.debug("Checking periodic broadcasts...")

    async with get_session_maker()() as session:
        try:
            # Получаем шаблоны, готовые к отправке
            templates = await get_periodic_templates_due(session)

            if not templates:
                logger.debug("No periodic broadcasts due")
                return

            logger.info(f"Found {len(templates)} periodic broadcasts to send")

            for template in templates:
                try:
                    logger.info(
                        f"Starting periodic broadcast: {template.id} - {template.name}"
                    )

                    # Выполняем рассылку
                    log = await execute_broadcast(bot, session, template)

                    logger.info(
                        f"Periodic broadcast {template.id} completed: "
                        f"sent={log.sent_count}, failed={log.failed_count}"
                    )

                except Exception as e:
                    logger.exception(f"Error in periodic broadcast {template.id}: {e}")

                    # Помечаем ошибку, но не останавливаем шаблон
                    await update_template(
                        session, template.id,
                        status=BroadcastStatus.SCHEDULED.value,
                    )

                # Небольшая пауза между рассылками
                await asyncio.sleep(1)

        except Exception as e:
            logger.exception(f"Error checking periodic broadcasts: {e}")


def schedule_broadcast_tasks(scheduler: AsyncIOScheduler, bot: Bot) -> None:
    """
    Настроить планировщик для рассылок

    Args:
        scheduler: APScheduler instance
        bot: Bot instance
    """
    # Проверяем каждые 5 минут
    scheduler.add_job(
        check_and_send_periodic_broadcasts,
        "interval",
        minutes=5,
        args=[bot],
        id="broadcast_periodic_check",
        replace_existing=True,
        max_instances=1,  # Не запускать параллельно
    )

    logger.info("Broadcast scheduler configured: checking every 5 minutes")


async def run_broadcast_scheduler(bot: Bot) -> None:
    """
    Альтернативный запуск планировщика как async task

    Использовать если APScheduler недоступен
    """
    logger.info("Starting broadcast scheduler loop")

    while True:
        try:
            await check_and_send_periodic_broadcasts(bot)
        except Exception as e:
            logger.exception(f"Broadcast scheduler error: {e}")

        # Ждём 5 минут
        await asyncio.sleep(300)
