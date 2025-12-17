# Stream Message Authentication Fix

**Дата:** 2025-11-25
**Проблема:** `Failed to send message: Error: No init data available`

## 🐛 Описание проблемы

При отправке сообщений в веб-версии приложения (не в Telegram Mini App) возникала ошибка:
```
Failed to send message: Error: No init data available
```

### Причина
Функции `streamMessage` и `regenerateMessage` в `frontend/shared/api/client.ts` использовали **только** Telegram initData для авторизации:

```typescript
const initData = useUserStore.getState().initData;
if (!initData) {
  throw new Error('No init data available');
}
```

Это работало только в Telegram Mini App, но **не работало** для web-пользователей, авторизованных через Magic Link.

## ✅ Решение

### 1. Обновлены функции streamMessage и regenerateMessage

Теперь обе функции поддерживают **мультиплатформенную авторизацию**:

```typescript
// Get platform-specific credentials
const credentials = await getPlatformCredentials();

// Determine authorization header
let authHeader = '';
if (credentials?.telegram_initData) {
  authHeader = `tma ${credentials.telegram_initData}`;
} else if (credentials?.auth_token) {
  authHeader = `Bearer ${credentials.auth_token}`;
} else if (typeof window !== 'undefined') {
  // Fallback: check localStorage
  const authToken = localStorage.getItem('auth_token');
  if (authToken) {
    authHeader = `Bearer ${authToken}`;
  } else {
    // Legacy: check Telegram initData in store
    const initData = useUserStore.getState().initData;
    if (initData) {
      authHeader = `tma ${initData}`;
    }
  }
}

if (!authHeader) {
  throw new Error('No authentication credentials available');
}
```

### 2. Схема приоритетов авторизации

```
1. getPlatformCredentials() → Telegram initData
                           → Web JWT token
2. localStorage.getItem('auth_token') → Web JWT fallback
3. useUserStore.getState().initData → Legacy Telegram fallback
```

## 🎯 Результат

- ✅ **Telegram Mini App** — работает как раньше (`tma ${initData}`)
- ✅ **Web (Magic Link)** — теперь работает (`Bearer ${token}`)
- ✅ **Streaming** — работает на обеих платформах
- ✅ **Regenerate** — работает на обеих платформах

## 📝 Изменённые файлы

- `frontend/shared/api/client.ts` (строки 209-253, 298-340)

## 🧪 Тестирование

### Telegram Mini App
1. Открыть бот в Telegram
2. Отправить сообщение
3. ✅ Должно работать

### Web (Desktop/Mobile)
1. Открыть https://syntra.ai
2. Авторизоваться через Magic Link
3. Отправить сообщение
4. ✅ Должно работать (раньше была ошибка)

## 🔍 Связанные документы

- [CORS_FIX_2025-11-25.md](./CORS_FIX_2025-11-25.md)
- [AUTH_IMPROVEMENTS_2025-01-25.md](./AUTH_IMPROVEMENTS_2025-01-25.md)
- [MULTI_PLATFORM_STRATEGY.md](./MULTI_PLATFORM_STRATEGY.md)
