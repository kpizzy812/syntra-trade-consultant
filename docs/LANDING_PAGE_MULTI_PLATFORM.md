# 🎯 Landing Page - Multi-Platform стратегия

## 📋 Текущая ситуация

### Landing page сейчас (Telegram-only):
```typescript
// frontend/app/landing/page.tsx
<Link href="https://t.me/SyntraAI_bot" target="_blank" className="btn btn-primary">
  🤖 Открыть @SyntraAI_bot
</Link>
```

**Проблема:**
- ❌ Ведет ТОЛЬКО в Telegram
- ❌ Веб-пользователи не могут зарегистрироваться
- ❌ Теряем конверсии

---

## ✅ Решение: Smart CTA (Auto-detect)

### Стратегия A: Auto-redirect (рекомендую!)

```typescript
// frontend/app/landing/page.tsx
'use client';

import { detectPlatform } from '@/lib/platform';
import { useRouter } from 'next/navigation';

export default function Landing() {
  const router = useRouter();

  const handleGetStarted = () => {
    const platform = detectPlatform();

    if (platform === 'telegram') {
      // Уже в Telegram → открыть бот
      window.open('https://t.me/SyntraAI_bot', '_blank');
    } else {
      // Веб → страница регистрации
      router.push('/auth/signup');
    }
  };

  return (
    <button onClick={handleGetStarted} className="btn btn-primary">
      Get Started
    </button>
  );
}
```

**Плюсы:**
- ✅ Автоматически выбирает правильный путь
- ✅ Простой UX (одна кнопка)
- ✅ Нет лишних шагов

---

### Стратегия B: Явный выбор платформы

```typescript
// frontend/app/landing/page.tsx
'use client';

import { useState } from 'react';
import { detectPlatform } from '@/lib/platform';

export default function Landing() {
  const [showChoice, setShowChoice] = useState(false);
  const detectedPlatform = detectPlatform();

  // Auto-detect: если в Telegram - сразу показываем Telegram кнопку
  if (detectedPlatform === 'telegram') {
    return (
      <Link
        href="https://t.me/SyntraAI_bot"
        target="_blank"
        className="btn btn-primary"
      >
        🤖 Открыть бота
      </Link>
    );
  }

  // Для веб - показываем выбор
  if (!showChoice) {
    return (
      <button
        onClick={() => setShowChoice(true)}
        className="btn btn-primary"
      >
        Get Started
      </button>
    );
  }

  // Показываем варианты
  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-xl font-bold">Choose your platform:</h3>

      {/* Telegram */}
      <Link
        href="https://t.me/SyntraAI_bot"
        target="_blank"
        className="btn btn-telegram"
      >
        <svg>...</svg>
        Continue with Telegram
      </Link>

      {/* Google */}
      <button
        onClick={() => signIn('google')}
        className="btn btn-google"
      >
        <svg>...</svg>
        Continue with Google
      </button>

      {/* Email */}
      <Link href="/auth/signup" className="btn btn-email">
        <svg>...</svg>
        Continue with Email
      </Link>
    </div>
  );
}
```

**Плюсы:**
- ✅ Явный выбор пользователя
- ✅ Показывает все опции
- ✅ Хорошо для A/B тестирования

**Минусы:**
- ❌ Лишний шаг для пользователя

---

### Стратегия C: Два CTA рядом (компромисс)

```typescript
// frontend/app/landing/page.tsx
'use client';

import { detectPlatform } from '@/lib/platform';

export default function Landing() {
  const platform = detectPlatform();
  const isTelegram = platform === 'telegram';

  return (
    <div className="flex flex-col sm:flex-row gap-4">
      {/* Primary CTA - зависит от платформы */}
      {isTelegram ? (
        <Link
          href="https://t.me/SyntraAI_bot"
          target="_blank"
          className="btn btn-primary"
        >
          🤖 Открыть бота
        </Link>
      ) : (
        <Link href="/auth/signup" className="btn btn-primary">
          Get Started Free
        </Link>
      )}

      {/* Secondary CTA */}
      {!isTelegram && (
        <Link
          href="https://t.me/SyntraAI_bot"
          target="_blank"
          className="btn btn-ghost"
        >
          Or use Telegram Bot
        </Link>
      )}
    </div>
  );
}
```

**Плюсы:**
- ✅ Оба варианта видны
- ✅ Приоритет зависит от платформы
- ✅ Хороший компромисс

---

## 🎯 Моя рекомендация: Стратегия A (Auto-redirect)

### Почему:
1. **Простой UX** - одна кнопка "Get Started"
2. **Автоматически** определяет платформу
3. **Меньше friction** - нет лишних шагов
4. **Работает везде** - Telegram, Web, Mobile

### Реализация:

```typescript
// frontend/app/landing/page.tsx
'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { detectPlatform } from '@/lib/platform';
import { useState, useEffect } from 'react';

export default function Landing() {
  const router = useRouter();
  const [platform, setPlatform] = useState<string>('web');

  useEffect(() => {
    setPlatform(detectPlatform());
  }, []);

  const handleGetStarted = () => {
    if (platform === 'telegram') {
      // В Telegram → открыть бот
      window.open('https://t.me/SyntraAI_bot', '_blank');
    } else {
      // На веб → страница регистрации
      router.push('/auth/signup');
    }
  };

  return (
    <section className="hero-container">
      <div>
        <h1>Твой личный AI-помощник по крипте</h1>
        <p>
          Syntra AI объясняет, что происходит на рынке — простым языком.
        </p>

        <div className="flex flex-wrap gap-4">
          {/* Primary CTA - Smart redirect */}
          <button
            onClick={handleGetStarted}
            className="btn btn-primary"
          >
            {platform === 'telegram' ? '🤖 Открыть бота' : 'Get Started Free'}
          </button>

          {/* Secondary CTA - Telegram channel */}
          <Link
            href="https://t.me/SyntraTrade"
            target="_blank"
            className="btn btn-ghost"
          >
            📢 Канал @SyntraTrade
          </Link>
        </div>

        <p className="text-sm text-white/40 mt-5">
          {platform === 'telegram'
            ? '5 бесплатных вопросов в день'
            : 'No credit card required • Free 5 questions/day'}
        </p>
      </div>

      {/* ... rest of landing ... */}
    </section>
  );
}
```

---

## 🎨 UI Варианты CTA

### Вариант 1: Одна кнопка (минимализм)
```tsx
<button onClick={handleSmartRedirect} className="btn btn-primary btn-lg">
  Get Started
</button>
```

### Вариант 2: С иконкой платформы
```tsx
<button onClick={handleSmartRedirect} className="btn btn-primary btn-lg">
  {platform === 'telegram' ? (
    <>
      <TelegramIcon /> Open in Telegram
    </>
  ) : (
    <>
      <SparklesIcon /> Get Started Free
    </>
  )}
</button>
```

### Вариант 3: Split button (продвинутый)
```tsx
<div className="btn-group">
  <button onClick={handleSmartRedirect} className="btn btn-primary">
    {platform === 'telegram' ? 'Open Bot' : 'Sign Up'}
  </button>

  <button onClick={toggleOptions} className="btn btn-primary-outline">
    <ChevronDownIcon />
  </button>

  {showOptions && (
    <div className="dropdown-menu">
      <button onClick={() => signInWith('telegram')}>
        <TelegramIcon /> Telegram
      </button>
      <button onClick={() => signInWith('google')}>
        <GoogleIcon /> Google
      </button>
      <button onClick={() => signInWith('email')}>
        <EmailIcon /> Email
      </button>
    </div>
  )}
</div>
```

---

## 📱 Адаптация для мобильных

### Для iOS/Android (будущее):

```typescript
const handleGetStarted = () => {
  const platform = detectPlatform();

  switch (platform) {
    case 'telegram':
      window.open('https://t.me/SyntraAI_bot', '_blank');
      break;

    case 'ios':
      // Deep link в iOS приложение (когда будет)
      window.location.href = 'syntra://signup';
      // Fallback после 1s
      setTimeout(() => {
        router.push('/auth/signup');
      }, 1000);
      break;

    case 'android':
      // Deep link в Android приложение (когда будет)
      window.location.href = 'syntra://signup';
      // Fallback
      setTimeout(() => {
        router.push('/auth/signup');
      }, 1000);
      break;

    default:
      // Web
      router.push('/auth/signup');
  }
};
```

---

## 🎯 A/B Testing стратегия

### Метрики для отслеживания:

```typescript
// Analytics tracking
const trackCTAClick = (platform: string, action: string) => {
  // Google Analytics / Mixpanel
  gtag('event', 'cta_click', {
    platform,
    action,
    page: 'landing',
  });
};

const handleGetStarted = () => {
  const platform = detectPlatform();

  trackCTAClick(platform, platform === 'telegram' ? 'open_bot' : 'signup');

  if (platform === 'telegram') {
    window.open('https://t.me/SyntraAI_bot', '_blank');
  } else {
    router.push('/auth/signup');
  }
};
```

### Варианты для A/B теста:

**Variant A: Auto-redirect (одна кнопка)**
- Метрика: Click-through rate (CTR)
- Цель: Максимизировать конверсии

**Variant B: Explicit choice (выбор платформы)**
- Метрика: Engagement rate
- Цель: Понять предпочтения пользователей

**Variant C: Two CTAs (два варианта)**
- Метрика: Split между Telegram и Web
- Цель: Найти баланс

---

## 🚀 Next Steps

### 1. Создать страницу регистрации (для веба):

```
frontend/app/auth/signup/page.tsx
```

```typescript
'use client';

export default function SignUpPage() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="max-w-md w-full">
        <h1>Create your account</h1>

        {/* Google Sign-In */}
        <button onClick={() => signIn('google')}>
          Continue with Google
        </button>

        {/* Apple Sign-In */}
        <button onClick={() => signIn('apple')}>
          Continue with Apple
        </button>

        {/* Email/Password */}
        <form onSubmit={handleEmailSignup}>
          <input type="email" placeholder="Email" />
          <input type="password" placeholder="Password" />
          <button type="submit">Sign Up</button>
        </form>

        {/* Telegram альтернатива */}
        <p className="mt-4 text-center">
          Or use{' '}
          <Link href="https://t.me/SyntraAI_bot">
            Telegram Bot
          </Link>
        </p>
      </div>
    </div>
  );
}
```

### 2. Настроить NextAuth.js

```bash
# Установить
npm install next-auth

# Создать API route
frontend/app/api/auth/[...nextauth]/route.ts
```

### 3. Update landing

Обновить все CTA кнопки на landing странице

---

## ✅ Summary

**Рекомендация:**
- ✅ Используй **Стратегию A (Auto-redirect)**
- ✅ Одна кнопка "Get Started"
- ✅ Auto-detect платформы
- ✅ Telegram → бот, Web → signup

**Преимущества:**
- Простой UX
- Работает для всех платформ
- Легко A/B тестировать
- Готов к iOS/Android

**Хочешь реализовать?** Начинаем с обновления landing page! 🚀
