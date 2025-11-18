# Premium UI Локализация

## Обзор

Система локализации для Premium подписок полностью реализована с использованием i18n.

## Структура локализационных ключей

### 1. `premium` - Основные тексты
- `title` - Заголовок Premium подписок
- `choose_plan` - "Выберите тариф"
- `select_below` - "Выберите тариф ниже"
- `back_to_menu` - Возврат в меню Premium

### 2. `premium_plans` - Описание тарифов
- `basic.*` - Тариф BASIC (20 запросов/день)
  - `name`, `emoji`, `limit`
  - `feature_1`, `feature_2`, `feature_3`
- `premium.*` - Тариф PREMIUM (100 запросов/день)
  - `name`, `emoji`, `limit`
  - `feature_1`, `feature_2`, `feature_3`, `feature_4`
- `vip.*` - Тариф VIP (безлимит)
  - `name`, `emoji`, `limit`
  - `feature_1`, `feature_2`, `feature_3`, `feature_4`

### 3. `premium_selection` - Выбор длительности
- `tier_selected` - "Выбран тариф: {tier}"
- `limit_label` - "Лимит:"
- `requests_per_day` - "запросов/день"
- `select_duration` - "Выберите длительность подписки"
- `longer_better` - "Чем дольше - тем выгоднее!"

### 4. `premium_purchase` - Оформление покупки
- `invoice_created` - "Счет создан! Оплатите ниже"
- `invoice_error` - "Ошибка создания счета"

### 5. `premium_payment` - Обработка платежа
- `success` - "Оплата успешна!"
- `activated` - "Подписка активирована:"
- `active_until` - "Активна до:"
- `paid` - "Получено"
- `stars` - "Stars"
- `thank_you` - "Спасибо за поддержку!"
- `activation_error` - "Ошибка активации подписки"
- `activation_error_text` - Текст ошибки активации

### 6. `premium_subscription` - Статус подписки
- `no_active` - "У вас нет активной подписки"
- `use_premium` - "Используйте /premium для оформления"
- `expired` - "Ваша подписка истекла"
- `use_renew` - "Используйте /premium для продления"
- `your_subscription` - "Ваша подписка"
- `plan` - "Тариф:"
- `limit` - "Лимит:"
- `expires` - "Истекает:"
- `days_left` - "Осталось дней:"
- `auto_renewal` - "Автопродление:"
- `enabled` - "Включено"
- `disabled` - "Выключено"
- `change_plan` - "Сменить тариф"

### 7. `premium_cancel` - Отмена автопродления
- `no_active` - "У вас нет активной подписки"
- `free_tier` - "У вас бесплатный тариф"
- `already_disabled` - "Автопродление уже отключено"
- `active_until` - "Подписка активна до:"
- `auto_renewal_disabled` - "Автопродление отключено"
- `remains_active` - "Подписка останется активной до:"
- `will_return` - "После этой даты вы вернетесь на бесплатный тариф"

### 8. `tier_names` - Названия тарифов
- `free` - "БЕСПЛАТНЫЙ" / "FREE"
- `basic` - "БАЗОВЫЙ" / "BASIC"
- `premium` - "ПРЕМИУМ" / "PREMIUM"
- `vip` - "VIP"

## Обновленные файлы

### Handlers
1. **src/bot/handlers/premium.py**
   - `cmd_premium()` - /premium команда
   - `get_tier_selection_keyboard()` - клавиатура выбора тарифа
   - `select_tier()` - выбор тарифа
   - `back_to_premium_menu()` - возврат в меню
   - `process_purchase()` - обработка покупки
   - `process_successful_payment()` - успешный платеж
   - `cmd_subscription()` - /subscription команда
   - `cmd_cancel_subscription()` - /cancel_subscription команда

2. **src/bot/handlers/menu.py**
   - `menu_premium_callback()` - обработчик кнопки Premium

### Локализации
1. **src/locales/ru.json** - Русские переводы
2. **src/locales/en.json** - Английские переводы

## Примеры использования

```python
# Получение названия тарифа
tier_name = i18n.get(f"tier_names.{tier_value}", user_language)

# Получение описания функции
feature = i18n.get("premium_plans.basic.feature_1", user_language)

# Построение составного сообщения
text = (
    f"{i18n.get('premium.title', user_language)}\n\n"
    f"{i18n.get('premium.choose_plan', user_language)}"
)

# Параметризированные переводы
text = i18n.get('premium_selection.tier_selected', user_language, tier=tier_name)
```

## Преимущества

✅ **Единый источник правды** - все тексты в JSON файлах
✅ **Легкость поддержки** - легко добавить новый язык
✅ **Консистентность** - одинаковые тексты везде
✅ **Переиспользование** - tier_names используются во всех handlers
✅ **Гибкость** - поддержка параметров в переводах

## Тестирование

```bash
# Проверка синтаксиса handlers
python -m py_compile src/bot/handlers/premium.py
python -m py_compile src/bot/handlers/menu.py

# Проверка валидности JSON
python -c "import json; json.load(open('src/locales/ru.json')); json.load(open('src/locales/en.json'))"
```

## Следующие шаги

- [ ] Добавить локализацию для уведомлений об истечении подписки (subscription_checker.py)
- [ ] Добавить локализацию для Telegram Stars Service (telegram_stars_service.py)
- [ ] Протестировать UI с реальными пользователями
- [ ] Добавить поддержку других языков (если требуется)
