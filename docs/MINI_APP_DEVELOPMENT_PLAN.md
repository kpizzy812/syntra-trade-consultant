# 🚀 Syntra Telegram Mini App - План разработки

> Полный план создания Telegram Mini App для проекта Syntra Trade Consultant с интеграцией в /start команду

**Дата создания**: 2025-01-18
**Статус**: Планирование
**Дизайн-система**: [SYNTRA_DESIGN_SYSTEM.md](SYNTRA_DESIGN_SYSTEM.md)

---

## 📋 Содержание

1. [Обзор проекта](#обзор-проекта)
2. [Архитектура](#архитектура)
3. [Фаза 1: Подготовка инфраструктуры](#фаза-1-подготовка-инфраструктуры)
4. [Фаза 2: Telegram SDK и авторизация](#фаза-2-telegram-sdk-и-авторизация)
5. [Фаза 3: Backend API](#фаза-3-backend-api)
6. [Фаза 4: UI компоненты](#фаза-4-ui-компоненты)
7. [Фаза 5: Интеграция с /start](#фаза-5-интеграция-с-start)
8. [Фаза 6: Функционал Mini App](#фаза-6-функционал-mini-app)
9. [Фаза 7: Тестирование и деплой](#фаза-7-тестирование-и-деплой)
10. [Прогресс-трекер](#прогресс-трекер)

---

## 🎯 Обзор проекта

### Цель
Создать Telegram Mini App для Syntra Trade Consultant с:
- 💎 Полноэкранным UI в стиле SYNTRA_DESIGN_SYSTEM
- 🔐 Безопасной авторизацией через Telegram initData
- 📊 Функционалом торговых аналитик
- 🤖 AI-ассистентом для трейдинга
- 💰 Premium функциями

### Точка входа
- **Web App кнопка** в /start команде (первая кнопка в первом ряду)
- Остальные inline-кнопки остаются без изменений

### Tech Stack
```json
{
  "frontend": {
    "framework": "Next.js 15 (App Router)",
    "language": "TypeScript 5",
    "styling": "Tailwind CSS v4",
    "animations": "Framer Motion 12",
    "telegram-sdk": "@telegram-apps/sdk",
    "state": "Zustand 5",
    "i18n": "next-intl 4",
    "http": "axios + swr"
  },
  "backend": {
    "framework": "FastAPI (Python)",
    "database": "PostgreSQL + SQLAlchemy",
    "auth": "Telegram initData validation",
    "ai": "OpenAI GPT-4"
  }
}
```

---

## 🏗 Архитектура

### Структура проекта
```
Syntra Trade Consultant/
├── frontend/                    # Next.js Mini App
│   ├── src/
│   │   ├── app/
│   │   │   ├── [locale]/       # Интернационализация
│   │   │   │   ├── page.tsx    # Главная страница
│   │   │   │   ├── chat/       # AI Trading Chat
│   │   │   │   ├── analytics/  # Аналитика
│   │   │   │   └── profile/    # Профиль
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Header.tsx
│   │   │   │   └── TabBar.tsx
│   │   │   ├── cards/
│   │   │   │   ├── BalanceCard.tsx
│   │   │   │   └── AnalyticsCard.tsx
│   │   │   └── modals/
│   │   ├── shared/
│   │   │   ├── api/
│   │   │   │   ├── client.ts
│   │   │   │   └── endpoints.ts
│   │   │   ├── telegram/
│   │   │   │   ├── auth.ts
│   │   │   │   ├── sdk.ts
│   │   │   │   └── vibration.ts
│   │   │   ├── store/
│   │   │   │   └── userStore.ts
│   │   │   └── hooks/
│   │   ├── types/
│   │   │   ├── telegram.d.ts
│   │   │   └── api.d.ts
│   │   └── messages/
│   │       ├── en.json
│   │       └── ru.json
│   ├── public/
│   │   ├── icons/
│   │   └── images/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── next.config.js
│
├── src/                         # Backend
│   ├── bot/
│   │   ├── handlers/
│   │   │   ├── start.py        # ✅ ИЗМЕНЕНИЕ: добавляем Web App кнопку
│   │   │   └── ...
│   │   └── ...
│   ├── api/                     # ✨ НОВОЕ: API для Mini App
│   │   ├── __init__.py
│   │   ├── auth.py             # Валидация initData
│   │   ├── analytics.py        # Эндпоинты аналитики
│   │   ├── chat.py             # AI chat эндпоинты
│   │   └── user.py             # User API
│   └── ...
│
└── docs/
    ├── MINI_APP_DEVELOPMENT_PLAN.md  # ← Этот файл
    └── SYNTRA_DESIGN_SYSTEM.md
```

### Поток данных
```
┌─────────────────┐
│  Telegram User  │
└────────┬────────┘
         │ /start
         ↓
┌─────────────────────────────────┐
│  Bot: /start handler            │
│  → Inline кнопка "Open App" 🚀  │
└────────┬────────────────────────┘
         │ WebAppInfo URL
         ↓
┌─────────────────────────────────┐
│  Mini App (Next.js)             │
│  → Получает initData            │
│  → Валидирует на backend        │
│  → Показывает UI                │
└────────┬────────────────────────┘
         │ API requests
         ↓
┌─────────────────────────────────┐
│  Backend (FastAPI)              │
│  → Валидирует initData          │
│  → Возвращает данные            │
└─────────────────────────────────┘
```

---

## 📦 Фаза 1: Подготовка инфраструктуры

### 1.1 Создание frontend проекта

**Задачи:**
- [ ] Создать директорию `frontend/` в корне проекта
- [ ] Инициализировать Next.js 15 с TypeScript
- [ ] Настроить Tailwind CSS v4
- [ ] Установить зависимости

**Команды:**
```bash
# В корне проекта
mkdir frontend
cd frontend

# Создание Next.js проекта
npx create-next-app@latest . \
  --typescript \
  --tailwind \
  --app \
  --no-src-dir \
  --import-alias "@/*"

# Установка дополнительных зависимостей
npm install \
  @telegram-apps/sdk@latest \
  framer-motion@latest \
  next-intl@latest \
  zustand@latest \
  axios@latest \
  swr@latest \
  react-hot-toast@latest \
  react-loading-skeleton@latest

# Dev dependencies
npm install -D \
  @types/node \
  @types/react \
  @types/react-dom
```

**Конфигурация: `frontend/next.config.js`**
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone', // Для деплоя
  reactStrictMode: true,

  // Telegram Mini App specific
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN', // Разрешаем iframe от Telegram
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
```

**Конфигурация: `frontend/tailwind.config.ts`**
```typescript
import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Syntra Design System
        'bg-primary': '#000000',
        'bg-secondary': '#111111',
        'bg-card': '#1A1A1A',
        'bg-card-hover': '#222222',
        'text-primary': '#FFFFFF',
        'text-secondary': '#A3A3A3',
        'text-muted': '#525252',
        'border-primary': '#262626',
        'border-accent': '#404040',
        'primary-blue': '#3B82F6',
        'primary-blue-dark': '#2563EB',
        'primary-blue-light': '#60A5FA',
        'accent-blue': '#1D4ED8',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};

export default config;
```

**Глобальные стили: `frontend/src/app/globals.css`**
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    /* Syntra Design System Variables */
    --bg-primary: #000000;
    --bg-secondary: #111111;
    --bg-card: #1A1A1A;
    --bg-card-hover: #222222;
    --text-primary: #FFFFFF;
    --text-secondary: #A3A3A3;
    --text-muted: #525252;
    --border-primary: #262626;
    --border-accent: #404040;
    --primary-blue: #3B82F6;
    --primary-blue-dark: #2563EB;
    --primary-blue-light: #60A5FA;
    --accent-blue: #1D4ED8;

    /* Telegram Safe Areas */
    --tg-safe-area-inset-top: 0px;
    --tg-safe-area-inset-bottom: 0px;
  }

  body {
    @apply bg-bg-primary text-text-primary;
    font-family: 'Inter', system-ui, sans-serif;
    overflow-x: hidden;
  }

  /* Mobile body для fullscreen */
  .mobile-body {
    overflow: hidden;
    height: 100dvh;
    padding-top: var(--tg-safe-area-inset-top);
    padding-bottom: var(--tg-safe-area-inset-bottom);
  }
}

@layer components {
  /* Glassmorphism эффекты */
  .glassmorphism {
    background: rgba(255, 255, 255, 0.02);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.05);
    box-shadow:
      0 4px 16px rgba(0, 0, 0, 0.2),
      inset 0 1px 0 rgba(255, 255, 255, 0.03);
  }

  .glassmorphism-card {
    background: rgba(255, 255, 255, 0.04);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow:
      0 8px 32px rgba(0, 0, 0, 0.25),
      inset 0 1px 0 rgba(255, 255, 255, 0.08);
  }

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
}

@layer utilities {
  .animate-fade-in {
    animation: fade-in 0.3s ease-out;
  }

  @keyframes fade-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }
}
```

### 1.2 Структура TypeScript типов

**Файл: `frontend/src/types/telegram.d.ts`**
```typescript
export interface TelegramWebApp {
  initData: string;
  initDataUnsafe: WebAppInitData;
  version: string;
  platform: string;
  colorScheme: 'light' | 'dark';
  themeParams: ThemeParams;
  isExpanded: boolean;
  viewportHeight: number;
  viewportStableHeight: number;
  headerColor: string;
  backgroundColor: string;
  isClosingConfirmationEnabled: boolean;

  // Methods
  ready(): void;
  expand(): void;
  close(): void;

  // Components
  MainButton: MainButton;
  BackButton: BackButton;
  HapticFeedback: HapticFeedback;
}

export interface WebAppInitData {
  query_id?: string;
  user?: WebAppUser;
  receiver?: WebAppUser;
  chat?: WebAppChat;
  chat_type?: string;
  chat_instance?: string;
  start_param?: string;
  can_send_after?: number;
  auth_date: number;
  hash: string;
}

export interface WebAppUser {
  id: number;
  is_bot?: boolean;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  is_premium?: boolean;
  photo_url?: string;
}

export interface MainButton {
  text: string;
  color: string;
  textColor: string;
  isVisible: boolean;
  isActive: boolean;
  isProgressVisible: boolean;

  setText(text: string): MainButton;
  onClick(callback: () => void): MainButton;
  offClick(callback: () => void): MainButton;
  show(): MainButton;
  hide(): MainButton;
  enable(): MainButton;
  disable(): MainButton;
  showProgress(leaveActive?: boolean): MainButton;
  hideProgress(): MainButton;
  setParams(params: MainButtonParams): MainButton;
}

export interface MainButtonParams {
  text?: string;
  color?: string;
  text_color?: string;
  is_active?: boolean;
  is_visible?: boolean;
}

export interface BackButton {
  isVisible: boolean;
  onClick(callback: () => void): BackButton;
  offClick(callback: () => void): BackButton;
  show(): BackButton;
  hide(): BackButton;
}

export interface HapticFeedback {
  impactOccurred(style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'): void;
  notificationOccurred(type: 'error' | 'success' | 'warning'): void;
  selectionChanged(): void;
}

export interface ThemeParams {
  bg_color?: string;
  text_color?: string;
  hint_color?: string;
  link_color?: string;
  button_color?: string;
  button_text_color?: string;
  secondary_bg_color?: string;
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }
}
```

**Файл: `frontend/src/types/api.d.ts`**
```typescript
// User types
export interface User {
  id: number;
  telegram_id: number;
  username?: string;
  first_name: string;
  last_name?: string;
  language: 'en' | 'ru';
  is_premium: boolean;
  balance: number;
  created_at: string;
}

// Analytics types
export interface AnalyticsData {
  symbol: string;
  price: number;
  change_24h: number;
  volume_24h: number;
  market_cap: number;
  indicators: TechnicalIndicators;
}

export interface TechnicalIndicators {
  rsi: number;
  macd: {
    macd: number;
    signal: number;
    histogram: number;
  };
  bollinger_bands: {
    upper: number;
    middle: number;
    lower: number;
  };
}

// Chat types
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface ChatResponse {
  message: string;
  analytics?: AnalyticsData;
}

// API Response types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}
```

---

## 🔐 Фаза 2: Telegram SDK и авторизация

### 2.1 Инициализация Telegram SDK

**Файл: `frontend/src/shared/telegram/sdk.ts`**
```typescript
import { retrieveLaunchParams, postEvent } from '@telegram-apps/sdk';

export interface TelegramInitData {
  initDataRaw: string;
  initData: any;
  user?: {
    id: number;
    firstName: string;
    lastName?: string;
    username?: string;
    languageCode?: string;
    isPremium?: boolean;
  };
}

/**
 * Инициализация Telegram WebApp SDK
 */
export function initTelegramSDK(): TelegramInitData | null {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    // Получаем launch parameters
    const { initDataRaw, initData } = retrieveLaunchParams();

    // Уведомляем Telegram что приложение готово
    postEvent('web_app_ready');

    // Разворачиваем на весь экран
    postEvent('web_app_expand');

    // Получаем WebApp instance
    const webApp = window.Telegram?.WebApp;

    if (webApp) {
      // Настраиваем цвета
      webApp.headerColor = '#000000';
      webApp.backgroundColor = '#000000';

      // Блокируем swipe-down закрытие
      webApp.isClosingConfirmationEnabled = true;
    }

    return {
      initDataRaw,
      initData,
      user: initData?.user ? {
        id: initData.user.id,
        firstName: initData.user.firstName,
        lastName: initData.user.lastName,
        username: initData.user.username,
        languageCode: initData.user.languageCode,
        isPremium: initData.user.isPremium,
      } : undefined,
    };
  } catch (error) {
    console.error('Failed to initialize Telegram SDK:', error);
    return null;
  }
}

/**
 * Запрос fullscreen режима
 */
export function requestFullscreen() {
  try {
    postEvent('web_app_request_fullscreen');
  } catch (error) {
    console.error('Failed to request fullscreen:', error);
  }
}

/**
 * Выход из fullscreen
 */
export function exitFullscreen() {
  try {
    postEvent('web_app_exit_fullscreen');
  } catch (error) {
    console.error('Failed to exit fullscreen:', error);
  }
}
```

**Файл: `frontend/src/shared/telegram/vibration.ts`**
```typescript
/**
 * Haptic feedback utilities
 */

type ImpactStyle = 'light' | 'medium' | 'heavy' | 'rigid' | 'soft';
type NotificationType = 'error' | 'success' | 'warning';

/**
 * Вибрация при клике/тапе
 */
export function vibrate(style: ImpactStyle = 'light') {
  if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
    try {
      window.Telegram.WebApp.HapticFeedback.impactOccurred(style);
    } catch (error) {
      console.error('Vibration failed:', error);
    }
  }
}

/**
 * Вибрация при уведомлении
 */
export function vibrateNotification(type: NotificationType) {
  if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
    try {
      window.Telegram.WebApp.HapticFeedback.notificationOccurred(type);
    } catch (error) {
      console.error('Notification vibration failed:', error);
    }
  }
}

/**
 * Вибрация при смене выбора
 */
export function vibrateSelection() {
  if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
    try {
      window.Telegram.WebApp.HapticFeedback.selectionChanged();
    } catch (error) {
      console.error('Selection vibration failed:', error);
    }
  }
}
```

### 2.2 Авторизация через initData

**Файл: `frontend/src/shared/telegram/auth.ts`**
```typescript
import axios from 'axios';
import { TelegramInitData } from './sdk';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface AuthResponse {
  success: boolean;
  user?: {
    id: number;
    telegram_id: number;
    username?: string;
    first_name: string;
    language: string;
    is_premium: boolean;
  };
  error?: string;
}

/**
 * Авторизация пользователя через Telegram initData
 */
export async function authenticateUser(
  initDataRaw: string
): Promise<AuthResponse> {
  try {
    const response = await axios.post<AuthResponse>(
      `${API_URL}/api/auth/telegram`,
      {},
      {
        headers: {
          Authorization: `tma ${initDataRaw}`,
          'Content-Type': 'application/json',
        },
      }
    );

    return response.data;
  } catch (error) {
    console.error('Authentication failed:', error);
    return {
      success: false,
      error: 'Failed to authenticate with Telegram',
    };
  }
}

/**
 * Hook для авторизации при загрузке приложения
 */
export function useAuth(telegramData: TelegramInitData | null) {
  const [isAuthenticated, setIsAuthenticated] = React.useState(false);
  const [user, setUser] = React.useState<AuthResponse['user'] | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);

  React.useEffect(() => {
    if (!telegramData?.initDataRaw) {
      setIsLoading(false);
      return;
    }

    authenticateUser(telegramData.initDataRaw)
      .then((response) => {
        if (response.success && response.user) {
          setIsAuthenticated(true);
          setUser(response.user);
        }
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [telegramData]);

  return { isAuthenticated, user, isLoading };
}
```

### 2.3 Zustand Store для состояния

**Файл: `frontend/src/shared/store/userStore.ts`**
```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface User {
  id: number;
  telegram_id: number;
  username?: string;
  first_name: string;
  language: 'en' | 'ru';
  is_premium: boolean;
  balance: number;
}

interface UserStore {
  user: User | null;
  isAuthenticated: boolean;
  initData: string | null;

  setUser: (user: User) => void;
  setInitData: (initData: string) => void;
  clearUser: () => void;
}

export const useUserStore = create<UserStore>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      initData: null,

      setUser: (user) => set({ user, isAuthenticated: true }),
      setInitData: (initData) => set({ initData }),
      clearUser: () => set({ user: null, isAuthenticated: false, initData: null }),
    }),
    {
      name: 'syntra-user-storage',
    }
  )
);
```

---

## 🔧 Фаза 3: Backend API

### 3.1 Структура API модуля

**Создать файлы:**
```
src/api/
├── __init__.py
├── router.py          # FastAPI router
├── auth.py            # Telegram initData validation
├── analytics.py       # Analytics endpoints
├── chat.py            # AI chat endpoints
└── user.py            # User endpoints
```

### 3.2 Валидация Telegram initData

**Файл: `src/api/auth.py`**
```python
"""
Telegram Mini App authentication
"""

import hashlib
import hmac
import time
from typing import Optional
from urllib.parse import parse_qs

from fastapi import HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud import get_user_by_telegram_id
from src.database.models import User
from config.config import Config


def validate_telegram_init_data(init_data: str, bot_token: str) -> dict:
    """
    Validate Telegram initData using HMAC-SHA256

    Args:
        init_data: Raw initData string from Telegram
        bot_token: Bot token for signature validation

    Returns:
        dict: Parsed and validated init data

    Raises:
        HTTPException: If validation fails
    """
    try:
        # Parse init data
        parsed = parse_qs(init_data)

        # Extract hash
        received_hash = parsed.get('hash', [None])[0]
        if not received_hash:
            raise HTTPException(status_code=401, detail="Missing hash in init data")

        # Extract auth_date and check expiration (5 minutes)
        auth_date = parsed.get('auth_date', [None])[0]
        if not auth_date:
            raise HTTPException(status_code=401, detail="Missing auth_date")

        auth_timestamp = int(auth_date)
        current_timestamp = int(time.time())

        if current_timestamp - auth_timestamp > 300:  # 5 minutes
            raise HTTPException(status_code=401, detail="Init data expired")

        # Prepare data check string
        data_check_arr = []
        for key in sorted(parsed.keys()):
            if key == 'hash':
                continue
            value = parsed[key][0]
            data_check_arr.append(f"{key}={value}")

        data_check_string = '\n'.join(data_check_arr)

        # Calculate signature
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        # Compare hashes
        if calculated_hash != received_hash:
            raise HTTPException(status_code=401, detail="Invalid hash")

        # Parse user data
        import json
        user_data = json.loads(parsed.get('user', ['{}'])[0])

        return {
            'user': user_data,
            'auth_date': auth_timestamp,
            'query_id': parsed.get('query_id', [None])[0],
            'chat_instance': parsed.get('chat_instance', [None])[0],
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=401, detail="Invalid user data format")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Validation failed: {str(e)}")


async def get_current_user(
    authorization: str = Header(...),
    session: AsyncSession = None
) -> User:
    """
    Dependency для получения текущего пользователя из initData

    Args:
        authorization: Header вида "tma <initDataRaw>"
        session: Database session

    Returns:
        User: Authenticated user

    Raises:
        HTTPException: If auth fails
    """
    if not authorization.startswith('tma '):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    init_data_raw = authorization[4:]  # Remove "tma " prefix

    # Validate init data
    init_data = validate_telegram_init_data(init_data_raw, Config.BOT_TOKEN)

    # Get user from database
    telegram_id = init_data['user']['id']
    user = await get_user_by_telegram_id(session, telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user
```

### 3.3 API Router

**Файл: `src/api/router.py`**
```python
"""
FastAPI router for Mini App API
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud import get_async_session
from src.api.auth import get_current_user
from src.database.models import User

router = APIRouter(prefix="/api", tags=["mini-app"])


@router.post("/auth/telegram")
async def authenticate_telegram(
    user: User = Depends(get_current_user),
):
    """
    Authenticate user via Telegram initData
    """
    return {
        "success": True,
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "language": user.language,
            "is_premium": user.is_premium,
            "balance": 0,  # TODO: реальный баланс
        }
    }


@router.get("/user/profile")
async def get_user_profile(
    user: User = Depends(get_current_user),
):
    """
    Get user profile
    """
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "language": user.language,
        "is_premium": user.is_premium,
        "created_at": user.created_at.isoformat(),
    }


@router.get("/analytics/{symbol}")
async def get_analytics(
    symbol: str,
    user: User = Depends(get_current_user),
):
    """
    Get trading analytics for symbol
    """
    # TODO: интеграция с существующими сервисами
    from src.services.binance_service import BinanceService
    from src.services.technical_indicators import TechnicalIndicators

    binance = BinanceService()
    indicators = TechnicalIndicators()

    # Получить данные
    price_data = await binance.get_ticker_price(symbol)
    # ... добавить индикаторы

    return {
        "symbol": symbol,
        "price": price_data['price'],
        "change_24h": 0,  # TODO
        "indicators": {},  # TODO
    }
```

### 3.4 Интеграция в основное приложение

**Файл: `bot.py` (изменения)**
```python
# Добавить в imports
from src.api.router import router as api_router

# После создания bot
app = FastAPI()
app.include_router(api_router)

# Добавить middleware для CORS
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local dev
        "https://your-mini-app-domain.com",  # Production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 🎨 Фаза 4: UI компоненты

### 4.1 Layout компоненты

**Файл: `frontend/src/components/layout/Header.tsx`**
```typescript
'use client';

import { motion } from 'framer-motion';
import { useUserStore } from '@/shared/store/userStore';

export default function Header() {
  const user = useUserStore((state) => state.user);

  return (
    <header className="glassmorphism-header px-4 py-3">
      <div className="flex items-center justify-between max-w-[520px] mx-auto">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
            <span className="text-white text-lg font-bold">S</span>
          </div>
          <div>
            <h1 className="text-white font-bold text-lg">Syntra</h1>
            <p className="text-gray-400 text-xs">AI Trade Consultant</p>
          </div>
        </div>

        {user && (
          <div className="flex items-center gap-2">
            <div className="glassmorphism rounded-full px-3 py-1.5">
              <p className="text-xs text-gray-400">Balance</p>
              <p className="text-sm font-bold text-white">${user.balance.toFixed(2)}</p>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
```

**Файл: `frontend/src/components/layout/TabBar.tsx`**
```typescript
'use client';

import { motion } from 'framer-motion';
import { usePathname, useRouter } from 'next/navigation';
import { vibrate } from '@/shared/telegram/vibration';

interface Tab {
  key: string;
  label: string;
  icon: React.ReactNode;
  path: string;
}

const tabs: Tab[] = [
  {
    key: 'home',
    label: 'Home',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/>
      </svg>
    ),
    path: '/',
  },
  {
    key: 'chat',
    label: 'AI Chat',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
      </svg>
    ),
    path: '/chat',
  },
  {
    key: 'analytics',
    label: 'Analytics',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M3 13h2v8H3zm4-6h2v14H7zm4-4h2v18h-2zm4 9h2v9h-2zm4-5h2v14h-2z"/>
      </svg>
    ),
    path: '/analytics',
  },
  {
    key: 'profile',
    label: 'Profile',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
      </svg>
    ),
    path: '/profile',
  },
];

export default function TabBar() {
  const pathname = usePathname();
  const router = useRouter();

  const handleTabClick = (tab: Tab) => {
    vibrate('light');
    router.push(tab.path);
  };

  return (
    <div
      className="fixed left-1/2 -translate-x-1/2 w-[90%] max-w-[520px] z-50"
      style={{
        bottom: 'max(env(safe-area-inset-bottom, 16px), 16px)',
      }}
    >
      <div className="glassmorphism-card rounded-3xl p-1">
        <div className="flex">
          {tabs.map((tab) => {
            const isActive = pathname === tab.path;

            return (
              <div key={tab.key} className="flex-1 relative">
                {isActive && (
                  <motion.div
                    className="absolute inset-0 bg-blue-600/20 rounded-2xl"
                    layoutId="activeTab"
                    transition={{ type: 'spring', duration: 0.3 }}
                  />
                )}

                <button
                  onClick={() => handleTabClick(tab)}
                  className={`
                    relative w-full py-3 px-2 text-center
                    transition-all duration-200 rounded-2xl
                    flex flex-col items-center justify-center gap-1
                    ${isActive ? 'text-white z-10' : 'text-gray-400 hover:text-gray-200'}
                  `}
                >
                  {tab.icon}
                  <span className="text-[10px] font-semibold">{tab.label}</span>
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
```

### 4.2 Главная страница

**Файл: `frontend/src/app/page.tsx`**
```typescript
'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import Header from '@/components/layout/Header';
import TabBar from '@/components/layout/TabBar';
import { initTelegramSDK } from '@/shared/telegram/sdk';
import { authenticateUser } from '@/shared/telegram/auth';
import { useUserStore } from '@/shared/store/userStore';

export default function HomePage() {
  const [isLoading, setIsLoading] = useState(true);
  const { user, setUser, setInitData } = useUserStore();

  useEffect(() => {
    // Initialize Telegram SDK
    const telegramData = initTelegramSDK();

    if (telegramData?.initDataRaw) {
      setInitData(telegramData.initDataRaw);

      // Authenticate
      authenticateUser(telegramData.initDataRaw)
        .then((response) => {
          if (response.success && response.user) {
            setUser(response.user as any);
          }
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
    }
  }, []);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black mobile-body">
      <Header />

      <main className="px-4 pt-4 pb-24">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          <div className="glassmorphism-card rounded-2xl p-5">
            <div className="text-center">
              <p className="text-gray-400 text-sm mb-2">Welcome back,</p>
              <h1 className="text-3xl font-bold text-white">
                {user?.first_name || 'Trader'}
              </h1>
            </div>
          </div>

          {/* TODO: добавить остальные компоненты */}
        </motion.div>
      </main>

      <TabBar />
    </div>
  );
}
```

---

## 🔗 Фаза 5: Интеграция с /start

### 5.1 Изменения в start.py

**Файл: `src/bot/handlers/start.py` (изменения)**
```python
def get_main_menu(language: str = "ru") -> InlineKeyboardMarkup:
    """
    Create main menu inline keyboard with Web App button first

    Args:
        language: User language (ru or en)

    Returns:
        InlineKeyboardMarkup with main navigation buttons
    """
    # Web App URL (замените на ваш URL после деплоя)
    webapp_url = os.getenv('WEBAPP_URL', 'https://your-mini-app-domain.com')

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            # ✨ НОВОЕ: Web App кнопка - первая в первом ряду
            [
                InlineKeyboardButton(
                    text=f"🚀 {i18n.get('menu.open_app', language)}",
                    web_app=WebAppInfo(url=webapp_url)
                ),
            ],
            # Остальные кнопки без изменений
            [
                InlineKeyboardButton(
                    text=i18n.get("menu.help", language),
                    callback_data="menu_help"
                ),
                InlineKeyboardButton(
                    text=i18n.get("menu.profile", language),
                    callback_data="menu_profile",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.get("menu.referral", language),
                    callback_data="menu_referral",
                ),
                InlineKeyboardButton(
                    text=i18n.get("menu.premium", language),
                    callback_data="menu_premium",
                ),
            ],
        ]
    )
    return keyboard
```

**Добавить импорт:**
```python
from aiogram.types import WebAppInfo
```

### 5.2 Добавить переводы

**Файл: `src/locales/ru.json`**
```json
{
  "menu.open_app": "Открыть приложение"
}
```

**Файл: `src/locales/en.json`**
```json
{
  "menu.open_app": "Open App"
}
```

### 5.3 Переменные окружения

**Файл: `.env`**
```bash
# Telegram Mini App
WEBAPP_URL=https://your-mini-app-domain.com

# Для разработки
# WEBAPP_URL=https://your-ngrok-url.ngrok.io
```

---

## 🎯 Фаза 6: Функционал Mini App

### 6.1 AI Trading Chat (приоритет 1)

**Файл: `frontend/src/app/chat/page.tsx`**
```typescript
'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import Header from '@/components/layout/Header';
import TabBar from '@/components/layout/TabBar';
import { vibrate } from '@/shared/telegram/vibration';

export default function ChatPage() {
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    vibrate('light');

    const userMessage = { role: 'user', content: input, timestamp: new Date() };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    // TODO: API call to backend
    // const response = await fetch('/api/chat', { ... });

    // Mock response
    setTimeout(() => {
      const botMessage = {
        role: 'assistant',
        content: 'AI response here...',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, botMessage]);
      setIsLoading(false);
    }, 1000);
  };

  return (
    <div className="min-h-screen bg-black mobile-body">
      <Header />

      <main className="px-4 pt-4 pb-32 space-y-3">
        {messages.map((msg, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`flex ${msg.role === 'assistant' ? 'justify-start' : 'justify-end'}`}
          >
            <div
              className={`
                max-w-[80%] p-3 rounded-2xl
                ${msg.role === 'assistant'
                  ? 'glassmorphism-card'
                  : 'bg-blue-600 text-white'
                }
              `}
            >
              <p className="text-sm">{msg.content}</p>
            </div>
          </motion.div>
        ))}
      </main>

      {/* Input */}
      <div className="fixed bottom-20 left-0 right-0 p-4 glassmorphism-header">
        <div className="flex gap-2 max-w-[520px] mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask about crypto..."
            className="flex-1 bg-gray-800/50 text-white rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSend}
            disabled={isLoading}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white w-10 h-10 rounded-full flex items-center justify-center transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
            </svg>
          </button>
        </div>
      </div>

      <TabBar />
    </div>
  );
}
```

### 6.2 Analytics Page (приоритет 2)

**Файл: `frontend/src/app/analytics/page.tsx`**
```typescript
'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import Header from '@/components/layout/Header';
import TabBar from '@/components/layout/TabBar';

const symbols = ['BTC', 'ETH', 'SOL', 'BNB'];

export default function AnalyticsPage() {
  const [selectedSymbol, setSelectedSymbol] = useState('BTC');

  return (
    <div className="min-h-screen bg-black mobile-body">
      <Header />

      <main className="px-4 pt-4 pb-24 space-y-4">
        {/* Symbol selector */}
        <div className="flex gap-2 overflow-x-auto">
          {symbols.map((symbol) => (
            <button
              key={symbol}
              onClick={() => setSelectedSymbol(symbol)}
              className={`
                px-4 py-2 rounded-full font-medium text-sm transition-colors
                ${selectedSymbol === symbol
                  ? 'bg-blue-600 text-white'
                  : 'glassmorphism text-gray-400'
                }
              `}
            >
              {symbol}
            </button>
          ))}
        </div>

        {/* TODO: Chart component */}
        <div className="glassmorphism-card rounded-2xl p-5">
          <h2 className="text-white font-bold text-lg mb-4">
            {selectedSymbol}/USDT
          </h2>
          <div className="h-64 bg-gray-800/30 rounded-xl flex items-center justify-center">
            <p className="text-gray-500">Chart placeholder</p>
          </div>
        </div>

        {/* TODO: Indicators */}
        <div className="glassmorphism-card rounded-2xl p-5">
          <h3 className="text-white font-bold mb-3">Technical Indicators</h3>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-400 text-sm">RSI</span>
              <span className="text-white font-medium">65.4</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400 text-sm">MACD</span>
              <span className="text-green-400 font-medium">Bullish</span>
            </div>
          </div>
        </div>
      </main>

      <TabBar />
    </div>
  );
}
```

### 6.3 Profile Page (приоритет 3)

**Файл: `frontend/src/app/profile/page.tsx`**
```typescript
'use client';

import { motion } from 'framer-motion';
import Header from '@/components/layout/Header';
import TabBar from '@/components/layout/TabBar';
import { useUserStore } from '@/shared/store/userStore';

export default function ProfilePage() {
  const user = useUserStore((state) => state.user);

  if (!user) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <p className="text-gray-400">Loading...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black mobile-body">
      <Header />

      <main className="px-4 pt-4 pb-24 space-y-4">
        {/* User card */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="glassmorphism-card rounded-2xl p-5"
        >
          <div className="flex items-center gap-4 mb-4">
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
              <span className="text-white text-2xl font-bold">
                {user.first_name[0]}
              </span>
            </div>
            <div>
              <h2 className="text-white font-bold text-xl">{user.first_name}</h2>
              <p className="text-gray-400 text-sm">@{user.username || 'no_username'}</p>
            </div>
          </div>

          {user.is_premium && (
            <div className="bg-gradient-to-r from-yellow-500/20 to-orange-500/20 border border-yellow-500/30 rounded-xl px-4 py-2">
              <p className="text-yellow-400 font-bold text-sm">⭐ Premium User</p>
            </div>
          )}
        </motion.div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-3">
          <div className="glassmorphism-card rounded-xl p-4">
            <p className="text-gray-400 text-xs mb-1">Total Trades</p>
            <p className="text-white font-bold text-2xl">0</p>
          </div>
          <div className="glassmorphism-card rounded-xl p-4">
            <p className="text-gray-400 text-xs mb-1">Win Rate</p>
            <p className="text-green-400 font-bold text-2xl">0%</p>
          </div>
        </div>

        {/* Settings */}
        <div className="glassmorphism-card rounded-2xl p-5">
          <h3 className="text-white font-bold mb-3">Settings</h3>
          <div className="space-y-3">
            <button className="w-full flex items-center justify-between py-2">
              <span className="text-gray-300">Language</span>
              <span className="text-blue-400">{user.language.toUpperCase()}</span>
            </button>
            <button className="w-full flex items-center justify-between py-2">
              <span className="text-gray-300">Notifications</span>
              <span className="text-green-400">Enabled</span>
            </button>
          </div>
        </div>
      </main>

      <TabBar />
    </div>
  );
}
```

---

## 🧪 Фаза 7: Тестирование и деплой

### 7.1 Локальное тестирование

**Запуск frontend:**
```bash
cd frontend
npm run dev
```

**Запуск backend:**
```bash
source .venv/bin/activate
python bot.py
```

**Использование ngrok для тестирования:**
```bash
# Terminal 1: Frontend
ngrok http 3000

# Terminal 2: Backend
ngrok http 8000

# Обновите WEBAPP_URL в .env на ngrok URL
```

### 7.2 Чек-лист тестирования

**Telegram SDK:**
- [ ] initData корректно получается
- [ ] Авторизация работает
- [ ] expand() разворачивает приложение
- [ ] Haptic feedback работает
- [ ] BackButton функционирует
- [ ] MainButton показывается корректно

**UI/UX:**
- [ ] Glassmorphism эффекты отображаются
- [ ] Анимации плавные
- [ ] TabBar работает корректно
- [ ] Safe areas учтены (iOS notch)
- [ ] Все компоненты responsive

**API:**
- [ ] Авторизация работает
- [ ] initData валидируется
- [ ] Все эндпоинты возвращают данные
- [ ] Ошибки обрабатываются корректно

**Интеграция:**
- [ ] /start показывает Web App кнопку
- [ ] Клик по кнопке открывает Mini App
- [ ] Данные пользователя синхронизируются

### 7.3 Деплой

**Frontend (Vercel):**
```bash
cd frontend
npm install -g vercel
vercel --prod
```

**Backend:**
- Уже запущен как FastAPI часть бота
- Обновить CORS origins на production URL

**Обновить переменные:**
```bash
# .env
WEBAPP_URL=https://your-production-url.vercel.app
```

**Зарегистрировать Web App в BotFather:**
```
/mybots
→ Select your bot
→ Bot Settings
→ Menu Button
→ Configure Menu Button
→ Enter Web App URL
```

---

## 📊 Прогресс-трекер

### Статус реализации

#### ✅ Завершено
- [x] Изучение дизайн-системы
- [x] Изучение Telegram Mini Apps API
- [x] Создание плана разработки
- [x] **Фаза 1: Инфраструктура** (5/5) ✅
  - [x] Создать frontend проект
  - [x] Настроить Tailwind CSS с дизайн-системой Syntra
  - [x] Настроить TypeScript
  - [x] Создать структуру директорий
  - [x] Установить все зависимости
- [x] **Фаза 2: SDK и авторизация** (4/4) ✅
  - [x] Создать TypeScript типы для Telegram WebApp
  - [x] Реализовать SDK утилиты (initTelegramSDK, expand, fullscreen)
  - [x] Реализовать haptic feedback (vibration)
  - [x] Создать Zustand store для состояния
- [x] **Фаза 3: Backend API** (4/4) ✅
  - [x] Создать API структуру в src/api/
  - [x] Реализовать Telegram initData validation (HMAC-SHA256)
  - [x] Создать API endpoints (auth, analytics, chat, user)
  - [x] Добавить mock режим для локального тестирования (dev_auth.py)
- [x] **Фаза 4: UI компоненты** (3/3) ✅
  - [x] Создать Header компонент
  - [x] Создать TabBar с анимациями
  - [x] Создать главную страницу с инициализацией
- [x] **Фаза 5: Интеграция с /start** (3/3) ✅
  - [x] Добавить Web App кнопку в start.py (первая кнопка в первом ряду)
  - [x] Настроить переменные окружения (WEBAPP_URL в config.py и .env.example)
  - [x] Добавить i18n ключи для кнопки (menu.open_app в ru.json и en.json)

#### ⏳ Ожидает выполнения
- [ ] **Фаза 6: Функционал** (0/3)
  - [ ] Создать Chat page
  - [ ] Создать Analytics page
  - [ ] Создать Profile page
- [ ] **Фаза 7: Тестирование** (0/3)
  - [ ] Локальное тестирование через ngrok
  - [ ] Проверка всех функций
  - [ ] Деплой

### Следующая сессия начать с:

**Текущий шаг**: Фаза 6 - Функционал Mini App

**Статус проекта**:
- ✅ **5 из 7 фаз завершены** (71%)
- ✅ Backend API полностью готов с валидацией и mock режимом
- ✅ Frontend структура и UI компоненты готовы
- ✅ Интеграция с /start завершена (кнопка добавлена, переменные настроены)

**Следующие задачи:**
1. Создать Chat page (frontend/app/chat/page.tsx)
2. Создать Analytics page (frontend/app/analytics/page.tsx)
3. Создать Profile page (frontend/app/profile/page.tsx)
4. Интегрировать API client для работы с backend
5. Тестировать через ngrok с реальным Telegram

**Команды для тестирования:**
```bash
# Terminal 1: Backend API
cd /Users/a1/Projects/Syntra\ Trade\ Consultant
source .venv/bin/activate
python api_server.py
# Запустится на http://localhost:8000

# Terminal 2: Frontend
cd /Users/a1/Projects/Syntra\ Trade\ Consultant/frontend
npm run dev
# Откроется на http://localhost:3000

# Terminal 3: ngrok для тестирования с Telegram
ngrok http 3000
# Обновить WEBAPP_URL в .env на ngrok URL
```

**Важные файлы для следующей сессии:**
- `frontend/app/page.tsx` - главная страница (уже готова)
- `frontend/app/chat/page.tsx` - нужно создать
- `frontend/app/analytics/page.tsx` - нужно создать
- `frontend/app/profile/page.tsx` - нужно создать
- `src/bot/handlers/start.py` - Web App кнопка добавлена ✅
- `src/api/router.py` - API endpoints готовы ✅
- `src/api/dev_auth.py` - mock auth для локального тестирования ✅

---

## 📚 Дополнительные ресурсы

### Документация
- [Telegram Mini Apps Official](https://core.telegram.org/bots/webapps)
- [Telegram Mini Apps Community](https://docs.telegram-mini-apps.com/)
- [Next.js 15 Docs](https://nextjs.org/docs)
- [Framer Motion](https://www.framer.com/motion/)
- [@telegram-apps/sdk](https://www.npmjs.com/package/@telegram-apps/sdk)

### Примеры
- [Telegram Web Apps Examples](https://github.com/telegram-mini-apps)
- [React Telegram Web App](https://github.com/vkruglikov/react-telegram-web-app)

### Дизайн
- [SYNTRA_DESIGN_SYSTEM.md](SYNTRA_DESIGN_SYSTEM.md)
- [Glassmorphism Generator](https://glassmorphism.com/)

---

## 🎯 Ключевые моменты

### Безопасность
1. **Всегда валидировать initData на backend**
2. Проверять auth_date (expire через 5 минут)
3. Использовать HTTPS для production
4. Настроить CORS корректно

### Performance
1. Использовать React.memo для оптимизации
2. Lazy loading для тяжелых компонентов
3. Оптимизировать изображения (Next.js Image)
4. Кэшировать API запросы (SWR)

### UX
1. Всегда вызывать vibrate() при кликах
2. Использовать анимации для всех переходов
3. Учитывать Safe Areas на iOS
4. Показывать loading states

---

**Создано**: 2025-01-18
**Последнее обновление**: 2025-01-18 (Завершены Фазы 1-5, прогресс 71%)
**Версия**: 1.1.0

🚀 **5 из 7 фаз завершены! Готово к созданию страниц функционала.**
