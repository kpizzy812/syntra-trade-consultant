# FREE Tier Technical Indicators Fix

**Дата:** 2025-11-26
**Проблема:** FREE пользователи не получали базовые индикаторы (RSI, MACD, EMA)
**Статус:** ✅ Исправлено

---

## 🐛 Проблема

На скриншоте от пользователя видно, что бот отвечал:
> "RSI не доступен в FREE версии, но вы можете проанализировать его самостоятельно"

Это **противоречило конфигурации**:
- В [config/limits.py:49](../config/limits.py#L49) - `"basic_indicators": True` ✅
- В [config/prompts_free.py:72](../config/prompts_free.py#L72) - "RSI, MACD, EMA доступны в FREE" ✅

**Корень проблемы:**
В [src/services/crypto_tools.py:1653](../src/services/crypto_tools.py#L1653) инструмент `get_technical_analysis` был **полностью заблокирован** для FREE tier:

```python
TOOL_FEATURE_MAP = {
    "get_technical_analysis": "advanced_indicators",  # BASIC+ ❌
    ...
}
```

FREE tier имеет только `basic_indicators`, поэтому весь инструмент блокировался, и AI не мог получить **НИКАКИЕ** данные, даже базовые.

---

## ✅ Решение

### 1. Разблокировали `get_technical_analysis` для FREE tier

**Файл:** [src/services/crypto_tools.py:1653-1660](../src/services/crypto_tools.py#L1653-L1660)

```python
# БЫЛО:
TOOL_FEATURE_MAP = {
    "get_technical_analysis": "advanced_indicators",  # BASIC+
    ...
}

# СТАЛО:
# NOTE: get_technical_analysis is available for ALL tiers (FREE gets basic indicators only)
TOOL_FEATURE_MAP = {
    # "get_technical_analysis" removed - available for FREE (with filtering)
    "get_candlestick_patterns": "candlestick_patterns",  # BASIC+
    ...
}
```

### 2. Добавили фильтрацию результата для FREE tier

**Файл:** [src/services/crypto_tools.py:1739-1810](../src/services/crypto_tools.py#L1739-L1810)

После выполнения `get_technical_analysis`, если пользователь FREE tier, результат фильтруется:

```python
if tier_enum == SubscriptionTier.FREE:
    # Keep only basic data for FREE tier
    filtered_result = {
        "success": True,
        "coin_id": ...,
        "timeframe": ...,
        "data_sources": [],
    }

    # ✅ ALLOWED for FREE:
    # - extended_data (price, market cap, volume)
    # - fear_greed (Fear & Greed Index)
    # - news
    # - technical_indicators (ONLY RSI, MACD, EMA)

    if "technical_indicators" in result:
        indicators = result["technical_indicators"]
        filtered_result["technical_indicators"] = {
            "rsi": indicators.get("rsi"),
            "macd": indicators.get("macd"),
            "macd_signal": indicators.get("macd_signal"),
            "macd_histogram": indicators.get("macd_histogram"),
            "ema_20": indicators.get("ema_20"),
            "ema_50": indicators.get("ema_50"),
            "ema_200": indicators.get("ema_200"),
        }

    # ❌ BLOCKED for FREE:
    # - candlestick_patterns
    # - funding_data
    # - long_short_data
    # - liquidation_data
    # - onchain_data
    # - cycle_data
    # - Advanced indicators (Bollinger, VWAP, OBV, ATR, etc.)
```

### 3. Добавили upgrade message

Если для монеты доступны продвинутые фичи, FREE пользователь увидит сообщение:

```
🔓 Unlock Candlestick Patterns, Funding Rates, Long/Short Ratio with BASIC+ subscription!

💎 BASIC ($9.99/mo) includes:
   • Candlestick Patterns
   • Funding Rates & Long/Short Ratio
   • All Advanced Indicators
   • 15 requests/day

🚀 Try 7-day FREE trial!
```

---

## 🧪 Тестирование

Создан unit-тест: [tests/test_free_tier_filtering_unit.py](../tests/test_free_tier_filtering_unit.py)

**Результат:**
```
✅ ALL CHECKS PASSED!
   - Basic indicators present: ✅
   - Advanced indicators filtered: ✅
   - Premium features blocked: ✅
```

**Проверено:**
- ✅ FREE tier получает RSI, MACD, EMA
- ✅ FREE tier НЕ получает Bollinger, VWAP, OBV, ATR
- ✅ FREE tier НЕ получает patterns, funding, on-chain
- ✅ Показывается upgrade message

---

## 📊 Что теперь доступно в FREE tier

### ✅ Доступно:
- **Базовая market data**: цена, market cap, volume, ATH/ATL
- **Fear & Greed Index**: текущее настроение рынка
- **Новости**: последние события по монете
- **Базовые индикаторы**:
  - RSI (Relative Strength Index)
  - MACD (Moving Average Convergence Divergence)
  - MACD Signal
  - MACD Histogram
  - EMA 20, 50, 200

### ❌ Недоступно (BASIC+):
- Candlestick Patterns (Три Белых Солдата, Голова и Плечи, и т.д.)
- Funding Rates (настроение трейдеров на фьючерсах)
- Long/Short Ratio (распределение позиций)
- Продвинутые индикаторы:
  - Bollinger Bands
  - VWAP (Volume Weighted Average Price)
  - OBV (On-Balance Volume)
  - ATR (Average True Range)

### ❌ Недоступно (PREMIUM+):
- Liquidation Data (история ликвидаций)
- On-Chain Metrics (движение китов, активность сети)
- Cycle Analysis (Pi Cycle Top Indicator, Rainbow Chart)

---

## 🎯 Итог

**До исправления:**
- FREE пользователь спрашивает про Bitcoin
- AI пытается вызвать `get_technical_analysis`
- Инструмент блокируется
- AI отвечает: "RSI недоступен в FREE версии" ❌

**После исправления:**
- FREE пользователь спрашивает про Bitcoin
- AI вызывает `get_technical_analysis`
- Инструмент выполняется, результат фильтруется
- AI получает RSI, MACD, EMA
- AI отвечает: "Bitcoin на $87,156. RSI 65 — рост, MACD бычий. Ближайшее сопротивление $90,000" ✅

---

## 📝 Примечания

1. **Промпт остался прежним** - [config/prompts_free.py](../config/prompts_free.py) уже корректно описывал что доступно в FREE
2. **Конфигурация тиров осталась прежней** - [config/limits.py](../config/limits.py) уже указывала `basic_indicators: True`
3. **Проблема была только в блокировке инструмента** на уровне `check_tool_access`

4. **Фильтрация добавлена на уровне результата**, а не на уровне доступа к инструменту - это позволяет:
   - FREE получает базовые данные
   - BASIC получает продвинутые индикаторы + patterns + funding
   - PREMIUM получает полный набор данных

5. **Саркастичный стиль** из промпта теперь не будет использоваться для недоступных данных, так как AI просто не узнает о них - в результате будут только доступные индикаторы.
