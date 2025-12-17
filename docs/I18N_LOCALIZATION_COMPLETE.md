# ✅ Полная Локализация Syntra AI - Реализовано

## 🎯 Цель
Реализована полная система интернационализации (i18n) для Syntra AI с поддержкой русского и английского языков.

## 📋 Что реализовано

### 1. Frontend - React/Next.js с next-intl

#### ✅ Компонент LanguageSwitcher
**Файл:** `/frontend/components/layout/LanguageSwitcher.tsx`

**Возможности:**
- 🎨 Круглая кнопка с SVG флагом текущего языка
- 🔄 Мгновенное переключение через dropdown
- 💾 Автоматическое сохранение в localStorage (cookie)
- 🌐 Синхронизация с бэкендом для залогиненных пользователей
- ⚡ Graceful degradation - работает даже если бэкенд недоступен
- 🎭 Анимации через framer-motion
- 📱 Адаптивные размеры (sm/md/lg)

**Использование:**
```tsx
import LanguageSwitcher from '@/components/layout/LanguageSwitcher';

// В компоненте
<LanguageSwitcher size="md" />
```

#### ✅ Интеграция в Header
**Файл:** `/frontend/components/layout/Header.tsx`

LanguageSwitcher автоматически добавлен в header всех страниц приложения.

#### ✅ Landing Page - Полная локализация
**Файл:** `/frontend/app/landing/page.tsx`

**Локализованные секции:**
- ✅ Header & Navigation
- ✅ Hero Section
- ✅ Problem Section
- ✅ Solution Section
- ✅ How it Works
- ✅ For Whom
- ✅ Features
- ✅ Personality
- ✅ Pricing (Free/Basic/Premium)
- ✅ Referral Program (Bronze/Silver/Gold/Platinum)
- ✅ FAQ (5 вопросов)
- ✅ Final CTA
- ✅ Footer

#### ✅ Файлы переводов
**Файлы:**
- `/frontend/messages/en.json` - английский
- `/frontend/messages/ru.json` - русский

**Структура:**
```json
{
  "common": {...},
  "premium": {...},
  "home": {...},
  "chat": {...},
  "profile": {...},
  "referral": {...},
  "landing": {
    "header": {...},
    "hero": {...},
    "problem": {...},
    "solution": {...},
    "how": {...},
    "forwho": {...},
    "features": {...},
    "personality": {...},
    "pricing": {...},
    "referral": {...},
    "faq": {...},
    "final_cta": {...},
    "footer": {...}
  }
}
```

#### ✅ Hooks и Утилиты

**`useCurrentLocale`** - `/frontend/shared/hooks/useCurrentLocale.ts`
```typescript
import { useCurrentLocale } from '@/shared/hooks/useCurrentLocale';

const currentLocale = useCurrentLocale(); // 'en' | 'ru'
```

**`getPreferredLocale`** - `/frontend/shared/lib/locale.ts`
```typescript
// Определяет язык в порядке приоритета:
// 1. Cookie (NEXT_LOCALE)
// 2. Telegram WebApp language_code
// 3. Browser language
// 4. Default: 'en'
```

**`setLocaleCookie`** - `/frontend/shared/lib/locale.ts`
```typescript
setLocaleCookie('ru'); // Сохраняет в cookie на 1 год
```

### 2. Backend - Python/FastAPI

#### ✅ Модель User с полем language
**Файл:** `/src/database/models.py`

```python
class User(Base):
    language: Mapped[str] = mapped_column(
        String(10),
        default="ru",
        nullable=False
    )
```

#### ✅ API Endpoint для обновления языка
**Файл:** `/src/api/profile.py`

**Endpoint:** `PATCH /api/profile/settings`

**Request:**
```json
{
  "language": "en"  // "ru" | "en"
}
```

**Response:**
```json
{
  "success": true,
  "language": "en",
  "updated_at": "2025-01-26T12:30:00Z"
}
```

#### ✅ Prompt Selector - Выбор промптов по языку
**Файл:** `/config/prompt_selector.py`

**Функции с поддержкой языка:**
- `get_system_prompt(language="ru|en", ...)`
- `get_few_shot_examples(language="ru|en", ...)`
- `get_vision_analysis_prompt(language="ru|en", ...)`
- `get_enhanced_vision_prompt(language="ru|en", ...)`
- `get_question_vision_prompt(language="ru|en", ...)`
- `get_price_analysis_prompt(language="ru|en", ...)`
- `get_general_question_prompt(language="ru|en")`
- `get_coin_detection_prompt(language="ru|en")`

**Использование в Chat API:**
```python
# В /src/api/chat.py
user_language = user.language or "ru"

# Автоматически выбираются промпты на нужном языке
await openai_service.stream_image_analysis(
    user_language=user_language,
    ...
)
```

#### ✅ Промпты на двух языках
**Файлы:**
- `/config/prompts.py` - русские промпты (основные)
- `/config/prompts_en.py` - английские промпты
- `/config/vision_prompts_ru.py` - русские промпты для vision
- `/config/vision_prompts_en.py` - английские промпты для vision
- `/config/prompts_free.py` - упрощенные промпты для FREE tier

### 3. Архитектура и Flow

#### Автоматическое определение языка

**При первом посещении:**
```
1. getPreferredLocale() проверяет:
   - Cookie NEXT_LOCALE
   - Telegram WebApp language_code
   - Browser navigator.language
   - Default: 'en'

2. Next.js загружает соответствующие переводы
3. Landing page отображается на выбранном языке
```

**При переключении языка:**
```
1. User кликает на LanguageSwitcher
2. Выбирает язык (EN/RU)
3. Frontend:
   - Сохраняет в cookie через setLocaleCookie()
   - Отправляет PATCH /api/profile/settings
   - Обновляет userStore
   - Перезагружает страницу (window.location.reload)
4. Backend:
   - Сохраняет user.language в БД
   - Возвращает success response
5. При следующих запросах к AI:
   - Бэкенд использует user.language
   - Выбирает промпты на нужном языке
   - AI отвечает на языке пользователя
```

#### Синхронизация Frontend ↔ Backend

```
┌─────────────────┐
│  User Action    │
│  (Switch Lang)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Cookie Save    │──────┐
│  (localStorage) │      │
└─────────────────┘      │
                         │
         ┌───────────────┘
         │
         ▼
┌─────────────────┐
│  API Request    │
│  PATCH /settings│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Database Save  │
│  user.language  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  AI Requests    │
│  Use user.lang  │
└─────────────────┘
```

## 🎨 UI/UX Features

### LanguageSwitcher Design
- ⚪ **Круглая кнопка** с флагом текущего языка
- 🎭 **Анимированный dropdown** с плавными переходами
- ✅ **Активное состояние** с галочкой и подсветкой
- 🚫 **Disabled state** во время обновления
- 📱 **Адаптивные размеры** (sm: 32px, md: 40px, lg: 48px)

### Иконки языков
- 🇬🇧 `/frontend/public/icons/en.svg` - флаг UK
- 🇷🇺 `/frontend/public/icons/ru.svg` - флаг России

## 🔧 Конфигурация next-intl

**Файл:** `/frontend/i18n.ts`

```typescript
export const locales = ['en', 'ru'] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = 'en';
```

**Middleware:** `/frontend/middleware.ts`
- Простой pass-through, без роутинга по локалям
- Язык определяется динамически через cookie

**Root Layout:** `/frontend/app/layout.tsx`
- NextIntlClientProvider обертывает все приложение
- Автоматическая загрузка messages по локали

## 📝 Как добавить новый язык

### 1. Frontend

1. Добавить в `/frontend/i18n.ts`:
```typescript
export const locales = ['en', 'ru', 'es'] as const;
```

2. Создать `/frontend/messages/es.json`:
```json
{
  "common": {...},
  "landing": {...}
}
```

3. Добавить флаг `/frontend/public/icons/es.svg`

4. Обновить `LanguageSwitcher.tsx`:
```typescript
const LANGUAGE_FLAGS = {
  en: '/icons/en.svg',
  ru: '/icons/ru.svg',
  es: '/icons/es.svg',
} as const;

const LANGUAGE_NAMES = {
  en: 'English',
  ru: 'Русский',
  es: 'Español',
} as const;
```

5. Добавить кнопку в dropdown

### 2. Backend

1. Создать `/config/prompts_es.py` с испанскими промптами

2. Обновить `/config/prompt_selector.py`:
```python
if language == "en":
    return prompts_en.get_system_prompt(mode)
elif language == "es":
    return prompts_es.get_system_prompt(mode)
else:
    return prompts_ru.get_system_prompt(mode)
```

3. Обновить validation в `/src/api/profile.py`:
```python
if v not in ["ru", "en", "es"]:
    raise ValueError("Language must be 'ru', 'en' or 'es'")
```

## 🧪 Тестирование

### Локальное тестирование

1. **Проверить переключение языков на landing page:**
```bash
npm run dev
# Открыть http://localhost:3000/landing
# Кликнуть на LanguageSwitcher
# Выбрать язык
# Проверить что все тексты поменялись
```

2. **Проверить сохранение в бэкенд:**
```bash
# Залогиниться
# Переключить язык
# Проверить в БД: SELECT id, username, language FROM users;
# Отправить запрос в чат
# Проверить что AI отвечает на выбранном языке
```

3. **Проверить cookie:**
```javascript
// В DevTools Console
document.cookie.split(';').find(c => c.includes('NEXT_LOCALE'))
// Должно вернуть: "NEXT_LOCALE=en" или "NEXT_LOCALE=ru"
```

### Production Checklist

- ✅ Landing page полностью локализован
- ✅ LanguageSwitcher работает на всех страницах
- ✅ Cookie сохраняется корректно
- ✅ Backend API обновляет user.language
- ✅ AI использует правильный язык в промптах
- ✅ Graceful degradation (работает без логина)
- ✅ Next.js production build проходит
- ✅ ESLint без ошибок

## 🚀 Deployment

### Environment Variables
Не требуется дополнительных переменных окружения.

### Build
```bash
cd frontend
npm run build
```

### Проверка
```bash
npm run lint
npm run build
```

## 📊 Метрики

- **Поддерживаемые языки:** 2 (EN, RU)
- **Переведенных ключей:** 150+
- **Локализованных страниц:** Landing, Chat, Profile, Referral
- **Компонентов с i18n:** Header, LanguageSwitcher, все страницы

## 🎓 Best Practices

1. **Всегда используйте useTranslations:**
```tsx
const t = useTranslations();
<h1>{t('landing.hero.title')}</h1>
```

2. **Для HTML тегов используйте dangerouslySetInnerHTML:**
```tsx
<p dangerouslySetInnerHTML={{ __html: t.raw('landing.pricing.subtitle') }} />
```

3. **Передавайте currentLocale в дочерние компоненты:**
```tsx
const currentLocale = useCurrentLocale();
<QuickLoginModal language={currentLocale} />
```

4. **Всегда тестируйте на обоих языках:**
- Проверяйте переводы
- Проверяйте длину текстов (особенно в кнопках)
- Проверяйте RTL support (если будет нужен Arabic)

## 🔮 Будущие улучшения

- [ ] Добавить языки: ES (испанский), DE (немецкий), FR (французский)
- [ ] i18n для Email шаблонов
- [ ] Автоматическое определение языка по геолокации IP
- [ ] A/B тестирование разных версий переводов
- [ ] Перевод динамического контента (AI ответы)
- [ ] RTL support для арабского/иврита
- [ ] Pluralization rules (1 день vs 2 дня vs 5 дней)
- [ ] Date/Time форматирование по локали

## 📞 Support

Вопросы по локализации → создавайте issue с тегом `i18n`

---

**Статус:** ✅ Готово к production
**Дата:** 2025-01-26
**Версия:** 1.0.0
