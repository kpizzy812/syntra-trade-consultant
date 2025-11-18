# Market Overview System Backup
**Дата**: 18 ноября 2024, 23:15
**Версия**: Production-ready с полной интеграцией уровней

## 📦 Содержимое бэкапа

### 1. **price_levels_service.py** (27K)
Сервис расчёта технических уровней

**Ключевые функции:**
- `calculate_fibonacci_retracement()` - Fibonacci уровни от ATH/ATL
- `calculate_support_resistance_from_ohlc()` - Swing High/Low + Volume liquidity zones
- `generate_scenario_levels()` - Сценарии с entry/SL/TP на базе ATR

**Новые возможности:**
- ✅ EMA уровни (20/50/200) с `distance_pct` и `position`
- ✅ ATR-based SL/TP (лонг: entry - ATR, шорт: entry + ATR)
- ✅ Volume liquidity zones (тело >3%, объём >1.8x avg)
- ✅ Leverage рекомендации на основе ATR волатильности
- ✅ Динамические EMA как поддержка/сопротивление

### 2. **crypto_tools.py** (54K)
Основной модуль сбора данных

**Функции:**
- `get_market_overview()` - Сбор BTC/ETH цен, TA, dominance, F&G, news
- `get_technical_analysis()` - Полный TA с индикаторами, уровнями, фьючами

**Интеграция:**
- Lines 1003-1023: Передача EMA/ATR в `generate_scenario_levels()`
- Lines 626-691: Извлечение всех индикаторов (RSI, MACD, EMA, funding, long/short, market phase)

### 3. **cryptopanic_service.py** (15K)
Сервис новостей CryptoPanic API

**Функции:**
- `get_relevant_market_news()` - Фильтрация по sentiment (bullish/bearish) на основе BTC движения
- Приоритет новостям последних 24ч с высоким importance score

### 4. **openai_service_two_step.py** (25K)
Two-step AI архитектура (GPT-4o-mini → GPT-4o)

**Step 1**: Сбор данных с function calls
**Step 2**: Styling с применением характера Syntra

**Styling Prompt для Market Overview (lines 346-422):**
- ✅ ТРЕБУЕТ использовать scenario_levels.key_levels (immediate_support/resistance)
- ✅ ТРЕБУЕТ использовать ema_levels с distance_pct
- ✅ ТРЕБУЕТ использовать liquidity_zones
- ✅ ТРЕБУЕТ использовать ATR, funding, long/short, market phase
- ✅ ЗАПРЕЩАЕТ выдумывать уровни которых нет в данных
- ✅ Для торговли: использует scenarios (entry/SL/TP) + leverage recommendation

### 5. **prompts.py** (60K)
Системные промпты и few-shot примеры

**Содержит:**
- `SYNTRA_CORE_PROMPT` - Основной характер и правила
- Market overview format (lines 73-104)
- Few-shot примеры для "что по рынку"
- Safeguard триггеры

---

## 🎯 Основные улучшения системы

### ✅ EMA Dynamic Levels
```python
"ema_levels": {
    "ema_50": {
        "price": 67500,
        "distance_pct": 3.2,  # Цена на 3.2% ниже EMA50
        "position": "below"
    }
}
```

### ✅ ATR-based SL/TP
```python
# Лонг
SL = entry - 1.0 × ATR (conservative) или entry - 0.5 × ATR (aggressive)
TP = entry + 0.5 × ATR (scalp), entry + 1.0 × ATR (swing), entry + 2.0 × ATR (extended)

# Шорт
SL = entry + 1.0 × ATR (conservative)
TP = entry - 1.0 × ATR (swing)
```

### ✅ Volume Liquidity Zones
```python
# Критерии
body_size_pct > 3.0%
volume_ratio > 1.8 × avg_volume

# Использование
"здесь свеча +3% на объёме x1.8 — зона ликвидности"
```

### ✅ Leverage Recommendations
```python
ATR < 2%: 3x-10x (низкая волатильность)
ATR 2-4%: 2x-7x (средняя волатильность)
ATR > 4%: 1x-5x (высокая волатильность - spot или минимальное плечо)
```

---

## 📊 Архитектура данных

### Market Overview Flow:
1. **get_market_overview()** → собирает BTC/ETH/market data
2. **get_technical_analysis("bitcoin", "1d")** → получает полный TA
3. **generate_scenario_levels()** → строит уровни + сценарии
4. **Step 2 Styling** → создаёт ответ используя ВСЕ данные

### Scenario Levels Structure:
```json
{
  "current_price": 67200,
  "atr": 1200,
  "atr_based_calculations": true,
  "leverage_recommendation": {
    "conservative": "2x-3x",
    "moderate": "3x-5x",
    "volatility_level": "medium",
    "atr_pct": 3.2
  },
  "key_levels": {
    "immediate_support": 65000,
    "immediate_resistance": 68500,
    "ema_levels": {
      "ema_50": {
        "price": 66800,
        "distance_pct": 0.6,
        "position": "below"
      }
    },
    "all_support_levels": [63000, 65000, 66800],
    "all_resistance_levels": [68500, 70000]
  },
  "scenarios": {
    "bullish_scenario": {
      "entry_zone": {"conservative": 65856, "aggressive": 68544},
      "stop_loss": {"conservative": 66000, "aggressive": 66600},
      "targets": {"target_1": 67800, "target_2": 68400, "target_3": 69600}
    }
  }
}
```

---

## 🔧 Как восстановить

```bash
# Скопировать файлы обратно в проект
cp price_levels_service.py ../../src/services/
cp crypto_tools.py ../../src/services/
cp cryptopanic_service.py ../../src/services/
cp openai_service_two_step.py ../../src/services/
cp prompts.py ../../config/

# Запустить тесты
source .venv/bin/activate
python -m py_compile src/services/*.py
```

---

## ⚠️ Критические зависимости

- **Binance API**: klines для OHLC данных (свечи)
- **CoinGecko API**: ATH/ATL для Fibonacci, dominance
- **CryptoPanic API**: news с sentiment фильтром
- **Fear & Greed API**: market sentiment index
- **OpenAI GPT-4o**: styling step (требует характер Syntra)

---

## 📝 Следующие улучшения (backlog)

1. 🔜 **Timeframe как явный флаг** (1h/4h/1d)
2. 🔜 **Distance_to_level_% для всех key_levels** (не только EMA)
3. 🔜 **Более короткие ответы** для market overview (убрать воду)
4. 🔜 **Multi-timeframe анализ** (дневка + 4H локальные уровни)

---

## 🎉 Результат

Система теперь:
1. ✅ Собирает ВСЕ данные (EMA, ATR, volume zones, funding, long/short, market phase)
2. ✅ Вычисляет профессиональные уровни из OHLC свечей
3. ✅ ТРЕБУЕТ от AI использовать эти данные в ответе
4. ✅ НЕ выдумывает уровни - только реальные из расчётов
5. ✅ Даёт конкретные торговые сценарии с entry/SL/TP + leverage

**Главная проблема решена**: Step 2 больше не игнорирует уровни! 🔥
