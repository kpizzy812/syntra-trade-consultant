# Deployment Fix 2025-11-25

## Проблемы которые были исправлены

### 1. Двойная инициализация PostHog
**Проблема:** PostHog инициализировался дважды:
- В `instrumentation-client.ts`
- В `components/providers/PostHogProvider.tsx`

**Решение:**
- Удален `frontend/instrumentation-client.ts`
- Добавлена проверка `!posthog.__loaded` в PostHogProvider.tsx

### 2. Telegram SDK Warnings
**Проблема:** Telegram WebApp API вызывал warnings для неподдерживаемых функций в версии 6.0

**Решение:**
- Добавлена проверка версии Telegram SDK перед вызовом методов
- Методы вызываются только для поддерживаемых версий:
  - `setHeaderColor`, `setBackgroundColor`: версия >= 6.1
  - `enableClosingConfirmation`: версия >= 6.2
  - `disableVerticalSwipes`: версия >= 7.0

### 3. API 404 Error
**Проблема:** nginx удалял `/api/` prefix перед проксированием на backend, но FastAPI router ожидал `/api/` в URL

**Решение:**
- Изменен nginx config: `proxy_pass http://syntra_miniapp_api/api/;` (добавлен /api/)
- Теперь URL сохраняется полностью при проксировании

## Деплой инструкции

### На локальной машине:
```bash
cd /Users/a1/Projects/Syntra\ Trade\ Consultant/frontend

# Соберите production билд
npm run build

# Создайте архив
tar -czf frontend-build.tar.gz .next/ public/ package.json
```

### На сервере:
```bash
# Загрузите на сервер
scp frontend-build.tar.gz syntra:/root/syntraai/frontend/

# На сервере
ssh syntra
cd /root/syntraai/frontend

# Распакуйте
tar -xzf frontend-build.tar.gz

# Перезапустите frontend
pm2 restart tradient-front

# Проверьте логи
pm2 logs tradient-front --lines 50
```

## Проверка работоспособности

### 1. API проверка:
```bash
curl https://ai.syntratrade.xyz/api/config/pricing
```

Должен вернуть JSON с тарифами.

### 2. Frontend проверка:
```bash
curl -I https://ai.syntratrade.xyz/
```

Должен вернуть 200 OK.

### 3. Telegram Mini App:
1. Откройте бота @SyntraAI_bot
2. Нажмите кнопку "Open Mini App"
3. Проверьте что приложение открывается без connection errors
4. Проверьте консоль браузера - не должно быть:
   - Двойной инициализации PostHog
   - Telegram SDK warnings

## Измененные файлы

- ❌ Удален: `frontend/instrumentation-client.ts`
- ✏️ Изменен: `frontend/components/providers/PostHogProvider.tsx`
- ✏️ Изменен: `frontend/components/providers/TelegramProvider.tsx`
- ✏️ Изменен: `/etc/nginx/sites-available/ai.syntratrade.xyz` (на сервере)

## Коммит изменений

```bash
cd /Users/a1/Projects/Syntra\ Trade\ Consultant

git add -A
git commit -m "Fix: Remove PostHog double init, add Telegram SDK version checks, fix nginx API routing

- Removed instrumentation-client.ts (duplicate PostHog init)
- Added posthog.__loaded check in PostHogProvider
- Added Telegram SDK version checks in TelegramProvider
- Fixed nginx config to preserve /api/ prefix in proxy_pass
- Connection errors в Telegram Mini App исправлены

🤖 Generated with Claude Code"

git push origin main
```
