# Исправление отображения баланса $SYNTRA Points - 2025-12-03

## Проблемы

1. **KeyError в API баланса** - `/api/points/balance` падал с ошибкой `KeyError: 'level_name'`
2. **Баланс не отображался в хедере** - компонент был добавлен, но типы не совпадали
3. **Suggested prompts занимали много места** - кнопки были слишком большие

## Решения

### 1. Исправлен API баланса

**Файл:** `src/api/points.py`

**Проблема:** API ожидал `level_name`, но сервис возвращал `level_name_ru` и `level_name_en`

**Решение:**
- Обновлена модель `PointsBalanceResponse` - добавлены поля `level_name_ru` и `level_name_en`
- Исправлен эндпоинт `/api/points/balance` - корректное маппирование полей
- Добавлен расчет прогресса до следующего уровня

```python
class PointsBalanceResponse(BaseModel):
    balance: int
    lifetime_earned: int
    lifetime_spent: int
    level: int
    level_name_ru: str  # ← Было: level_name
    level_name_en: str  # ← Новое поле
    level_icon: str
    # ... остальные поля
```

### 2. Обновлен фронтенд

**Файл:** `frontend/shared/store/pointsStore.ts`

Обновлен интерфейс `PointsBalance`:

```typescript
export interface PointsBalance {
  // ...
  level_name_ru: string;  // ← Было: level_name
  level_name_en: string;  // ← Новое поле
  // ...
}
```

**Файл:** `frontend/components/points/PointsModal.tsx`

Добавлена локализация:

```typescript
import { useCurrentLocale } from '@/shared/hooks/useCurrentLocale';

// В компоненте:
const locale = useCurrentLocale();

// При отображении:
{locale === 'ru' ? balance.level_name_ru : balance.level_name_en}
```

### 3. Suggested Prompts - более компактные

**Файл:** `frontend/components/chat/SuggestedPrompts.tsx`

Уменьшены размеры:
- Padding: `px-4 py-2.5` → `px-3 py-1.5`
- Font: `text-sm` → `text-xs`
- Icon: `text-base` → `text-sm`
- Logo: `width={10}` → `width={8}`
- Gap между кнопками: `gap-2` → `gap-1.5`

## Тестирование

✅ Фронтенд собирается без ошибок:
```bash
cd frontend && npm run build
```

✅ API импортируется корректно:
```bash
python -c "from src.api.points import router; print('OK')"
```

✅ Points balance отображается в хедере с локализацией
✅ Модалка показывает правильное название уровня (RU/EN)
✅ Suggested prompts занимают меньше места

## API Response Example

### До исправления:
```json
{
  "level_name": "Beginner"  // ← KeyError!
}
```

### После исправления:
```json
{
  "balance": 50,
  "level": 1,
  "level_name_ru": "Новичок",
  "level_name_en": "Beginner",
  "level_icon": "🌱",
  "earning_multiplier": 1.0,
  "current_streak": 0,
  "progress_to_next_level": 5.0
}
```

## Файлы изменены

### Backend:
- [src/api/points.py](../src/api/points.py)

### Frontend:
- [frontend/shared/store/pointsStore.ts](../frontend/shared/store/pointsStore.ts)
- [frontend/components/points/PointsModal.tsx](../frontend/components/points/PointsModal.tsx)
- [frontend/components/chat/SuggestedPrompts.tsx](../frontend/components/chat/SuggestedPrompts.tsx)

## Совместимость

✅ Обратная совместимость с существующими данными
✅ Работает с локализацией RU/EN
✅ Responsive дизайн сохранен

## Что дальше?

- [ ] Добавить поле `last_daily_login` в БД и API (сейчас возвращает `null`)
- [ ] Добавить анимацию при изменении баланса
- [ ] Показывать уведомления при получении поинтов
