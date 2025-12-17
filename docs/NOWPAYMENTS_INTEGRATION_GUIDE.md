# NOWPayments - Пошаговая интеграция для Syntra AI

## Что нужно для подключения NOWPayments

### ✅ Требования

1. **Аккаунт NOWPayments** (регистрация бесплатна)
2. **Email для активации**
3. **Крипто-кошелек для вывода средств** (любой из 300+ поддерживаемых)
4. **Без KYC** для старта (верификация опциональна)
5. **Без минимального баланса**

### 💰 Комиссии

- **0.5%** - одна криптовалюта
- **1.0%** - конверсия между криптовалютами
- **Минимальная транзакция:** ~$1 (эквивалент 0.003 BTC)

---

## 📝 Шаг 1: Регистрация аккаунта

### 1.1 Создание аккаунта

1. Перейти на https://nowpayments.io/
2. Нажать **"Get started"** или **"Create account"**
3. Заполнить форму регистрации:
   - Email
   - Пароль (сильный!)
   - Принять условия

### 1.2 Активация

1. Проверить email
2. Кликнуть на ссылку активации
3. Войти в аккаунт

### 1.3 Настройка безопасности

1. **Включить 2FA** (обязательно!)
   - Dashboard → Security → Two-Factor Authentication
   - Использовать Google Authenticator или Authy

2. **Настроить Whitelist** (для вывода средств)
   - Dashboard → Security → Withdrawal Whitelist
   - Добавить адреса кошельков

---

## 🔑 Шаг 2: Получение API ключа

### 2.1 Создание API ключа

1. Войти в Dashboard: https://account.nowpayments.io/
2. Перейти в **Settings → API Keys**
3. Нажать **"Add new key"**
4. **Сохранить API ключ** (показывается только один раз!)

### 2.2 Sandbox для тестирования

1. Перейти на https://sandbox.nowpayments.io/
2. Зарегистрировать Sandbox аккаунт
3. Получить **Sandbox API Key**
4. Использовать для разработки

**ВАЖНО:** Sandbox и Production - это разные аккаунты!

---

## 💳 Шаг 3: Настройка кошелька для вывода

### 3.1 Добавление Outcome Wallet

1. Dashboard → **Outcome Wallet**
2. Выбрать криптовалюту (например, USDT TRC20)
3. Ввести адрес кошелька
4. Сохранить

**Рекомендации:**
- **USDT TRC20** - низкие комиссии сети (~$1)
- **USDT ERC20** - высокие комиссии (~$10-50)
- **TON** - моментальные переводы, низкие комиссии

### 3.2 Автоматический вывод (опционально)

1. Dashboard → Settings → **Auto Withdrawal**
2. Включить автовывод
3. Настроить расписание (ежедневно/еженедельно)
4. Установить минимальную сумму

---

## 🐍 Шаг 4: Установка Python SDK

### 4.1 Установка пакета

```bash
# Активировать виртуальное окружение
source .venv/bin/activate

# Установить NOWPayments SDK
pip install nowpayment

# Или альтернативный пакет
pip install nowpayments-api
```

### 4.2 Добавление в requirements.txt

```txt
# requirements.txt
nowpayment>=1.0.0  # NOWPayments SDK
```

---

## 🔧 Шаг 5: Конфигурация в проекте

### 5.1 Добавить в .env

```bash
# .env

# NOWPayments API Configuration
NOWPAYMENTS_API_KEY=your_api_key_here
NOWPAYMENTS_IPN_SECRET=your_ipn_secret_here  # Для webhook безопасности
NOWPAYMENTS_SANDBOX=true  # false для production

# Outcome wallet (для получения средств)
NOWPAYMENTS_OUTCOME_WALLET=TYourUSDTTRC20AddressHere
```

### 5.2 Добавить в .env.example

```bash
# .env.example

# NOWPayments API Configuration
# Get your API key from: https://account.nowpayments.io/
# Supports 300+ cryptocurrencies with 0.5% fee
NOWPAYMENTS_API_KEY=
NOWPAYMENTS_IPN_SECRET=
NOWPAYMENTS_SANDBOX=true
NOWPAYMENTS_OUTCOME_WALLET=
```

---

## 💻 Шаг 6: Создание сервиса

### 6.1 Создать файл сервиса

```python
# src/services/nowpayments_service.py
"""
NOWPayments Service для Syntra AI

Функционал:
- Создание платежей в 300+ криптовалютах
- Автоконверсия в фиат
- Webhook обработка
- Invoice management
"""

import os
import hmac
import hashlib
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta, UTC

from nowpayment import NowPayments
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
    """

    def __init__(self):
        """Инициализация NOWPayments client"""
        self.api_key = os.getenv("NOWPAYMENTS_API_KEY", "")
        self.ipn_secret = os.getenv("NOWPAYMENTS_IPN_SECRET", "")
        self.is_sandbox = os.getenv("NOWPAYMENTS_SANDBOX", "true").lower() == "true"

        if not self.api_key:
            logger.warning("⚠️ NOWPAYMENTS_API_KEY не настроен!")
            self.client = None
            return

        # Инициализируем клиент
        self.client = NowPayments(self.api_key)

        network = "Sandbox" if self.is_sandbox else "Production"
        logger.info(f"✅ NOWPaymentsService инициализирован ({network})")

    async def get_available_currencies(self) -> list[str]:
        """
        Получить список доступных криптовалют

        Returns:
            Список тикеров валют (например: ['BTC', 'ETH', 'USDT', ...])
        """
        if not self.client:
            return []

        try:
            currencies = self.client.currency.get_available_currencies()
            logger.info(f"✅ Получено {len(currencies)} валют")
            return currencies
        except Exception as e:
            logger.error(f"❌ Ошибка получения валют: {e}")
            return []

    async def estimate_price(
        self,
        amount_usd: float,
        currency_from: str = "usd",
        currency_to: str = "btc"
    ) -> Optional[Dict[str, Any]]:
        """
        Получить оценку стоимости для конвертации

        Args:
            amount_usd: Сумма в USD
            currency_from: Исходная валюта (default: usd)
            currency_to: Целевая валюта (default: btc)

        Returns:
            Словарь с оценкой: {
                "currency_from": "usd",
                "amount_from": 100.0,
                "currency_to": "btc",
                "estimated_amount": 0.00234
            }
        """
        if not self.client:
            return None

        try:
            estimate = self.client.currency.get_estimate(
                amount=amount_usd,
                currency_from=currency_from,
                currency_to=currency_to
            )

            logger.info(
                f"💱 Оценка: {amount_usd} {currency_from.upper()} = "
                f"{estimate['estimated_amount']} {currency_to.upper()}"
            )

            return estimate

        except Exception as e:
            logger.error(f"❌ Ошибка оценки цены: {e}")
            return None

    async def create_payment(
        self,
        session: AsyncSession,
        user_id: int,
        tier: SubscriptionTier,
        duration_months: int,
        amount_usd: Decimal,
        pay_currency: str = "btc",
        order_description: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Создать платеж через NOWPayments

        Args:
            session: Database session
            user_id: ID пользователя
            tier: Subscription tier
            duration_months: Длительность подписки
            amount_usd: Сумма в USD
            pay_currency: Валюта для оплаты (btc, eth, usdt и т.д.)
            order_description: Описание заказа

        Returns:
            Словарь с данными платежа: {
                "payment_id": "123456789",
                "payment_url": "https://nowpayments.io/payment/...",
                "pay_address": "bc1q...",
                "pay_amount": 0.00234,
                "pay_currency": "btc",
                "price_amount": 100.0,
                "price_currency": "usd",
                "expires_at": "2025-01-26T12:00:00Z"
            }
        """
        if not self.client:
            logger.error("❌ NOWPayments client не инициализирован")
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

            # Создаем платеж через SDK
            payment_response = self.client.payment.create_payment(
                price_amount=float(amount_usd),
                price_currency="usd",
                pay_currency=pay_currency.lower(),
                order_id=order_id,
                order_description=order_description,
                ipn_callback_url=f"{os.getenv('WEBAPP_URL', '')}/api/webhooks/nowpayments",  # Webhook URL
                success_url=f"{os.getenv('WEBAPP_URL', '')}/payment/success",
                cancel_url=f"{os.getenv('WEBAPP_URL', '')}/payment/cancel",
            )

            # Сохраняем платеж в БД
            payment = Payment(
                user_id=user_id,
                provider=PaymentProvider.NOWPAYMENTS,  # Добавим в enum
                amount=amount_usd,
                currency="USD",
                status=PaymentStatus.PENDING,
                tier=tier.value,
                duration_months=duration_months,
                provider_payment_id=str(payment_response["payment_id"]),
                provider_data={
                    "order_id": order_id,
                    "pay_address": payment_response.get("pay_address"),
                    "pay_amount": payment_response.get("pay_amount"),
                    "pay_currency": pay_currency,
                    "payment_url": payment_response.get("payment_url"),
                    "expires_at": payment_response.get("expiration_estimate_date"),
                },
            )

            session.add(payment)
            await session.commit()
            await session.refresh(payment)

            logger.info(
                f"✅ NOWPayments платеж создан: user={user_id}, tier={tier.value}, "
                f"amount=${amount_usd}, pay_currency={pay_currency}, "
                f"payment_id={payment_response['payment_id']}"
            )

            return {
                "payment_id": payment_response["payment_id"],
                "payment_url": payment_response.get("payment_url"),
                "pay_address": payment_response.get("pay_address"),
                "pay_amount": payment_response.get("pay_amount"),
                "pay_currency": pay_currency,
                "price_amount": float(amount_usd),
                "price_currency": "usd",
                "expires_at": payment_response.get("expiration_estimate_date"),
                "db_payment_id": payment.id,
            }

        except Exception as e:
            logger.exception(f"❌ Ошибка создания NOWPayments платежа: {e}")
            await session.rollback()
            return None

    async def create_invoice(
        self,
        session: AsyncSession,
        user_id: int,
        tier: SubscriptionTier,
        duration_months: int,
        amount_usd: Decimal,
        order_description: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Создать invoice (пользователь выбирает валюту сам)

        Отличие от create_payment:
        - Invoice: пользователь выбирает валюту на странице NOWPayments
        - Payment: валюта зафиксирована заранее

        Args:
            session: Database session
            user_id: ID пользователя
            tier: Subscription tier
            duration_months: Длительность подписки
            amount_usd: Сумма в USD
            order_description: Описание заказа

        Returns:
            Словарь с данными invoice: {
                "invoice_id": "123456789",
                "invoice_url": "https://nowpayments.io/payment/...",
                "price_amount": 100.0,
                "price_currency": "usd",
                "expires_at": "2025-01-26T12:00:00Z"
            }
        """
        if not self.client:
            logger.error("❌ NOWPayments client не инициализирован")
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

            # Создаем invoice через SDK
            invoice_response = self.client.payment.create_invoice(
                price_amount=float(amount_usd),
                price_currency="usd",
                order_id=order_id,
                order_description=order_description,
                ipn_callback_url=f"{os.getenv('WEBAPP_URL', '')}/api/webhooks/nowpayments",
                success_url=f"{os.getenv('WEBAPP_URL', '')}/payment/success",
                cancel_url=f"{os.getenv('WEBAPP_URL', '')}/payment/cancel",
            )

            # Сохраняем платеж в БД
            payment = Payment(
                user_id=user_id,
                provider=PaymentProvider.NOWPAYMENTS,
                amount=amount_usd,
                currency="USD",
                status=PaymentStatus.PENDING,
                tier=tier.value,
                duration_months=duration_months,
                provider_payment_id=str(invoice_response["id"]),
                provider_data={
                    "order_id": order_id,
                    "invoice_url": invoice_response.get("invoice_url"),
                    "expires_at": invoice_response.get("created_at"),  # Invoice обычно не истекает
                },
            )

            session.add(payment)
            await session.commit()
            await session.refresh(payment)

            logger.info(
                f"✅ NOWPayments invoice создан: user={user_id}, tier={tier.value}, "
                f"amount=${amount_usd}, invoice_id={invoice_response['id']}"
            )

            return {
                "invoice_id": invoice_response["id"],
                "invoice_url": invoice_response.get("invoice_url"),
                "price_amount": float(amount_usd),
                "price_currency": "usd",
                "created_at": invoice_response.get("created_at"),
                "db_payment_id": payment.id,
            }

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

        Args:
            payment_id: NOWPayments payment ID

        Returns:
            Словарь со статусом платежа
        """
        if not self.client:
            return None

        try:
            status = self.client.payment.get_payment_status(payment_id)

            logger.info(f"📊 Статус платежа {payment_id}: {status.get('payment_status')}")

            return status

        except Exception as e:
            logger.error(f"❌ Ошибка проверки статуса платежа: {e}")
            return None

    def verify_ipn_signature(
        self,
        request_body: bytes,
        signature: str
    ) -> bool:
        """
        Верифицировать IPN webhook signature

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
        - finished: Платеж завершен
        - failed: Платеж не удался
        - refunded: Возврат средств
        - expired: Истек срок платежа

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

            logger.info(f"📨 IPN callback: payment_id={payment_id}, status={payment_status}")

            # Находим платеж в БД
            result = await session.execute(
                select(Payment).where(
                    Payment.provider_payment_id == str(payment_id)
                )
            )
            payment = result.scalar_one_or_none()

            if not payment:
                logger.warning(f"⚠️ Платеж не найден: payment_id={payment_id}")
                return False

            # Обновляем статус
            if payment_status == "finished":
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
                    f"✅ Платеж завершен: user={payment.user_id}, "
                    f"tier={payment.tier}, payment_id={payment_id}"
                )

            elif payment_status in ["failed", "expired", "refunded"]:
                payment.status = PaymentStatus.FAILED
                logger.warning(f"⚠️ Платеж не удался: payment_id={payment_id}, status={payment_status}")

            else:
                # Промежуточные статусы (waiting, confirming, confirmed, sending)
                logger.info(f"📊 Промежуточный статус: {payment_status}")

            # Обновляем metadata
            payment.provider_data["ipn_data"] = ipn_data
            payment.provider_data["last_status_update"] = datetime.now(UTC).isoformat()

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
```

---

## 🔔 Шаг 7: Настройка Webhooks (IPN)

### 7.1 Получить IPN Secret

1. Dashboard → Settings → **IPN Secret Key**
2. Скопировать ключ
3. Добавить в `.env` как `NOWPAYMENTS_IPN_SECRET`

### 7.2 Создать Webhook Endpoint

```python
# src/api/webhooks_nowpayments.py
"""
NOWPayments Webhook Handler
"""

from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.engine import get_session
from src.services.nowpayments_service import get_nowpayments_service
from loguru import logger


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/nowpayments")
async def nowpayments_ipn_callback(
    request: Request,
    session: AsyncSession = Depends(get_session),
    x_nowpayments_sig: str = Header(None),
):
    """
    IPN Callback от NOWPayments

    Вызывается при изменении статуса платежа:
    - waiting → confirming → confirmed → sending → finished

    Security: Верифицируем HMAC-SHA512 signature
    """
    try:
        # Читаем raw body
        body = await request.body()

        # Парсим JSON
        ipn_data = await request.json()

        # Верифицируем signature
        service = get_nowpayments_service()

        if not service.verify_ipn_signature(body, x_nowpayments_sig):
            logger.error("❌ Invalid IPN signature!")
            raise HTTPException(status_code=403, detail="Invalid signature")

        # Обрабатываем callback
        success = await service.process_ipn_callback(session, ipn_data)

        if success:
            return {"status": "ok"}
        else:
            raise HTTPException(status_code=400, detail="Failed to process IPN")

    except Exception as e:
        logger.exception(f"❌ Ошибка обработки IPN: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

### 7.3 Зарегистрировать роутер

```python
# src/api/router.py

from src.api import webhooks_nowpayments

# Добавить в роутер
app.include_router(webhooks_nowpayments.router, prefix="/api")
```

---

## 🚀 Шаг 8: Создание Payment API

```python
# src/api/payment.py

from src.services.nowpayments_service import get_nowpayments_service


@router.post("/nowpayments/create-invoice", response_model=PaymentResponse)
async def create_nowpayments_invoice(
    request: CreateNOWPaymentsInvoiceRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Создать NOWPayments invoice

    Пользователь выбирает валюту (из 300+) на странице оплаты
    """
    try:
        # Validate tier
        tier = SubscriptionTier(request.tier)

        # Validate duration
        if request.duration_months not in [1, 3, 12]:
            raise HTTPException(status_code=400, detail="Invalid duration")

        # Get plan price
        from src.services.telegram_stars_service import TelegramStarsService
        stars_service = TelegramStarsService()
        plan = stars_service.get_plan_details(tier, request.duration_months)
        amount_usd = Decimal(str(plan["usd"]))

        # Create invoice
        service = get_nowpayments_service()
        invoice = await service.create_invoice(
            session=session,
            user_id=user.id,
            tier=tier,
            duration_months=request.duration_months,
            amount_usd=amount_usd,
        )

        if not invoice:
            raise HTTPException(status_code=500, detail="Failed to create invoice")

        logger.info(
            f"✅ NOWPayments invoice: user={user.id}, tier={tier.value}, "
            f"amount=${amount_usd}, invoice_id={invoice['invoice_id']}"
        )

        return PaymentResponse(
            success=True,
            message="Invoice created successfully",
            data={
                "invoice_id": invoice["invoice_id"],
                "invoice_url": invoice["invoice_url"],
                "amount_usd": float(amount_usd),
                "tier": tier.value,
                "duration_months": request.duration_months,
            },
        )

    except Exception as e:
        logger.exception(f"❌ Error creating NOWPayments invoice: {e}")
        return PaymentResponse(
            success=False,
            message="Failed to create invoice",
            error=str(e)
        )
```

---

## ✅ Шаг 9: Тестирование

### 9.1 Sandbox тестирование

1. Использовать **Sandbox API Key**
2. Создать тестовый invoice
3. Открыть `invoice_url` в браузере
4. Выбрать тестовую криптовалюту
5. Использовать тестовый адрес для оплаты

### 9.2 Production проверка

1. Создать invoice с минимальной суммой ($1-2)
2. Оплатить реальной криптовалютой
3. Проверить webhook callbacks
4. Проверить активацию подписки

---

## 📊 Мониторинг и логи

### Dashboard

- https://account.nowpayments.io/payments - все платежи
- https://account.nowpayments.io/stats - статистика
- https://account.nowpayments.io/logs - IPN логи

### Логирование в коде

```python
# Логи для отладки
logger.info(f"✅ Invoice created: {invoice_id}")
logger.warning(f"⚠️ Payment status: {status}")
logger.error(f"❌ Payment failed: {error}")
logger.success(f"💰 Payment completed: ${amount}")
```

---

## 🔒 Безопасность

### Checklist

- ✅ **Включить 2FA** в аккаунте
- ✅ **Верифицировать IPN signature** (HMAC-SHA512)
- ✅ **Использовать Whitelist** для withdrawal адресов
- ✅ **Хранить API ключ в .env** (не в коде!)
- ✅ **Не логировать API ключи**
- ✅ **Проверять суммы платежей** (защита от манипуляций)

---

## 📚 Полезные ссылки

- **Dashboard:** https://account.nowpayments.io/
- **Sandbox:** https://sandbox.nowpayments.io/
- **API Docs:** https://documenter.getpostman.com/view/7907941/2s93JusNJt
- **Integration Guide:** https://nowpayments.io/blog/integration-guide
- **Support:** https://nowpayments.io/help

### Python SDK

- **PyPI:** https://pypi.org/project/nowpayment/
- **GitHub:** https://github.com/Ventura94/NOWPayments-Python-API
- **Alternative SDK:** https://github.com/NikolaiSch/NowPay-python

---

## ⏱ Временные рамки интеграции

| Этап | Время | Описание |
|------|-------|----------|
| Регистрация | 10 мин | Создание аккаунта + 2FA |
| API ключ | 5 мин | Получение ключа |
| Кошелек | 5 мин | Настройка outcome wallet |
| Код сервиса | 2-3 часа | Написание NOWPaymentsService |
| Webhook endpoint | 1 час | IPN callback обработка |
| API endpoints | 1-2 часа | Payment API |
| Тестирование | 2-3 часа | Sandbox + production тесты |
| **ИТОГО** | **1-2 дня** | Полная интеграция |

---

## 💡 Pro Tips

### 1. Используйте Invoice вместо Payment

**Invoice** (рекомендуется):
- Пользователь выбирает валюту сам
- Поддержка 300+ криптовалют
- Проще UX

**Payment** (фиксированная валюта):
- Валюта зафиксирована заранее
- Нужна оценка курса
- Сложнее UX

### 2. Автовывод средств

Настройте **Auto Withdrawal** для автоматического вывода на кошелек:
- Ежедневно или еженедельно
- Минимальная сумма: $10-50
- Избегайте накопления средств на NOWPayments

### 3. Multi-currency поддержка

Принимайте топ криптовалюты:
- **USDT TRC20** - низкие комиссии сети
- **TON** - для Telegram аудитории
- **BTC** - для Bitcoin-максималистов
- **ETH** - для Ethereum экосистемы

### 4. Фиатная конверсия

Используйте автоконверсию крипты в фиат:
- Защита от волатильности
- Стабильный доход
- Упрощенная бухгалтерия

---

## 🐛 Частые проблемы

### Проблема: "API key invalid"

**Решение:**
- Проверьте что используете правильный ключ (Sandbox vs Production)
- Убедитесь что ключ активен в Dashboard

### Проблема: "IPN signature verification failed"

**Решение:**
- Проверьте `NOWPAYMENTS_IPN_SECRET` в .env
- Используйте raw request body для signature
- Проверьте header: `x-nowpayments-sig`

### Проблема: "Minimum amount not met"

**Решение:**
- Минимум: ~$1 (0.003 BTC эквивалент)
- Увеличьте сумму платежа

---

## ✅ Готово!

Теперь у вас есть полная интеграция NOWPayments с:
- ✅ 300+ криптовалют + 75 фиатных валют
- ✅ Комиссия 0.5-1% (в 6 раз дешевле Stripe!)
- ✅ Webhook обработка
- ✅ Invoice management
- ✅ Глобальный охват (включая РФ)

**Следующий шаг:** Добавить российский процессинг (ЮКassa/CloudPayments) для фиатных платежей! 🚀
