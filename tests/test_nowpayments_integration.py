"""
Тест интеграции NOWPayments

Проверяет:
1. Инициализацию сервиса
2. Создание invoice
3. Проверку статуса API
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.nowpayments_service import get_nowpayments_service
from src.database.engine import get_session
from src.database.models import SubscriptionTier, User
from sqlalchemy import select
from decimal import Decimal


async def test_nowpayments():
    """Тест NOWPayments интеграции"""

    print("🧪 Тестирование NOWPayments Integration\n")

    # 1. Проверка инициализации сервиса
    print("1️⃣ Инициализация сервиса...")
    service = get_nowpayments_service()

    if not service.enabled:
        print("❌ Сервис не инициализирован! Проверь NOWPAYMENTS_API_KEY в .env")
        return

    print(f"✅ Сервис инициализирован")
    print(f"   Base URL: {service.base_url}")
    print(f"   Sandbox: {service.is_sandbox}")
    print()

    # 2. Проверка статуса API
    print("2️⃣ Проверка статуса API...")
    api_status = await service.get_api_status()

    if api_status:
        print(f"✅ API доступен: {api_status.get('message')}")
    else:
        print("❌ API недоступен!")
        return
    print()

    # 3. Получение доступных валют
    print("3️⃣ Получение списка валют...")
    currencies = await service.get_available_currencies()

    if currencies:
        print(f"✅ Доступно валют: {len(currencies)}")
        # Если элементы - словари, извлекаем код валюты
        if currencies and isinstance(currencies[0], dict):
            currency_codes = [c.get('currency', c.get('code', str(c))).upper() for c in currencies[:10]]
            print(f"   Примеры: {', '.join(currency_codes)}")
        else:
            # Если просто строки
            print(f"   Примеры: {', '.join(str(c).upper() for c in currencies[:10])}")
    else:
        print("⚠️ Не удалось получить список валют")
    print()

    # 4. Создание тестового invoice
    print("4️⃣ Создание тестового invoice...")

    # Получаем первого пользователя из БД для теста
    async for session in get_session():
        result = await session.execute(select(User).limit(1))
        user = result.scalar_one_or_none()

        if not user:
            print("❌ Нет пользователей в БД для теста!")
            print("   Сначала запусти бота и зарегистрируйся")
            return

        print(f"   User: {user.id} (@{user.username or 'no username'})")

        # Создаем invoice
        invoice = await service.create_invoice(
            session=session,
            user_id=user.id,
            tier=SubscriptionTier.BASIC,
            duration_months=1,
            amount_usd=Decimal("4.99"),
            pay_currency="btc"  # BTC для теста
        )

        if invoice:
            print(f"✅ Invoice создан!")
            print(f"   Invoice ID: {invoice['invoice_id']}")
            print(f"   Invoice URL: {invoice['invoice_url']}")
            print(f"   Amount: ${invoice['price_amount']} USD")
            print(f"   Pay currency: {invoice.get('pay_currency', 'user choice')}")
            print()
            print(f"🌐 Открой URL для оплаты:")
            print(f"   {invoice['invoice_url']}")
        else:
            print("❌ Не удалось создать invoice!")

        break

    print()
    print("✅ Тест завершен!")


if __name__ == "__main__":
    asyncio.run(test_nowpayments())
