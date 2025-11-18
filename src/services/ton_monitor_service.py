# coding: utf-8
"""
TON Monitor Service for Syntra Trade Consultant

Автоматический мониторинг входящих транзакций на TON blockchain:
- Сканирование deposit адреса на новые TON/USDT транзакции
- Парсинг memo из Cell структур
- Валидация Jetton wallet (защита от фейковых токенов!)
- Автоматическое зачисление подписок при получении платежа

Adapted from Tradient AI ton_monitor.py
"""

import json
import asyncio
import os
from typing import Optional, List, Dict, AsyncGenerator
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import logging
from src.utils.i18n import i18n

# TON blockchain libraries
try:
    from tonutils.client import ToncenterV2Client
    from tonutils.utils import Address
    from pytoniq_core import Cell
    TONUTILS_AVAILABLE = True
except ImportError:
    TONUTILS_AVAILABLE = False
    logging.warning("tonutils не установлен. Установите: pip install tonutils pytoniq-core")

from src.database.models import (
    Payment,
    PaymentStatus,
    PaymentProvider,
    SubscriptionTier,
    User,
    Subscription,
)

logger = logging.getLogger(__name__)


class TonMonitorService:
    """
    Сервис для мониторинга TON адресов на входящие транзакции

    Использует TON Center API через tonutils для:
    1. Получения списка транзакций по адресу
    2. Парсинга memo/comment из Cell сообщений
    3. Определения суммы и типа актива (TON или USDT Jetton)
    4. Автоматического зачисления подписок
    """

    # USDT Jetton Master адреса
    USDT_JETTON_MASTER_MAINNET = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
    USDT_JETTON_MASTER_TESTNET = "kQAiboDEv_qRrcEdrYdwbVLNOXBHwShFbtKGbQVJ2OKxY_Di"

    def __init__(self, is_testnet: bool = False):
        """
        Инициализация сервиса

        Args:
            is_testnet: Использовать testnet (True) или mainnet (False)
        """
        if not TONUTILS_AVAILABLE:
            raise ImportError(
                "tonutils не установлен. Установите: pip install tonutils pytoniq-core"
            )

        self.is_testnet = is_testnet
        self.network = "testnet" if is_testnet else "mainnet"

        # Инициализируем TON Center client с API ключом
        api_key = os.getenv("TON_CENTER_API_KEY", None)

        if not api_key:
            logger.warning(
                "TON_CENTER_API_KEY не установлен! Работа с лимитом 1 RPS. "
                "Получите ключ через @tonapibot в Telegram для увеличения до 10 RPS"
            )

        self.client = ToncenterV2Client(
            api_key=api_key,
            is_testnet=is_testnet
        )

        # USDT Jetton Master адрес
        self.usdt_jetton_master = (
            self.USDT_JETTON_MASTER_TESTNET if is_testnet
            else self.USDT_JETTON_MASTER_MAINNET
        )

        # Deposit адрес из конфигурации
        self.deposit_address = os.getenv("TON_DEPOSIT_ADDRESS", "")

        if not self.deposit_address:
            logger.warning("TON_DEPOSIT_ADDRESS не установлен в конфигурации!")

        logger.info(f"TonMonitorService инициализирован ({self.network})")

    async def get_transactions(
        self,
        address: str,
        limit: int = 100
    ) -> List[Dict]:
        """
        Получить транзакции для адреса

        Args:
            address: TON адрес (raw или user-friendly)
            limit: Количество транзакций (макс 100)

        Returns:
            Список транзакций
        """
        try:
            transactions = await self.client.get_transactions(
                address=address,
                limit=min(limit, 100)
            )
            return transactions

        except Exception as e:
            error_msg = str(e)
            # HTTP 500 - временная проблема API, не спамим логи
            if "HTTP 500" in error_msg or "500 Error" in error_msg:
                logger.debug(f"TON Center API временно недоступен (HTTP 500)")
            else:
                logger.error(f"Ошибка при получении транзакций для {address[:16]}...: {e}")
            return []

    def _parse_message_text(self, message_data: Dict) -> Optional[str]:
        """
        Извлечь текст memo/comment из сообщения

        TON использует TL-B схему для сериализации данных.
        Текстовый комментарий начинается с opcode 0x00000000 (32 нулевых бита)

        Args:
            message_data: Данные сообщения из транзакции

        Returns:
            Текст комментария или None
        """
        try:
            if not message_data or "message_content" not in message_data:
                return None

            content = message_data["message_content"]

            # Проверяем decoded
            if "decoded" in content and isinstance(content["decoded"], dict):
                decoded = content["decoded"]

                # Текстовый комментарий
                if decoded.get("type") == "text_comment":
                    return decoded.get("comment", "")

                # Jetton transfer может содержать comment в forward_payload
                if decoded.get("type") in ["jetton::transfer_notification", "jetton::transfer"]:
                    # Сначала проверяем forward_payload
                    forward_payload = decoded.get("forward_payload")
                    if forward_payload and isinstance(forward_payload, dict):
                        if forward_payload.get("type") == "text_comment":
                            return forward_payload.get("comment", "")

                    # Также может быть напрямую в comment
                    if decoded.get("comment"):
                        return decoded.get("comment", "")

            return None

        except Exception as e:
            logger.warning(f"Ошибка при парсинге message_text: {e}")
            return None

    def _is_jetton_notification(self, tx_data: Dict) -> bool:
        """
        Проверить является ли транзакция Jetton transfer_notification

        Проверяет opcode 0x7362d09c (transfer_notification) согласно TEP-74.
        Это входящее уведомление от jetton wallet о получении токенов.

        НЕ ПУТАТЬ с jetton::transfer (0xf8a7ea5) - это исходящий запрос!
        """
        try:
            in_msg = tx_data.get("in_msg")
            if not in_msg or "message_content" not in in_msg:
                return False

            content = in_msg["message_content"]
            if "decoded" in content and isinstance(content["decoded"], dict):
                decoded = content["decoded"]

                msg_type = decoded.get("type", "")
                opcode = decoded.get("op", "")

                # transfer_notification имеет opcode 0x7362d09c
                return (
                    msg_type == "jetton::transfer_notification" or
                    opcode in ["0x7362d09c", "7362d09c", 1935855772]
                )

            return False

        except Exception as e:
            logger.warning(f"Ошибка при проверке jetton notification: {e}")
            return False

    async def _validate_jetton_wallet(
        self,
        source_address: str,
        my_address: str
    ) -> bool:
        """
        Валидация источника jetton transfer_notification

        КРИТИЧЕСКИ ВАЖНО для безопасности!
        Проверяет что source сообщения - это легитимный jetton wallet.

        Защита от атаки:
        1. Злоумышленник создает фейковый jetton с похожим названием
        2. Отправляет фейковый transfer_notification с нашим адресом
        3. Без валидации мы зачислим фейковые токены как настоящие!

        Алгоритм валидации:
        1. Получаем jetton master из source jetton wallet (get_wallet_data)
        2. Проверяем что jetton master = известный USDT адрес

        Args:
            source_address: Адрес отправителя сообщения (jetton wallet)
            my_address: Наш адрес получателя

        Returns:
            True если источник легитимный, False если фейк
        """
        try:
            # Получаем данные jetton wallet
            wallet_data = await self.client.run_get_method(
                address=source_address,
                method_name="get_wallet_data",
                stack=[]
            )

            # wallet_data[2] содержит jetton master address
            if len(wallet_data) < 3:
                logger.warning(f"Некорректный ответ get_wallet_data от {source_address[:16]}...")
                return False

            # Извлекаем jetton master из ответа
            jetton_master_cell = wallet_data[2]

            # Получаем адрес из cell
            if hasattr(jetton_master_cell, 'load_address'):
                jetton_master = jetton_master_cell.load_address()
            elif hasattr(jetton_master_cell, 'to_str'):
                jetton_master = jetton_master_cell.to_str()
            else:
                jetton_master = str(jetton_master_cell)

            # Нормализуем адреса для сравнения
            jetton_master_normalized = str(jetton_master).strip()
            usdt_master_normalized = self.usdt_jetton_master.strip()

            # Проверяем что jetton master совпадает с официальным USDT
            if jetton_master_normalized.lower() != usdt_master_normalized.lower():
                logger.warning(
                    f"⚠️ ФЕЙКОВЫЙ JETTON! Master: {jetton_master_normalized} != {usdt_master_normalized}"
                )
                return False

            return True

        except Exception as e:
            logger.error(
                f"Ошибка при валидации jetton wallet {source_address[:16]}...: {e}",
                exc_info=True
            )
            # В случае ошибки валидации - считаем невалидным (безопаснее)
            return False

    def _extract_jetton_amount(self, tx_data: Dict) -> Optional[float]:
        """
        Извлечь сумму Jetton из transfer_notification

        Args:
            tx_data: Данные транзакции

        Returns:
            Сумма в USDT (с учетом decimals=6)
        """
        try:
            in_msg = tx_data.get("in_msg", {})
            content = in_msg.get("message_content", {})
            decoded = content.get("decoded", {})

            # Проверяем что это transfer_notification
            msg_type = decoded.get("type", "")
            if msg_type not in ["jetton::transfer_notification", "jetton::transfer"]:
                return None

            # Извлекаем amount
            amount = decoded.get("amount", 0)
            if isinstance(amount, str):
                amount = int(amount)
            elif not isinstance(amount, int):
                return None

            # USDT в TON имеет 6 decimals
            return amount / 1_000_000

        except Exception as e:
            logger.warning(f"Ошибка при извлечении Jetton amount: {e}")
            return None

    def _transaction_to_dict(self, tx) -> Dict:
        """
        Конвертировать объект Transaction из tonutils в словарь

        Args:
            tx: Объект Transaction из tonutils

        Returns:
            Словарь с данными транзакции
        """
        try:
            result = {
                "transaction_id": {},
                "in_msg": {},
                "out_msgs": [],
                "utime": 0
            }

            # Извлекаем transaction_id (lt и hash)
            if hasattr(tx, 'lt'):
                result["transaction_id"]["lt"] = str(tx.lt)

            # Извлекаем hash из tx.cell.hash
            if hasattr(tx, 'cell') and hasattr(tx.cell, 'hash'):
                hash_value = tx.cell.hash.hex()
                result["transaction_id"]["hash"] = hash_value
            elif hasattr(tx, 'hash'):
                if isinstance(tx.hash, bytes):
                    hash_value = tx.hash.hex()
                elif isinstance(tx.hash, str):
                    hash_value = tx.hash
                else:
                    hash_value = str(tx.hash)
                result["transaction_id"]["hash"] = hash_value

            # Извлекаем timestamp
            if hasattr(tx, 'utime'):
                result["utime"] = tx.utime
            elif hasattr(tx, 'now'):
                result["utime"] = tx.now

            # Извлекаем входящее сообщение
            if hasattr(tx, 'in_msg') and tx.in_msg:
                in_msg = tx.in_msg

                source = ''
                destination = ''
                value = 0

                # Извлекаем из info
                if hasattr(in_msg, 'info') and in_msg.info:
                    info = in_msg.info

                    # Source
                    if hasattr(info, 'src') and info.src:
                        src = info.src
                        if hasattr(src, 'to_str'):
                            source = src.to_str(is_user_friendly=True)
                        else:
                            source = str(src)

                    # Destination
                    if hasattr(info, 'dest') and info.dest:
                        dest = info.dest
                        if hasattr(dest, 'to_str'):
                            destination = dest.to_str(is_user_friendly=True)
                        else:
                            destination = str(dest)

                    # Amount из info.value (CurrencyCollection)
                    if hasattr(info, 'value') and info.value:
                        try:
                            if hasattr(info.value, 'grams'):
                                value = int(info.value.grams) if info.value.grams else 0
                            elif hasattr(info.value, 'coins'):
                                value = int(info.value.coins) if info.value.coins else 0
                            else:
                                value = 0
                        except Exception:
                            value = 0

                result["in_msg"] = {
                    "source": source,
                    "destination": destination,
                    "value": value,
                    "message_content": {}
                }

                # Извлекаем message content
                if hasattr(in_msg, 'body') or hasattr(in_msg, 'message_content'):
                    body = getattr(in_msg, 'body', None) or getattr(in_msg, 'message_content', None)
                    if body:
                        result["in_msg"]["message_content"] = self._parse_message_body(body)

            return result

        except Exception as e:
            logger.error(f"Ошибка при конвертации Transaction в dict: {e}", exc_info=True)
            return {
                "transaction_id": {"lt": "0", "hash": ""},
                "in_msg": {},
                "out_msgs": [],
                "utime": 0
            }

    def _parse_message_body(self, body) -> Dict:
        """
        Парсинг тела сообщения из Transaction объекта

        Поддерживает извлечение текстового комментария из Cell объекта (pytoniq_core)

        Args:
            body: Тело сообщения (Cell из pytoniq_core или dict)

        Returns:
            Словарь с decoded данными
        """
        try:
            result = {"decoded": {}}

            # Если это уже словарь, возвращаем как есть
            if isinstance(body, dict):
                return body

            # Проверяем что это Cell объект из pytoniq_core
            if hasattr(body, 'begin_parse'):
                try:
                    slice_obj = body.begin_parse()

                    # Проверяем что Slice не пустой
                    remaining = slice_obj.remaining_bits

                    if remaining < 32:
                        return result

                    # Загружаем opcode (первые 32 бита)
                    opcode = slice_obj.load_uint(32)

                    # Text comment имеет opcode = 0x00000000
                    if opcode == 0:
                        if slice_obj.remaining_bits > 0 or slice_obj.remaining_refs > 0:
                            comment_text = slice_obj.load_snake_string()

                            result["decoded"] = {
                                "type": "text_comment",
                                "comment": comment_text,
                                "op": "0x00000000"
                            }
                        else:
                            result["decoded"] = {
                                "type": "text_comment",
                                "comment": "",
                                "op": "0x00000000"
                            }

                    # Jetton Transfer Notification (opcode = 0x7362d09c)
                    elif opcode == 0x7362d09c:
                        # Пропускаем query_id (64 бита)
                        slice_obj.load_bits(64)

                        # Загружаем amount
                        amount = slice_obj.load_coins()

                        # Загружаем sender address
                        sender = slice_obj.load_address()

                        result["decoded"] = {
                            "type": "jetton::transfer_notification",
                            "op": "0x7362d09c",
                            "amount": str(amount),
                            "sender": sender.to_str(is_user_friendly=True) if sender else None
                        }

                        # Пытаемся прочитать forward_payload с комментарием
                        try:
                            if slice_obj.remaining_refs > 0:
                                forward_cell = slice_obj.load_ref()
                                forward_slice = forward_cell.begin_parse()

                                if forward_slice.remaining_bits >= 32:
                                    forward_op = forward_slice.load_uint(32)
                                    if forward_op == 0:
                                        forward_comment = forward_slice.load_snake_string()
                                        result["decoded"]["comment"] = forward_comment
                        except Exception:
                            pass

                    # Неизвестный opcode
                    else:
                        result["decoded"] = {
                            "type": "unknown",
                            "op": f"0x{opcode:08x}"
                        }

                except Exception as e:
                    logger.warning(f"Error parsing Cell: {e}", exc_info=True)
                    return result

            return result

        except Exception as e:
            logger.warning(f"Ошибка при парсинге message body: {e}")
            return {"decoded": {}}

    async def scan_address(
        self,
        session: AsyncSession,
        address: Optional[str] = None,
        last_lt: Optional[int] = None
    ) -> AsyncGenerator[Dict, None]:
        """
        Сканировать адрес на новые входящие транзакции

        Args:
            session: Async database session
            address: TON адрес для мониторинга (по умолчанию DEPOSIT_ADDRESS)
            last_lt: Logical Time последней обработанной транзакции

        Yields:
            Словари с данными входящих транзакций
        """
        address = address or self.deposit_address
        if not address:
            logger.error("TON deposit address не установлен!")
            return

        try:
            # Нормализуем целевой адрес
            target_address = Address(address)

            # Получаем последнюю обработанную транзакцию из БД (если last_lt не указан)
            if last_lt is None:
                result = await session.execute(
                    select(Payment)
                    .where(
                        Payment.provider == PaymentProvider.TON_CONNECT,
                        Payment.status != PaymentStatus.PENDING,
                    )
                    .order_by(Payment.created_at.desc())
                    .limit(1)
                )
                last_payment = result.scalar_one_or_none()

                # Извлекаем lt из metadata если есть
                if last_payment and last_payment.metadata:
                    last_lt = last_payment.metadata.get("lt", 0)
                else:
                    last_lt = 0

            # Получаем транзакции
            transactions = await self.get_transactions(address, limit=100)

            if not transactions:
                logger.debug(f"Нет транзакций для {address[:16]}...")
                return

            logger.debug(f"📊 Получено {len(transactions)} транзакций от TON API")

            for tx in transactions:
                # Конвертируем Transaction объект в словарь
                try:
                    if hasattr(tx, '__dict__'):
                        tx_dict = self._transaction_to_dict(tx)
                    else:
                        tx_dict = tx
                except Exception as e:
                    logger.warning(f"Ошибка при конвертации транзакции: {e}")
                    continue

                # Пропускаем уже обработанные
                tx_lt = int(tx_dict.get("transaction_id", {}).get("lt", 0))
                tx_hash = tx_dict.get("transaction_id", {}).get("hash", "")

                if tx_lt <= last_lt:
                    continue

                # Обрабатываем только входящие сообщения
                in_msg = tx_dict.get("in_msg")
                if not in_msg:
                    continue

                # Проверяем что это входящее на наш адрес
                destination = in_msg.get("destination")
                if not destination:
                    continue

                try:
                    dest_address = Address(destination)
                    if dest_address != target_address:
                        continue
                except Exception:
                    continue

                # Определяем тип транзакции (TON или Jetton notification)
                is_jetton = self._is_jetton_notification(tx_dict)

                # Извлекаем данные
                source = in_msg.get("source", "")
                value = int(in_msg.get("value", 0)) / 1_000_000_000  # nanoton -> TON

                # Парсим memo/comment
                memo = self._parse_message_text(in_msg)

                if is_jetton:
                    # USDT Jetton перевод - ТРЕБУЕТСЯ ВАЛИДАЦИЯ!
                    is_valid = await self._validate_jetton_wallet(source, address)

                    if not is_valid:
                        logger.warning(f"⚠️ ФЕЙКОВЫЙ JETTON! TX {tx_hash[:16]}... игнорируется")
                        continue

                    jetton_amount = self._extract_jetton_amount(tx_dict)
                    if jetton_amount:
                        yield {
                            "tx_hash": tx_hash,
                            "lt": tx_lt,
                            "asset": "USDT",
                            "amount": jetton_amount,
                            "from_address": source,
                            "to_address": address,
                            "memo": memo,
                            "timestamp": datetime.fromtimestamp(tx_dict.get("utime", 0)),
                            "raw_data": json.dumps(tx_dict)
                        }
                else:
                    # Нативный TON перевод
                    if value > 0:
                        yield {
                            "tx_hash": tx_hash,
                            "lt": tx_lt,
                            "asset": "TON",
                            "amount": value,
                            "from_address": source,
                            "to_address": address,
                            "memo": memo,
                            "timestamp": datetime.fromtimestamp(tx_dict.get("utime", 0)),
                            "raw_data": json.dumps(tx_dict)
                        }

                # Обновляем last_lt после yield транзакции
                last_lt = tx_lt

        except Exception as e:
            logger.error(f"Ошибка при сканировании адреса {address}: {e}", exc_info=True)

    async def process_transaction(
        self,
        session: AsyncSession,
        tx_data: Dict,
        bot=None
    ) -> bool:
        """
        Обработать входящую транзакцию

        1. Найти payment по memo
        2. Валидировать сумму
        3. Активировать подписку
        4. Обновить payment status
        5. Отправить уведомления пользователю и админам

        Args:
            session: Async database session
            tx_data: Данные транзакции
            bot: Telegram Bot instance для уведомлений (опционально)

        Returns:
            True если успешно обработано
        """
        try:
            memo = tx_data.get("memo", "").strip().upper()

            if not memo or not memo.startswith("PAY_"):
                logger.debug(f"Неверный или отсутствующий memo: {memo}")
                return False

            # Ищем payment по memo
            result = await session.execute(
                select(Payment).where(
                    Payment.provider_payment_id == memo,
                    Payment.status == PaymentStatus.PENDING,
                )
            )
            payment = result.scalar_one_or_none()

            if not payment:
                logger.warning(f"Payment не найден для memo: {memo}")
                return False

            # Валидируем сумму
            expected_amount = (
                payment.metadata.get("amount_usdt")
                if tx_data["asset"] == "USDT"
                else payment.metadata.get("amount_ton")
            )

            if not expected_amount:
                logger.error(f"Expected amount не найден в payment metadata")
                return False

            # Допускаем расхождение ±2%
            received_amount = tx_data["amount"]
            diff_percent = abs(received_amount - expected_amount) / expected_amount * 100

            if diff_percent > 2:
                logger.warning(
                    f"Сумма не соответствует: получено {received_amount} {tx_data['asset']}, "
                    f"ожидалось {expected_amount} {tx_data['asset']} (разница {diff_percent:.1f}%)"
                )
                # Можно создать алерт для админа
                return False

            # Обновляем payment
            payment.status = PaymentStatus.COMPLETED
            payment.completed_at = datetime.now(UTC)
            payment.metadata["tx_hash"] = tx_data["tx_hash"]
            payment.metadata["from_address"] = tx_data["from_address"]
            payment.metadata["received_amount"] = received_amount
            payment.metadata["received_asset"] = tx_data["asset"]
            payment.metadata["lt"] = tx_data["lt"]

            # Активируем подписку
            await self._activate_subscription(
                session,
                payment.user_id,
                payment.tier,
                payment.duration_months
            )

            await session.commit()

            logger.info(
                f"✅ TON payment обработан: user={payment.user_id}, "
                f"tier={payment.tier}, amount={received_amount} {tx_data['asset']}"
            )

            # Отправляем уведомления через Telegram bot
            if bot:
                await self._send_notifications(
                    bot=bot,
                    session=session,
                    payment=payment,
                    tx_data=tx_data
                )

            return True

        except Exception as e:
            logger.error(f"Ошибка при обработке TON транзакции: {e}", exc_info=True)
            await session.rollback()
            return False

    async def _activate_subscription(
        self,
        session: AsyncSession,
        user_id: int,
        tier_str: str,
        duration_months: int,
    ):
        """
        Активировать/обновить подписку пользователя

        Args:
            session: Async database session
            user_id: ID пользователя
            tier_str: Subscription tier (строка)
            duration_months: Длительность в месяцах
        """
        from datetime import timedelta

        try:
            tier = SubscriptionTier(tier_str)

            # Получаем или создаем подписку
            result = await session.execute(
                select(Subscription).where(Subscription.user_id == user_id)
            )
            subscription = result.scalar_one_or_none()

            if subscription:
                # Обновляем существующую подписку
                if subscription.is_active and subscription.expires_at > datetime.now(UTC):
                    # Продлеваем от текущего expires_at
                    subscription.expires_at += timedelta(days=duration_months * 30)
                else:
                    # Активируем заново
                    subscription.expires_at = datetime.now(UTC) + timedelta(
                        days=duration_months * 30
                    )

                subscription.tier = tier
                subscription.is_active = True
                subscription.auto_renew = False  # TON payments не поддерживают auto-renew

            else:
                # Создаем новую подписку
                subscription = Subscription(
                    user_id=user_id,
                    tier=tier,
                    expires_at=datetime.now(UTC) + timedelta(days=duration_months * 30),
                    is_active=True,
                    auto_renew=False,
                )
                session.add(subscription)

            # Обновляем user.is_premium
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if user:
                user.is_premium = True  # type: ignore

            await session.commit()

            logger.info(
                f"Subscription активирована: user={user_id}, tier={tier.value}, "
                f"duration={duration_months}m"
            )

        except Exception as e:
            logger.exception(f"Ошибка при активации subscription: {e}")
            raise

    async def _send_notifications(
        self,
        bot,
        session: AsyncSession,
        payment,
        tx_data: Dict
    ):
        """
        Отправить уведомления о успешном платеже

        Args:
            bot: Telegram Bot instance
            session: Async database session
            payment: Payment object
            tx_data: Данные транзакции
        """
        try:
            from sqlalchemy import select

            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.id == payment.user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"User {payment.user_id} не найден для уведомления")
                return

            # Получаем подписку
            result = await session.execute(
                select(Subscription).where(Subscription.user_id == user.id)
            )
            subscription = result.scalar_one_or_none()

            # Форматируем дату истечения
            expires_at_str = "Unknown"
            if subscription and subscription.expires_at:
                from datetime import datetime
                expires_at_str = subscription.expires_at.strftime("%d.%m.%Y")

            # Tier emoji
            tier_emoji = {
                "basic": "🥉",
                "premium": "🥈",
                "vip": "🥇"
            }.get(payment.tier, "⭐")

            # === Уведомление пользователю ===
            try:
                # Получаем язык пользователя
                lang = user.language or "en"

                # Формируем локализованное сообщение
                user_message = (
                    f"{i18n.get('ton_payment.user_notification.title', lang)}\n\n"
                    f"{i18n.get('ton_payment.user_notification.plan', lang).format(emoji=tier_emoji, tier=payment.tier.upper())}\n"
                    f"{i18n.get('ton_payment.user_notification.duration', lang).format(months=payment.duration_months)}\n"
                    f"{i18n.get('ton_payment.user_notification.received', lang).format(amount=tx_data['amount'], asset=tx_data['asset'])}\n"
                    f"{i18n.get('ton_payment.user_notification.active_until', lang).format(date=expires_at_str)}\n\n"
                    f"{i18n.get('ton_payment.user_notification.tx', lang).format(tx_hash=tx_data['tx_hash'][:16] + '...')}\n\n"
                    f"{i18n.get('ton_payment.user_notification.thank_you', lang)}"
                )

                await bot.send_message(
                    user.telegram_id,
                    user_message,
                    parse_mode="HTML"
                )

                logger.info(f"Уведомление отправлено пользователю {user.telegram_id}")

            except Exception as e:
                logger.warning(f"Ошибка при отправке уведомления пользователю: {e}")

            # === Уведомление админам ===
            try:
                admin_ids = os.getenv("ADMIN_IDS", [])

                if admin_ids:
                    # Username или ID для отображения
                    user_display = f"@{user.username}" if user.username else f"ID {user.telegram_id}"

                    # Админские уведомления всегда на английском
                    admin_lang = "en"

                    # Формируем локализованное сообщение для админа
                    admin_message = (
                        f"{i18n.get('ton_payment.admin_notification.title', admin_lang)}\n\n"
                        f"{i18n.get('ton_payment.admin_notification.user', admin_lang).format(user_display=user_display)}\n"
                        f"{i18n.get('ton_payment.admin_notification.plan', admin_lang).format(emoji=tier_emoji, tier=payment.tier.upper())}\n"
                        f"{i18n.get('ton_payment.admin_notification.duration', admin_lang).format(months=payment.duration_months)}\n"
                        f"{i18n.get('ton_payment.admin_notification.amount', admin_lang).format(amount=tx_data['amount'], asset=tx_data['asset'], usd=payment.amount)}\n"
                        f"{i18n.get('ton_payment.admin_notification.tx', admin_lang).format(tx_hash=tx_data['tx_hash'])}\n"
                        f"{i18n.get('ton_payment.admin_notification.memo', admin_lang).format(memo=payment.provider_payment_id)}\n\n"
                        f"{i18n.get('ton_payment.admin_notification.active_until', admin_lang).format(date=expires_at_str)}"
                    )

                    for admin_id in admin_ids:
                        try:
                            await bot.send_message(
                                admin_id,
                                admin_message,
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.warning(f"Ошибка при отправке админу {admin_id}: {e}")

                    logger.info(f"Уведомления отправлены {len(admin_ids)} админам")

            except Exception as e:
                logger.warning(f"Ошибка при отправке уведомлений админам: {e}")

        except Exception as e:
            logger.exception(f"Ошибка в _send_notifications: {e}")


# Глобальный singleton
_ton_monitor_service: Optional[TonMonitorService] = None


def get_ton_monitor_service(is_testnet: bool = False) -> TonMonitorService:
    """
    Получить глобальный экземпляр TonMonitorService (синглтон)

    Args:
        is_testnet: Использовать testnet (True) или mainnet (False)

    Returns:
        Инициализированный TonMonitorService
    """
    global _ton_monitor_service

    if _ton_monitor_service is None:
        _ton_monitor_service = TonMonitorService(is_testnet=is_testnet)

    return _ton_monitor_service
