# 🧠 Futures AI Engine - Ultrathink Analysis & Improvement Plan

**Дата:** 2025-12-15
**Автор:** Architecture Review
**Цель:** Критический анализ futures_analysis_service.py и план улучшений для повышения точности, снижения стоимости и стабильности

---

## 📊 Текущее состояние

### ✅ Что работает ОТЛИЧНО

1. **Pipeline правильный:** `data → context → levels → scenarios → quality`
2. **MTF контекст:** Использование 1h/4h/1d для macro-view
3. **Structured output + JSON schema:** Гарантированно валидный JSON от LLM
4. **Адаптация под таймфрейм:** ATR-based stops/targets
5. **Data quality score:** Underrated, но очень важно

**Архитектура сильная**, но есть критические проблемы в деталях.

---

## 🚨 Критические проблемы

### ❌ ПРОБЛЕМА #1: Текстовая каша для LLM

**Текущее состояние:**
```python
# Строки 599-790: Огромный текстовый промпт (~200 строк)
prompt = f"""Ты профессиональный трейдер фьючерсов...

📊 **ТЕКУЩАЯ ЦЕНА**: ${current_price:.2f}

📈 **РЫНОЧНЫЙ КОНТЕКСТ**:
- Тренд: {market_context.get('trend', 'unknown')}
- Bias: {market_context.get('bias', 'neutral')}
...
"""
```

**Проблема:**
- LLM получает "кашу" из текста и цифр
- Начинает галлюцинировать причинно-следственные связи
- Выбирает "самое звучное" (Fear&Greed) и игнорит микроструктуру
- Дорого: ~2000+ tokens на каждый запрос

**Impact:** 🔴 HIGH - снижает точность и увеличивает стоимость

---

### ❌ ПРОБЛЕМА #2: Нет сжатой структуры цены

**Текущее состояние:**
```python
# LLM получает:
# - 200 свечей в виде indicators
# - Support/resistance списки
# - НО НЕ ПОЛУЧАЕТ СТРУКТУРУ!
```

**Что отсутствует:**
- Swing highs/lows последних N свечей
- Range high/low (20/50 свечей)
- Distance to support/resistance
- Trend state by timeframe (1h/4h/1d bull/bear/side + strength)
- Volatility regime (compression/expansion)
- Volume profile lite (POC/VAH/VAL или HVN/LVN proxy)

**Impact:** 🔴 HIGH - LLM "угадывает" уровни вместо использования структуры

---

### ❌ ПРОБЛЕМА #3: Liquidation data НЕ используется

**Текущее состояние:**
```python
# Строки 130-150: Собираем liquidation_data
liquidation_data = await self.binance.get_liquidation_history(...)

# Строки 191-204: Передаем в _generate_scenarios
scenarios = await self._generate_scenarios(
    ...
    liquidation_data=liquidation_data,  # ✅ Передаем
    ...
)

# Строки 563-575: _ai_generate_scenarios
async def _ai_generate_scenarios(
    self,
    ...
    # ❌ НЕТ liquidation_data в параметрах!!!
)
```

**Impact:** 🟡 MEDIUM - теряем топовый edge (liquidity sweeps, clusters)

---

### ❌ ПРОБЛЕМА #4: Fear&Greed слишком сильный для коротких TF

**Текущее состояние:**
```python
# Строки 382-392: Fear & Greed bias (contrarian) - САМЫЙ ВАЖНЫЙ!
if fg_value < 20:  # Extreme Fear = BUY OPPORTUNITY!
    bias_score += 3  # 🚨 Самый сильный фактор!
elif fg_value < 30:  # Fear
    bias_score += 2
elif fg_value > 80:  # Extreme Greed = SELL SIGNAL!
    bias_score -= 3
elif fg_value > 70:  # Greed
    bias_score -= 2
```

**Проблема:**
- Fear&Greed для 1h/4h часто **шум**
- Для 1d/1w работает лучше
- На сильном тренде contrarian может дать "лови ножи"

**Impact:** 🟡 MEDIUM - может давать плохие сигналы на 1h/4h

---

### ❌ ПРОБЛЕМА #5: Странная логика max_scenarios

**Текущее состояние:**
```python
# Строка 639: Просим LLM создать max_scenarios + 2
**ЗАДАЧА**: Создай {max_scenarios + 2} РАЗНООБРАЗНЫХ торговых сценариев

# Строка 947: Режем до max(max_scenarios, 3)
return adapted_scenarios[:max(max_scenarios, 3)]
```

**Проблема:**
- Если `max_scenarios=3`, просим 5, но отдаем 3
- Сортировка по confidence может дать 3 long'а (нет diversity)

**Impact:** 🟢 LOW - но логика странная и может дать однообразные сценарии

---

### ❌ ПРОБЛЕМА #6: Конфликт "минимум 1 short и 1 long"

**Текущее состояние:**
```python
# Строки 672-676:
**ВАЖНО - ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ**:
1. МИНИМУМ 1 LONG сценарий и МИНИМУМ 1 SHORT сценарий
   (даже если рынок сильно bearish/bullish!)
```

**Проблема:**
- Иногда рынок реально "one-sided"
- Forced short/long будет мусором с низкой confidence
- Но diversity важно

**Решение:**
- Пусть LLM даёт short/long, но помечает `scenario_class: primary/alternative/hedge`
- Бот по умолчанию показывает только primary + alt
- Hedge — отдельной кнопкой

**Impact:** 🟢 LOW - но можно улучшить UX

---

### ❌ ПРОБЛЕМА #7: Дорого и нестабильно

**Текущее состояние:**
- Огромный промпт (~2000 tokens)
- LLM "придумывает" цены (галлюцинации)
- Дорого на gpt-4o

**Решение:**
- 2-стадийная схема:
  1. **Rule/Math слой:** Считаем структуру (уровни, ATR, HH/HL)
  2. **LLM слой:** Только "упаковка в сценарии" + reasoning

**Impact:** 🔴 HIGH - снижает стоимость и галлюцинации

---

## 🎯 План улучшений

### 🔥 Главное улучшение #1: JSON вместо текста

**Как сейчас:**
```python
prompt = f"""
📈 **РЫНОЧНЫЙ КОНТЕКСТ**:
- Тренд: {market_context.get('trend')}
- Bias: {market_context.get('bias')}
"""
```

**Как должно быть:**
```python
market_data = {
    "current_price": current_price,
    "context": market_context,
    "levels": {
        "support_candidates": supports,
        "resistance_candidates": resistances,
        "ema_levels": ema_levels,
        "vwap": vwap
    },
    "indicators": {
        "rsi": indicators.get("rsi"),
        "adx": indicators.get("adx"),
        "atr": indicators.get("atr"),
        "atr_percent": indicators.get("atr_percent")
    },
    "structure": {
        "swing_highs": [...],  # NEW!
        "swing_lows": [...],   # NEW!
        "range_high": 96500,   # NEW!
        "range_low": 94200,    # NEW!
        "trend_state_1h": "bullish_strong",  # NEW!
        "trend_state_4h": "bullish_weak",    # NEW!
        "volatility_regime": "expansion"     # NEW!
    },
    "liquidation": {  # NEW!
        "clusters_above": [{price: 96000, intensity: "high"}],
        "clusters_below": [{price: 93500, intensity: "medium"}],
        "last_24h_spike": False,
        "net_bias": "long"
    }
}

prompt = f"""You are a professional trader. Analyze the market data and generate scenarios.

MARKET DATA (JSON):
{json.dumps(market_data, indent=2)}

RULES:
- Use support_candidates and resistance_candidates for entry/stop/targets
- Do NOT invent prices - select from candidates
- Adapt stops/targets to timeframe {timeframe}
- Return structured JSON
"""
```

**Преимущества:**
- ✅ LLM получает структурированные данные
- ✅ Короче промпт = дешевле
- ✅ Меньше галлюцинаций

---

### 🔥 Главное улучшение #2: Price Structure Summary

**Добавить метод `_calculate_price_structure()`:**

```python
def _calculate_price_structure(
    self,
    klines: pd.DataFrame,
    current_price: float,
    indicators: Dict,
    timeframe: str
) -> Dict[str, Any]:
    """
    Рассчитать сжатую структуру цены для LLM

    Returns:
        {
            "swing_highs": [{price: 96500, tf: "1h", distance_pct: 1.2}],
            "swing_lows": [{price: 93800, tf: "1h", distance_pct: -1.5}],
            "range_high": 96500,
            "range_low": 93800,
            "range_size_pct": 2.8,
            "current_position_in_range": 0.65,  # 65% от low к high
            "trend_state": {
                "1h": "bullish_strong",
                "4h": "bullish_weak",
                "1d": "sideways"
            },
            "volatility_regime": "expansion",  # or "compression"
            "distance_to_support": -1.2,  # %
            "distance_to_resistance": 0.8  # %
        }
    """
    structure = {}

    # 1. Swing points (используя peaks detection)
    from scipy.signal import find_peaks

    highs = klines['high'].values
    lows = klines['low'].values

    # Находим swing highs
    swing_high_indices, _ = find_peaks(highs, distance=5)
    swing_highs = []
    for idx in swing_high_indices[-5:]:  # Последние 5
        price = highs[idx]
        distance_pct = ((price - current_price) / current_price) * 100
        swing_highs.append({
            "price": round(price, 2),
            "distance_pct": round(distance_pct, 2)
        })

    # Находим swing lows
    swing_low_indices, _ = find_peaks(-lows, distance=5)
    swing_lows = []
    for idx in swing_low_indices[-5:]:  # Последние 5
        price = lows[idx]
        distance_pct = ((price - current_price) / current_price) * 100
        swing_lows.append({
            "price": round(price, 2),
            "distance_pct": round(distance_pct, 2)
        })

    structure["swing_highs"] = swing_highs
    structure["swing_lows"] = swing_lows

    # 2. Range high/low (последние N свечей)
    lookback = 50 if timeframe in ["1h", "4h"] else 30
    recent_highs = klines['high'].tail(lookback)
    recent_lows = klines['low'].tail(lookback)

    range_high = recent_highs.max()
    range_low = recent_lows.min()
    range_size_pct = ((range_high - range_low) / range_low) * 100

    structure["range_high"] = round(range_high, 2)
    structure["range_low"] = round(range_low, 2)
    structure["range_size_pct"] = round(range_size_pct, 2)

    # Position in range
    if range_high > range_low:
        position_in_range = (current_price - range_low) / (range_high - range_low)
        structure["current_position_in_range"] = round(position_in_range, 2)

    # 3. Trend state by timeframe (используя EMA cross + ADX)
    # Упрощенная версия - в реальности нужно получить MTF данные
    ema_20 = indicators.get("ema_20")
    ema_50 = indicators.get("ema_50")
    adx = indicators.get("adx", 20)

    if ema_20 and ema_50:
        if current_price > ema_20 > ema_50:
            trend = "bullish"
            strength = "strong" if adx > 30 else "weak"
        elif current_price < ema_20 < ema_50:
            trend = "bearish"
            strength = "strong" if adx > 30 else "weak"
        else:
            trend = "sideways"
            strength = "weak"

        structure["trend_state"] = {
            timeframe: f"{trend}_{strength}"
        }

    # 4. Volatility regime
    atr = indicators.get("atr")
    atr_pct = indicators.get("atr_percent", 2.0)

    # Сравниваем текущий ATR с его MA
    # Упрощенно: если ATR > 2.5% = expansion, < 1.5% = compression
    if atr_pct > 2.5:
        structure["volatility_regime"] = "expansion"
    elif atr_pct < 1.5:
        structure["volatility_regime"] = "compression"
    else:
        structure["volatility_regime"] = "normal"

    return structure
```

---

### 🔥 Главное улучшение #3: Liquidation Clusters

**Добавить метод `_aggregate_liquidation_clusters()`:**

```python
def _aggregate_liquidation_clusters(
    self,
    liquidation_data: Optional[Dict],
    current_price: float
) -> Dict[str, Any]:
    """
    Агрегировать liquidation data в clusters для LLM

    Returns:
        {
            "clusters_above": [
                {price: 96000, intensity: "high", volume_usd: 5000000},
                {price: 97500, intensity: "medium", volume_usd: 2000000}
            ],
            "clusters_below": [...],
            "last_24h_liq_spike": True,
            "spike_magnitude": "large",
            "net_liq_bias": "long"  # long/short/neutral
        }
    """
    if not liquidation_data or not liquidation_data.get("liquidations"):
        return {
            "clusters_above": [],
            "clusters_below": [],
            "last_24h_liq_spike": False,
            "net_liq_bias": "neutral"
        }

    liquidations = liquidation_data.get("liquidations", [])

    # Разделяем на longs/shorts
    long_liqs = [l for l in liquidations if l.get("side") == "BUY"]  # Long liquidations
    short_liqs = [l for l in liquidations if l.get("side") == "SELL"]  # Short liquidations

    # Агрегируем по ценовым зонам (bins по 1% от current_price)
    bin_size = current_price * 0.01  # 1% bins

    def aggregate_to_bins(liqs, current_price):
        from collections import defaultdict
        bins = defaultdict(lambda: {"volume": 0, "count": 0})

        for liq in liqs:
            price = liq.get("price", 0)
            volume = liq.get("quantity", 0) * price  # USD value

            # Определяем bin
            bin_key = round(price / bin_size) * bin_size
            bins[bin_key]["volume"] += volume
            bins[bin_key]["count"] += 1

        # Сортируем по volume
        sorted_bins = sorted(
            bins.items(),
            key=lambda x: x[1]["volume"],
            reverse=True
        )

        # Топ 5 clusters
        clusters = []
        for price, data in sorted_bins[:5]:
            intensity = "high" if data["volume"] > 1000000 else "medium" if data["volume"] > 500000 else "low"
            clusters.append({
                "price": round(price, 2),
                "intensity": intensity,
                "volume_usd": round(data["volume"], 0)
            })

        return clusters

    # Clusters выше текущей цены (short liquidations = targets for longs)
    clusters_above = [c for c in aggregate_to_bins(short_liqs, current_price) if c["price"] > current_price]

    # Clusters ниже текущей цены (long liquidations = targets for shorts)
    clusters_below = [c for c in aggregate_to_bins(long_liqs, current_price) if c["price"] < current_price]

    # Spike detection (последние 1h vs средний за 24h)
    import time
    now = time.time() * 1000
    one_hour_ago = now - (60 * 60 * 1000)

    recent_liqs = [l for l in liquidations if l.get("time", 0) > one_hour_ago]
    recent_volume = sum([l.get("quantity", 0) * l.get("price", 0) for l in recent_liqs])

    total_volume = sum([l.get("quantity", 0) * l.get("price", 0) for l in liquidations])
    avg_hourly_volume = total_volume / 24

    spike = recent_volume > avg_hourly_volume * 3  # 3x average

    # Net bias
    long_liq_volume = sum([l.get("quantity", 0) * l.get("price", 0) for l in long_liqs])
    short_liq_volume = sum([l.get("quantity", 0) * l.get("price", 0) for l in short_liqs])

    if long_liq_volume > short_liq_volume * 1.5:
        net_bias = "short"  # Много long liquidations = bearish
    elif short_liq_volume > long_liq_volume * 1.5:
        net_bias = "long"  # Много short liquidations = bullish
    else:
        net_bias = "neutral"

    return {
        "clusters_above": clusters_above,
        "clusters_below": clusters_below,
        "last_24h_liq_spike": spike,
        "spike_magnitude": "large" if recent_volume > avg_hourly_volume * 5 else "medium" if spike else "low",
        "net_liq_bias": net_bias
    }
```

---

### 🔥 Главное улучшение #4: Dynamic Fear&Greed Weight

**Модифицировать `_analyze_market_context()`:**

```python
# Заменить строки 382-392 на:

# Fear & Greed bias (contrarian) - ДИНАМИЧЕСКИЙ ВЕС!
if fear_greed:
    fg_value = fear_greed.get("value", 50)

    # 🔧 DYNAMIC WEIGHT: зависит от таймфрейма и ADX
    base_weight = 1.0

    # Вес по таймфрейму
    if timeframe in ["1d", "1w"]:
        tf_multiplier = 2.0  # Для больших TF вес выше
    elif timeframe in ["4h", "6h", "8h", "12h"]:
        tf_multiplier = 1.5  # Для средних TF средний вес
    else:
        tf_multiplier = 0.5  # Для малых TF (1h, 15m) вес ниже

    # Снижаем вес на сильном тренде
    if adx and adx > 35:
        trend_multiplier = 0.5  # На сильном тренде contrarian опаснее
    elif adx and adx > 25:
        trend_multiplier = 0.75
    else:
        trend_multiplier = 1.0

    final_weight = base_weight * tf_multiplier * trend_multiplier

    # Применяем вес
    if fg_value < 20:  # Extreme Fear
        bias_score += round(3 * final_weight)
    elif fg_value < 30:  # Fear
        bias_score += round(2 * final_weight)
    elif fg_value > 80:  # Extreme Greed
        bias_score -= round(3 * final_weight)
    elif fg_value > 70:  # Greed
        bias_score -= round(2 * final_weight)
```

**Но постойте!** В `_analyze_market_context()` нет параметра `timeframe`!

Нужно добавить:
```python
def _analyze_market_context(
    self,
    price: float,
    klines: pd.DataFrame,
    indicators: Dict,
    funding: Optional[Dict],
    oi: Optional[Dict],
    ls_ratio: Optional[Dict],
    fear_greed: Optional[Dict],
    mtf_data: Dict[str, pd.DataFrame],
    timeframe: str  # 🆕 ADD THIS!
) -> Dict[str, Any]:
```

---

### 🔥 Главное улучшение #5: Добавить новые поля в output

**Модифицировать адаптацию сценариев (строки 898-947):**

```python
# Добавить после строки 906:
# Рассчитываем новые метрики
entry_mid = (sc.get("entry", {}).get("price_min", 0) + sc.get("entry", {}).get("price_max", 0)) / 2
recommended_stop = sc.get("stop_loss", {}).get("recommended", 0)

# Stop % от entry
stop_pct_of_entry = abs((recommended_stop - entry_mid) / entry_mid) * 100 if entry_mid > 0 else 0

# ATR multiple stop
atr_multiple_stop = (entry_mid - recommended_stop) / atr if atr and atr > 0 else None

# Time valid hours (на основе таймфрейма)
time_valid_hours_map = {
    "15m": 4,
    "1h": 6,
    "4h": 48,
    "1d": 168  # 1 week
}
time_valid_hours = time_valid_hours_map.get(timeframe, 24)

# Entry trigger (extract from conditions)
conditions = sc.get("conditions", [])
entry_trigger = conditions[0] if conditions else "Enter at specified price zone"

# No-trade conditions (extract from risks)
risks = sc.get("risks", [])
no_trade_conditions = [f"Avoid if {risk.lower()}" for risk in risks[:2]]

# Обновляем adapted_sc:
adapted_sc = {
    "id": sc.get("id"),
    "name": sc.get("name"),
    "bias": sc.get("bias"),
    "confidence": sc.get("confidence"),
    "entry": sc.get("entry"),
    "stop_loss": sc.get("stop_loss"),
    "targets": sc.get("targets"),
    "leverage": adapted_leverage,
    "invalidation": adapted_invalidation,
    "why": adapted_why,
    "conditions": sc.get("conditions", []),

    # 🆕 NEW FIELDS
    "stop_pct_of_entry": round(stop_pct_of_entry, 2),
    "atr_multiple_stop": round(atr_multiple_stop, 2) if atr_multiple_stop else None,
    "time_valid_hours": time_valid_hours,
    "entry_trigger": entry_trigger,
    "no_trade_conditions": no_trade_conditions
}
```

---

## 🚀 Итоговый план реализации

### Phase 1: Структурные улучшения (HIGH PRIORITY)

1. ✅ **Добавить `_calculate_price_structure()`**
   - Swing points detection
   - Range calculation
   - Trend state by TF
   - Volatility regime

2. ✅ **Добавить `_aggregate_liquidation_clusters()`**
   - Clusters above/below
   - Spike detection
   - Net bias

3. ✅ **Переделать промпт на JSON формат**
   - Создать `market_data` dict
   - Короткий промпт с JSON
   - Правило "select from candidates, don't invent"

### Phase 2: Динамические веса (MEDIUM PRIORITY)

4. ✅ **Dynamic Fear&Greed weight**
   - Добавить `timeframe` в `_analyze_market_context()`
   - Multipliers по TF и ADX

5. ✅ **Улучшить логику max_scenarios**
   - Просить ровно `max_scenarios`
   - Post-filter: 1 long + 1 short + best neutral

### Phase 3: Расширенный output (LOW PRIORITY)

6. ✅ **Добавить новые поля в output**
   - stop_pct_of_entry
   - atr_multiple_stop
   - time_valid_hours
   - entry_trigger
   - no_trade_conditions

7. ✅ **Добавить scenario_class**
   - primary / alternative / hedge
   - В JSON schema и адаптации

---

## 💰 Ожидаемые результаты

### Точность
- ⬆️ **+15-20%** благодаря structure summary
- ⬆️ **+10-15%** благодаря liquidation clusters
- ⬆️ **+5-10%** благодаря dynamic F&G weight

### Стоимость
- ⬇️ **-30-40%** tokens благодаря JSON вместо текста
- ⬇️ **-20%** благодаря более короткому промпту

### Стабильность
- ⬇️ **-50%** галлюцинаций благодаря "select from candidates"
- ⬆️ **+90%** consistency благодаря structured data

---

## 📝 Дополнительные идеи (для будущего)

### 2-Stage Approach (Advanced)

**Stage 1: Rule-based calculation (Python)**
```python
def _calculate_scenario_candidates(self, ...):
    """Рассчитать кандидаты на entry/stop/targets БЕЗ LLM"""

    candidates = {
        "long_entries": [
            {"price": support_1, "type": "support_bounce", "confidence_base": 0.6},
            {"price": ema_20, "type": "ema_pullback", "confidence_base": 0.7},
            {"price": resistance_break, "type": "breakout", "confidence_base": 0.5}
        ],
        "long_stops": [
            {"price": support_1 - atr, "type": "below_support_1atr"},
            {"price": swing_low, "type": "below_swing_low"}
        ],
        "long_targets": [
            {"price": resistance_1, "type": "first_resistance", "rr": 2.0},
            {"price": resistance_2, "type": "major_resistance", "rr": 4.0}
        ]
    }

    return candidates
```

**Stage 2: LLM reasoning (AI)**
```python
prompt = f"""You have pre-calculated scenario candidates.
Your job: select best combinations and explain reasoning.

CANDIDATES (JSON):
{json.dumps(candidates)}

Select 3 scenarios and explain WHY each is valid.
"""
```

**Преимущества:**
- LLM не "придумывает" цены
- Дешевле (меньше работы для LLM)
- Стабильнее (все цены валидные)

---

## 🎯 Метрики для A/B тестирования

После реализации улучшений, сравнить:

1. **Accuracy:** Win rate сценариев (TP1/TP2/TP3 hit rate)
2. **Cost:** Average tokens per request
3. **Stability:** Variance в confidence scores
4. **Speed:** Response time

**Цель:**
- Accuracy: 60% → 75% (TP1 hit rate)
- Cost: $0.05 → $0.03 per request
- Stability: stdev(confidence) < 0.1

---

## ✅ Checklist для реализации

- [ ] Создать `_calculate_price_structure()`
- [ ] Создать `_aggregate_liquidation_clusters()`
- [ ] Переделать промпт на JSON формат
- [ ] Добавить `timeframe` в `_analyze_market_context()`
- [ ] Реализовать dynamic Fear&Greed weight
- [ ] Добавить новые поля в output
- [ ] Обновить JSON schema с scenario_class
- [ ] Написать unit tests
- [ ] A/B тест: старая vs новая версия
- [ ] Deploy в production

---

## 🔗 Связанные документы

- [FUTURES_TRADING_API.md](./FUTURES_TRADING_API.md)
- [FUTURES_API_FINAL_SUMMARY.md](./FUTURES_API_FINAL_SUMMARY.md)
- [PROMPT_ENGINEERING_ANALYSIS_2025.md](./PROMPT_ENGINEERING_ANALYSIS_2025.md)

---

**Статус:** 📋 План готов к реализации
**Приоритет:** 🔴 HIGH (влияет на точность и стоимость)
**Следующий шаг:** Реализовать Phase 1
