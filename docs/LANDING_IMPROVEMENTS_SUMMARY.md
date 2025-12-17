# 🚀 Landing Page Improvements - Summary

## ✅ Что реализовано (High Priority)

### 1. **Детальное отслеживание кликов через PostHog**

#### Созданные компоненты:
- `TrackedLink` - компонент ссылки с автоматическим tracking ([TrackedLink.tsx](../frontend/components/analytics/TrackedLink.tsx))
- `TrackedButton` - кнопка с tracking ([TrackedButton.tsx](../frontend/components/analytics/TrackedButton.tsx))

#### Что отслеживается:
- Все клики на CTA кнопки ("Открыть бота", "Канал @SyntraTrade")
- UTM параметры (источник трафика) автоматически
- Timestamp, page_url, button_text
- Кастомные eventProperties для каждого клика

#### Пример использования:
```tsx
import TrackedLink from '@/components/analytics/TrackedLink';

<TrackedLink
  href="https://t.me/SyntraAI_bot"
  eventName="bot_opened"
  eventProperties={{ source: 'hero_cta' }}
  className="btn btn-primary"
>
  🤖 Открыть бота
</TrackedLink>
```

---

### 2. **Отслеживание скролла до секций**

#### Созданные хуки:
- `useScrollTracking` - отслеживание просмотра конкретной секции ([useScrollTracking.ts](../frontend/hooks/useScrollTracking.ts))
- `useScrollDepthTracking` - отслеживание глубины скролла (25%, 50%, 75%, 100%)

#### Что отслеживается:
- Когда пользователь доскролливает до секции (pricing, features, faq, и т.д.)
- Глубина скролла страницы (вехи: 25%, 50%, 75%, 100%)
- UTM параметры автоматически прикрепляются

#### Пример использования:
```tsx
import { useScrollTracking, useScrollDepthTracking } from '@/hooks/useScrollTracking';

function PricingSection() {
  useScrollTracking({
    sectionId: 'pricing',
    sectionName: 'Pricing Section',
    threshold: 0.5, // 50% видимости
  });

  return <section id="pricing">...</section>;
}

// В корне страницы
function LandingPage() {
  useScrollDepthTracking();
  return <div>...</div>;
}
```

---

### 3. **A/B тестирование заголовков через PostHog**

#### Созданные хуки:
- `useHeroTitleABTest` - A/B/C тестирование заголовка Hero секции ([useABTest.ts](../frontend/hooks/useABTest.ts))
- `useABTestConversion` - отслеживание конверсии в A/B тесте

#### Варианты заголовков:
- **Вариант A**: "AI-платформа для криптотрейдеров" (текущий)
- **Вариант B**: "Твой личный AI-помощник по крипте"
- **Вариант C**: "AI, который объясняет крипту простым языком"

#### Пример использования:
```tsx
import { useHeroTitleABTest, HERO_TITLE_VARIANTS } from '@/hooks/useABTest';

function HeroSection() {
  const variant = useHeroTitleABTest();
  const title = HERO_TITLE_VARIANTS[variant];

  return <h1>{title}</h1>;
}
```

#### Настройка в PostHog:
1. Зайти в PostHog Dashboard → Feature Flags
2. Создать feature flag `hero-title-test`
3. Настроить варианты: `a` (33%), `b` (33%), `c` (34%)
4. Включить для всех пользователей

---

### 4. **Анимированный аватар бота с glow эффектом** ✨

#### Созданный компонент:
- `BotAvatar` - анимированный аватар с glow/pulse ([BotAvatar.tsx](../frontend/components/BotAvatar.tsx))

#### Фичи:
- Плавная пульсация (scale animation)
- Многослойный glow эффект (3 слоя)
- Настраиваемый размер
- Опциональная анимация (можно отключить для mobile)

#### Пример использования:
```tsx
import BotAvatar from '@/components/BotAvatar';

// С анимацией
<BotAvatar size={40} animated={true} />

// Без анимации (для mobile)
<BotAvatar size={40} animated={false} />
```

#### Где использовать:
- В header секциях с аватаром бота
- В chat примерах
- На странице "О боте"

---

## 📋 Что осталось сделать (Pending)

### 5. **Интеграция всех компонентов в landing page**

Нужно обновить [landing/page.tsx](../frontend/app/landing/page.tsx):

```tsx
// 1. Импорты
import TrackedLink from '@/components/analytics/TrackedLink';
import { useScrollTracking, useScrollDepthTracking } from '@/hooks/useScrollTracking';
import { useHeroTitleABTest, HERO_TITLE_VARIANTS } from '@/hooks/useABTest';
import BotAvatar from '@/components/BotAvatar';

export default function LandingPage() {
  // A/B тест заголовка
  const heroVariant = useHeroTitleABTest();
  const heroTitle = HERO_TITLE_VARIANTS[heroVariant];

  // Отслеживание глубины скролла
  useScrollDepthTracking();

  return (
    <>
      {/* Hero */}
      <section id="hero">
        <h1>{heroTitle}</h1>
        <TrackedLink
          href="https://t.me/SyntraAI_bot"
          eventName="bot_opened"
          eventProperties={{ source: 'hero_cta' }}
          className="btn btn-primary"
        >
          🤖 Начать бесплатно
        </TrackedLink>

        {/* Анимированный аватар */}
        <BotAvatar size={40} animated={true} />
      </section>

      {/* Pricing - с tracking скролла */}
      <PricingSection />

      {/* Features - с tracking скролла */}
      <FeaturesSection />
    </>
  );
}

// Пример секции с tracking
function PricingSection() {
  useScrollTracking({
    sectionId: 'pricing',
    sectionName: 'Pricing Section',
    threshold: 0.5,
  });

  return (
    <section id="pricing">
      <h2>Начни с 7-Day Premium Trial</h2>
      <TrackedLink
        href="https://t.me/SyntraAI_bot"
        eventName="bot_opened"
        eventProperties={{ source: 'pricing_cta' }}
        className="btn btn-primary"
      >
        Начать Premium trial
      </TrackedLink>
    </section>
  );
}
```

#### Checklist для интеграции:
- [ ] Заменить все `<Link>` на `<TrackedLink>` для CTA кнопок
- [ ] Добавить `useScrollTracking` в ключевые секции (pricing, features, faq, referral)
- [ ] Добавить `useScrollDepthTracking` в корень страницы
- [ ] Интегрировать `useHeroTitleABTest` для A/B теста заголовка
- [ ] Заменить обычные аватары на `<BotAvatar>` компонент
- [ ] Обновить [LiveChatExamplesCompact.tsx](../frontend/components/landing/LiveChatExamplesCompact.tsx) для использования `<BotAvatar>`

---

### 6. **Расширить Framer Motion анимации**

Секции уже частично анимированы, но можно улучшить:

```tsx
// Добавить staggered animations для карточек
const staggerFast = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.08,
    },
  },
};

<motion.div variants={staggerFast}>
  {features.map((feature) => (
    <motion.div variants={fadeInUp} className="card">
      {feature.content}
    </motion.div>
  ))}
</motion.div>
```

**Где применить:**
- Карточки в секции "For Who"
- Features карточки
- FAQ items
- Pricing cards

---

### 7. **Parallax эффект на background blobs**

Добавить parallax используя Framer Motion `useScroll`:

```tsx
import { useScroll, useTransform, motion } from 'framer-motion';

function BackgroundBlobs() {
  const { scrollYProgress } = useScroll();

  // Blob 1 движется медленнее
  const y1 = useTransform(scrollYProgress, [0, 1], [0, -100]);

  // Blob 2 движется быстрее
  const y2 = useTransform(scrollYProgress, [0, 1], [0, 200]);

  return (
    <>
      <motion.div className="blob-1" style={{ y: y1 }} />
      <motion.div className="blob-2" style={{ y: y2 }} />
    </>
  );
}
```

**Эффект:**
- Blobs движутся с разной скоростью при скролле
- Создает глубину и динамику
- Усиливает premium визуал

---

## 📊 События PostHog - что отслеживается

### Автоматические события:
| Событие | Когда срабатывает | Параметры |
|---------|-------------------|-----------|
| `$pageview` | Просмотр страницы | `$current_url`, UTM params |
| `section_viewed` | Скролл до секции | `section_id`, `section_name`, `scroll_depth`, UTM |
| `scroll_depth_reached` | Достижение вехи скролла | `scroll_depth` (25/50/75/100), UTM |

### Клики на CTA:
| Событие | Где срабатывает | Параметры |
|---------|----------------|-----------|
| `bot_opened` | Клик "Открыть бота" | `source` (hero/pricing/final_cta), `link_url`, UTM |
| `channel_opened` | Клик "@SyntraTrade" | `source`, `link_url`, UTM |
| `link_clicked` | Любой tracked link | `link_url`, `link_text`, UTM |

### A/B тесты:
| Событие | Когда срабатывает | Параметры |
|---------|-------------------|-----------|
| `ab_test_assigned` | Назначение варианта | `test_name`, `variant` (A/B/C), `title` |
| `ab_test_conversion_bot_opened` | Конверсия в A/B тесте | `variant`, UTM |

---

## 🎯 Воронка для анализа в PostHog

### Пример воронки "От лендинга до бота":
1. **Шаг 1:** `$pageview` (landing page) - 100%
2. **Шаг 2:** `section_viewed` (pricing) - ~60%
3. **Шаг 3:** `bot_opened` - ~15-20%

### Как создать в PostHog:
1. Dashboard → Insights → New Insight → Funnel
2. Добавить шаги:
   - Event: `$pageview` → Filter: `$current_url contains 'landing'`
   - Event: `section_viewed` → Filter: `section_name = 'Pricing Section'`
   - Event: `bot_opened`
3. Group by: `utm_source` (для анализа каналов)

---

## 🔧 Настройка окружения

### 1. Добавить в `.env.local`:
```bash
NEXT_PUBLIC_POSTHOG_KEY=phc_your_project_api_key_here
NEXT_PUBLIC_POSTHOG_HOST=https://us.i.posthog.com
```

### 2. Проверить инициализацию PostHog:
- Открыть консоль браузера
- Выполнить: `console.log(posthog.__loaded)` → должно быть `true`
- Проверить Live Events в PostHog Dashboard

---

## 📚 Документация

- [Полная инструкция по аналитике](./LANDING_ANALYTICS_SETUP.md)
- [UTM Tracking Guide](./UTM_TRACKING_GUIDE.md)
- [Copy-Paste примеры UTM ссылок](./COPY_PASTE_EXAMPLES.md)

---

## ⚡ Quick Start - Интеграция за 10 минут

1. **Добавь PostHog ключ в `.env.local`**
2. **Замени Link на TrackedLink:**
   ```tsx
   // Было:
   <Link href="https://t.me/SyntraAI_bot">Открыть бота</Link>

   // Стало:
   <TrackedLink
     href="https://t.me/SyntraAI_bot"
     eventName="bot_opened"
     eventProperties={{ source: 'hero' }}
   >
     Открыть бота
   </TrackedLink>
   ```
3. **Добавь scroll tracking:**
   ```tsx
   useScrollDepthTracking(); // в корне страницы
   useScrollTracking({ sectionId: 'pricing', sectionName: 'Pricing' }); // в секциях
   ```
4. **Запусти A/B тест:**
   ```tsx
   const variant = useHeroTitleABTest();
   const title = HERO_TITLE_VARIANTS[variant];
   ```
5. **Используй анимированный аватар:**
   ```tsx
   <BotAvatar size={40} animated={true} />
   ```

---

## 🎉 Результаты после внедрения

### Что получим:
✅ **Воронка конверсии** - понимание, где пользователи отваливаются
✅ **Эффективность каналов** - какие UTM источники лучше конвертируют
✅ **Поведение пользователей** - до какой секции доскролливают
✅ **A/B тесты** - какой заголовок лучше работает
✅ **Premium визуал** - анимированный аватар усиливает wow-эффект

### Метрики для отслеживания:
- **CTR на "Открыть бота"** - цель 15-20%
- **Scroll depth 75%+** - цель 40-50%
- **Section view rate (pricing)** - цель 60-70%
- **Winning variant A/B test** - через 1000+ визитов

---

**Готово! 🚀** Все компоненты созданы, осталось только интегрировать их в landing page.
