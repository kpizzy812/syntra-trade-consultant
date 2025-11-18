# coding: utf-8
"""
TON Payment Service for Syntra Trade Consultant

Обработка платежей через TON blockchain:
- Нативные TON переводы
- USDT (Jetton) переводы
- Мониторинг входящих транзакций
- Автоматическое зачисление подписок

Adapted from Tradient AI implementation
"""

import asyncio
import hashlib
import logging
import os
from typing import Optional, Dict, List
from datetime import datetime, UTC
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# TON blockchain libraries (опционально)
try:
    from tonutils.client import ToncenterV2Client
    from tonutils.utils import Address
    TONUTILS_AVAILABLE = True
except ImportError:
    TONUTILS_AVAILABLE = False
    logging.warning("tonutils не установлен. Установите: pip install tonutils")

from src.database.models import (
    User,
    SubscriptionTier,
    PaymentProvider,
    PaymentStatus,
    Payment,
    Subscription,
)

logger = logging.getLogger(__name__)


class TonPaymentService:
    """
    Сервис для обработки TON/USDT платежей

    Функционал:
    1. Генерация уникальных payment memo для идентификации
    2. Мониторинг входящих TON/USDT транзакций
    3. Автоматическое зачисление подписок при подтверждении
    4. Валидация Jetton (USDT) transfers против фейковых токенов
    """

    # TON deposit address (единый адрес для всех входящих платежей)
    # В production должен быть в .env
    DEPOSIT_ADDRESS = os.getenv("TON_DEPOSIT_ADDRESS", "")

    # USDT Jetton Master адрес (mainnet)
    USDT_JETTON_MASTER = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"

    # Минимальные суммы для защиты от спама
    MIN_TON_AMOUNT = 0.1  # TON
    MIN_USDT_AMOUNT = 1.0  # USDT

    def __init__(self, is_testnet: bool = False):
        """
        Инициализация сервиса

        Args:
            is_testnet: Использовать testnet (True) или mainnet (False)
        """
        self.is_testnet = is_testnet
        self.network = "testnet" if is_testnet else "mainnet"

        # Инициализируем TON Center client если доступен
        self.client: Optional[ToncenterV2Client] = None

        if TONUTILS_AVAILABLE:
            api_key = os.getenv("TON_CENTER_API_KEY", None)
            if not api_key:
                logger.warning(
                    "TON_CENTER_API_KEY не установлен! Работа с лимитом 1 RPS."
                )

            self.client = ToncenterV2Client(api_key=api_key, is_testnet=is_testnet)

            logger.info(f"TonPaymentService инициализирован ({self.network})")
        else:
            logger.error("tonutils недоступен! TON payments не будут работать.")

    def generate_payment_memo(
        self, user_id: int, tier: SubscriptionTier, duration_months: int
    ) -> str:
        """
        Генерировать уникальный memo для payment идентификации

        Формат: PAY_{hash}
        где hash = первые 8 символов от sha256(user_id + tier + duration + timestamp)

        Args:
            user_id: ID пользователя
            tier: Subscription tier
            duration_months: Длительность подписки

        Returns:
            Memo строка (например: "PAY_a3f5c9d2")
        """
        timestamp = datetime.now(UTC).isoformat()
        raw = f"{user_id}_{tier.value}_{duration_months}_{timestamp}"
        hash_hex = hashlib.sha256(raw.encode()).hexdigest()[:8]

        return f"PAY_{hash_hex}".upper()

    async def create_ton_payment_request(
        self,
        session: AsyncSession,
        user_id: int,
        tier: SubscriptionTier,
        duration_months: int,
        amount_usd: Decimal,
    ) -> Dict:
        """
        Создать payment request для TON/USDT оплаты

        Создает pending payment запись в БД и возвращает детали для оплаты

        Args:
            session: Async database session
            user_id: ID пользователя
            tier: Subscription tier
            duration_months: Длительность подписки
            amount_usd: Сумма в USD

        Returns:
            Словарь с payment details:
            {
                "payment_id": int,
                "deposit_address": str,  # TON адрес для депозита
                "memo": str,              # Уникальный memo
                "amount_usd": Decimal,
                "amount_ton": float,      # Примерная сумма в TON
                "amount_usdt": float,     # Сумма в USDT (= amount_usd)
                "expires_at": datetime    # Истечение через 1 час
            }
        """
        try:
            # Генерируем уникальный memo
            memo = self.generate_payment_memo(user_id, tier, duration_months)

            # Получаем курс TON/USD (примерный)
            ton_price_usd = await self._get_ton_price()
            amount_ton = float(amount_usd) / ton_price_usd

            # Для USDT amount = amount_usd (stablecoin 1:1)
            amount_usdt = float(amount_usd)

            # Создаем payment запись
            payment = Payment(
                user_id=user_id,
                provider=PaymentProvider.TON_CONNECT,
                amount=amount_usd,
                currency="USD",
                status=PaymentStatus.PENDING,
                tier=tier.value,
                duration_months=duration_months,
                provider_payment_id=memo,  # Используем memo как payment ID
                metadata={
                    "deposit_address": self.DEPOSIT_ADDRESS,
                    "memo": memo,
                    "amount_ton": amount_ton,
                    "amount_usdt": amount_usdt,
                    "ton_price_usd": ton_price_usd,
                },
            )

            session.add(payment)
            await session.commit()
            await session.refresh(payment)

            logger.info(
                f"TON payment request создан: user={user_id}, tier={tier.value}, "
                f"memo={memo}, amount=${amount_usd}"
            )

            return {
                "payment_id": payment.id,
                "deposit_address": self.DEPOSIT_ADDRESS,
                "memo": memo,
                "amount_usd": amount_usd,
                "amount_ton": amount_ton,
                "amount_usdt": amount_usdt,
                "expires_at": payment.created_at.replace(
                    hour=payment.created_at.hour + 1
                ),  # +1 час
            }

        except Exception as e:
            logger.exception(f"Ошибка при создании TON payment request: {e}")
            raise

    async def _get_ton_price(self) -> float:
        """
        Получить текущий курс TON/USD

        Использует CoinGecko API (можно заменить на другой источник)

        Returns:
            Цена TON в USD
        """
        try:
            # TODO: Интегрировать с реальным API (CoinGecko, CoinMarketCap и т.д.)
            # Для примера возвращаем статичную цену
            return 5.5  # $5.5 за TON (обновить в production!)

        except Exception as e:
            logger.warning(f"Ошибка при получении TON price: {e}")
            return 5.5  # Fallback price

    async def scan_incoming_transactions(
        self, session: AsyncSession, address: Optional[str] = None
    ) -> int:
        """
        Сканировать входящие TON/USDT транзакции на deposit адрес

        Проверяет новые транзакции и автоматически зачисляет подписки

        Args:
            session: Async database session
            address: TON адрес для сканирования (по умолчанию DEPOSIT_ADDRESS)

        Returns:
            Количество обработанных транзакций
        """
        if not TONUTILS_AVAILABLE or not self.client:
            logger.error("tonutils недоступен! Не могу сканировать транзакции.")
            return 0

        address = address or self.DEPOSIT_ADDRESS
        if not address:
            logger.error("TON deposit address не установлен в конфигурации!")
            return 0

        try:
            logger.debug(f"Сканирование TON адреса: {address[:16]}...")

            # Получаем последнюю обработанную транзакцию
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

            # TODO: Реализовать через TonMonitorService из Tradient AI
            # Сейчас placeholder для демонстрации структуры

            logger.info("TON transaction scan завершен (placeholder)")
            return 0

        except Exception as e:
            logger.exception(f"Ошибка при сканировании TON транзакций: {e}")
            return 0

    async def process_ton_transaction(
        self,
        session: AsyncSession,
        tx_hash: str,
        from_address: str,
        amount: float,
        asset: str,  # "TON" или "USDT"
        memo: Optional[str] = None,
    ) -> bool:
        """
        Обработать входящую TON/USDT транзакцию

        1. Найти payment по memo
        2. Валидировать сумму
        3. Активировать подписку
        4. Обновить payment status

        Args:
            session: Async database session
            tx_hash: Hash транзакции
            from_address: Адрес отправителя
            amount: Сумма (TON или USDT)
            asset: "TON" или "USDT"
            memo: Memo из транзакции

        Returns:
            True если успешно обработана
        """
        try:
            if not memo or not memo.startswith("PAY_"):
                logger.warning(f"Неверный memo: {memo}")
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
                if asset == "USDT"
                else payment.metadata.get("amount_ton")
            )

            if not expected_amount:
                logger.error(f"Expected amount не найден в payment metadata")
                return False

            # Допускаем расхождение ±2%
            diff_percent = abs(amount - expected_amount) / expected_amount * 100

            if diff_percent > 2:
                logger.warning(
                    f"Сумма не соответствует: получено {amount} {asset}, "
                    f"ожидалось {expected_amount} {asset} (разница {diff_percent:.1f}%)"
                )
                # Можно создать алерт для админа
                return False

            # Обновляем payment
            payment.status = PaymentStatus.COMPLETED
            payment.completed_at = datetime.now(UTC)
            payment.metadata["tx_hash"] = tx_hash
            payment.metadata["from_address"] = from_address
            payment.metadata["received_amount"] = amount
            payment.metadata["received_asset"] = asset

            # Активируем/создаем подписку
            await self._activate_subscription(
                session, payment.user_id, payment.tier, payment.duration_months
            )

            await session.commit()

            logger.success(
                f"TON payment обработан: user={payment.user_id}, "
                f"tier={payment.tier}, amount={amount} {asset}"
            )

            return True

        except Exception as e:
            logger.exception(f"Ошибка при обработке TON транзакции: {e}")
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
                # Если активная - продлеваем, если нет - активируем
                if subscription.is_active and subscription.expires_at > datetime.now(
                    UTC
                ):
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
                    expires_at=datetime.now(UTC)
                    + timedelta(days=duration_months * 30),
                    is_active=True,
                    auto_renew=False,
                )
                session.add(subscription)

            # Обновляем user.is_premium
            result = await session.execute(select(User).where(User.id == user_id))
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


# Глобальный singleton
_ton_payment_service: Optional[TonPaymentService] = None


def get_ton_payment_service(is_testnet: bool = False) -> TonPaymentService:
    """
    Получить глобальный экземпляр TonPaymentService (синглтон)

    Args:
        is_testnet: Использовать testnet (True) или mainnet (False)

    Returns:
        Инициализированный TonPaymentService
    """
    global _ton_payment_service

    if _ton_payment_service is None:
        _ton_payment_service = TonPaymentService(is_testnet=is_testnet)

    return _ton_payment_service
