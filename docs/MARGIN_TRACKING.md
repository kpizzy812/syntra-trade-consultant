# Real-time Margin Tracking

## 🎯 Назначение

Модуль `src/services/margin_calculator.py` анализирует **РЕАЛЬНЫЕ** данные из БД для расчета маржи проекта, а не теоретические предположения.

---

## 🔍 Проблема

### ❌ Старый подход (теоретический):
```python
# Догадки и предположения
avg_cost_per_request = 0.00648  # Откуда эта цифра?
usage_percent = 0.40             # Все используют 40%?
monthly_cost = limit * 30 * usage_percent * avg_cost_per_request
```

**Проблемы:**
- Неизвестно реальное использование API
- Неизвестна реальная стоимость запросов
- Невозможно найти убыточных пользователей
- Нельзя оптимизировать ревшар на фактах

### ✅ Новый подход (реальные данные):
```python
# Факты из БД
costs = await get_real_costs_per_user(session, user_id, days=30)
# {
#   'total_cost': 8.50,           # Реальные затраты из ChatMessage
#   'request_count': 850,         # Фактическое количество запросов
#   'avg_cost_per_request': 0.01, # Рассчитано из фактов
# }
```

---

## 📊 Источники данных

### 1. ChatMessage таблица
Каждый запрос к OpenAI сохраняется с метриками:
```sql
SELECT
  COUNT(*) as request_count,
  SUM(total_tokens) as total_tokens,
  SUM(total_cost) as total_cost
FROM chat_messages
WHERE user_id = ? AND created_at >= ?
```

### 2. Payment таблица
Реальная выручка от пользователя:
```sql
SELECT SUM(amount) as revenue
FROM payments
WHERE user_id = ?
  AND status = 'completed'
  AND completed_at >= ?
```

### 3. User таблица
Метрики реферальной программы:
- `referral_balance` - текущий баланс
- `total_referral_earnings` - всего выплачено

---

## 🛠 API

### `get_real_costs_per_user(session, user_id, days=30)`

Получить **РЕАЛЬНЫЕ** затраты на пользователя за период.

**Returns:**
```python
{
    'total_cost': 12.50,           # Общие затраты в USD
    'request_count': 850,          # Количество запросов
    'avg_cost_per_request': 0.0147, # Средняя стоимость запроса
    'total_tokens': 125000,        # Всего токенов
}
```

**Пример:**
```python
from src.services.margin_calculator import get_real_costs_per_user

costs = await get_real_costs_per_user(session, user_id=123, days=30)
print(f"User spent ${costs['total_cost']:.2f} in last 30 days")
```

---

### `get_real_margin_for_subscription(session, user_id, days=30)`

Рассчитать **РЕАЛЬНУЮ** маржу для подписки пользователя.

**Returns:**
```python
{
    'subscription_price': 24.99,
    'real_cost': 8.50,
    'margin_usd': 16.49,
    'margin_percent': 66.0,
    'usage_percent': 45.0,  # Реальный % использования
    'is_profitable': True,
}
```

**Пример:**
```python
from src.services.margin_calculator import get_real_margin_for_subscription

margin = await get_real_margin_for_subscription(session, user_id=123)
if not margin['is_profitable']:
    print(f"⚠️ User {user_id} is unprofitable! Margin: {margin['margin_percent']}%")
```

---

### `get_global_margin_analytics(session, days=30)`

Получить глобальную аналитику маржи для **всего проекта**.

**Returns:**
```python
{
    'total_revenue': 1249.50,
    'total_costs': 425.30,
    'total_margin': 824.20,
    'margin_percent': 65.96,
    'avg_margin_per_user': 16.48,
    'users_analyzed': 50,
    'profitable_users': 45,
    'unprofitable_users': 5,
    'total_revshare_paid': 124.95,
    'effective_revshare_percent': 10.0,
    'recommended_revenue_share': 7.95,  # 🎯 На основе реальных данных!
}
```

**Пример:**
```python
from src.services.margin_calculator import get_global_margin_analytics

analytics = await get_global_margin_analytics(session, days=30)

print(f"📊 Total margin: ${analytics['total_margin']:.2f} ({analytics['margin_percent']:.1f}%)")
print(f"🤝 Recommended revshare: {analytics['recommended_revenue_share']:.2f}%")

if analytics['margin_percent'] < 50:
    print("⚠️ Low margin! Need to optimize costs or reduce revshare")
```

---

### `get_margin_by_tier(session, days=30)`

Получить маржу по каждому тиру подписки.

**Returns:**
```python
{
    'basic': {
        'users': 20,
        'revenue': 99.80,
        'costs': 30.50,
        'margin_usd': 69.30,
        'margin_percent': 69.4,
    },
    'premium': {
        'users': 25,
        'revenue': 624.75,
        'costs': 187.43,
        'margin_usd': 437.32,
        'margin_percent': 70.0,
    },
    'vip': {
        'users': 5,
        'revenue': 249.95,
        'costs': 75.20,
        'margin_usd': 174.75,
        'margin_percent': 69.9,
    },
}
```

**Пример:**
```python
from src.services.margin_calculator import get_margin_by_tier

tier_data = await get_margin_by_tier(session, days=30)

for tier_name, data in tier_data.items():
    print(f"{tier_name.upper()}: {data['margin_percent']:.1f}% margin with {data['users']} users")
```

---

### `check_margin_alerts(session, threshold_percent=30.0)`

Проверить пользователей с низкой маржой (**алерты**).

**Returns:**
```python
{
    'threshold_percent': 30.0,
    'low_margin_users': [
        {
            'user_id': 123,
            'telegram_id': 123456789,
            'username': '@john',
            'margin_percent': 25.5,
            'margin_usd': 6.38,
            'cost': 18.61,
            'revenue': 24.99,
        },
        # ...
    ],
    'alert_count': 3,
}
```

**Пример:**
```python
from src.services.margin_calculator import check_margin_alerts

alerts = await check_margin_alerts(session, threshold_percent=30.0)

if alerts['alert_count'] > 0:
    print(f"⚠️ {alerts['alert_count']} users with low margin!")

    for user in alerts['low_margin_users']:
        print(f"User {user['username']}: {user['margin_percent']:.1f}% margin")

        if user['margin_percent'] < 20:
            # Критически низкая маржа - нужно действовать!
            logger.warning(f"CRITICAL: User {user['telegram_id']} needs attention!")
```

---

## 💻 Админ команда

### `/admin_margin`

Показывает real-time margin analytics в Telegram.

**Что показывает:**

1. **Глобальные метрики** (за последние 30 дней):
   - Выручка, расходы, маржа (USD и %)
   - Средняя маржа на пользователя
   - Количество прибыльных/убыточных пользователей

2. **Revenue Share метрики**:
   - Сколько реально выплачено реферерам
   - Эффективный % ревшара (фактический)
   - **Рекомендуемый % на основе РЕАЛЬНЫХ данных**

3. **Маржа по тирам**:
   - BASIC, PREMIUM, VIP
   - Revenue vs Costs для каждого
   - Маржа в USD и %

4. **Алерты**:
   - Пользователи с маржой <30%
   - Top 5 проблемных юзеров
   - Детали: revenue, cost, margin

**Пример вывода:**
```
💰 Real-time Margin Analytics
Период: последние 30 дней

📊 Глобальные метрики:
├ Выручка: $1,249.50
├ Расходы: $425.30
├ Маржа: $824.20 (65.9%)
├ Средняя маржа/юзер: $16.48
└ Пользователей: 50 (45 прибыльных)

🤝 Revenue Share:
├ Выплачено: $124.95
├ Эффективный %: 10.0%
└ Рекомендуемый %: 7.95%
   (на основе реальных данных)

🎯 Маржа по тирам:
🟢 BASIC (20 users):
   Revenue: $99.80 | Costs: $30.50
   Margin: $69.30 (69.4%)

⚠️ Алерты (маржа <30%):
Найдено пользователей: 2
```

---

## 🧮 Алгоритм расчета рекомендуемого ревшара

```python
# 1. Получить реальную маржу из БД
actual_margin = 65.9%  # Из фактических данных

# 2. Целевая маржа (минимум который хотим сохранить)
target_margin = 50.0%

# 3. Доступная маржа для ревшара
available_margin = actual_margin - target_margin = 15.9%

# 4. Ревшар = 50% от доступной маржи (остальное - резерв)
recommended_revshare = available_margin * 0.5 = 7.95%

# 5. Применить границы
recommended_revshare = max(5%, min(20%, recommended_revshare))
```

**Логика:**
- Если **маржа высокая** (>60%) → можно повысить ревшар
- Если **маржа низкая** (<50%) → нужно снизить ревшар
- Если **маржа критическая** (<30%) → отключить ревшар или оптимизировать

---

## 🎯 Use Cases

### 1. Мониторинг здоровья проекта
```python
analytics = await get_global_margin_analytics(session, days=30)

if analytics['margin_percent'] < 40:
    send_alert_to_admin("⚠️ Low margin! Need to optimize")
```

### 2. Динамическая корректировка ревшара
```python
analytics = await get_global_margin_analytics(session, days=7)
recommended = analytics['recommended_revenue_share']

# Обновить config/referral_config.py
REFERRAL_TIERS['gold']['revenue_share_percent'] = recommended
```

### 3. Поиск проблемных пользователей
```python
alerts = await check_margin_alerts(session, threshold_percent=20.0)

for user in alerts['low_margin_users']:
    # Ограничить лимит или предложить upgrade
    await reduce_user_limit(user['user_id'])
```

### 4. Отчеты для инвесторов
```python
tier_data = await get_margin_by_tier(session, days=90)
analytics = await get_global_margin_analytics(session, days=90)

generate_investor_report(analytics, tier_data)
```

---

## ✅ Преимущества

1. **Точность** - данные из БД, а не догадки
2. **Real-time** - актуальная информация
3. **Actionable** - можно принимать решения на основе фактов
4. **Scalable** - работает с любым количеством пользователей
5. **Automatic** - рекомендации по оптимизации ревшара

---

## 📝 Лог операций

Все операции логируются:

```
INFO: Margin analytics requested by admin 12345
INFO: Analyzed 50 users, margin: 65.9%, recommended revshare: 7.95%
WARNING: 2 users with margin <30%
WARNING: User 123456789 has 25.5% margin - needs attention
```

---

## 🔐 Безопасность

- ✅ Доступ только для админов (middleware проверка)
- ✅ Все запросы логируются
- ✅ Проверка существования данных
- ✅ Обработка ошибок БД

---

## 🚀 Будущие улучшения

1. **Автоматические действия при low margin**:
   - Auto-reduce лимитов для убыточных пользователей
   - Email алерты админу
   - Предложение upgrade подписки

2. **Предиктивная аналитика**:
   - Прогноз маржи на следующий месяц
   - Seasonal patterns
   - Churn prediction

3. **Оптимизация промптов**:
   - Анализ каких промптов стоят дороже всего
   - Рекомендации по prompt caching
   - Model routing optimization

4. **Dashboard визуализация**:
   - Графики маржи по времени
   - Breakdown по моделям (GPT-4o vs mini)
   - Cost per feature analysis

---

Готово! Теперь у проекта есть **real-time margin tracking** на основе фактических данных! 🎉
