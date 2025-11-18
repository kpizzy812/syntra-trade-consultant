# coding: utf-8
"""
Background task для сканирования TON blockchain

Периодически проверяет deposit адрес на входящие TON/USDT транзакции
Автоматически активирует подписки при получении платежа с корректным memo

Adapted from Tradient AI ton_scanner.py
"""

import asyncio
from datetime import datetime, UTC
import os

from src.database.engine import get_session_maker
from src.services.ton_monitor_service import get_ton_monitor_service
import logging

logger = logging.getLogger(__name__)


async def scan_ton_deposits():
    """
    Периодический сканер TON/USDT транзакций

    Запускается каждые 60 секунд и проверяет:
    - TON deposit адрес на нативные TON переводы
    - TON deposit адрес на USDT (Jetton) переводы
    - Парсит memo из транзакций (формат PAY_XXXXXXXX)
    - Автоматически активирует подписки при совпадении memo
    """
    from aiogram import Bot

    logger.info("🚀 Запущен TON blockchain scanner")

    # Инициализируем сервис мониторинга
    is_testnet = os.getenv("TON_NETWORK_TESTNET", "false").lower() == "true"
    monitor = get_ton_monitor_service(is_testnet=is_testnet)

    # Инициализируем бота для уведомлений
    bot_token = os.getenv("BOT_TOKEN", "")
    bot = Bot(token=bot_token)

    # Получаем deposit адрес
    deposit_address = os.getenv("TON_DEPOSIT_ADDRESS", "")

    if not deposit_address:
        logger.error("TON_DEPOSIT_ADDRESS не настроен в конфигурации!")
        return

    logger.info(f"📍 Мониторинг адреса: {deposit_address}")
    logger.info(f"🌐 Сеть: {'testnet' if is_testnet else 'mainnet'}")

    # Интервал сканирования (секунды)
    scan_interval = int(os.getenv("TON_SCAN_INTERVAL_SECONDS", "60"))

    while True:
        try:
            scan_start = datetime.now(UTC)
            transactions_found = 0
            processed_success = 0
            processed_failed = 0

            # Используем async context manager для сессии БД
            session_maker = get_session_maker()
            async with session_maker() as session:
                # Сканируем адрес на новые транзакции
                async for tx_data in monitor.scan_address(session, deposit_address):
                    transactions_found += 1

                    # Обрабатываем транзакцию (передаем bot для уведомлений)
                    success = await monitor.process_transaction(session, tx_data, bot=bot)

                    if success:
                        processed_success += 1
                        logger.info(
                            f"✅ Подписка активирована: {tx_data['amount']} {tx_data['asset']} "
                            f"→ memo: {tx_data.get('memo', 'N/A')}"
                        )
                    else:
                        processed_failed += 1
                        # Детали ошибки уже залогированы в process_transaction

            # Вычисляем время выполнения
            scan_duration = (datetime.now(UTC) - scan_start).total_seconds()

            # Компактный вывод итогов сканирования
            if transactions_found > 0:
                parts = []
                if processed_success:
                    parts.append(f"✅ {processed_success} обработано")
                if processed_failed:
                    parts.append(f"⚠️ {processed_failed} требует проверки")

                status = ", ".join(parts) if parts else "обработано"
                logger.info(
                    f"🔍 TON Scan: {transactions_found} новых TX | {status} | {scan_duration:.1f}с"
                )
            else:
                # Не выводим если нет новых транзакций (не засоряем логи)
                logger.debug(f"🔍 TON Scan: нет новых транзакций | {scan_duration:.1f}с")

        except Exception as e:
            logger.exception(f"❌ Ошибка при сканировании TON blockchain: {e}")

        # Ждем перед следующим сканированием
        await asyncio.sleep(scan_interval)


async def start_ton_scanner():
    """
    Запуск scanner как background task

    Используется для интеграции с aiogram bot
    """
    try:
        await scan_ton_deposits()
    except asyncio.CancelledError:
        logger.info("⛔ TON Scanner остановлен")
    except Exception as e:
        logger.exception(f"Критическая ошибка TON Scanner: {e}")


if __name__ == "__main__":
    """
    Запуск scanner как отдельный процесс:

    source .venv/bin/activate
    python -m src.tasks.ton_scanner
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        asyncio.run(scan_ton_deposits())
    except KeyboardInterrupt:
        logger.info("\n⛔ TON Scanner остановлен пользователем")
