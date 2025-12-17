# Magic Link Verification Crash Fix

**Дата**: 2025-11-25
**Статус**: 🔴 Критическая проблема

## Проблема

Приложение крашится на странице верификации magic link (`/auth/verify`) при попытке верифицировать токен.

### Симптомы

1. **Application error**: "A client-side exception has occurred while loading ai.syntratrade.xyz"
2. **401 ошибка** при запросе `api/auth/magic/verify?token=...`
3. **Failed to load chunk** `/_next/static/chunks/93d8cae8c026fb8e.js`
4. PostHog analytics blocked (не критично)

### Консоль браузера

```
api/auth/magic/verify?token=9hphqd7DC0Q8Mq-zzi0WYDS0Xk7pE42DpFOHZRWf6IU:1
Failed to load resource: the server responded with a status of 401 ()

turbopack-55ca736ac526348c.js:1 Uncaught Error:
Failed to load chunk /_next/static/chunks/93d8cae8c026fb8e.js from module 64893
```

## Анализ причин

### 1. 401 Ошибка верификации

**Причины:**
- Токен magic link истек (срок действия: 15 минут)
- Токен уже был использован (одноразовый)
- Токен неверный или поврежден

**Код проверки** ([src/api/magic_auth.py:274-295](src/api/magic_auth.py#L274-L295)):

```python
# Check if expired
if magic_link.expires_at < datetime.now(UTC):
    raise HTTPException(
        status_code=400,
        detail="Magic link has expired. Please request a new one."
    )

# Check if already used
if magic_link.is_used:
    raise HTTPException(
        status_code=401,
        detail="Magic link has already been used. Please request a new one."
    )
```

### 2. Failed to load chunk (Next.js)

**Причины:**
- Устаревший build Next.js
- Несоответствие между client-side chunks и server-side манифестом
- Проблема с turbopack кэшем

**Как это происходит:**
1. Пользователь получает magic link в email
2. Открывает ссылку `/auth/verify?token=...`
3. Next.js пытается загрузить chunk для страницы
4. Chunk не найден (404) → критическая ошибка → краш

### 3. API URL Routing

**Текущая конфигурация:**

Frontend ([frontend/shared/api/client.ts:13-20](frontend/shared/api/client.ts#L13-L20)):
```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});
```

Environment ([frontend/.env.production:5](frontend/.env.production#L5)):
```env
NEXT_PUBLIC_API_URL=https://ai.syntratrade.xyz
```

Backend router ([src/api/router.py:39](src/api/router.py#L39)):
```python
router.include_router(magic_auth_router)  # Prefix: /auth/magic
```

**Полный путь endpoint:**
```
https://ai.syntratrade.xyz/api/auth/magic/verify?token=...
```

## Решение

### 1. Исправить Error Handling для Expired Tokens

**Проблема**: В [frontend/app/auth/verify/page.tsx:86-92](frontend/app/auth/verify/page.tsx#L86-L92) не различаются типы ошибок:

```typescript
} catch (err: any) {
  setStatus('error');
  const errorMessage = err?.response?.data?.detail || err?.message || 'Network error. Please try again.';
  setError(errorMessage);
  console.error('Verification error:', err);
}
```

**Решение**: Добавить специальную обработку для 401 ошибки (уже использован токен).

### 2. Очистить и пересобрать Next.js Build

**Команды для исправления:**

```bash
cd frontend

# Очистить все кэши Next.js
rm -rf .next
rm -rf node_modules/.cache

# Пересобрать production build
npm run build

# Перезапустить
pm2 restart frontend
```

### 3. Добавить Better UX для Expired Links

**Текущая реализация:**
- Показывает общую ошибку "Verification error"
- Нет автоматического redirect на login page

**Предложение:**
- Показать специальное сообщение для expired/used tokens
- Кнопка "Request new magic link"
- Автоматический redirect через 10 секунд

### 4. Добавить Logging для Debug

**Backend** ([src/api/magic_auth.py](src/api/magic_auth.py)):

```python
# После строки 275 добавить:
logger.warning(
    f"⚠️ Magic link verification failed: token={token[:10]}... "
    f"expired={magic_link.expires_at < datetime.now(UTC)}, "
    f"used={magic_link.is_used}"
)
```

**Frontend** ([frontend/app/auth/verify/page.tsx](frontend/app/auth/verify/page.tsx)):

```typescript
console.error('Verification error:', {
  status: err?.response?.status,
  detail: err?.response?.data?.detail,
  token: token.substring(0, 10) + '...'
});
```

## Action Plan

- [ ] Очистить Next.js build и кэши
- [ ] Пересобрать frontend с production env
- [ ] Перезапустить frontend на сервере
- [ ] Добавить better error handling для expired tokens
- [ ] Добавить logging для debug
- [ ] Протестировать flow с новым magic link

## Testing

**Тестовый сценарий:**

1. Запросить новый magic link через `/auth/login`
2. Проверить email
3. Кликнуть на ссылку
4. Должен произойти успешный redirect на `/chat`
5. Попытаться использовать ту же ссылку повторно → должна показаться понятная ошибка

## Превентивные меры

1. **Health check** для Next.js chunks
2. **Версионирование** static assets
3. **Fallback UI** при ошибках загрузки
4. **Better monitoring** для magic link verification

## Related Files

- [frontend/app/auth/verify/page.tsx](frontend/app/auth/verify/page.tsx) - Страница верификации
- [frontend/shared/api/client.ts](frontend/shared/api/client.ts) - API client
- [src/api/magic_auth.py](src/api/magic_auth.py) - Backend API для magic links
- [src/api/router.py](src/api/router.py) - FastAPI router
- [frontend/.env.production](frontend/.env.production) - Environment variables

## Заметки

- Magic links одноразовые (security best practice)
- Срок действия 15 минут (balance между security и UX)
- После успешной верификации токен помечается как использованный
- JWT токен для web платформы действует 30 дней
