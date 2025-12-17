# 🏗️ Platform Abstraction Layer - Архитектура

## 📋 Анализ текущей архитектуры

### ❌ Найденные Telegram-зависимости:

#### 1. **Layout.tsx** (всегда загружает Telegram SDK)
```typescript
// frontend/app/layout.tsx:39-43
<Script
  src="https://telegram.org/js/telegram-web-app.js"
  strategy="beforeInteractive"
/>
```
**Проблема:** SDK загружается даже для веб-пользователей

#### 2. **API Client** (hardcoded Telegram auth)
```typescript
// frontend/shared/api/client.ts:26-30
client.interceptors.request.use((config) => {
  const initData = useUserStore.getState().initData;
  if (initData && config.headers) {
    config.headers.Authorization = `tma ${initData}`;  // ❌ Только Telegram
  }
  return config;
});
```

#### 3. **UserStore** (только Telegram ID)
```typescript
// frontend/shared/store/userStore.ts:12-14
interface User {
  telegram_id: number;  // ❌ Только Telegram
  initData: string | null;  // ❌ Telegram initData
  // Нет email для веб-пользователей
}
```

#### 4. **Providers** (обязательные)
```typescript
// frontend/app/layout.tsx:47-52
<TelegramProvider>  {/* ❌ Всегда рендерится */}
  <TonConnectProvider>  {/* ❌ Telegram-специфично */}
    {children}
  </TonConnectProvider>
</TelegramProvider>
```

#### 5. **Payments** (только Telegram)
```typescript
// frontend/shared/api/client.ts:343-349
payment: {
  createStarsInvoice: async (...) => { /* ❌ Только Telegram Stars */ },
  createTonPayment: async (...) => { /* ❌ Только TON Connect */ },
  // Нет Stripe для веб-пользователей
}
```

---

## ✅ Решение: Platform Abstraction Layer

### Архитектура:
```
┌─────────────────────────────────────────────────────┐
│              Application Code                        │
│  (Components, Pages, Business Logic)                │
└──────────────────┬───────────────────────────────────┘
                   │ использует
                   ↓
┌─────────────────────────────────────────────────────┐
│          Platform Abstraction Layer                  │
│  ┌────────────────────────────────────────────────┐ │
│  │   IPlatformAdapter (interface)                 │ │
│  │   - auth: IAuthProvider                        │ │
│  │   - payments: IPaymentProvider                 │ │
│  │   - storage: IStorageProvider                  │ │
│  │   - ui: IUIProvider                            │ │
│  └────────────────────────────────────────────────┘ │
└──────────────────┬───────────────────────────────────┘
                   │ реализуют
          ┌────────┴────────┬───────────────┐
          ↓                 ↓               ↓
   ┌─────────────┐   ┌─────────────┐  ┌─────────────┐
   │  Telegram   │   │     Web     │  │   Mobile    │
   │  Platform   │   │  Platform   │  │  Platform   │
   └─────────────┘   └─────────────┘  └─────────────┘
```

---

## 📁 Структура файлов

```
frontend/
├─ lib/
│  └─ platform/
│     ├─ index.ts                    # Экспорт всего API
│     ├─ types.ts                    # TypeScript интерфейсы
│     ├─ PlatformProvider.tsx        # React Context Provider
│     ├─ usePlatform.ts              # React Hook
│     │
│     ├─ adapters/
│     │  ├─ TelegramPlatform.ts      # Telegram реализация
│     │  ├─ WebPlatform.ts           # Web реализация
│     │  └─ MobilePlatform.ts        # Mobile реализация (будущее)
│     │
│     ├─ providers/
│     │  ├─ auth/
│     │  │  ├─ TelegramAuthProvider.ts
│     │  │  ├─ NextAuthProvider.ts
│     │  │  └─ SupabaseAuthProvider.ts
│     │  │
│     │  ├─ payments/
│     │  │  ├─ TelegramStarsProvider.ts
│     │  │  ├─ TonConnectProvider.ts
│     │  │  ├─ StripeProvider.ts
│     │  │  └─ PayPalProvider.ts
│     │  │
│     │  ├─ storage/
│     │  │  ├─ TelegramCloudStorage.ts
│     │  │  └─ LocalStorageProvider.ts
│     │  │
│     │  └─ ui/
│     │     ├─ TelegramUIProvider.ts  # HapticFeedback, MainButton
│     │     └─ WebUIProvider.ts        # Native modals, vibration
│     │
│     └─ utils/
│        ├─ platformDetector.ts       # Auto-detect платформы
│        └─ platformConfig.ts         # Конфигурация
│
└─ shared/
   ├─ api/
   │  └─ client.ts                     # ✅ Теперь platform-agnostic
   │
   └─ store/
      └─ userStore.ts                  # ✅ Поддержка email + telegram_id
```

---

## 🎯 TypeScript Interfaces

### Основной интерфейс:
```typescript
// lib/platform/types.ts

/**
 * Platform Type
 */
export type PlatformType = 'telegram' | 'web' | 'ios' | 'android' | 'desktop';

/**
 * User Credentials (platform-agnostic)
 */
export interface UserCredentials {
  // Telegram users
  telegram_id?: number;
  telegram_initData?: string;

  // Web users
  email?: string;
  auth_token?: string;

  // Mobile users (будущее)
  device_id?: string;
}

/**
 * Platform Adapter Interface
 */
export interface IPlatformAdapter {
  readonly type: PlatformType;
  readonly isReady: boolean;

  // Sub-providers
  auth: IAuthProvider;
  payments: IPaymentProvider;
  storage: IStorageProvider;
  ui: IUIProvider;

  // Platform info
  getPlatformInfo(): PlatformInfo;
  initialize(): Promise<void>;
  cleanup(): void;
}

/**
 * Auth Provider Interface
 */
export interface IAuthProvider {
  readonly type: 'telegram' | 'nextauth' | 'supabase';

  // Get current credentials for API calls
  getCredentials(): Promise<UserCredentials | null>;

  // Login/Logout
  login(): Promise<UserCredentials>;
  logout(): Promise<void>;

  // Token refresh (for JWT-based auth)
  refreshToken?(): Promise<string>;

  // Check if user is authenticated
  isAuthenticated(): boolean;
}

/**
 * Payment Provider Interface
 */
export interface IPaymentProvider {
  readonly type: 'telegram_stars' | 'ton_connect' | 'stripe' | 'paypal';

  // Create payment
  createPayment(params: PaymentParams): Promise<PaymentResult>;

  // Check payment status
  checkPayment(paymentId: string): Promise<PaymentStatus>;

  // Cancel payment
  cancelPayment?(paymentId: string): Promise<void>;

  // Get payment methods (for web)
  getPaymentMethods?(): Promise<PaymentMethod[]>;
}

export interface PaymentParams {
  tier: 'basic' | 'premium' | 'vip';
  duration_months: number;
  amount: number;
  currency: 'USD' | 'EUR' | 'TON' | 'USDT' | 'STARS';
}

export interface PaymentResult {
  payment_id: string;
  status: 'pending' | 'completed' | 'failed';
  redirect_url?: string;  // Для Stripe Checkout
  invoice_url?: string;    // Для Telegram Stars
}

export interface PaymentStatus {
  payment_id: string;
  status: 'pending' | 'completed' | 'failed' | 'cancelled';
  paid_at?: Date;
}

/**
 * Storage Provider Interface
 */
export interface IStorageProvider {
  readonly type: 'telegram_cloud' | 'localstorage' | 'indexeddb';

  setItem(key: string, value: string): Promise<void>;
  getItem(key: string): Promise<string | null>;
  removeItem(key: string): Promise<void>;
  clear(): Promise<void>;
}

/**
 * UI Provider Interface
 */
export interface IUIProvider {
  readonly type: 'telegram' | 'web' | 'native';

  // Haptic feedback
  haptic?: {
    impact(style: 'light' | 'medium' | 'heavy'): void;
    notification(type: 'success' | 'warning' | 'error'): void;
    selection(): void;
  };

  // Platform-specific UI elements
  showMainButton?(text: string, onClick: () => void): void;
  hideMainButton?(): void;
  showBackButton?(onClick: () => void): void;
  hideBackButton?(): void;

  // Modals/Alerts
  showAlert(message: string): Promise<void>;
  showConfirm(message: string): Promise<boolean>;

  // Share
  share(data: ShareData): Promise<void>;
}

export interface ShareData {
  title?: string;
  text?: string;
  url?: string;
}

/**
 * Platform Info
 */
export interface PlatformInfo {
  type: PlatformType;
  version: string;
  isExpanded?: boolean;  // Telegram-specific
  viewportHeight?: number;
  colorScheme: 'light' | 'dark';
  themeParams?: Record<string, string>;
}
```

---

## 🎯 Реализация: TelegramPlatform

```typescript
// lib/platform/adapters/TelegramPlatform.ts
import type {
  IPlatformAdapter,
  IAuthProvider,
  IPaymentProvider,
  IStorageProvider,
  IUIProvider,
  PlatformInfo,
} from '../types';

import { TelegramAuthProvider } from '../providers/auth/TelegramAuthProvider';
import { TelegramStarsProvider } from '../providers/payments/TelegramStarsProvider';
import { TelegramCloudStorage } from '../providers/storage/TelegramCloudStorage';
import { TelegramUIProvider } from '../providers/ui/TelegramUIProvider';

export class TelegramPlatform implements IPlatformAdapter {
  readonly type = 'telegram' as const;
  private _isReady = false;

  // Sub-providers
  public readonly auth: IAuthProvider;
  public readonly payments: IPaymentProvider;
  public readonly storage: IStorageProvider;
  public readonly ui: IUIProvider;

  private webApp: any;

  constructor() {
    // Проверяем наличие Telegram WebApp
    if (typeof window === 'undefined' || !window.Telegram?.WebApp) {
      throw new Error('TelegramPlatform can only be used in Telegram Mini App');
    }

    this.webApp = window.Telegram.WebApp;

    // Инициализируем провайдеры
    this.auth = new TelegramAuthProvider(this.webApp);
    this.payments = new TelegramStarsProvider(this.webApp);
    this.storage = new TelegramCloudStorage(this.webApp);
    this.ui = new TelegramUIProvider(this.webApp);
  }

  get isReady(): boolean {
    return this._isReady;
  }

  async initialize(): Promise<void> {
    console.log('🚀 Initializing TelegramPlatform...');

    // Готовность
    this.webApp.ready();

    // Развернуть viewport
    if (this.webApp.expand) {
      this.webApp.expand();
    }

    // Настройка цветов
    if (this.webApp.setHeaderColor) {
      this.webApp.setHeaderColor('#000000');
    }
    if (this.webApp.setBackgroundColor) {
      this.webApp.setBackgroundColor('#000000');
    }

    // Подтверждение закрытия
    if (this.webApp.enableClosingConfirmation) {
      this.webApp.enableClosingConfirmation();
    }

    // Отключить вертикальные свайпы
    if (this.webApp.disableVerticalSwipes) {
      this.webApp.disableVerticalSwipes();
    }

    this._isReady = true;

    console.log('✅ TelegramPlatform ready!', this.getPlatformInfo());
  }

  cleanup(): void {
    if (this.webApp.MainButton) {
      this.webApp.MainButton.hide();
    }
    if (this.webApp.BackButton) {
      this.webApp.BackButton.hide();
    }
    this._isReady = false;
  }

  getPlatformInfo(): PlatformInfo {
    return {
      type: 'telegram',
      version: this.webApp.version,
      isExpanded: this.webApp.isExpanded,
      viewportHeight: this.webApp.viewportHeight,
      colorScheme: this.webApp.colorScheme,
      themeParams: this.webApp.themeParams,
    };
  }
}
```

---

## 🌐 Реализация: WebPlatform

```typescript
// lib/platform/adapters/WebPlatform.ts
import type {
  IPlatformAdapter,
  IAuthProvider,
  IPaymentProvider,
  IStorageProvider,
  IUIProvider,
  PlatformInfo,
} from '../types';

import { NextAuthProvider } from '../providers/auth/NextAuthProvider';
import { StripeProvider } from '../providers/payments/StripeProvider';
import { LocalStorageProvider } from '../providers/storage/LocalStorageProvider';
import { WebUIProvider } from '../providers/ui/WebUIProvider';

export class WebPlatform implements IPlatformAdapter {
  readonly type = 'web' as const;
  private _isReady = false;

  // Sub-providers
  public readonly auth: IAuthProvider;
  public readonly payments: IPaymentProvider;
  public readonly storage: IStorageProvider;
  public readonly ui: IUIProvider;

  constructor() {
    this.auth = new NextAuthProvider();
    this.payments = new StripeProvider();
    this.storage = new LocalStorageProvider();
    this.ui = new WebUIProvider();
  }

  get isReady(): boolean {
    return this._isReady;
  }

  async initialize(): Promise<void> {
    console.log('🌐 Initializing WebPlatform...');

    // Для веб-платформы инициализация простая
    // Можем проверить доступность localStorage, etc

    if (typeof window === 'undefined') {
      throw new Error('WebPlatform can only be used in browser');
    }

    // Проверяем localStorage
    try {
      window.localStorage.setItem('test', 'test');
      window.localStorage.removeItem('test');
    } catch (e) {
      console.warn('localStorage не доступен');
    }

    this._isReady = true;

    console.log('✅ WebPlatform ready!', this.getPlatformInfo());
  }

  cleanup(): void {
    // Cleanup для web (если нужно)
    this._isReady = false;
  }

  getPlatformInfo(): PlatformInfo {
    return {
      type: 'web',
      version: '1.0.0',
      viewportHeight: window.innerHeight,
      colorScheme: window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light',
    };
  }
}
```

---

## 🔧 Platform Detection

```typescript
// lib/platform/utils/platformDetector.ts
import { PlatformType } from '../types';

/**
 * Auto-detect current platform
 */
export function detectPlatform(): PlatformType {
  if (typeof window === 'undefined') {
    return 'web'; // SSR
  }

  // Check for Telegram
  if (window.Telegram?.WebApp?.initData) {
    return 'telegram';
  }

  // Check for mobile app (через user agent или custom flag)
  const userAgent = navigator.userAgent.toLowerCase();

  if (/iphone|ipad|ipod/.test(userAgent)) {
    // TODO: Проверить deep link схему (syntra://)
    return 'ios';
  }

  if (/android/.test(userAgent)) {
    // TODO: Проверить deep link схему (syntra://)
    return 'android';
  }

  // Default: web
  return 'web';
}

/**
 * Check if platform is available
 */
export function isPlatformAvailable(type: PlatformType): boolean {
  switch (type) {
    case 'telegram':
      return typeof window !== 'undefined' && !!window.Telegram?.WebApp;

    case 'web':
      return typeof window !== 'undefined';

    case 'ios':
    case 'android':
      // TODO: Check for mobile app
      return false;

    default:
      return false;
  }
}
```

---

## 🎯 React Context Provider

```typescript
// lib/platform/PlatformProvider.tsx
'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import type { IPlatformAdapter, PlatformType } from './types';
import { detectPlatform, isPlatformAvailable } from './utils/platformDetector';
import { TelegramPlatform } from './adapters/TelegramPlatform';
import { WebPlatform } from './adapters/WebPlatform';

interface PlatformContextValue {
  platform: IPlatformAdapter | null;
  platformType: PlatformType;
  isReady: boolean;
}

const PlatformContext = createContext<PlatformContextValue>({
  platform: null,
  platformType: 'web',
  isReady: false,
});

export function usePlatform() {
  const context = useContext(PlatformContext);
  if (!context.platform) {
    throw new Error('usePlatform must be used within PlatformProvider');
  }
  return context;
}

interface Props {
  children: ReactNode;
  forcePlatform?: PlatformType; // Для тестирования
}

export function PlatformProvider({ children, forcePlatform }: Props) {
  const [platform, setPlatform] = useState<IPlatformAdapter | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [platformType, setPlatformType] = useState<PlatformType>('web');

  useEffect(() => {
    async function initializePlatform() {
      try {
        // Определяем платформу
        const detectedType = forcePlatform || detectPlatform();
        setPlatformType(detectedType);

        console.log(`🎯 Detected platform: ${detectedType}`);

        // Проверяем доступность
        if (!isPlatformAvailable(detectedType)) {
          console.warn(`⚠️ Platform ${detectedType} not available, fallback to web`);
          setPlatformType('web');
        }

        // Создаем адаптер
        let adapter: IPlatformAdapter;

        switch (detectedType) {
          case 'telegram':
            adapter = new TelegramPlatform();
            break;

          case 'web':
          default:
            adapter = new WebPlatform();
            break;

          // TODO: case 'ios', 'android'
        }

        // Инициализируем
        await adapter.initialize();

        setPlatform(adapter);
        setIsReady(true);

        console.log('✅ Platform initialized successfully');

      } catch (error) {
        console.error('❌ Failed to initialize platform:', error);

        // Fallback to WebPlatform
        const webPlatform = new WebPlatform();
        await webPlatform.initialize();
        setPlatform(webPlatform);
        setPlatformType('web');
        setIsReady(true);
      }
    }

    initializePlatform();

    // Cleanup
    return () => {
      if (platform) {
        platform.cleanup();
      }
    };
  }, [forcePlatform]);

  return (
    <PlatformContext.Provider value={{ platform, platformType, isReady }}>
      {children}
    </PlatformContext.Provider>
  );
}
```

---

## 🔄 Refactored API Client

```typescript
// shared/api/client.ts (НОВЫЙ)
'use client';

import axios, { AxiosInstance } from 'axios';
import { usePlatform } from '@/lib/platform';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Create platform-agnostic API client
 */
export const createApiClient = async (): Promise<AxiosInstance> => {
  const client = axios.create({
    baseURL: API_URL,
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // Request interceptor - добавляем платформо-специфичную авторизацию
  client.interceptors.request.use(
    async (config) => {
      // ✅ ИСПОЛЬЗУЕМ PLATFORM ADAPTER!
      const { platform } = usePlatform();

      if (platform && config.headers) {
        const credentials = await platform.auth.getCredentials();

        if (credentials) {
          // Telegram
          if (credentials.telegram_initData) {
            config.headers.Authorization = `tma ${credentials.telegram_initData}`;
          }
          // Web (NextAuth JWT token)
          else if (credentials.auth_token) {
            config.headers.Authorization = `Bearer ${credentials.auth_token}`;
          }
        }
      }

      return config;
    },
    (error) => Promise.reject(error)
  );

  return client;
};

// Singleton
export const apiClient = await createApiClient();
```

---

## 📱 Использование в компонентах

### До (Telegram-specific):
```typescript
// ❌ Старый код
import { useTelegram } from '@/components/providers/TelegramProvider';

function MyComponent() {
  const { webApp } = useTelegram();

  const handleClick = () => {
    webApp?.HapticFeedback.impactOccurred('medium');
  };

  return <button onClick={handleClick}>Click</button>;
}
```

### После (Platform-agnostic):
```typescript
// ✅ Новый код
import { usePlatform } from '@/lib/platform';

function MyComponent() {
  const { platform } = usePlatform();

  const handleClick = () => {
    // Работает на всех платформах!
    platform.ui.haptic?.impact('medium');
  };

  return <button onClick={handleClick}>Click</button>;
}
```

---

## 🎯 Migration Plan

### Phase 1: Создать Platform Layer (2 дня)
```
Day 1:
  ✅ Создать types.ts (interfaces)
  ✅ Создать platformDetector.ts
  ✅ Создать PlatformProvider.tsx

Day 2:
  ✅ Реализовать TelegramPlatform
  ✅ Реализовать WebPlatform
  ✅ Создать провайдеры (Auth, Payments, Storage, UI)
```

### Phase 2: Рефакторинг API Client (1 день)
```
  ✅ Обновить client.ts для использования platform.auth
  ✅ Тесты
```

### Phase 3: Рефакторинг Layout (1 день)
```
  ✅ Условная загрузка Telegram SDK
  ✅ Заменить TelegramProvider на PlatformProvider
  ✅ Обновить layout.tsx
```

### Phase 4: Рефакторинг компонентов (2 дня)
```
  ✅ Заменить useTelegram() на usePlatform()
  ✅ Обновить все компоненты
  ✅ Тестирование
```

### Phase 5: Добавить Web Auth (NextAuth) (2 дня)
```
  ✅ Настроить NextAuth.js
  ✅ Реализовать NextAuthProvider
  ✅ Magic Link + Google/Apple OAuth
```

### Phase 6: Добавить Stripe Payments (2 дня)
```
  ✅ Настроить Stripe
  ✅ Реализовать StripeProvider
  ✅ Checkout flow
```

**TOTAL: ~10 дней (2 недели)**

---

## 🎯 Преимущества нового подхода

### ✅ Чистый код:
```typescript
// Один код работает везде!
function PayButton() {
  const { platform } = usePlatform();

  const handlePay = async () => {
    await platform.payments.createPayment({
      tier: 'premium',
      duration_months: 1,
      amount: 9.99,
      currency: platform.type === 'telegram' ? 'STARS' : 'USD',
    });
  };

  return <button onClick={handlePay}>Subscribe</button>;
}
```

### ✅ Легко добавить новые платформы:
```typescript
// Просто создаем новый adapter
class MobilePlatform implements IPlatformAdapter {
  // ...
}

// Регистрируем в PlatformProvider
case 'ios':
  adapter = new MobilePlatform();
  break;
```

### ✅ Тестируемость:
```typescript
// Mock platform для тестов
const mockPlatform: IPlatformAdapter = {
  type: 'web',
  isReady: true,
  auth: mockAuthProvider,
  payments: mockPaymentProvider,
  // ...
};

<PlatformProvider value={mockPlatform}>
  <MyComponent />
</PlatformProvider>
```

---

## 🚀 Следующие шаги

Хочешь начать:
1. **Создать базовые interfaces?** (types.ts)
2. **Реализовать TelegramPlatform?** (сохранить существующий функционал)
3. **Реализовать WebPlatform?** (новый функционал)
4. **Рефакторить API Client?** (platform-agnostic)

Начинаем?
