# Telegram SDK Timing Issue - ИСПРАВЛЕНО

## Проблема

Telegram Mini App не определялся ни на мобиле, ни на макбуке - всегда открывался лендинг вместо приложения.

### Почему это происходило?

**Root Cause: Race Condition в загрузке SDK**

```
1. PlatformProvider монтируется
   ↓
2. PlatformProvider.useEffect запускается
   ↓
3. Проверяет window.Telegram.WebApp
   ❌ SDK ещё не загружен!
   ↓
4. Определяет платформу как "web"
   ↓
5. ConditionalTelegramScript.useEffect запускается
   ↓
6. Загружает SDK асинхронно
   ⚠️ Но уже поздно! Платформа определена.
```

### Дополнительный фактор

Mini App открывает `/home`, а НЕ корень `/`:

```env
# .env.example строка 81
WEBAPP_URL=http://localhost:3000/home
```

На странице `/home` тоже была проверка платформы:

```tsx
// home/page.tsx:38-43
if (platformType !== 'telegram') {
  router.push('/landing');  // ❌ Редирект на landing
  return;
}
```

## Решение

### 1. Статическая загрузка Telegram SDK

**Файл:** [frontend/app/layout.tsx](frontend/app/layout.tsx:46-49)

Заменили условную асинхронную загрузку на **статическую синхронную**:

```tsx
// ❌ БЫЛО: ConditionalTelegramScript (useEffect, async)
<ConditionalTelegramScript />

// ✅ СТАЛО: Static Script (beforeInteractive)
<Script
  src="https://telegram.org/js/telegram-web-app.js"
  strategy="beforeInteractive"
/>
```

### 2. Почему это безопасно?

- **Размер SDK:** ~30kb gzipped - минимальный оверхед
- **Если не Telegram:** SDK загрузится, но `initData` будет пустым
- **Определение платформы:** Происходит по `initData`, а не по наличию SDK
- **No timing issues:** SDK загружается ДО инициализации PlatformProvider

## Как работает определение платформы

### До исправления

```typescript
// ConditionalTelegramScript.tsx (useEffect - асинхронно)
useEffect(() => {
  const isTelegramEnv =
    window.Telegram?.WebApp ||
    /Telegram/i.test(navigator.userAgent) ||
    window.location.search.includes('tgWebAppData');

  if (isTelegramEnv) {
    // Загружаем SDK асинхронно
    setShouldLoad(true);
  }
}, []);
```

**Проблема:** К моменту проверки в `PlatformProvider`, SDK еще не загружен.

### После исправления

```typescript
// layout.tsx - синхронная загрузка в <head>
<Script
  src="https://telegram.org/js/telegram-web-app.js"
  strategy="beforeInteractive"  // Загружается ДО гидратации React
/>
```

**Результат:** SDK доступен сразу при инициализации `PlatformProvider`.

## Логика определения платформы

**Файл:** [frontend/lib/platform/utils/platformDetector.ts](frontend/lib/platform/utils/platformDetector.ts:52-105)

```typescript
export function isTelegramPlatform(): PlatformDetection {
  // 1. Проверяем наличие SDK
  const hasTelegramObject = !!window.Telegram?.WebApp;

  if (!hasTelegramObject) {
    return { isAvailable: false };
  }

  // 2. ГЛАВНАЯ ПРОВЕРКА: initData
  const webApp = window.Telegram.WebApp;
  const hasInitData = !!webApp.initData;

  if (!hasInitData) {
    // SDK загружен, но initData пустой = открыто в браузере
    return { isAvailable: false };
  }

  // ✅ Telegram Mini App с валидными данными
  return { isAvailable: true };
}
```

## Флоу после исправления

### Telegram Mini App

```
User открывает Mini App
       ↓
Telegram передает initData
       ↓
Открывается /home
       ↓
SDK уже загружен (beforeInteractive)
       ↓
PlatformProvider проверяет window.Telegram.WebApp
       ✅ SDK есть
       ↓
Проверяет initData
       ✅ initData валидный
       ↓
platformType = 'telegram'
       ↓
/home проверяет platformType
       ✅ telegram - продолжает работу
       ↓
Приложение работает
```

### Web Browser

```
User открывает ai.syntratrade.xyz в браузере
       ↓
Открывается корневая страница /
       ↓
SDK загружен (но initData пустой)
       ↓
PlatformProvider проверяет window.Telegram.WebApp
       ✅ SDK есть
       ↓
Проверяет initData
       ❌ initData пустой
       ↓
platformType = 'web'
       ↓
page.tsx делает редирект на /landing
       ↓
Landing page показывается
```

## Логи для отладки

При открытии Mini App в консоли:

```
🔍 Telegram detection: hasTelegramObject = true
🔍 Telegram detection details: {
  initData: "query_id=...&user=...",
  initDataUnsafe: { ... },
  platform: "ios",
  version: "7.0"
}
✅ Telegram Mini App detected!
🎯 Detected platform: telegram
```

При открытии в браузере:

```
🔍 Telegram detection: hasTelegramObject = true
🔍 Telegram detection details: {
  initData: "",
  initDataUnsafe: {},
  platform: "unknown",
  version: "7.0"
}
⚠️ Telegram SDK loaded but no initData (opened in browser?)
🎯 Detected platform: web
🌐 Redirecting web user to /landing
```

## Производительность

### До исправления
- ❌ Условная загрузка через useEffect
- ❌ Проверка user agent и query params
- ❌ Timing issues
- ❌ False negatives (Mini App определялся как Web)

### После исправления
- ✅ Статическая загрузка SDK (~30kb)
- ✅ SDK доступен сразу при инициализации
- ✅ Нет race conditions
- ✅ Надежное определение по initData

### Trade-off
- **+30kb для веб-пользователей** - приемлемо для надежной работы Mini App
- Alternative: Server-side detection по User-Agent (но менее надежно)

## Тестирование

### ✅ Сценарий 1: Telegram Mobile (iOS/Android)

```
1. Открыть бот в Telegram
2. Нажать кнопку "Открыть приложение"
3. Должен открыться /home с приложением

Ожидаемые логи:
✅ Telegram Mini App detected!
platformType = 'telegram'
```

### ✅ Сценарий 2: Telegram Desktop (macOS/Windows)

```
1. Открыть бот в Telegram Desktop
2. Нажать кнопку "Открыть приложение"
3. Должен открыться /home с приложением

Ожидаемые логи:
✅ Telegram Mini App detected!
platformType = 'telegram'
```

### ✅ Сценарий 3: Web Browser

```
1. Открыть ai.syntratrade.xyz в Chrome/Safari
2. Должен открыться /landing

Ожидаемые логи:
⚠️ Telegram SDK loaded but no initData
platformType = 'web'
🌐 Redirecting web user to /landing
```

## Deployment Checklist

После деплоя на продакшн:

- [ ] Проверить Mini App на iOS
- [ ] Проверить Mini App на Android
- [ ] Проверить Mini App на macOS (Telegram Desktop)
- [ ] Проверить Mini App на Windows (Telegram Desktop)
- [ ] Проверить веб-версию в браузере
- [ ] Убедиться что логи показывают правильную платформу

## Измененные файлы

1. ✅ [layout.tsx](frontend/app/layout.tsx) - статическая загрузка SDK
2. ✅ [platformDetector.ts](frontend/lib/platform/utils/platformDetector.ts) - детальные логи
3. ✅ [page.tsx](frontend/app/page.tsx) - smart routing по платформе
4. ✅ Удалено: `ConditionalTelegramScript` (больше не используется)

## Build Status

```bash
✓ Compiled successfully in 5.7s
✓ TypeScript check passed
✓ All routes generated
✓ No errors
```

---

**Дата:** 2025-11-25
**Статус:** ✅ ИСПРАВЛЕНО
**Тестирование:** ⏳ Требуется проверка на реальных устройствах
