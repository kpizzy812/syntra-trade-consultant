# 💎 Premium Subscription System - Architecture

**Дата создания:** 2025-11-17
**Статус:** 🔄 В разработке
**Версия:** 1.0

---

## 📋 ОБЗОР

Система Premium подписок для Syntra Trade Consultant с целью **генерации трафика в экосистему**.

### Стратегия
- ❌ НЕ монетизация (низкая маржа 34%)
- ✅ Генерация трафика
- ✅ Привлечение активных пользователей
- ✅ Перелив в экосистему

---

## 💰 ТАРИФНЫЕ ПЛАНЫ

### Pricing Matrix

| Тариф | Лимит | Месяц | Квартал (-15%) | Год (-25%) | Маржа |
|-------|-------|-------|----------------|------------|-------|
| **FREE** | 5/день | $0 | $0 | $0 | -$0.83 (loss-leader) |
| **BASIC** | 20/день | $4.99 | $4.24/мес ($12.72) | $3.74/мес ($44.88) | 34% |
| **PREMIUM** | 100/день | $24.99 | $21.24/мес ($63.72) | $18.74/мес ($224.88) | 34% |
| **VIP** | ∞ Безлимит | $49.99 | $42.49/мес ($127.47) | $37.49/мес ($449.88) | 34% |

### Себестоимость

| Тариф | Запросов/месяц | AI Cost | Инфра | Итого |
|-------|----------------|---------|-------|-------|
| FREE | 150 | $0.75 | $0.08 | $0.83 |
| BASIC | 600 | $3.00 | $0.30 | $3.30 |
| PREMIUM | 3000 | $15.00 | $1.50 | $16.50 |
| VIP | ~6000 | $30.00 | $3.00 | $33.00 |

---

## 🏗️ АРХИТЕКТУРА БД

### 1. Enum: SubscriptionTier

```python
from enum import Enum

class SubscriptionTier(str, Enum):
    """Subscription tier levels"""
    FREE = "free"           # 5 requests/day
    BASIC = "basic"         # 20 requests/day
    PREMIUM = "premium"     # 100 requests/day
    VIP = "vip"            # Unlimited
```

### 2. Model: Subscription

```python
class Subscription(Base):
    """
    User subscription model

    Tracks:
    - Current tier (FREE/BASIC/PREMIUM/VIP)
    - Subscription period (start/end dates)
    - Auto-renewal status
    - Trial status
    """
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,  # One subscription per user
        index=True
    )

    # Subscription tier
    tier: Mapped[str] = mapped_column(
        String(20),
        default=SubscriptionTier.FREE,
        nullable=False,
        index=True,
        comment="Subscription tier: free, basic, premium, vip"
    )

    # Subscription period
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="Subscription start date"
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Subscription expiration date (NULL for FREE)"
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Is subscription currently active"
    )

    auto_renew: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Auto-renew subscription"
    )

    # Trial
    is_trial: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Is this a trial subscription"
    )

    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Trial end date"
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="subscription")
    payments = relationship("Payment", back_populates="subscription", cascade="all, delete-orphan")
```

### 3. Model: Payment

```python
class PaymentStatus(str, Enum):
    """Payment status"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"

class PaymentProvider(str, Enum):
    """Payment providers"""
    TELEGRAM_STARS = "telegram_stars"
    TON_CONNECT = "ton_connect"
    CRYPTO_BOT = "crypto_bot"

class Payment(Base):
    """
    Payment transactions model

    Tracks all payment transactions for subscriptions
    """
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Relations
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    subscription_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )

    # Payment details
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Payment provider: telegram_stars, ton_connect, crypto_bot"
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=PaymentStatus.PENDING,
        nullable=False,
        index=True,
        comment="Payment status"
    )

    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Payment amount in USD"
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="USD",
        nullable=False,
        comment="Currency: USD, STARS, TON, USDT"
    )

    # Subscription details
    tier: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Purchased tier"
    )

    duration_months: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Subscription duration in months (1, 3, 12)"
    )

    # Provider-specific data
    provider_payment_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="External payment ID from provider"
    )

    provider_data: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional provider data (JSON)"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Payment completion timestamp"
    )

    # Relationships
    user = relationship("User", back_populates="payments")
    subscription = relationship("Subscription", back_populates="payments")
```

### 4. Update: User Model

```python
# Add to User model:

# Relationships
subscription = relationship(
    "Subscription",
    back_populates="user",
    uselist=False,  # One-to-one
    cascade="all, delete-orphan"
)

payments = relationship(
    "Payment",
    back_populates="user",
    cascade="all, delete-orphan"
)

# Helper method
def get_request_limit(self) -> int:
    """Get user's daily request limit based on subscription tier"""
    if not self.subscription or not self.subscription.is_active:
        return 5  # FREE tier

    tier_limits = {
        SubscriptionTier.FREE: 5,
        SubscriptionTier.BASIC: 20,
        SubscriptionTier.PREMIUM: 100,
        SubscriptionTier.VIP: 999999  # Unlimited (practical limit)
    }

    return tier_limits.get(self.subscription.tier, 5)
```

---

## 🔧 ОПТИМИЗАЦИИ

### 1. Cached System Prompts

**Экономия:** 50% на input токенах system prompt (~1000 tokens)

```python
# openai_service.py

from openai import AsyncOpenAI

async def chat_with_caching(
    client: AsyncOpenAI,
    messages: list,
    model: str = "gpt-4o-mini"
):
    """
    Use prompt caching for system messages

    OpenAI automatically caches prompts > 1024 tokens
    that appear in the first system message
    """
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        # OpenAI auto-caches system messages > 1024 tokens
    )
    return response
```

**Требования:**
- System prompt должен быть первым сообщением
- Длина > 1024 токенов для кэширования
- Кэш живет 5-10 минут
- Экономия: input_tokens × 50%

**Текущий system prompt:** ~1500 токенов ✅
**Экономия на запрос:** ~$0.001 (20% от себестоимости)

### 2. Batch API для Retention

**Экономия:** 75% на retention рассылки

```python
# retention_service.py

async def send_retention_batch(users: List[User], message: str):
    """
    Send retention messages via Batch API

    Batch API pricing:
    - GPT-4o: $0.625 input (vs $2.50) = 75% cheaper
    - GPT-4o-mini: $0.075 input (vs $0.15) = 50% cheaper
    """

    # Create batch job
    batch_file = await client.files.create(
        file=batch_requests_file,
        purpose="batch"
    )

    batch = await client.batches.create(
        input_file_id=batch_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h"  # Process within 24h
    )

    return batch.id
```

**Use cases:**
- Retention рассылки (не срочные)
- Еженедельные дайджесты
- Персонализированные рекомендации

---

## 💳 PAYMENT INTEGRATION

### 1. Telegram Stars ⭐ (Priority #1)

**Преимущества:**
- ✅ Нативная интеграция в Telegram
- ✅ Низкая комиссия (~3-5%)
- ✅ Мгновенная обработка
- ✅ Не требует KYC

**Integration:**
```python
from aiogram import Bot
from aiogram.types import LabeledPrice

async def create_invoice(
    bot: Bot,
    chat_id: int,
    tier: str,
    duration_months: int
):
    """Create payment invoice"""

    prices = {
        ("basic", 1): 499,      # $4.99 = 499 Stars
        ("basic", 3): 1272,     # $12.72 = 1272 Stars
        ("basic", 12): 4488,    # $44.88 = 4488 Stars
        ("premium", 1): 2499,
        ("premium", 3): 6372,
        ("premium", 12): 22488,
        ("vip", 1): 4999,
        ("vip", 3): 12747,
        ("vip", 12): 44988,
    }

    price = prices.get((tier, duration_months))

    await bot.send_invoice(
        chat_id=chat_id,
        title=f"Syntra {tier.upper()} - {duration_months} мес",
        description=f"Premium подписка {tier.upper()}",
        payload=f"subscription_{tier}_{duration_months}",
        provider_token="",  # Empty for Stars
        currency="XTR",  # Telegram Stars
        prices=[LabeledPrice(label="Подписка", amount=price)],
        start_parameter=f"subscribe_{tier}"
    )
```

### 2. TON Connect 🔷 (Priority #2)

**Преимущества:**
- ✅ Прямые крипто-платежи (USDT/TON)
- ✅ Низкая комиссия (<1%)
- ✅ Web3 интеграция
- ✅ Decentralized

**Integration:**
```python
# Использовать библиотеку pytonconnect
from pytonconnect import TonConnect

async def create_ton_payment(
    user_id: int,
    amount_usdt: float,
    tier: str
):
    """Create TON Connect payment"""

    connector = TonConnect(manifest_url="https://your-app.com/tonconnect-manifest.json")

    # Generate payment request
    payment_request = {
        "to": "EQC...your_wallet",  # Your TON wallet
        "amount": amount_usdt * 1_000_000,  # Convert to nanotons
        "payload": f"subscription_{user_id}_{tier}"
    }

    return payment_request
```

### 3. CryptoBot 🤖 (Priority #3, Optional)

**Преимущества:**
- ✅ Простая интеграция
- ✅ Поддержка BTC, ETH, USDT, TON
- ✅ Webhook notifications

---

## 🔄 SUBSCRIPTION LIFECYCLE

### State Machine

```
┌──────────────────────────────────────────────────────┐
│                  SUBSCRIPTION STATES                  │
├──────────────────────────────────────────────────────┤
│                                                       │
│  [FREE] ──────────────────────────────────────────┐  │
│    │                                              │  │
│    │ Payment Success                              │  │
│    ↓                                              │  │
│  [ACTIVE PAID] ───→ [EXPIRING SOON] ───→ [EXPIRED]│  │
│    │                 (7 days left)         │      │  │
│    │                                       │      │  │
│    │ Auto-renew                            │      │  │
│    └───────────────────────────────────────┘      │  │
│                                                    │  │
│  [CANCELLED] ──────────────────────────────────────┤  │
│                                                       │
└──────────────────────────────────────────────────────┘
```

### Cron Jobs

```python
# subscription_cron.py

import asyncio
from datetime import datetime, timedelta

async def check_expiring_subscriptions():
    """
    Run daily: Check for expiring subscriptions
    Send notifications 7, 3, 1 days before expiry
    """
    now = datetime.now(UTC)

    # Expiring in 7 days
    expiring_7d = await get_subscriptions_expiring_in(days=7)
    for sub in expiring_7d:
        await send_expiry_notification(sub.user_id, days_left=7)

    # Expiring in 3 days
    expiring_3d = await get_subscriptions_expiring_in(days=3)
    for sub in expiring_3d:
        await send_expiry_notification(sub.user_id, days_left=3)

    # Expiring in 1 day
    expiring_1d = await get_subscriptions_expiring_in(days=1)
    for sub in expiring_1d:
        await send_expiry_notification(sub.user_id, days_left=1)


async def process_expired_subscriptions():
    """
    Run daily: Process expired subscriptions
    """
    now = datetime.now(UTC)
    expired = await get_expired_subscriptions()

    for sub in expired:
        if sub.auto_renew:
            # Try to renew
            await attempt_renewal(sub)
        else:
            # Downgrade to FREE
            await downgrade_to_free(sub)


async def auto_renew_subscriptions():
    """
    Run daily: Auto-renew subscriptions
    """
    renewing = await get_auto_renewing_subscriptions()

    for sub in renewing:
        try:
            # Charge payment method
            payment = await process_renewal_payment(sub)

            if payment.status == PaymentStatus.COMPLETED:
                # Extend subscription
                await extend_subscription(sub, months=sub.duration_months)
        except Exception as e:
            logger.error(f"Auto-renew failed for {sub.id}: {e}")
            await notify_renewal_failure(sub.user_id)
```

---

## 🛡️ MIDDLEWARE UPDATES

### 1. Update: request_limit.py

```python
async def check_subscription_limit(user: User, session: AsyncSession) -> bool:
    """
    Check if user can make request based on subscription tier

    Returns:
        True if user can make request
        False if limit exceeded
    """

    # Get user's daily limit based on tier
    daily_limit = user.get_request_limit()

    # VIP = unlimited
    if user.subscription and user.subscription.tier == SubscriptionTier.VIP:
        return True

    # Check today's usage
    today = date.today()
    limit_record = await get_or_create_request_limit(session, user.id, today)

    if limit_record.count >= daily_limit:
        return False

    return True
```

### 2. New: subscription_checker.py

```python
class SubscriptionMiddleware(BaseMiddleware):
    """
    Middleware to check subscription status

    - Blocks expired subscriptions
    - Notifies about expiring subscriptions
    - Updates subscription status
    """

    async def __call__(self, handler, event, data):
        user: User = data.get("user")

        if not user or not user.subscription:
            return await handler(event, data)

        sub = user.subscription

        # Check if expired
        if sub.expires_at and sub.expires_at < datetime.now(UTC):
            if sub.is_active:
                # Downgrade to FREE
                await downgrade_to_free(sub)
                await event.answer(
                    "⚠️ Ваша подписка истекла. Вы переведены на FREE тариф.\n"
                    "Продлите подписку: /premium"
                )

        # Check if expiring soon (7 days)
        elif sub.expires_at and (sub.expires_at - datetime.now(UTC)).days <= 7:
            days_left = (sub.expires_at - datetime.now(UTC)).days
            # Show notification once per day
            # (implement with cache or DB flag)
            pass

        return await handler(event, data)
```

---

## 📱 USER INTERFACE

### Commands

```python
# /premium - Show subscription info and upgrade options
# /subscribe [tier] [duration] - Subscribe to tier
# /cancel_subscription - Cancel auto-renewal
# /subscription_status - Check current subscription
```

### Inline Keyboard Layout

```
┌─────────────────────────────────────────┐
│         💎 Выберите тариф               │
├─────────────────────────────────────────┤
│  🆓 FREE    - 5 запросов/день          │
│  [Текущий тариф]                        │
├─────────────────────────────────────────┤
│  ⭐ BASIC   - 20 запросов/день         │
│  $4.99/мес  $4.24/мес (3м)  $3.74 (год) │
│  [Выбрать BASIC]                        │
├─────────────────────────────────────────┤
│  💎 PREMIUM - 100 запросов/день        │
│  $24.99/мес $21.24/мес (3м) $18.74(год) │
│  [Выбрать PREMIUM]                      │
├─────────────────────────────────────────┤
│  👑 VIP     - Безлимит ∞               │
│  $49.99/мес $42.49/мес (3м) $37.49(год) │
│  [Выбрать VIP]                          │
└─────────────────────────────────────────┘

После выбора тарифа:
┌─────────────────────────────────────────┐
│    Выбран: PREMIUM ($24.99/мес)         │
├─────────────────────────────────────────┤
│  Выберите длительность:                 │
│  ○ 1 месяц  - $24.99                   │
│  ○ 3 месяца - $63.72 (скидка 15%)     │
│  ○ 12 месяцев - $224.88 (скидка 25%)  │
├─────────────────────────────────────────┤
│  Способ оплаты:                         │
│  ⭐ Telegram Stars                      │
│  🔷 TON/USDT (TON Connect)             │
└─────────────────────────────────────────┘
```

---

## 🧪 TESTING CHECKLIST

- [ ] Subscription creation (all tiers)
- [ ] Payment flow (Stars + TON Connect)
- [ ] Subscription upgrade/downgrade
- [ ] Subscription expiry handling
- [ ] Auto-renewal logic
- [ ] Request limits per tier
- [ ] Cron jobs (expiry notifications, renewals)
- [ ] Refund handling
- [ ] Edge cases (concurrent payments, race conditions)

---

## 📊 METRICS & ANALYTICS

### KPIs to Track

1. **Conversion Funnel**
   - FREE → BASIC conversion rate
   - BASIC → PREMIUM upgrade rate
   - Trial → Paid conversion rate

2. **Revenue Metrics**
   - MRR (Monthly Recurring Revenue)
   - ARPU (Average Revenue Per User)
   - Churn rate
   - LTV (Lifetime Value)

3. **Engagement Metrics**
   - Requests per tier (average)
   - Feature usage by tier
   - Retention by tier

4. **Cost Metrics**
   - Cost per request (by tier)
   - Profit margin (by tier)
   - CAC (Customer Acquisition Cost)

---

## 🚀 DEPLOYMENT PLAN

### Phase 1: Core Implementation (Week 1-2)
- [x] Database models + migrations
- [ ] CRUD operations
- [ ] Middleware updates
- [ ] Basic UI (commands + keyboards)

### Phase 2: Payment Integration (Week 2-3)
- [ ] Telegram Stars integration
- [ ] TON Connect integration
- [ ] Payment webhooks
- [ ] Transaction logging

### Phase 3: Subscription Management (Week 3-4)
- [ ] Cron jobs (expiry, renewals)
- [ ] Auto-renewal logic
- [ ] Notification system
- [ ] Admin controls

### Phase 4: Optimization (Week 4+)
- [ ] Cached prompts implementation
- [ ] Batch API for retention
- [ ] Performance monitoring
- [ ] Analytics dashboard

---

## 📚 REFERENCES

- [OpenAI Pricing](https://openai.com/api/pricing/)
- [Telegram Stars Docs](https://core.telegram.org/bots/payments)
- [TON Connect](https://docs.ton.org/develop/dapps/ton-connect/overview)
- [OpenAI Prompt Caching](https://platform.openai.com/docs/guides/prompt-caching)
- [OpenAI Batch API](https://platform.openai.com/docs/guides/batch)

---

**Prepared by:** Claude Code
**Last updated:** 2025-11-17
