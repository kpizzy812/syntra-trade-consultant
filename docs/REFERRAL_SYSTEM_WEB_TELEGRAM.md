# Реферальная Система - Web & Telegram

## Что реализовано

### ✅ 1. Двойная Реферальная Система

Теперь поддерживаются **два типа реферальных ссылок**:

#### 📱 Telegram Bot Links
```
https://t.me/SyntraAI_bot?start=ref_ABC123
```
- Для пользователей, которые заходят через Telegram
- Автоматическое определение платформы
- QR код для быстрого доступа

#### 🌐 Web App Links
```
https://syntra.ai/auth/choose?ref=ABC123&utm_source=referral&utm_medium=web&utm_campaign=friend_invite
```
- Для пользователей, которые заходят через веб
- Поддержка UTM параметров для аналитики
- Сохранение ref кода в localStorage (TTL: 30 дней)
- QR код для быстрого доступа

---

## Файлы

### Backend

#### 1. [config/config.py](../config/config.py)
```python
# Добавлено:
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "SyntraAI_bot")
```

**Зачем:** Централизованное хранение username бота для генерации ссылок

#### 2. [src/api/referral.py](../src/api/referral.py:129-131)
```python
# Обновлено:
from config.config import BOT_USERNAME
referral_link = f"https://t.me/{BOT_USERNAME}?start=ref_{code}"
```

**Зачем:** Использование конфигурируемого bot username вместо хардкода

---

### Frontend

#### 3. [frontend/lib/referral.ts](../frontend/lib/referral.ts) - **НОВЫЙ**

Утилиты для работы с реферальными ссылками:

##### Генерация Telegram ссылок
```typescript
generateTelegramReferralLink(code: string): string
// https://t.me/SyntraAI_bot?start=ref_ABC123
```

##### Генерация Web ссылок
```typescript
generateWebReferralLink({
  code: 'ABC123',
  utm_source: 'referral',
  utm_medium: 'web',
  utm_campaign: 'friend_invite'
}): string
// https://syntra.ai/auth/choose?ref=ABC123&utm_source=...
```

##### Универсальная генерация
```typescript
generateReferralLink(options): string
// Автоматически определяет платформу (Telegram/Web)
```

##### Управление ref кодом
```typescript
// Извлечение из URL
extractReferralCode(): string | null

// Сохранение в localStorage
saveReferralCode(code: string): void

// Получение сохраненного (TTL: 30 дней)
getSavedReferralCode(): string | null
```

##### QR коды
```typescript
generateQRCodeURL(referralLink: string, size?: number): string
// Генерирует URL для QR кода через qrserver.com API
```

---

#### 4. [frontend/app/referral/page.tsx](../frontend/app/referral/page.tsx) - **ОБНОВЛЕН**

##### Новые фичи:

**Platform Tabs**
```tsx
<button onClick={() => setActiveTab('telegram')}>
  📱 Telegram Bot
</button>
<button onClick={() => setActiveTab('web')}>
  🌐 Web App
</button>
```

**Динамический QR код**
```tsx
<img src={generateQRCodeURL(getCurrentReferralLink(), 240)} />
// QR код меняется в зависимости от выбранной платформы
```

**Динамическая ссылка**
```tsx
const getCurrentReferralLink = () => {
  return activeTab === 'telegram'
    ? generateTelegramReferralLink(link.referral_code)
    : generateWebReferralLink({
        code: link.referral_code,
        utm_source: 'referral',
        utm_medium: 'web',
        utm_campaign: 'friend_invite',
      });
};
```

**Автоопределение платформы**
```tsx
useEffect(() => {
  const detectedPlatform = detectPlatform();
  setPlatform(detectedPlatform);
  setActiveTab(detectedPlatform === 'telegram' ? 'telegram' : 'web');
}, []);
```

---

## Как это работает

### Сценарий 1: Telegram → Telegram
1. Пользователь А в Telegram боте открывает `/referral`
2. Видит **Telegram Bot** таб активным
3. Копирует ссылку `t.me/SyntraAI_bot?start=ref_ABC123`
4. Делится с другом Б в Telegram
5. Друг Б открывает бота → автоматически привязывается к пользователю А

### Сценарий 2: Web → Web
1. Пользователь А на сайте syntra.ai открывает `/referral`
2. Видит **Web App** таб активным
3. Копирует ссылку `syntra.ai/auth/choose?ref=ABC123&utm_...`
4. Делится с другом Б (email, социальные сети, etc.)
5. Друг Б открывает ссылку → ref код сохраняется в localStorage
6. При регистрации ref код автоматически применяется

### Сценарий 3: Web → Telegram (кросс-платформа)
1. Пользователь А на сайте открывает `/referral`
2. **Переключает таб** на **Telegram Bot**
3. Копирует Telegram ссылку
4. Делится с другом Б
5. Друг Б открывает бота → привязывается к пользователю А

---

## UTM Parameters

Веб-ссылки включают UTM параметры для аналитики:

```
utm_source=referral    - источник трафика
utm_medium=web         - канал
utm_campaign=friend_invite - кампания
```

Эти параметры можно использовать в **PostHog/Google Analytics** для отслеживания эффективности реферальной программы.

---

## LocalStorage Management

### Сохранение ref кода
```typescript
// При открытии ссылки syntra.ai/?ref=ABC123
saveReferralCode('ABC123');
```

Сохраняет:
- `syntra_referral_code` = "ABC123"
- `syntra_referral_timestamp` = "1704067200000"

### Получение ref кода (TTL: 30 дней)
```typescript
const code = getSavedReferralCode();
// Возвращает код если не истек TTL, иначе null
```

### Применение при регистрации
При регистрации через `/auth/*` страницы:
1. Проверяется URL параметр `?ref=`
2. Если нет - проверяется localStorage
3. Найденный код отправляется на backend при создании аккаунта

---

## QR Code Generation

QR коды генерируются через публичный API:
```
https://api.qrserver.com/v1/create-qr-code/?size=240x240&data={link}
```

**Преимущества:**
- Не нужен собственный сервис генерации
- Мгновенная генерация
- Бесплатно
- Высокое качество

**Размеры:**
- Referral page: 240x240 (оптимально для мобильных)
- Backend API: 300x300 (высокое качество для печати)

---

## Environment Variables

Добавить в `.env`:
```bash
# Telegram Bot Username (без @)
BOT_USERNAME=SyntraAI_bot
```

**Важно:** Если вы меняете username бота, обновите эту переменную.

---

## API Endpoints

### GET /referral/link
Возвращает реферальную информацию:
```json
{
  "referral_code": "ABC123",
  "referral_link": "https://t.me/SyntraAI_bot?start=ref_ABC123",
  "qr_code_url": "https://api.qrserver.com/v1/create-qr-code/?...",
  "created_at": "2025-01-18T00:00:00Z"
}
```

**Note:** Backend генерирует только Telegram ссылку. Web ссылки генерируются на frontend для гибкости с UTM параметрами.

---

## Следующие шаги (TODO)

### 🔜 Landing Page Integration
- [ ] Добавить обработку `?ref=` параметра в [landing/page.tsx](../frontend/app/landing/page.tsx)
- [ ] Автосохранение ref кода при посещении landing page
- [ ] Передача ref кода при клике на "Get Started"

### 🔜 Локализация (i18n)
- [ ] Создать translations для RU/EN
- [ ] Обновить [referral/page.tsx](../frontend/app/referral/page.tsx)
- [ ] Обновить [landing/page.tsx](../frontend/app/landing/page.tsx)

### 🔜 Analytics
- [ ] PostHog события для referral links
- [ ] UTM tracking в dashboard
- [ ] Conversion funnel analysis

---

## Тестирование

### 1. Проверка Telegram ссылок
```bash
# Перейти на /referral в мини-апп
# Выбрать таб "Telegram Bot"
# Скопировать ссылку
# Открыть в другом аккаунте
# Проверить привязку referral
```

### 2. Проверка Web ссылок
```bash
# Перейти на /referral через web
# Выбрать таб "Web App"
# Скопировать ссылку
# Открыть в incognito
# Проверить localStorage: syntra_referral_code
```

### 3. Проверка QR кодов
```bash
# Отсканировать QR код на Telegram табе -> должен открыть бота
# Отсканировать QR код на Web табе -> должен открыть сайт с ref параметром
```

---

## Сборка

✅ **Frontend:** Сборка успешна без ошибок
```bash
cd frontend && npm run build
```

---

## Summary

**Реализовано:**
- ✅ Двойная реферальная система (Web + Telegram)
- ✅ Platform-aware link generation
- ✅ QR коды для обеих платформ
- ✅ UTM параметры для веб-ссылок
- ✅ LocalStorage management с TTL
- ✅ Автоопределение платформы
- ✅ Tab switching в UI

**Осталось:**
- ⏳ Landing page ref parameter handling
- ⏳ Локализация (RU/EN)
- ⏳ Замена хардкода на актуальные данные из API

