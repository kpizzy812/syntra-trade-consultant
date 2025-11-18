# 🎨 Syntra Design System

> Полное руководство по созданию приложений в стиле Syntra — минималистичный dark mode дизайн с glassmorphism эффектами

---

## 📋 Содержание

1. [Обзор дизайн-системы](#обзор-дизайн-системы)
2. [Цветовая палитра](#цветовая-палитра)
3. [Типографика](#типографика)
4. [Glassmorphism эффекты](#glassmorphism-эффекты)
5. [Компоненты](#компоненты)
6. [Анимации](#анимации)
7. [Layout & Spacing](#layout--spacing)
8. [Telegram Mini App интеграция](#telegram-mini-app-интеграция)
9. [Tech Stack](#tech-stack)
10. [Best Practices](#best-practices)

---

## 🎯 Обзор дизайн-системы

Syntra использует **минималистичную черно-синюю схему** с акцентом на:

- ✨ **Glassmorphism** — полупрозрачные элементы с blur эффектом
- 🌑 **Dark Mode First** — основной фон #000000
- 💙 **Синий акцент** — #3B82F6 для интерактивных элементов
- 📱 **Mobile-First** — оптимизация для Telegram Mini App
- ⚡ **Плавные анимации** — framer-motion для всех переходов

---

## 🎨 Цветовая палитра

### Основные цвета

```css
/* Фоновые цвета */
--bg-primary: #000000;      /* Основной фон */
--bg-secondary: #111111;    /* Вторичный фон */
--bg-card: #1A1A1A;         /* Фон карточек */
--bg-card-hover: #222222;   /* Hover состояние карточек */

/* Текстовые цвета */
--text-primary: #FFFFFF;    /* Основной текст */
--text-secondary: #A3A3A3;  /* Вторичный текст */
--text-muted: #525252;      /* Приглушенный текст */

/* Границы */
--border-primary: #262626;  /* Основные границы */
--border-accent: #404040;   /* Акцентные границы */
```

### Акцентные цвета

```css
/* Синяя палитра (основной акцент) */
--primary-blue: #3B82F6;        /* Основной синий */
--primary-blue-dark: #2563EB;   /* Темный синий */
--primary-blue-light: #60A5FA;  /* Светлый синий */
--accent-blue: #1D4ED8;         /* Акцентный синий */

/* Статусные цвета */
--success: #22C55E;   /* Зеленый для успеха */
--danger: #EF4444;    /* Красный для ошибок */
--warning: #F59E0B;   /* Желтый для предупреждений */
```

### Как использовать

```tsx
// В Tailwind
<div className="bg-[#1A1A1A] text-white border border-[#262626]">
  <p className="text-[#A3A3A3]">Вторичный текст</p>
  <button className="bg-[#3B82F6] hover:bg-[#2563EB]">Кнопка</button>
</div>

// Через CSS переменные
<div className="bg-bg-card text-text-primary border-border-primary">
  Контент
</div>
```

---

## 📝 Типографика

### Заголовки

```css
/* Очень крупный заголовок */
.heading-xl {
  font-size: 2.5rem;    /* 40px */
  font-weight: 800;
  line-height: 1.2;
  color: var(--text-primary);
}

/* Большой заголовок */
.heading-lg {
  font-size: 2rem;      /* 32px */
  font-weight: 700;
  line-height: 1.3;
  color: var(--text-primary);
}

/* Средний заголовок */
.heading-md {
  font-size: 1.5rem;    /* 24px */
  font-weight: 600;
  line-height: 1.4;
  color: var(--text-primary);
}
```

### Примеры использования

```tsx
// Заголовок карточки
<h2 className="text-white font-bold text-lg">
  Blue Chip Pool
</h2>

// Крупный баланс
<h1 className="text-3xl font-bold text-white">
  ${formatCurrency(balance)}
</h1>

// Описание
<p className="text-gray-400 text-xs">
  AI Trading Pool
</p>

// Микро-текст
<span className="text-[10px] text-zinc-500">
  Daily yield: 0.5-2%
</span>
```

---

## ✨ Glassmorphism эффекты

### Базовый Glassmorphism

```css
.glassmorphism {
  background: rgba(255, 255, 255, 0.02);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow:
    0 4px 16px rgba(0, 0, 0, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.03);
}
```

### Glassmorphism для карточек

```css
.glassmorphism-card {
  background: rgba(255, 255, 255, 0.04);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
```

### Glassmorphism для модалок

```css
.glassmorphism-modal {
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(32px);
  -webkit-backdrop-filter: blur(32px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow:
    0 16px 64px rgba(0, 0, 0, 0.5),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}
```

### Glassmorphism для header

```css
.glassmorphism-header {
  position: sticky;
  top: 0;
  z-index: 40;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
}
```

### Использование в компонентах

```tsx
// Карточка пула
<div className="glassmorphism-card rounded-2xl p-5">
  <h2 className="text-white font-bold">Blue Chip Pool</h2>
  <p className="text-gray-400 text-xs">AI Trading</p>
</div>

// Модальное окно
<div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center">
  <div className="glassmorphism-modal rounded-2xl p-4 max-w-md">
    Контент модалки
  </div>
</div>

// Хедер
<header className="glassmorphism-header px-4 py-3">
  <h1 className="text-white font-bold">Syntra</h1>
</header>
```

---

## 🧩 Компоненты

### 1. Карточка с балансом (BalanceCard)

```tsx
<div className="glassmorphism-card rounded-2xl p-5 mb-4">
  {/* Заголовок */}
  <div className="text-center flex-1">
    <p className="text-gray-400 text-sm mb-2 font-medium">
      Balance
    </p>
    <div className="flex items-baseline gap-3 justify-center">
      <h1 className="text-3xl font-bold text-white">
        ${formatCurrency(balance)}
      </h1>
      <div className="px-3 py-1.5 rounded-full text-xs font-semibold border bg-green-500/10 text-green-400 border-green-500/20">
        +12.5%
      </div>
    </div>
  </div>

  {/* Статистика в 3 колонки */}
  <div className="grid grid-cols-3 gap-4 mt-4">
    <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
      <p className="text-gray-400 text-xs mb-2 font-medium">Total P&L</p>
      <p className="font-bold text-sm text-green-400">+$125.00</p>
    </div>

    <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
      <p className="text-gray-400 text-xs mb-2 font-medium">Invested</p>
      <p className="font-bold text-sm text-white">$1,000.00</p>
    </div>

    <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700/50">
      <p className="text-gray-400 text-xs mb-2 font-medium">Withdrawn</p>
      <p className="font-bold text-sm text-blue-400">$50.00</p>
    </div>
  </div>
</div>
```

### 2. Карточка пула (PoolCard)

```tsx
<div className="glassmorphism-card rounded-2xl overflow-hidden">
  {/* Верхняя часть - кликабельная */}
  <button className="w-full p-5 flex items-center justify-between text-left hover:bg-gray-800/20 transition-colors">
    <div className="flex items-center gap-3 flex-1">
      {/* Иконки криптовалют */}
      <div className="flex -space-x-2">
        <div className="w-8 h-8 rounded-full border-2 border-gray-800 bg-gray-900 overflow-hidden">
          <img src="/icons/crypto/BTC.png" alt="BTC" className="w-full h-full object-cover" />
        </div>
        <div className="w-8 h-8 rounded-full border-2 border-gray-800 bg-gray-900 overflow-hidden">
          <img src="/icons/crypto/ETH.png" alt="ETH" className="w-full h-full object-cover" />
        </div>
      </div>

      <div>
        <h2 className="text-white font-bold text-lg">Blue Chip</h2>
        <p className="text-gray-400 text-xs">BTC, ETH, SOL Trading</p>
      </div>
    </div>

    {/* Бейдж доходности */}
    <div className="bg-gradient-to-br from-green-500/10 to-emerald-500/10 border border-green-500/30 rounded-full px-2.5 py-1.5">
      <div className="text-green-400 font-bold text-base text-center"
           style={{ filter: 'drop-shadow(0 0 6px rgba(52, 211, 153, 0.4))' }}>
        2.0%
      </div>
      <p className="text-gray-400 text-[8px] text-center font-medium mt-0.5">daily</p>
    </div>
  </button>

  {/* Раскрывающийся контент */}
  <div className="px-5 pb-5">
    {/* Баланс */}
    <div className="bg-gray-800/30 rounded-xl p-3.5 mb-4">
      <p className="text-gray-400 text-[10px] mb-1 font-medium">Your Balance</p>
      <p className="font-bold text-xl text-blue-400"
         style={{ filter: 'drop-shadow(0 0 8px rgba(59, 130, 246, 0.5))' }}>
        $500.00
      </p>
    </div>

    {/* Кнопка Invest с пульсацией */}
    <button className="relative bg-blue-600 hover:bg-blue-700 text-white font-medium w-full py-3 rounded-full transition-all"
            style={{ boxShadow: '0 0 20px rgba(59, 130, 246, 0.4)' }}>
      <div className="flex items-center justify-center gap-2">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
          {/* Иконка инвестиций */}
        </svg>
        <span className="text-sm font-bold">Invest</span>
      </div>
      <p className="text-[9px] text-blue-100 mt-0.5 opacity-90">Start earning daily</p>
    </button>
  </div>
</div>
```

### 3. Модальное окно (Modal)

```tsx
<div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-3">
  <motion.div
    initial={{ scale: 0.95, opacity: 0 }}
    animate={{ scale: 1, opacity: 1 }}
    className="w-full max-w-md glassmorphism-modal p-4 rounded-2xl space-y-3"
  >
    {/* Заголовок */}
    <h2 className="text-white text-lg font-bold text-center">
      Invest in Blue Chip
    </h2>

    {/* Ввод суммы */}
    <div className="text-center">
      <p className="text-zinc-400 text-xs mb-1">Amount:</p>
      <div className="flex items-center justify-center gap-2">
        <input
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="w-32 text-center text-3xl font-bold bg-transparent text-white border-b-2 border-blue-500 focus:outline-none"
        />
        <span className="text-2xl text-zinc-400">USD</span>
      </div>
    </div>

    {/* Ползунок */}
    <div className="px-1">
      <input
        type="range"
        min="20"
        max="1000"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        className="w-full h-2 bg-gray-700 rounded-lg slider"
      />
    </div>

    {/* Быстрый выбор */}
    <div className="grid grid-cols-4 gap-2">
      {[50, 100, 500, 1000].map(preset => (
        <button
          key={preset}
          onClick={() => setAmount(preset)}
          className="py-2 px-3 rounded-lg text-xs font-medium bg-gray-700 hover:bg-gray-600"
        >
          ${preset}
        </button>
      ))}
    </div>

    {/* Прогноз прибыли */}
    <div className="bg-blue-900/20 border border-blue-500/30 rounded-xl p-3">
      <p className="text-blue-400 text-xs font-medium mb-2">Profit Forecast</p>
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-gray-900/30 rounded-lg p-2">
          <p className="text-[10px] text-zinc-400 mb-1">Day</p>
          <p className="text-[11px] font-bold text-white">$10.00</p>
        </div>
        <div className="bg-gray-900/30 rounded-lg p-2">
          <p className="text-[10px] text-zinc-400 mb-1">Week</p>
          <p className="text-[11px] font-bold text-white">$70.00</p>
        </div>
        <div className="bg-gray-900/30 rounded-lg p-2">
          <p className="text-[10px] text-zinc-400 mb-1">Month</p>
          <p className="text-[11px] font-bold text-white">$300.00</p>
        </div>
      </div>
    </div>
  </motion.div>
</div>
```

### 4. Tab Bar (Нижняя навигация)

```tsx
<div className="glassmorphism-card rounded-3xl p-0.5">
  <div className="flex">
    {tabs.map((tab, index) => {
      const isActive = tab.key === activeTab;

      return (
        <div key={tab.key} className="flex-1 relative">
          {/* Активный индикатор с анимацией */}
          {isActive && (
            <motion.div
              className="absolute inset-0 glassmorphism-button rounded-xl"
              layoutId="activeTab"
              transition={{ type: "spring", duration: 0.3 }}
            />
          )}

          <button
            onClick={() => onTabChange(tab.key)}
            className={`
              relative w-full py-2 px-2 text-center font-medium text-[10px]
              transition-all duration-200 rounded-xl
              flex flex-col items-center justify-center gap-0.5
              ${isActive ? 'text-white z-10' : 'text-gray-400 hover:text-gray-200'}
            `}
          >
            <TabIcon isActive={isActive} />
            <span className="font-semibold tracking-wide">{tab.label}</span>
          </button>
        </div>
      );
    })}
  </div>
</div>
```

### 5. Кнопки

```tsx
{/* Основная кнопка */}
<button className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-5 py-2.5 rounded-full transition-colors">
  Continue
</button>

{/* Вторичная кнопка */}
<button className="bg-gray-700 hover:bg-gray-600 text-white font-medium px-5 py-2.5 rounded-full transition-colors">
  Cancel
</button>

{/* Кнопка с иконкой */}
<button className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-5 py-2.5 rounded-full flex items-center gap-2">
  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
    {/* SVG иконка */}
  </svg>
  Withdraw
</button>

{/* Кнопка с эффектом свечения */}
<button
  className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-5 py-2.5 rounded-full"
  style={{ boxShadow: '0 0 20px rgba(59, 130, 246, 0.4)' }}
>
  Invest Now
</button>

{/* Кнопка быстрого выбора */}
<button className="py-2 px-3 rounded-lg text-xs font-medium bg-gray-700 hover:bg-gray-600 text-gray-300">
  $100
</button>
```

---

## 🎬 Анимации

### Используемая библиотека

**Framer Motion** — основная библиотека для всех анимаций

```bash
npm install framer-motion
```

### Базовые анимации

```tsx
import { motion, AnimatePresence } from 'framer-motion';

// Fade in с масшт��бированием (модалки)
<motion.div
  initial={{ scale: 0.95, opacity: 0 }}
  animate={{ scale: 1, opacity: 1 }}
  exit={{ scale: 0.95, opacity: 0 }}
  className="glassmorphism-modal"
>
  Контент
</motion.div>

// Slide up (появление карточек)
<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.4 }}
>
  Карточка
</motion.div>

// Пульсация (кнопка Invest)
<motion.div
  animate={{ scale: [1, 1.05, 1] }}
  transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
>
  <button>Invest</button>
</motion.div>
```

### Анимация раскрытия (Accordion)

```tsx
<AnimatePresence initial={false}>
  {isExpanded && (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.2, ease: 'easeInOut' }}
      style={{ overflow: 'hidden' }}
    >
      Скрытый контент
    </motion.div>
  )}
</AnimatePresence>
```

### Анимация переключения табов

```tsx
{isActive && (
  <motion.div
    className="absolute inset-0 glassmorphism-button"
    layoutId="activeTab"
    transition={{ type: "spring", duration: 0.3 }}
  />
)}
```

### CSS Keyframes анимации

```css
/* Fade in */
@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.animate-fade-in {
  animation: fade-in 0.3s ease-out;
}

/* Slide up */
@keyframes slide-up {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-slide-up {
  animation: slide-up 0.4s ease-out;
}

/* Пульсация для подсветки */
@keyframes onboarding-pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7);
    border-color: rgba(59, 130, 246, 0.8);
  }
  50% {
    box-shadow: 0 0 0 12px rgba(59, 130, 246, 0);
    border-color: rgba(59, 130, 246, 1);
  }
}

.onboarding-highlight {
  animation: onboarding-pulse 2s ease-out;
  border: 2px solid rgba(59, 130, 246, 0.8);
}
```

---

## 📐 Layout & Spacing

### Mobile-First Layout

```tsx
// Основная структура для Telegram Mini App
<div className="min-h-screen bg-black">
  {/* Header */}
  <header className="glassmorphism-header px-4 py-3">
    <h1>Syntra</h1>
  </header>

  {/* Content */}
  <main className="px-4 pt-2 pb-24">
    <div className="space-y-3">
      {/* Карточки с отступом 12px (space-y-3) */}
    </div>
  </main>

  {/* Fixed Tab Bar */}
  <div
    className="fixed left-1/2 -translate-x-1/2 w-[85%] max-w-[520px] z-50"
    style={{
      bottom: 'max(env(safe-area-inset-bottom, 8px), 8px)'
    }}
  >
    <TabBar />
  </div>
</div>
```

### Отступы (padding/margin)

```css
/* Стандартные отступы */
px-4  /* 16px горизонтальный padding */
py-3  /* 12px вертикальный padding */
p-5   /* 20px padding со всех сторон */

/* Отступы между элементами */
gap-2   /* 8px */
gap-3   /* 12px */
gap-4   /* 16px */

/* Вертикальные отступы между секциями */
space-y-3  /* 12px между child элементами */
space-y-4  /* 16px между child элементами */
```

### Responsive Design

```tsx
// Desktop adaptation (max-width для Telegram Desktop)
<div className="w-full max-w-md glassmorphism-modal">
  {/* Модалка ограничена 448px */}
</div>

// Центрирование с ограничением ширины
<div className="max-w-[520px] mx-auto">
  Контент
</div>

// Grid responsive
<div className="grid grid-cols-3 gap-4">
  {/* 3 колонки на мобильных */}
</div>

<div className="grid grid-cols-2 md:grid-cols-4 gap-2">
  {/* 2 колонки на мобильных, 4 на планшетах */}
</div>
```

---

## 📱 Telegram Mini App интеграция

### Safe Areas (iOS Notch)

```css
/* CSS переменные для safe areas */
:root {
  --tg-safe-area-inset-top: 0px;
  --tg-safe-area-inset-bottom: 0px;
  --tg-content-safe-area-inset-top: 0px;
  --tg-content-safe-area-inset-bottom: 0px;
}

/* Применение safe areas */
.glassmorphism-header {
  padding-top: var(--tg-content-safe-area-inset-top);
}

/* Bottom padding для TabBar */
.safe-area-bottom {
  padding-bottom: max(
    env(safe-area-inset-bottom),
    var(--tg-safe-area-inset-bottom),
    8px
  );
}
```

### Fullscreen режим

```css
/* Mobile body - блокирует swipe-down закрытие */
.mobile-body {
  overflow: hidden;
  height: 100dvh; /* Dynamic viewport height */
  padding-top: var(--tg-safe-area-inset-top);
  padding-bottom: var(--tg-safe-area-inset-bottom);
}

/* Wrapper для fullscreen контента */
.mobile-wrap {
  position: absolute;
  inset: 0;
  overflow-x: hidden;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}
```

### Telegram WebApp API

```tsx
import { useEffect } from 'react';

// Вибрация при клике
const vibrate = () => {
  if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
    window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
  }
};

// Использование в кнопках
<button onClick={() => {
  vibrate();
  handleAction();
}}>
  Click me
</button>

// Main Button
useEffect(() => {
  if (window.Telegram?.WebApp) {
    const mainButton = window.Telegram.WebApp.MainButton;
    mainButton.text = 'Continue';
    mainButton.color = '#3B82F6';
    mainButton.onClick(() => handleSubmit());
    mainButton.show();

    return () => mainButton.hide();
  }
}, []);
```

---

## 🛠 Tech Stack

### Core Dependencies

```json
{
  "dependencies": {
    "next": "15.3.2",                    // Next.js 15 с App Router
    "react": "^19.0.0",                  // React 19
    "typescript": "^5",                  // TypeScript
    "tailwindcss": "^4",                 // Tailwind CSS v4
    "framer-motion": "^12.12.1",         // Анимации
    "next-intl": "^4.1.0",               // Интернационализация
    "zustand": "^5.0.1",                 // State management
    "@twa-dev/sdk": "^8.0.2",            // Telegram Mini App SDK
    "axios": "^1.7.4",                   // HTTP клиент
    "swr": "^2.2.4",                     // Data fetching
    "react-hot-toast": "^2.4.1",         // Toast notifications
    "react-loading-skeleton": "^3.5.0"   // Loading placeholders
  }
}
```

### Структура проекта

```
frontend/
├── src/
│   ├── app/                 # Next.js App Router
│   │   ├── [locale]/       # Локализованные страницы
│   │   └── globals.css     # Глобальные стили
│   ├── components/          # React компоненты
│   │   ├── modals/         # Модальные окна
│   │   ├── BalanceCard.tsx
│   │   ├── PoolCard.tsx
│   │   └── TabBar.tsx
│   ├── shared/              # Общий код
│   │   ├── api.ts          # API клиент
│   │   ├── auth.ts         # Авторизация
│   │   ├── store.ts        # Zustand store
│   │   └── hooks/          # Custom hooks
│   ├── types/               # TypeScript типы
│   └── messages/            # i18n переводы
│       ├── en.json
│       ├── ru.json
│       └── uk.json
└── public/
    ├── icons/              # SVG иконки
    └── images/             # Изображения
```

---

## ✅ Best Practices

### 1. Всегда используй Glassmorphism для карточек

```tsx
// ✅ Правильно
<div className="glassmorphism-card rounded-2xl p-5">
  Контент
</div>

// ❌ Неправильно
<div className="bg-gray-900 rounded-2xl p-5">
  Контент
</div>
```

### 2. Используй CSS переменные для цветов

```tsx
// ✅ Правильно - гибкость для темизации
<div style={{ background: 'var(--bg-card)' }}>

// ❌ Неправильно - хардкод цветов
<div style={{ background: '#1A1A1A' }}>
```

### 3. Анимируй все модальные окна

```tsx
// ✅ Правильно - плавное появление
<motion.div
  initial={{ scale: 0.95, opacity: 0 }}
  animate={{ scale: 1, opacity: 1 }}
  className="glassmorphism-modal"
>

// ❌ Неправильно - резкое появление
<div className="glassmorphism-modal">
```

### 4. Используй vibrate() для всех кликов

```tsx
import { vibrate } from '@/shared/vibration';

// ✅ Правильно
<button onClick={() => {
  vibrate();
  handleClick();
}}>

// ❌ Неправильно - нет тактильной обратной связи
<button onClick={handleClick}>
```

### 5. Всегда учитывай Safe Areas

```tsx
// ✅ Правильно
<div
  className="fixed bottom-0"
  style={{
    bottom: 'max(env(safe-area-inset-bottom, 8px), 8px)'
  }}
>

// ❌ Неправильно - будет скрыто за iPhone notch
<div className="fixed bottom-0">
```

### 6. Используй семантическую разметку

```tsx
// ✅ Правильно
<header className="glassmorphism-header">
  <h1>Syntra</h1>
</header>

<main className="px-4">
  <section>
    <h2>Pools</h2>
    <article>...</article>
  </section>
</main>

// ❌ Неправильно
<div className="glassmorphism-header">
  <div>Syntra</div>
</div>
```

### 7. Оптимизируй изображения

```tsx
import Image from 'next/image';

// ✅ Правильно - Next.js Image с оптимизацией
<Image
  src="/images/logo.png"
  alt="Syntra Logo"
  width={32}
  height={32}
  className="rounded-full"
/>

// ❌ Неправильно - обычный img без оптимизации
<img src="/images/logo.png" alt="Syntra Logo" />
```

### 8. Типизируй все пропсы

```tsx
// ✅ Правильно
interface PoolCardProps {
  pool: PoolInfo;
  onInvest: (pool: PoolInfo) => void;
  onWithdraw?: (pool: PoolInfo) => void;
}

export const PoolCard: React.FC<PoolCardProps> = ({ pool, onInvest }) => {
  // ...
}

// ❌ Неправильно
export const PoolCard = ({ pool, onInvest }: any) => {
```

### 9. Используй `clsx` для условных классов

```tsx
import clsx from 'clsx';

// ✅ Правильно
<button
  className={clsx(
    'py-2 px-3 rounded-lg text-xs font-medium transition',
    isActive ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
  )}
>

// ❌ Неправильно - сложно читать
<button
  className={`py-2 px-3 rounded-lg text-xs font-medium transition ${
    isActive ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
  }`}
>
```

### 10. Используй React.memo для оптимизации

```tsx
// ✅ Правильно - мемоизация дорогих компонентов
export const PoolCard = React.memo<PoolCardProps>(({ pool, onInvest }) => {
  // ...
});

// Для простых компонентов memo не обязателен
export const Icon = ({ name }: IconProps) => {
  // ...
};
```

---

## 🎯 Примеры реализации

### AI Trading Chat Bot в стиле Syntra

```tsx
'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { vibrate } from '@/shared/vibration';

export const TradingChatBot = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');

  const handleSend = () => {
    vibrate();
    // Логика отправки
  };

  return (
    <div className="min-h-screen bg-black">
      {/* Header */}
      <header className="glassmorphism-header px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
            <span className="text-white text-lg">🤖</span>
          </div>
          <div>
            <h1 className="text-white font-bold">AI Trading Assistant</h1>
            <p className="text-gray-400 text-xs">Powered by GPT-4</p>
          </div>
        </div>
      </header>

      {/* Chat Messages */}
      <main className="px-4 pt-4 pb-24 space-y-3">
        {messages.map((msg, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`flex ${msg.isBot ? 'justify-start' : 'justify-end'}`}
          >
            <div
              className={`
                max-w-[80%] p-3 rounded-2xl
                ${msg.isBot
                  ? 'glassmorphism-card'
                  : 'bg-blue-600 text-white'
                }
              `}
            >
              <p className="text-sm">{msg.text}</p>
            </div>
          </motion.div>
        ))}
      </main>

      {/* Input */}
      <div className="fixed bottom-0 left-0 right-0 p-4 glassmorphism-header">
        <div className="flex gap-2 max-w-[520px] mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask me anything..."
            className="flex-1 bg-gray-800/50 text-white rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSend}
            className="bg-blue-600 hover:bg-blue-700 text-white w-10 h-10 rounded-full flex items-center justify-center transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};
```

---

## 📚 Дополнительные ресурсы

- [Next.js 15 Docs](https://nextjs.org/docs)
- [Tailwind CSS v4](https://tailwindcss.com/docs)
- [Framer Motion](https://www.framer.com/motion/)
- [Telegram Mini Apps](https://core.telegram.org/bots/webapps)
- [React 19](https://react.dev)

---

## 🎨 Финальный чеклист

Перед деплоем проверь:

- [ ] Все карточки используют `glassmorphism-card`
- [ ] Все модалки анимированы через `framer-motion`
- [ ] Все кнопки вызывают `vibrate()` при клике
- [ ] Учтены Safe Areas для iOS notch
- [ ] Цвета используются через CSS переменные
- [ ] Все компоненты типизированы (TypeScript)
- [ ] Адаптивность проверена на мобильных и desktop
- [ ] Loading states используют `react-loading-skeleton`
- [ ] Error states показывают `toast` уведомления

---

**Создано для экосистемы Syntra** 🚀
