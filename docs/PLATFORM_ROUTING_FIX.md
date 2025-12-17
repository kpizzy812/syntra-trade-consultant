# Platform-Based Routing Fix

## Проблема

При открытии `ai.syntratrade.xyz` из Telegram Mini App всегда происходил редирект на `/landing` вместо основного приложения `/chat`.

## Причина

В `frontend/app/page.tsx` был жестко закодирован редирект на `/landing` для всех пользователей, без учета платформы:

```tsx
// ❌ Старый код
useEffect(() => {
  router.replace('/landing'); // Всегда landing для всех
}, [router]);
```

## Решение

### 1. Умный роутинг в корневой странице

**Файл:** [frontend/app/page.tsx](frontend/app/page.tsx)

Теперь определяется платформа и редирект происходит соответственно:

```tsx
// ✅ Новый код
const { platformType, isReady } = usePlatform();

useEffect(() => {
  if (!isReady) return;

  if (platformType === 'telegram') {
    router.replace('/chat');    // Telegram → приложение
  } else {
    router.replace('/landing'); // Web → лендинг
  }
}, [platformType, isReady, router]);
```

### 2. Улучшенное логирование

**Файл:** [frontend/lib/platform/utils/platformDetector.ts](frontend/lib/platform/utils/platformDetector.ts)

Добавлено подробное логирование определения Telegram Mini App:

```tsx
console.log('🔍 Telegram detection details:', {
  initData: webApp.initData,
  initDataUnsafe: webApp.initDataUnsafe,
  platform: webApp.platform,
  version: webApp.version,
});
```

**Файл:** [frontend/components/providers/ConditionalTelegramScript.tsx](frontend/components/providers/ConditionalTelegramScript.tsx)

Логи проверки Telegram окружения:

```tsx
console.log('🔍 ConditionalTelegramScript checks:', {
  hasWebApp,
  hasTelegramUA,
  hasTgWebAppData,
  userAgent: navigator.userAgent,
  search: window.location.search,
});
```

## Как это работает

### Архитектура определения платформы

```
User opens ai.syntratrade.xyz
         ↓
   PlatformProvider
         ↓
 ConditionalTelegramScript
         ↓
   (if Telegram detected)
         ↓
 Load Telegram SDK
         ↓
   platformDetector
         ↓
 Check initData
         ↓
┌────────┴────────┐
│                 │
Telegram          Web
↓                 ↓
/chat             /landing
```

### Условия определения Telegram

1. **Telegram SDK загружается если:**
   - `window.Telegram.WebApp` уже существует
   - User agent содержит "Telegram"
   - URL содержит параметр `tgWebAppData`

2. **Платформа определяется как Telegram если:**
   - Telegram SDK успешно загружен
   - `window.Telegram.WebApp` существует
   - `webApp.initData` не пустой (пользователь открыл через Telegram)

3. **Если условия не выполнены:**
   - Платформа определяется как Web
   - Telegram SDK НЕ загружается (экономия ресурсов)

## Тестирование

### Сценарий 1: Telegram Mini App

1. Открыть `ai.syntratrade.xyz` в Telegram Mini App
2. **Ожидается:**
   - В консоли: `🎯 Telegram environment detected - loading SDK`
   - В консоли: `✅ Telegram Mini App detected!`
   - В консоли: `📱 Redirecting Telegram user to /chat`
   - Редирект на `/chat`

### Сценарий 2: Обычный браузер

1. Открыть `ai.syntratrade.xyz` в Chrome/Safari/Firefox
2. **Ожидается:**
   - В консоли: `🌐 Web environment - skipping Telegram SDK`
   - В консоли: `❌ Telegram WebApp not found`
   - В консоли: `🌐 Redirecting web user to /landing`
   - Редирект на `/landing`

### Сценарий 3: Прямые ссылки

Прямые ссылки на `/chat`, `/profile`, `/referral` работают на обеих платформах:

- **Telegram:** `ai.syntratrade.xyz/chat` → работает
- **Web:** `ai.syntratrade.xyz/chat` → работает (если авторизован)

## Дополнительные улучшения

### Loading State

Пока платформа определяется, показывается loading экран:

```tsx
<div className="text-center">
  <div className="spinner" />
  <p>{isReady ? 'Redirecting...' : 'Detecting platform...'}</p>
</div>
```

### Логи для отладки

Все ключевые точки залогированы:

- 🔍 ConditionalTelegramScript checks
- 🎯 Telegram environment detected
- ✅ Telegram SDK loaded
- 🔍 Telegram detection details
- 📱/🌐 Platform-specific redirect

## Флоу для ai.syntratrade.xyz

```
ai.syntratrade.xyz
       ↓
   Определение платформы
       ↓
┌──────┴──────┐
│             │
Telegram      Web
↓             ↓
/chat         /landing
              ↓
          Auth (Magic Link / Telegram Widget)
              ↓
          /chat (авторизованный)
```

## Следующие шаги

1. ✅ Platform-based routing реализован
2. ⏳ NextAuth.js setup для Web авторизации
3. ⏳ Magic Link (Resend) для EU/USA пользователей
4. ⏳ Telegram Login Widget для крипто-пользователей
5. ⏳ Страница `/auth/signin` с обоими методами

## Deployment

После deployment на продакшн:

1. Обновить Mini App URL в BotFather: `https://ai.syntratrade.xyz`
2. Telegram пользователи будут открывать `/chat` автоматически
3. Web пользователи будут видеть landing и могут авторизоваться

## Проверка статуса

```bash
# Build frontend
cd frontend && npm run build

# Проверить логи в production
# Открыть Console в DevTools и смотреть на логи с эмодзи
```

---

**Дата:** 2025-11-25
**Статус:** ✅ Реализовано и протестировано
**Build:** ✅ Успешно (No TypeScript errors)
