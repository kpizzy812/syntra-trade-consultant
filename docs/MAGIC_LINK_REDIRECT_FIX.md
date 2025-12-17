# Magic Link Authentication Redirect Fix

**Дата:** 2025-11-25
**Проблема:** После успешной авторизации через magic link происходит редирект обратно на `/auth/choose`

## Описание проблемы

### Симптомы
1. Пользователь переходит по magic link из email
2. Страница `/auth/verify` успешно проверяет токен
3. JWT токен сохраняется в localStorage
4. Происходит редирект на `/chat`
5. **Сразу после редиректа** происходит повторный редирект на `/auth/choose`

### Ошибка в консоли
```
❌ User not authenticated, redirecting to /auth/choose
```

## Анализ причины

### Flow авторизации
1. **Verify страница** (`frontend/app/auth/verify/page.tsx:76-77`):
   ```typescript
   localStorage.setItem('auth_token', data.token);
   localStorage.setItem('user', JSON.stringify(data.user));
   ```

2. **Редирект на /chat** (строка 83):
   ```typescript
   router.push('/chat');
   ```

3. **Auth Guard на /chat** (`frontend/app/chat/page.tsx:61`):
   ```typescript
   const { isChecking, isAuthenticated } = useAuthGuard();
   ```

4. **Валидация токена** (`frontend/shared/hooks/useAuthGuard.ts:78`):
   ```typescript
   const response = await api.auth.validateToken();
   ```

5. **Проверка ответа** (строка 80):
   ```typescript
   if (response && response.user) {
     setIsAuthenticated(true);
   } else {
     clearAuth(); // ❌ Проблема здесь
   }
   ```

### Корневая причина

**Backend endpoint** `/api/user/profile` (`src/api/router.py:121-150`) возвращал НЕПРАВИЛЬНЫЙ формат:

```python
# ❌ БЫЛО (неправильно):
return {
    "id": user.id,
    "telegram_id": user.telegram_id,
    "username": user.username,
    ...
}
```

**Frontend** ожидал формат с ключом `user`:
```typescript
if (response && response.user) {  // response.user === undefined
```

Результат: `response.user` был `undefined`, токен считался невалидным и удалялся.

## Решение

### Изменение в backend

**Файл:** `src/api/router.py:121-154`

```python
# ✅ СТАЛО (правильно):
@router.get("/user/profile")
async def get_user_profile(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get current user profile

    Requires: Authorization header with valid initData or JWT token

    Returns:
        {
            "user": {  # ← Добавлен ключ "user"
                "id": 1,
                "telegram_id": 123456,
                "username": "john_doe",
                ...
            }
        }
    """
    return {
        "user": {  # ← Обернули данные в объект с ключом "user"
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language": user.language,
            "is_premium": user.is_premium,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
    }
```

### Изменения в документации

Обновлена документация endpoint'а чтобы отражать правильный формат ответа:
- Добавлено: `Requires: Authorization header with valid initData or JWT token`
- Исправлен формат возвращаемых данных в docstring

## Проверка работоспособности

### 1. Проверка через curl (с валидным JWT токеном)

```bash
# Получить JWT токен после magic link авторизации
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Проверить endpoint
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8003/api/user/profile
```

Ожидаемый ответ:
```json
{
  "user": {
    "id": 123,
    "email": "user@example.com",
    "first_name": null,
    "language": "en",
    "is_premium": false,
    "created_at": "2025-11-25T12:00:00"
  }
}
```

### 2. Проверка через браузер

1. Открыть https://ai.syntratrade.xyz/auth/login
2. Ввести email и запросить magic link
3. Перейти по ссылке из email
4. Убедиться что НЕТ редиректа на `/auth/choose`
5. Проверить консоль браузера - ошибки `❌ User not authenticated` быть НЕ должно

### 3. Проверка localStorage

Открыть DevTools → Application → Local Storage:
- `auth_token` должен содержать JWT токен
- `user` должен содержать JSON объект с данными пользователя

## Связанные файлы

### Backend
- [src/api/router.py:121-154](../src/api/router.py) - Исправленный endpoint
- [src/api/auth.py:187-269](../src/api/auth.py) - get_current_user (поддержка JWT)
- [src/api/magic_auth.py:235-340](../src/api/magic_auth.py) - Verify endpoint

### Frontend
- [frontend/shared/hooks/useAuthGuard.ts](../frontend/shared/hooks/useAuthGuard.ts) - Auth guard hook
- [frontend/app/auth/verify/page.tsx](../frontend/app/auth/verify/page.tsx) - Magic link verification
- [frontend/app/chat/page.tsx](../frontend/app/chat/page.tsx) - Chat page с auth guard
- [frontend/shared/api/client.ts:151-166](../frontend/shared/api/client.ts) - validateToken method

## Примечания

- ✅ Backend поддерживает как Telegram initData, так и JWT токены
- ✅ Формат ответа теперь консистентен между всеми auth методами
- ✅ Auto-reload в uvicorn автоматически применяет изменения
- ⚠️ Убедитесь что `NEXTAUTH_SECRET` в `.env` совпадает на frontend и backend
