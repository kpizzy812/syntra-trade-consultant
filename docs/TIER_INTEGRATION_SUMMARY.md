# 🚀 Tier Integration & Analytics Setup

**Дата**: 2025-01-25
**Статус**: ✅ Реализовано

## ✅ Что сделано за час:

### 1. ✅ Tier-Aware Model Routing

**Проблема**: FREE пользователи могли получить дорогой GPT-4o → утечка денег
**Решение**: Модель выбирается на основе tier + сложности запроса

**Изменения**:
- [src/services/openai_service.py:106-197](../src/services/openai_service.py#L106-L197) - `select_model()` теперь принимает `user_tier`
- [src/services/openai_service.py:255-292](../src/services/openai_service.py#L255-L292) - `stream_completion()` передает tier
- [src/api/chat.py:134-145](../src/api/chat.py#L134-L145) - API передает tier из user.subscription
- [src/bot/handlers/crypto.py:250-265](../src/bot/handlers/crypto.py#L250-L265) - Bot handlers передают tier

**Логика роутинга**:
```python
FREE/BASIC → ВСЕГДА gpt-4o-mini (дешевая модель)
PREMIUM/VIP → Smart routing:
  - Простой запрос → gpt-4o-mini
  - Сложный запрос → gpt-4o (дорогая)
```

**Экономия**: FREE tier больше НЕ может получить GPT-4o! 💰

---

### 2. ✅ Tier Gating для Killer Features

**Проблема**: Продвинутые фичи были доступны всем
**Решение**: Проверка tier перед выполнением инструментов

**Изменения**:
- [src/services/crypto_tools.py:1553-1602](../src/services/crypto_tools.py#L1553-L1602) - `check_tool_access()` + tier gating
- [src/services/openai_service.py:398](../src/services/openai_service.py#L398) - Передача tier в execute_tool()

**Feature Map**:
```
FREE:
  ✅ Базовая цена
  ✅ Базовые индикаторы (RSI, MACD, EMA)
  ✅ Новости
  ✅ Fear & Greed Index

BASIC+:
  ✅ Candlestick patterns
  ✅ Advanced indicators
  ✅ Funding rates

PREMIUM+:
  ✅ On-chain metrics
  ✅ Liquidation history
  ✅ Market cycle analysis
```

**UX**: Пользователи видят: "🔒 This feature requires PREMIUM+ subscription"

---

### 3. ✅ PostHog Product Analytics

**Проблема**: Летели вслепую - нет метрик конверсии и retention
**Решение**: PostHog интеграция с key events

**Изменения**:
- [requirements.txt:28](../requirements.txt#L28) - Добавлен `posthog`
- [src/services/posthog_service.py](../src/services/posthog_service.py) - Новый сервис (220 строк)
- [src/api/chat.py:19](../src/api/chat.py#L19) - Event tracking в AI requests
- [src/api/chat.py:80-84](../src/api/chat.py#L80-L84) - Tracking limit hits
- [src/api/payment.py:23](../src/api/payment.py#L23) - Tracking payments
- [src/api/payment.py:139-146](../src/api/payment.py#L139-L146) - Track payment started

**Tracked Events**:
- `user_registered` - новый пользователь
- `ai_request_sent` - AI запрос (с tier, model, cost, tokens)
- `limit_hit` - достижение лимита (с tier, type, count)
- `pricing_page_viewed` - просмотр цен
- `payment_started` - начало оплаты
- `subscription_purchased` - успешная покупка
- `feature_used` - использование фич

**Graceful Degradation**: Если PostHog не настроен, просто логирует warning

---

### 4. ✅ Simplified Payment Endpoints

**Проблема**: Два дублирующих endpoint'а `/status` и `/verify`
**Решение**: Удален `/verify`, оставлен только `/status/{payment_id}`

**Изменения**:
- [src/api/payment.py:372-373](../src/api/payment.py#L372-L373) - Удален `/verify` endpoint

**Результат**: Чище API, меньше путаницы

---

## 🚀 Установка и настройка

### Шаг 1: Установить зависимости

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Шаг 2: Настроить PostHog (опционально)

Создайте бесплатный аккаунт: https://posthog.com/signup

Добавьте в `.env`:
```bash
# PostHog Analytics (optional)
POSTHOG_API_KEY=phc_your_project_api_key_here
POSTHOG_HOST=https://app.posthog.com
```

**Без PostHog** бот работает нормально, просто без аналитики.

### Шаг 3: Проверить код

```bash
# Линтер
ruff check src/services/openai_service.py
ruff check src/services/crypto_tools.py
ruff check src/services/posthog_service.py
ruff check src/api/chat.py
ruff check src/api/payment.py
```

---

## 📊 Как это работает

### Пример 1: FREE пользователь делает запрос

```
1. User (tier=free): "глубокий анализ bitcoin"
2. OpenAI service → select_model(tier="free")
3. ✅ Возвращает: "gpt-4o-mini" (ВСЕГДА, даже если есть "глубокий")
4. PostHog: track("ai_request_sent", {tier: "free", model: "gpt-4o-mini", cost: $0.003})
```

### Пример 2: PREMIUM пользователь использует продвинутую фичу

```
1. User (tier=premium): AI вызывает "get_onchain_metrics"
2. crypto_tools → check_tool_access("get_onchain_metrics", "premium")
3. ✅ has_feature(PREMIUM, "onchain_metrics") = True
4. Execute tool → return data
5. PostHog: track("feature_used", {feature: "onchain_metrics", tier: "premium"})
```

### Пример 3: BASIC пытается использовать PREMIUM фичу

```
1. User (tier=basic): AI вызывает "get_onchain_metrics"
2. crypto_tools → check_tool_access("get_onchain_metrics", "basic")
3. ❌ has_feature(BASIC, "onchain_metrics") = False
4. Return: {"error": "🔒 This feature requires PREMIUM+ subscription"}
5. AI показывает: "Эта фича доступна только в PREMIUM. Апгрейднитесь!"
```

### Пример 4: Пользователь достигает лимита

```
1. User (tier=free, requests=1/day) делает 2-й запрос
2. check_request_limit() → can_send=False, current_count=1, limit=1
3. PostHog: track("limit_hit", {tier: "free", limit_type: "text", requests_used: 1, limit: 1})
4. Return: HTTP 429 "Rate limit exceeded"
5. Frontend показывает: "Лимит исчерпан. Upgrade to BASIC!"
```

---

## 🎯 Метрики которые теперь видны

### В PostHog dashboards:

**Dashboard 1: Acquisition**
- Регистраций/день
- Источники (organic vs referral)
- Retention (D1, D7, D30)

**Dashboard 2: Engagement**
- AI requests по tier
- Модели использование (gpt-4o vs mini)
- Feature usage (какие фичи используют)
- Limit hits (где пользователи упираются)

**Dashboard 3: Conversion**
- FREE → PAID conversion rate (ЦЕЛЬ: >5%)
- Pricing page views
- Payment completion rate
- Time to first purchase

**Dashboard 4: Revenue**
- MRR (Monthly Recurring Revenue)
- Revenue by tier breakdown
- LTV (Lifetime Value)
- Churn rate

---

## 🐛 Troubleshooting

### PostHog не работает

```bash
# Проверить что установлен
pip list | grep posthog

# Проверить .env
echo $POSTHOG_API_KEY

# Проверить логи
tail -f logs/bot.log | grep PostHog
```

**Если не настроен** - ничего страшного, бот работает без аналитики.

### Tier роутинг не работает

```bash
# Проверить что user.subscription загружен
# В handlers добавить:
logger.info(f"User {user.id} tier: {user.subscription.tier if user.subscription else 'free'}")

# Проверить логи модели:
tail -f logs/bot.log | grep "Using.*model"
```

### Feature gating не работает

```bash
# Проверить что tier передается в execute_tool
tail -f logs/bot.log | grep "Executing tool.*tier"

# Тестовый запрос (как PREMIUM):
# Должен работать: get_onchain_metrics
# Как FREE - должен блокироваться
```

---

## 📈 Следующие шаги

1. ✅ **Настроить PostHog dashboards** (1 час)
   - Создать 4 основных dashboard'а
   - Настроить alerts

2. ✅ **A/B тестирование** (когда будет достаточно данных)
   - Тест: FREE 1 vs 3 запроса/день
   - Тест: Pricing $4.99 vs $5.99

3. ✅ **Улучшить onboarding** (на основе данных)
   - Где теряются пользователи?
   - Как повысить conversion?

---

## 📝 Changelog

**2025-01-25**:
- ✅ Добавлен tier-aware model routing
- ✅ Добавлен tier gating для features
- ✅ Интегрирован PostHog analytics
- ✅ Упрощены payment endpoints
- ✅ Добавлен event tracking в критичные места

**Время выполнения**: ~1 час
**Статус**: ✅ Production Ready

---

🎉 **Готово! Теперь больше НЕ теряем деньги на FREE users и видим все метрики!** 💰📊
