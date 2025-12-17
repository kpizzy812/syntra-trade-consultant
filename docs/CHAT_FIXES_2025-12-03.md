# Исправления чата - 2025-12-03

## Проблемы

### 1. ❌ Горизонтальный скролл чата
**Симптом:** Чат мог прокручиваться влево-вправо при отображении широкого контента (таблицы, код)

**Причина:** Отсутствовал `overflow-x: hidden` на контейнерах чата

**Исправление:**
- [frontend/components/chat/MessageList.tsx:46](frontend/components/chat/MessageList.tsx#L46) - добавлен `overflow-x-hidden`
- [frontend/app/chat/page.tsx:540](frontend/app/chat/page.tsx#L540) - добавлен `overflow-x-hidden`

### 2. ❌ Сообщения не сохранялись в историю для FREE tier
**Симптом:** После перезагрузки страницы история чата терялась для бесплатных пользователей

**Причина:** В конфиге FREE tier был `"save_chat_history": False`

**Код проверки в backend:**
```python
# src/services/openai_service.py:368-381
if should_save_chat_history(tier_enum):
    if chat_id:
        await add_chat_message_to_chat(
            session, chat_id=chat_id, role="user", content=user_message
        )
```

**Исправление:**
- [config/limits.py:31](config/limits.py#L31) - изменено `"save_chat_history": True`

**Важно:** `chat_history_messages: 0` остался без изменений - это правильно!
- `save_chat_history: True` = сохранять сообщения в БД (для UI истории чатов)
- `chat_history_messages: 0` = не загружать контекст в промпт (экономия токенов)

## Технические детали

### Логика сохранения (backend)
1. **При отправке сообщения** (`/api/chat/stream`):
   - Проверяется `should_save_chat_history(tier)`
   - Если `True` → сохраняется user message через `add_chat_message_to_chat()`
   - После генерации → сохраняется assistant message

2. **При загрузке истории** (`/api/chats/{chat_id}/messages`):
   - Возвращаются все сохраненные сообщения из БД
   - Не зависит от `chat_history_messages` (это для контекста промпта)

### Разница между параметрами
- `save_chat_history` - сохранять ли сообщения в БД вообще
- `chat_history_messages` - сколько сообщений загружать в контекст для AI

**Для FREE tier:**
- `save_chat_history: True` ✅ - сохраняем в БД для UI
- `chat_history_messages: 0` ✅ - не загружаем в промпт (экономия)

## Проверка

### Frontend build
```bash
cd frontend && npm run build
```
✅ Успешно собран без ошибок

### Тестирование
1. Отправить сообщение в чат (FREE tier)
2. Перезагрузить страницу
3. ✅ История должна загрузиться из БД

## Файлы изменены

1. `frontend/components/chat/MessageList.tsx` - добавлен `overflow-x-hidden`
2. `frontend/app/chat/page.tsx` - добавлен `overflow-x-hidden`
3. `config/limits.py` - включено сохранение истории для FREE tier

## Влияние на производительность

### Хранение данных
- **Раньше:** FREE tier не сохранял сообщения → БД не росла
- **Теперь:** FREE tier сохраняет сообщения → рост БД ~1 KB/день на юзера

### Затраты на токены
- **Не изменились:** `chat_history_messages: 0` → контекст не передается в API
- FREE tier по-прежнему платит только за current message

### Оценка
При 10,000 FREE юзеров:
- Сообщений в день: ~10,000 (1 запрос/день)
- Размер БД: ~10 MB/день = ~300 MB/месяц
- **Приемлемо** для текущей инфраструктуры

## Next Steps

1. Мониторить размер таблицы `chat_messages` в БД
2. Рассмотреть архивацию старых сообщений (>90 дней) для FREE tier
3. Добавить лимит на количество чатов для FREE tier (например, max 5 чатов)
