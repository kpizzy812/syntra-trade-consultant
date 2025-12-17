# coding: utf-8
"""
NOWPayments Service для Syntra AI

Функционал:
- Создание invoice для оплаты в 300+ криптовалютах
- Проверка статуса платежа
- Webhook обработка (IPN callbacks)
- Автоконверсия в фиат
- Non-custodial (вы контролируете средства)

API Documentation: https://documenter.getpostman.com/view/7907941/S1a32n38
Комиссия: 0.5% (одна валюта) или 1% (конверсия)
"""

import os
import hmac
import hashlib
import json
from typing import Optional, Dict, Any, List
from decimal import Decimal
from datetime import datetime, UTC

import requests
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database.models import (
    User,
    Payment,
    PaymentProvider,
    PaymentStatus,
    SubscriptionTier,
)


class NOWPaymentsService:
    """
    Сервис для работы с NOWPayments API

    Features:
    - 300+ криптовалют + 75+ фиатных валют
    - Комиссия: 0.5% (одна валюта) или 1% (конверсия)
    - Автоконверсия крипты в фиат
    - Non-custodial (вы контролируете средства)
    - Глобальный охват (работает в РФ)
    """

    # API Base URL
    API_BASE_URL = "https://api.nowpayments.io/v1"
    SANDBOX_API_URL = "https://api-sandbox.nowpayments.io/v1"

    def __init__(self):
        """Инициализация NOWPayments client"""
        self.api_key = os.getenv("NOWPAYMENTS_API_KEY", "")
        self.ipn_secret = os.getenv("NOWPAYMENTS_IPN_SECRET", "")
        self.is_sandbox = os.getenv("NOWPAYMENTS_SANDBOX", "false").lower() == "true"

        if not self.api_key:
            logger.warning("⚠️ NOWPAYMENTS_API_KEY не настроен!")
            self.enabled = False
            return

        self.enabled = True
        self.base_url = self.SANDBOX_API_URL if self.is_sandbox else self.API_BASE_URL

        network = "Sandbox" if self.is_sandbox else "Production"
        logger.info(f"✅ NOWPaymentsService инициализирован ({network})")

    def _get_headers(self) -> Dict[str, str]:
        """Получить headers для API запросов"""
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }

    async def get_api_status(self) -> Optional[Dict[str, Any]]:
        """
        Проверить статус API (доступность сервиса)

        Returns:
            {"message": "OK"} если API доступен
        """
        if not self.enabled:
            return None

        try:
            url = f"{self.base_url}/status"
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()

            data = response.json()
            logger.info(f"✅ NOWPayments API status: {data.get('message')}")
            return data

        except Exception as e:
            logger.error(f"❌ Ошибка проверки API status: {e}")
            return None

    async def get_available_currencies(self) -> List[str]:
        """
        Получить список доступных криптовалют

        Returns:
            Список тикеров валют (например: ['btc', 'eth', 'usdt', ...])
        """
        if not self.enabled:
            return []

        try:
            url = f"{self.base_url}/currencies?fixed_rate=true"
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()

            data = response.json()
            currencies = data.get("currencies", [])

            logger.info(f"✅ Получено {len(currencies)} валют")
            return currencies

        except Exception as e:
            logger.error(f"❌ Ошибка получения валют: {e}")
            return []

    async def create_invoice(
        self,
        session: AsyncSession,
        user_id: int,
        tier: SubscriptionTier,
        duration_months: int,
        amount_usd: Decimal,
        order_description: Optional[str] = None,
        pay_currency: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Создать invoice для оплаты подписки

        Invoice позволяет пользователю выбрать валюту самостоятельно на странице оплаты.

        Args:
            session: Database session
            user_id: ID пользователя
            tier: Subscription tier
            duration_months: Длительность подписки
            amount_usd: Сумма в USD
            order_description: Описание заказа
            pay_currency: Валюта для оплаты (опционально, если None - пользователь выбирает сам)

        Returns:
            Словарь с данными invoice: {
                "invoice_id": 123456789,
                "invoice_url": "https://nowpayments.io/payment/...",
                "order_id": "syntra_...",
                "price_amount": 4.99,
                "price_currency": "usd",
                "created_at": "2025-01-26T12:00:00Z",
                "db_payment_id": 1
            }
        """
        if not self.enabled:
            logger.error("❌ NOWPayments не инициализирован")
            return None

        try:
            # Генерируем order_id
            timestamp = int(datetime.now(UTC).timestamp())
            order_id = f"syntra_{user_id}_{tier.value}_{duration_months}m_{timestamp}"

            # Описание заказа
            if not order_description:
                tier_names = {
                    SubscriptionTier.BASIC: "Basic",
                    SubscriptionTier.PREMIUM: "Premium",
                    SubscriptionTier.VIP: "VIP"
                }
                duration_text = f"{duration_months} month" if duration_months == 1 else f"{duration_months} months"
                order_description = f"Syntra AI {tier_names[tier]} - {duration_text}"

            # Webhook URL
            webapp_url = os.getenv("WEBAPP_URL", "https://ai.syntratrade.xyz")
            ipn_callback_url = f"{webapp_url}/api/webhooks/nowpayments"
            success_url = f"{webapp_url}/payment/success"
            cancel_url = f"{webapp_url}/payment/cancel"

            # Payload для создания invoice
            payload = {
                "price_amount": float(amount_usd),
                "price_currency": "usd",
                "order_id": order_id,
                "order_description": order_description,
                "ipn_callback_url": ipn_callback_url,
                "success_url": success_url,
                "cancel_url": cancel_url,
            }

            # Если указана валюта для оплаты
            if pay_currency:
                payload["pay_currency"] = pay_currency.lower()

            # Создаем invoice через API
            url = f"{self.base_url}/invoice"
            response = requests.post(
                url,
                headers=self._get_headers(),
                data=json.dumps(payload)
            )
            response.raise_for_status()

            invoice_data = response.json()

            # Сохраняем платеж в БД
            payment = Payment(
                user_id=user_id,
                provider=PaymentProvider.NOWPAYMENTS,
                amount=amount_usd,
                currency="USD",
                status=PaymentStatus.PENDING,
                tier=tier.value,
                duration_months=duration_months,
                provider_payment_id=str(invoice_data["id"]),
                provider_data=json.dumps({
                    "invoice_id": invoice_data["id"],
                    "token_id": invoice_data.get("token_id"),
                    "order_id": order_id,
                    "invoice_url": invoice_data.get("invoice_url"),
                    "pay_currency": invoice_data.get("pay_currency"),
                    "created_at": invoice_data.get("created_at"),
                }),
            )

            session.add(payment)
            await session.commit()
            await session.refresh(payment)

            logger.info(
                f"✅ NOWPayments invoice создан: user={user_id}, tier={tier.value}, "
                f"amount=${amount_usd}, invoice_id={invoice_data['id']}"
            )

            return {
                "invoice_id": invoice_data["id"],
                "invoice_url": invoice_data["invoice_url"],
                "order_id": order_id,
                "price_amount": float(amount_usd),
                "price_currency": "usd",
                "pay_currency": invoice_data.get("pay_currency"),
                "created_at": invoice_data.get("created_at"),
                "db_payment_id": payment.id,
            }

        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP ошибка создания invoice: {e.response.status_code} - {e.response.text}")
            await session.rollback()
            return None
        except Exception as e:
            logger.exception(f"❌ Ошибка создания NOWPayments invoice: {e}")
            await session.rollback()
            return None

    async def get_payment_status(
        self,
        payment_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Проверить статус платежа

        Payment статусы:
        - waiting: Ожидание оплаты от клиента
        - confirming: Транзакция обрабатывается на блокчейне
        - confirmed: Подтверждено блокчейном
        - sending: Средства отправляются на ваш кошелек
        - partially_paid: Клиент заплатил меньше чем нужно
        - finished: Платеж завершен успешно
        - failed: Ошибка платежа
        - refunded: Средства возвращены
        - expired: Истек срок оплаты (7 дней)

        Args:
            payment_id: ID платежа в NOWPayments

        Returns:
            Словарь со статусом платежа
        """
        if not self.enabled:
            return None

        try:
            url = f"{self.base_url}/payment/{payment_id}"
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()

            data = response.json()

            logger.info(
                f"📊 NOWPayments статус: payment_id={payment_id}, "
                f"status={data.get('payment_status')}"
            )

            return data

        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP ошибка проверки статуса: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка проверки статуса платежа: {e}")
            return None

    def verify_ipn_signature(
        self,
        request_body: bytes,
        signature: str
    ) -> bool:
        """
        Верифицировать IPN webhook signature (HMAC-SHA512)

        Args:
            request_body: Raw request body (bytes)
            signature: Signature from x-nowpayments-sig header

        Returns:
            True если signature валидна
        """
        if not self.ipn_secret:
            logger.warning("⚠️ NOWPAYMENTS_IPN_SECRET не настроен!")
            return False

        try:
            # Вычисляем HMAC-SHA512
            expected_signature = hmac.new(
                self.ipn_secret.encode(),
                request_body,
                hashlib.sha512
            ).hexdigest()

            # Constant-time comparison
            is_valid = hmac.compare_digest(signature, expected_signature)

            if not is_valid:
                logger.warning("❌ Invalid IPN signature")

            return is_valid

        except Exception as e:
            logger.error(f"❌ Ошибка верификации signature: {e}")
            return False

    async def process_ipn_callback(
        self,
        session: AsyncSession,
        ipn_data: Dict[str, Any]
    ) -> bool:
        """
        Обработать IPN callback от NOWPayments

        IPN статусы:
        - waiting: Ожидание оплаты
        - confirming: Подтверждение транзакции
        - confirmed: Транзакция подтверждена
        - sending: Отправка на outcome wallet
        - finished: Платеж завершен ✅
        - failed: Платеж не удался ❌
        - refunded: Возврат средств
        - expired: Истек срок платежа
        - partially_paid: Частичная оплата

        Args:
            session: Database session
            ipn_data: IPN данные от NOWPayments

        Returns:
            True если успешно обработан
        """
        try:
            payment_id = ipn_data.get("payment_id")
            payment_status = ipn_data.get("payment_status")
            order_id = ipn_data.get("order_id")
            invoice_id = ipn_data.get("invoice_id")

            logger.info(
                f"📨 IPN callback: payment_id={payment_id}, "
                f"invoice_id={invoice_id}, status={payment_status}"
            )

            # Находим платеж в БД по invoice_id
            result = await session.execute(
                select(Payment).where(
                    Payment.provider_payment_id == str(invoice_id)
                )
            )
            payment = result.scalar_one_or_none()

            if not payment:
                logger.warning(f"⚠️ Платеж не найден: invoice_id={invoice_id}")
                return False

            # Обновляем статус в зависимости от payment_status
            if payment_status == "finished":
                # Платеж завершен успешно
                payment.status = PaymentStatus.COMPLETED
                payment.completed_at = datetime.now(UTC)

                # Активируем подписку
                from src.database.crud import activate_subscription
                await activate_subscription(
                    session,
                    payment.user_id,
                    SubscriptionTier(payment.tier),
                    payment.duration_months
                )

                logger.success(
                    f"✅ NOWPayments платеж завершен: user={payment.user_id}, "
                    f"tier={payment.tier}, invoice_id={invoice_id}"
                )

                # 💎 Award bonus points for subscription purchase
                try:
                    from src.services.points_service import PointsService
                    from src.database.models import PointsTransactionType
                    from config.points_config import get_subscription_bonus

                    bonus_points = get_subscription_bonus(payment.tier, payment.duration_months)
                    if bonus_points > 0:
                        points_transaction = await PointsService.earn_points(
                            session=session,
                            user_id=payment.user_id,
                            transaction_type=PointsTransactionType.EARN_SUBSCRIPTION,
                            amount=bonus_points,
                            description=f"Бонус за покупку подписки {payment.tier.upper()} ({payment.duration_months} мес.)",
                            metadata={
                                "tier": payment.tier,
                                "duration_months": payment.duration_months,
                                "payment_id": payment.id,
                                "invoice_id": invoice_id,
                                "payment_provider": "nowpayments",
                                "amount_usd": payment.amount,
                                "pay_currency": ipn_data.get("pay_currency"),
                            },
                            transaction_id=f"sub_bonus:{payment.user_id}:{payment.id}",
                        )
                        if points_transaction:
                            logger.info(
                                f"💎 Awarded {bonus_points} bonus points to user {payment.user_id} "
                                f"for subscription purchase (balance: {points_transaction.balance_after})"
                            )
                except Exception as points_error:
                    # Don't fail payment if points fail
                    logger.error(f"Failed to award subscription bonus points: {points_error}")

            elif payment_status in ["failed", "expired", "refunded"]:
                # Платеж не удался
                payment.status = PaymentStatus.FAILED
                logger.warning(
                    f"⚠️ Платеж не удался: invoice_id={invoice_id}, "
                    f"status={payment_status}"
                )

            elif payment_status == "partially_paid":
                # Частичная оплата
                logger.warning(
                    f"⚠️ Частичная оплата: invoice_id={invoice_id}, "
                    f"paid={ipn_data.get('actually_paid')} {ipn_data.get('pay_currency')}"
                )

            else:
                # Промежуточные статусы (waiting, confirming, confirmed, sending)
                logger.info(f"📊 Промежуточный статус: {payment_status}")

            # Обновляем provider_data с IPN данными
            try:
                provider_data = json.loads(payment.provider_data) if payment.provider_data else {}
            except json.JSONDecodeError:
                provider_data = {}

            provider_data["ipn_data"] = ipn_data
            provider_data["last_status_update"] = datetime.now(UTC).isoformat()
            provider_data["payment_status"] = payment_status
            payment.provider_data = json.dumps(provider_data)

            await session.commit()

            return True

        except Exception as e:
            logger.exception(f"❌ Ошибка обработки IPN callback: {e}")
            await session.rollback()
            return False


# Глобальный singleton
_nowpayments_service: Optional[NOWPaymentsService] = None


def get_nowpayments_service() -> NOWPaymentsService:
    """Получить глобальный экземпляр NOWPaymentsService (синглтон)"""
    global _nowpayments_service

    if _nowpayments_service is None:
        _nowpayments_service = NOWPaymentsService()

    return _nowpayments_service
