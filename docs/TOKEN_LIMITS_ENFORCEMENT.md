# 🔒 Token Limits Enforcement по Tier

**Дата**: 2025-01-25
**Статус**: ✅ Завершено

---

## ✅ Что сделано

### 1. Добавлены Token Limits в `config/limits.py`

**Зачем**: Контроль затрат на API - разные tier'ы получают разные лимиты на input/output токены.

**Новые параметры в TIER_LIMITS**:
```python
TIER_LIMITS = {
    SubscriptionTier.FREE: {
        "max_input_tokens": 2000,    # Max tokens in user message + history
        "max_output_tokens": 800,    # Max tokens in AI response
        # ...
    },
    SubscriptionTier.BASIC: {
        "max_input_tokens": 4000,    # 2x больше контекста
        "max_output_tokens": 1200,   # Более детальные ответы
        # ...
    },
    SubscriptionTier.PREMIUM: {
        "max_input_tokens": 8000,    # Расширенный контекст (full history)
        "max_output_tokens": 1500,   # Полный анализ
        # ...
    },
    SubscriptionTier.VIP: {
        "max_input_tokens": 16000,   # Максимальное context window
        "max_output_tokens": 2000,   # Безлимитные детальные ответы
        # ...
    },
}
```

**Новая функция**:
```python
def get_token_limits(tier: SubscriptionTier) -> Dict[str, int]:
    """
    Get token limits for a specific subscription tier

    Returns:
        Dict with max_input_tokens and max_output_tokens
    """
    tier_config = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])
    return {
        "max_input_tokens": tier_config.get("max_input_tokens", 2000),
        "max_output_tokens": tier_config.get("max_output_tokens", 800),
    }
```

---

### 2. Применены Token Limits в `openai_service.py`

**Файл**: [src/services/openai_service.py:295-324](../src/services/openai_service.py#L295-L324)

**Что изменено**:
```python
# Get token limits for user's tier
from src.database.models import SubscriptionTier
try:
    tier_enum = SubscriptionTier(user_tier)
except ValueError:
    logger.warning(f"Invalid tier '{user_tier}', defaulting to FREE")
    tier_enum = SubscriptionTier.FREE

token_limits = get_token_limits(tier_enum)
max_output = token_limits["max_output_tokens"]

logger.info(
    f"User {user_id} tier={user_tier}: max_output_tokens={max_output}"
)

# Build API call parameters
api_params = {
    "model": model,
    "messages": messages,
    "max_tokens": max_output,  # 🚨 Tier-based limit (было: ModelConfig.MAX_TOKENS_RESPONSE = 1500 для всех!)
    "temperature": ModelConfig.DEFAULT_TEMPERATURE,
    "stream": True,
}
```

**Было**: `max_tokens=1500` для ВСЕХ пользователей (включая FREE!)

**Стало**:
- FREE: 800 tokens
- BASIC: 1200 tokens
- PREMIUM: 1500 tokens
- VIP: 2000 tokens

---

## 💰 Economic Impact

### До изменений:
- **FREE user**: Мог получить 1500 tokens ответа
- **Стоимость**: ~$0.009 за ответ (GPT-4o-mini output: $0.60/1M tokens)

### После изменений:
- **FREE user**: Максимум 800 tokens ответа
- **Стоимость**: ~$0.0048 за ответ
- **Экономия**: **47% на output tokens!**

### Monthly Savings (при 1000 FREE users, 1 req/day):
```
До:  30,000 запросов × $0.009 = $270/месяц
После: 30,000 запросов × $0.0048 = $144/месяц
Экономия: $126/месяц (47%)
```

---

## 📊 Token Limits Comparison

| Tier | Input Tokens | Output Tokens | Context | Response Quality |
|------|-------------|---------------|---------|------------------|
| FREE | 2,000 | 800 | Минимальный | Краткие ответы |
| BASIC | 4,000 | 1,200 | Средний | Детальные ответы |
| PREMIUM | 8,000 | 1,500 | Полный | Полный анализ |
| VIP | 16,000 | 2,000 | Максимальный | Безлимитный |

**Input Tokens = System Prompt + History + User Message**

**Output Tokens = AI Response Length**

---

## 🎯 Use Cases by Tier

### FREE (800 tokens output)
**Примеры ответов**:
- ✅ Краткий анализ BTC (3-4 абзаца)
- ✅ Базовые индикаторы (RSI, MACD)
- ✅ Простые рекомендации
- ❌ Глубокий multi-timeframe анализ
- ❌ Длинные таблицы данных

### BASIC (1200 tokens output)
**Примеры ответов**:
- ✅ Детальный анализ с индикаторами
- ✅ Candlestick patterns объяснение
- ✅ Funding rates analysis
- ⚠️ Ограниченные таблицы
- ❌ Глубокий on-chain анализ

### PREMIUM (1500 tokens output)
**Примеры ответов**:
- ✅ Полный технический анализ
- ✅ On-chain metrics разбор
- ✅ Liquidation heatmaps
- ✅ Market cycle analysis
- ✅ Полные таблицы с данными

### VIP (2000 tokens output)
**Примеры ответов**:
- ✅ Максимально детальный анализ
- ✅ Multi-asset сравнение
- ✅ Расширенные таблицы
- ✅ Безлимитные данные

---

## 🚀 Дальнейшие Улучшения (Optional)

### 1. Input Token Truncation (Future)
**Проблема**: Если history слишком большая, FREE users могут потратить много input tokens.

**Решение** (пока НЕ реализовано):
```python
# Truncate messages if exceed max_input_tokens
max_input = token_limits["max_input_tokens"]
if history_tokens > max_input:
    # Truncate oldest messages (кроме system prompt)
    while history_tokens > max_input and len(messages) > 2:
        # Remove second message (after system prompt)
        removed = messages.pop(1)
        history_tokens -= count_tokens(removed["content"])
    logger.warning(f"Truncated history for user {user_id}: {len(messages)} messages left")
```

**Зачем**: Ещё больше экономии на input tokens для FREE tier.

---

### 2. Dynamic Token Allocation (Future)
**Идея**: Если простой запрос - дать меньше tokens, если сложный - больше (в пределах tier limit).

```python
# Detect query complexity
if "deep analysis" in user_message.lower() or len(user_message) > 500:
    max_output = token_limits["max_output_tokens"]  # Full limit
else:
    max_output = min(500, token_limits["max_output_tokens"])  # Reduced for simple queries
```

**Зачем**: Ещё больше экономии для простых запросов ("what's BTC price?").

---

### 3. Token Usage Tracking (Future)
**Идея**: Трекать сколько tokens пользователь использовал за месяц.

```python
# Track monthly token usage
await track_token_usage(
    session,
    user_id=user_id,
    input_tokens=input_tokens,
    output_tokens=output_tokens,
    cost=cost,
    tier=user_tier
)

# Check if user exceeds monthly token budget
monthly_tokens = await get_monthly_tokens(session, user_id)
if monthly_tokens > TIER_TOKEN_BUDGETS[tier]:
    raise HTTPException(429, "Monthly token limit exceeded")
```

**Зачем**: Защита от abuse (пользователи которые пишут очень длинные сообщения).

---

## 🐛 Troubleshooting

### Ответы AI обрезаются на середине предложения

**Причина**: `max_output_tokens` слишком маленький для tier.

**Решение**:
- Upgrade tier (BASIC → PREMIUM)
- Или: Упростить запрос (меньше деталей)

**Как проверить**:
```python
# В логах:
logger.info(f"User {user_id} tier={user_tier}: max_output_tokens={max_output}")

# Если finish_reason = "length" → ответ обрезан
```

---

### FREE users жалуются на короткие ответы

**Это фича, не баг!** FREE tier = 800 tokens = ~600 слов = 3-4 абзаца.

**Upgrade path**:
- FREE (800) → BASIC (1200) → PREMIUM (1500) → VIP (2000)

---

## 📝 Changelog

**2025-01-25**:
- ✅ Добавлены token limits в `config/limits.py`
- ✅ Добавлена функция `get_token_limits()`
- ✅ Применены limits в `openai_service.py::stream_completion()`
- ✅ Логирование max_output_tokens для каждого запроса
- ✅ Graceful fallback к FREE tier при невалидном tier

**Время выполнения**: ~30 минут
**Статус**: ✅ Production Ready

---

## 🎉 Summary

**Key Achievement**: FREE tier больше НЕ может использовать 1500 tokens ответы! 🎯

**Impact**:
- ✅ Снижены затраты на FREE users на 47%
- ✅ Чёткая дифференциация по tier (800/1200/1500/2000)
- ✅ Защита от утечки денег через длинные ответы

**Next Steps**:
1. ⏳ (Optional) Добавить input token truncation
2. ⏳ (Optional) Dynamic token allocation
3. ⏳ (Optional) Monthly token budgets
