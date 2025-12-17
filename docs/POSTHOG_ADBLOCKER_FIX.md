# PostHog AdBlocker Fix

## Проблема
PostHog блокируется браузерными adblockers (например, uBlock Origin), что приводит к:
- Бесконечным retry запросов
- Засорению консоли ошибками `net::ERR_BLOCKED_BY_CLIENT`
- Засорению Network tab ошибками блокировки
- Негативному влиянию на dev experience

## Решение

### ⚡ ГЛАВНОЕ РЕШЕНИЕ: Отключение в dev режиме
PostHog теперь **полностью отключен** в dev режиме (`NODE_ENV === 'development'`).
Это самый простой и эффективный способ избежать проблем с блокировщиками при разработке.

```typescript
if (posthogKey && !posthog.__loaded && !isDev) {
  // PostHog инициализируется только в production
}
```

### Дополнительные меры защиты (для production)

### 1. Обработка ошибок при инициализации
```typescript
on_request_error: () => {
  // Не логируем ошибки - они замусоривают консоль
},
```

### 2. Таймауты для предотвращения бесконечных retry
```typescript
feature_flag_request_timeout_ms: 3000,
```

### 3. Отключение ненужных фич в dev режиме
```typescript
disable_session_recording: isDev,
disable_surveys: isDev,
```

### 4. Безопасная обёртка над PostHog API
Создан `SafePostHog` интерфейс и `safePostHog` объект, который:
- Проверяет `posthog.__loaded` перед каждым вызовом
- Обрабатывает все ошибки через try-catch
- Возвращает безопасные значения по умолчанию

### 5. Graceful degradation
Если PostHog заблокирован:
- Приложение продолжает работать нормально
- Аналитика просто не отправляется
- Никаких ошибок в консоли

## Использование

```typescript
const posthog = usePostHog()

// Все методы безопасны и не выбросят ошибку
if (posthog.__loaded) {
  posthog.capture('event_name', { property: 'value' })
}

posthog.identify('user_id', { name: 'John' })
posthog.isFeatureEnabled('feature_flag')
posthog.getFeatureFlag('ab_test')
```

## Результат
- ✅ **PostHog полностью отключен в dev режиме** - никаких ошибок
- ✅ Консоль чистая, без ошибок
- ✅ Network tab чистый, без failed requests
- ✅ Приложение работает стабильно
- ✅ PostHog работает в production когда доступен
- ✅ Graceful degradation когда заблокирован
- ✅ Build проходит без ошибок TypeScript

## Как включить PostHog в dev режиме (для тестирования)

Если нужно протестировать PostHog локально, измени условие в `PostHogProvider.tsx`:

```typescript
// Было:
if (posthogKey && !posthog.__loaded && !isDev) {

// Стало (временно для тестирования):
if (posthogKey && !posthog.__loaded) {
```

Или добавь PostHog домен в whitelist твоего блокировщика рекламы.

## Альтернативное решение (для production)
Для полного решения проблемы с adblockers рекомендуется настроить reverse proxy:
1. Настроить proxy на своем домене (например, `/ingest`)
2. Перенаправлять запросы на PostHog через свой сервер
3. Adblockers не будут блокировать запросы к своему домену

См. документацию: https://posthog.com/docs/advanced/proxy
