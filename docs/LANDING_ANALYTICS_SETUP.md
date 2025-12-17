# 📊 Landing Page Analytics Setup Guide

## Обзор

Комплексная система аналитики для лендинга Syntra AI, включающая:
- ✅ **UTM tracking** - отслеживание источников трафика
- ✅ **PostHog интеграция** - продвинутая аналитика и A/B тесты
- ✅ **Отслеживание кликов** - все CTA кнопки и ссылки
- ✅ **Scroll tracking** - глубина скролла и просмотр секций
- ✅ **A/B тестирование** - заголовков и других элементов

---

## 1. Настройка PostHog

### Шаг 1: Добавить переменные окружения

В `.env.local`:

```bash
NEXT_PUBLIC_POSTHOG_KEY=your_posthog_project_api_key
NEXT_PUBLIC_POSTHOG_HOST=https://us.i.posthog.com
```

### Шаг 2: PostHog уже инициализирован

Проверь `frontend/components/providers/PostHogProvider.tsx` - инициализация происходит автоматически.

---

## 2. Использование TrackedLink для отслеживания кликов

### Базовое использование

```tsx
import TrackedLink from '@/components/analytics/TrackedLink';

<TrackedLink
  href="https://t.me/SyntraAI_bot"
  target="_blank"
  eventName="bot_opened"
  eventProperties={{ source: 'hero_cta' }}
  className="btn btn-primary"
>
  Открыть бота
</TrackedLink>
```

### Отслеживаемые параметры

- `link_url` - URL ссылки
- `link_text` - текст ссылки
- `link_target` - target атрибут
- `utm_source`, `utm_medium`, и т.д. - UTM параметры (автоматически)
- `timestamp` - время клика
- `page_url` - URL страницы

---

## 3. Отслеживание скролла до секций

### useScrollTracking

Добавь в каждую важную секцию:

```tsx
import { useScrollTracking } from '@/hooks/useScrollTracking';

function PricingSection() {
  useScrollTracking({
    sectionId: 'pricing',
    sectionName: 'Pricing Section',
    threshold: 0.5, // 50% видимости
  });

  return (
    <section id="pricing">
      {/* контент */}
    </section>
  );
}
```

### useScrollDepthTracking

Отслеживает глубину скролла страницы (25%, 50%, 75%, 100%):

```tsx
import { useScrollDepthTracking } from '@/hooks/useScrollTracking';

export default function LandingPage() {
  useScrollDepthTracking(); // Добавь в корень страницы

  return <div>...</div>;
}
```

---

## 4. A/B тестирование заголовков

### Использование хука

```tsx
import { useHeroTitleABTest, HERO_TITLE_VARIANTS } from '@/hooks/useABTest';

export default function HeroSection() {
  const variant = useHeroTitleABTest();
  const title = HERO_TITLE_VARIANTS[variant];

  return <h1>{title}</h1>;
}
```

### Варианты заголовков

- **Вариант A**: "AI-платформа для криптотрейдеров"
- **Вариант B**: "Твой личный AI-помощник по крипте"
- **Вариант C**: "AI, который объясняет крипту простым языком"

### Настройка Feature Flag в PostHog

1. Зайди в PostHog Dashboard → Feature Flags
2. Создай новый feature flag `hero-title-test`
3. Настрой варианты:
   - Вариант: `a` (33%)
   - Вариант: `b` (33%)
   - Вариант: `c` (34%)
4. Включи flag для всех пользователей

### Отслеживание конверсии

```tsx
import { useABTestConversion } from '@/hooks/useABTest';

function CTAButton() {
  const trackConversion = useABTestConversion();

  const handleClick = () => {
    trackConversion('bot_opened', {
      button_location: 'hero',
    });
  };

  return <button onClick={handleClick}>Открыть бота</button>;
}
```

---

## 5. События, которые отслеживаются

### Автоматические события

- `$pageview` - просмотр страницы
- `section_viewed` - просмотр секции (pricing, features, faq, и т.д.)
- `scroll_depth_reached` - достижение глубины скролла (25%, 50%, 75%, 100%)

### Клики на CTA

- `bot_opened` - клик на ссылку бота
  - `source`: 'hero', 'pricing', 'final_cta', и т.д.
- `channel_opened` - клик на ссылку канала @SyntraTrade
- `link_clicked` - любой другой клик на ссылку

### A/B тесты

- `ab_test_assigned` - пользователю назначен вариант теста
  - `test_name`: 'hero_title_test'
  - `variant`: 'A', 'B', или 'C'
  - `title`: текст заголовка
- `ab_test_conversion_bot_opened` - конверсия в тесте

---

## 6. Анализ воронки в PostHog

### Пример воронки

1. **Шаг 1**: `$pageview` (landing page)
2. **Шаг 2**: `section_viewed` (pricing)
3. **Шаг 3**: `bot_opened`

### Создание воронки в PostHog

1. Dashboard → Insights → New Insight → Funnel
2. Добавь шаги воронки
3. Группируй по UTM параметрам для анализа каналов

---

## 7. Примеры запросов в PostHog

### Какие источники трафика приводят больше конверсий?

Фильтр: `bot_opened` → Group by: `utm_source`

### Какой вариант заголовка лучше конвертирует?

Фильтр: `ab_test_conversion_bot_opened` → Group by: `variant`

### До какой секции доскролливают пользователи?

Фильтр: `section_viewed` → Breakdown: `section_name`

---

## 8. Checklist для внедрения на лендинг

- [ ] Добавить NEXT_PUBLIC_POSTHOG_KEY в `.env.local`
- [ ] Заменить все `<Link>` на `<TrackedLink>` для важных CTA
- [ ] Добавить `useScrollTracking` в ключевые секции
- [ ] Добавить `useScrollDepthTracking` в корень страницы
- [ ] Настроить A/B тест заголовков через `useHeroTitleABTest`
- [ ] Создать feature flag `hero-title-test` в PostHog
- [ ] Настроить воронку в PostHog для анализа
- [ ] Проверить события в PostHog Live Events

---

## 9. Отладка

### Проверка в консоли

```javascript
// Проверить, что PostHog загружен
console.log(posthog.__loaded); // должно быть true

// Посмотреть текущие feature flags
console.log(posthog.getFeatureFlag('hero-title-test'));

// Посмотреть UTM параметры
console.log(sessionStorage.getItem('syntra_utm_params'));
```

### PostHog Live Events

1. PostHog Dashboard → Live Events
2. Проверь, что события приходят в реальном времени
3. Проверь, что UTM параметры прикрепляются к событиям

---

## 10. Best Practices

✅ **DO:**
- Всегда используй `TrackedLink` для важных CTA
- Добавляй `eventProperties` для контекста
- Используй понятные имена событий (например, `bot_opened`, а не `click1`)
- Отслеживай ключевые секции через `useScrollTracking`

❌ **DON'T:**
- Не отслеживай каждый клик (только важные действия)
- Не забывай про GDPR (PostHog GDPR-compliant)
- Не отслеживай персональные данные без согласия

---

**Готово! 🎉** Теперь у тебя полная аналитика лендинга с отслеживанием воронки и A/B тестами.
