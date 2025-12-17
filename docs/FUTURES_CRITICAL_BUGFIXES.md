# 🐛 Futures AI Engine - Critical Bugfixes

**Дата:** 2025-12-15
**Файл:** `src/services/futures_analysis_service.py`
**Статус:** ✅ **ALL FIXED**

---

## Исправленные критичные баги

### 🔧 Bug #1: volatility_regime - very_low недостижим

**Проблема:**
```python
# СТАРЫЙ КОД (НЕПРАВИЛЬНО)
if atr_pct > 3.0:
    volatility_regime = "very_high"
elif atr_pct > 2.5:
    volatility_regime = "expansion"
elif atr_pct < 1.5:
    volatility_regime = "compression"  # Выполнится для atr_pct < 1.5
elif atr_pct < 1.0:
    volatility_regime = "very_low"     # ❌ НИКОГДА не случится!
```

`atr_pct < 1.0` всегда попадает в `< 1.5`, поэтому `very_low` мёртвый код.

**Решение:**
```python
# НОВЫЙ КОД (ПРАВИЛЬНО)
if atr_pct > 3.0:
    volatility_regime = "very_high"
elif atr_pct > 2.5:
    volatility_regime = "expansion"
elif atr_pct < 1.0:        # ✅ Сначала очень низкий
    volatility_regime = "very_low"
elif atr_pct < 1.5:        # ✅ Потом просто низкий
    volatility_regime = "compression"
else:
    volatility_regime = "normal"
```

**Impact:** 🟢 Теперь very_low корректно определяется

---

### 🔧 Bug #2: swing_highs берёт самые высокие по цене, а не последние

**Проблема:**
```python
# СТАРЫЙ КОД (НЕПРАВИЛЬНО)
swing_highs.append({
    "price": round(price, 2),
    "distance_pct": round(distance_pct, 2)
})

# Сортируем по ЦЕНЕ - берём самые высокие!
structure["swing_highs"] = sorted(swing_highs, key=lambda x: x["price"], reverse=True)[:5]
```

Это даёт топ-5 **самых высоких цен**, а не **последние 5 свингов** по времени. В реальном трейде важнее актуальные свинги.

**Решение:**
```python
# НОВЫЙ КОД (ПРАВИЛЬНО)
swing_highs.append({
    "price": round(price, 2),
    "distance_pct": round(distance_pct, 2),
    "idx": i  # ✅ Сохраняем индекс для сортировки по времени
})

# Сортируем по ВРЕМЕНИ - берём последние!
structure["swing_highs"] = sorted(swing_highs, key=lambda x: x["idx"], reverse=True)[:5]
```

**Impact:** 🟢 Теперь берутся актуальные swing points, а не исторические максимумы

---

### 🔧 Bug #3: liquidation binning - round() прыгает

**Проблема:**
```python
# СТАРЫЙ КОД
bin_size = current_price * 0.01  # 1% bins (слишком грубо)
bin_key = round(price / bin_size) * bin_size  # ❌ Может прыгнуть вверх/вниз
```

`round()` может неожиданно перекинуть bin:
- `round(95.5) = 96` (вверх)
- `round(95.4) = 95` (вниз)

**Решение:**
```python
# НОВЫЙ КОД
import math
bin_size = current_price * 0.005  # ✅ 0.5% bins (лучше точность)
bin_key = math.floor(price / bin_size) * bin_size  # ✅ Предсказуемо
```

**Impact:** 🟢 Более точная кластеризация ликвидаций

---

### 🔧 Bug #4: spike detection - hours_in_data < 1 взрывает avg

**Проблема:**
```python
# СТАРЫЙ КОД
hours_in_data = (now - min([l.get("time", now) for l in liquidations])) / (60 * 60 * 1000)
avg_hourly_volume = total_volume / hours_in_data  # ❌ Если hours_in_data = 0.1, взрыв!
```

Если ликвидации только за 6 минут (0.1 часа), `avg_hourly_volume` взлетит в 10x!

**Решение:**
```python
# НОВЫЙ КОД
hours_in_data = (now - min([l.get("time", now) for l in liquidations])) / (60 * 60 * 1000)
hours_in_data = max(hours_in_data, 1.0)  # ✅ Минимум 1 час
avg_hourly_volume = total_volume / hours_in_data
```

**Impact:** 🟢 Стабильная spike detection

---

### 🔧 Bug #5: net_liq_bias - путаница в нейминге

**Проблема:**
```python
# СТАРЫЙ КОД
net_bias = "short"  # Много long'ов ликвидировано
```

Название `net_liq_bias` читается как "в какую сторону лонговать", но по факту это "давление от ликвидаций". Путаница!

**Решение:**
```python
# НОВЫЙ КОД
liq_pressure = "bearish"  # ✅ Ясно: bearish давление от ликвидации long'ов

result = {
    ...
    "liq_pressure_bias": liq_pressure  # ✅ Renamed
}
```

**Impact:** 🟢 LLM и разработчики не путаются

---

### 🔧 Bug #6: Empty candidates → LLM галлюцинирует

**Проблема:**
```python
# СТАРЫЙ КОД
supports = key_levels.get("support", [])  # ❌ Может быть []!
resistances = key_levels.get("resistance", [])  # ❌ Может быть []!

# В промпте: "Use support_candidates" - но они пустые!
# LLM начинает сочинять цены из головы
```

**Решение:**
```python
# НОВЫЙ КОД
# Fallback #1: Из swing points
if not supports and price_structure:
    swing_lows = price_structure.get("swing_lows", [])
    supports = [sl["price"] for sl in swing_lows]

# Fallback #2: Из range/ema/vwap
if not supports:
    fallback_supports = []
    if price_structure:
        range_low = price_structure.get("range_low")
        if range_low:
            fallback_supports.append(range_low)
    if ema_levels:
        for ema in ["ema_20", "ema_50", "ema_200"]:
            ema_val = ema_levels.get(ema, {}).get("price")
            if ema_val and ema_val < current_price:
                fallback_supports.append(ema_val)
    supports = sorted(fallback_supports, reverse=True)[:5]

# Также добавляем swing candidates явно в levels
"levels": {
    "support_candidates": [round(s, 2) for s in supports[:5]],
    "resistance_candidates": [round(r, 2) for r in resistances[:5]],
    "swing_high_candidates": [...],  # ✅ NEW
    "swing_low_candidates": [...]    # ✅ NEW
}
```

**Impact:** 🟢 LLM всегда имеет candidates и не галлюцинирует

---

### 🔧 Bug #7: timeframe map неполный

**Проблема:**
```python
# СТАРЫЙ КОД
time_valid_hours_map = {
    "15m": 4,
    "1h": 6,
    "4h": 48,
    "1d": 168
}
time_valid_hours = time_valid_hours_map.get(timeframe, 24)  # ❌ Что если "6h"? "30m"?
```

Если прилетит `6h`, `12h`, `30m` → fallback на `24` (некорректно).

**Решение:**
```python
# НОВЫЙ КОД - Динамический парсинг
if timeframe.endswith("m"):
    minutes = int(timeframe[:-1])
    tf_hours = minutes / 60.0
elif timeframe.endswith("h"):
    tf_hours = int(timeframe[:-1])
elif timeframe.endswith("d"):
    days = int(timeframe[:-1])
    tf_hours = days * 24
elif timeframe.endswith("w"):
    weeks = int(timeframe[:-1])
    tf_hours = weeks * 168
else:
    tf_hours = 24  # Default

# Validity = 12x timeframe
time_valid_hours = round(tf_hours * 12)

# Cap минимум/максимум
time_valid_hours = max(2, min(time_valid_hours, 336))  # От 2ч до 2 недель
```

**Impact:** 🟢 Поддержка любых timeframes (15m, 30m, 6h, 12h, etc.)

---

## 📊 Итоговый результат

### Исправленные файлы
- `src/services/futures_analysis_service.py`

### Количество исправлений
- **7 критичных багов**
- **~80 строк кода изменено**

### Улучшения
1. ✅ **volatility_regime** - теперь all cases покрыты
2. ✅ **swing points** - актуальные, а не исторические максимумы
3. ✅ **liquidation binning** - точнее (0.5% вместо 1%) и предсказуемее (floor вместо round)
4. ✅ **spike detection** - стабильная (min 1 hour)
5. ✅ **naming** - liq_pressure_bias вместо net_liq_bias (ясно)
6. ✅ **fallback candidates** - LLM всегда имеет уровни
7. ✅ **timeframe support** - любые TF (15m, 30m, 6h, 12h, 1w, etc.)

---

## 🚀 Следующие шаги

1. **Тестирование** на реальных данных
2. **Мониторинг** метрик:
   - Частота `very_low` volatility (должна появиться)
   - Актуальность swing points
   - Точность liquidation clusters
   - Стабильность spike detection

---

**Статус:** ✅ **DONE**
**Приоритет:** 🔴 **CRITICAL**
**Следующий шаг:** Testing в production
