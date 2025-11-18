# 🔄 Система Refresh Авторизации

> **Дата создания:** 2025-11-18
> **Статус:** ✅ Реализовано
> **Версия:** 1.0.0

---

## 📋 Обзор

Система автоматического мониторинга и обновления авторизации для Telegram Mini App. Отслеживает время жизни `initData` и уведомляет пользователя о необходимости обновления сессии.

---

## 🎯 Основные возможности

### 1. Увеличенный Expiration Time

**Backend:** [src/api/auth.py](../src/api/auth.py)

```python
# Expiration time для initData (по умолчанию 24 часа = 86400 секунд)
INIT_DATA_EXPIRATION = int(os.getenv('INIT_DATA_EXPIRATION', '86400'))
```

**Настройка через .env:**
```bash
# .env
INIT_DATA_EXPIRATION=86400  # 24 часа
```

**Преимущества:**
- ✅ Пользователь может работать целый день без отключений
- ✅ Меньше ошибок авторизации
- ✅ Лучший UX
- ✅ Настраивается через env variables

---

### 2. Автоматический Мониторинг Сессии

**Хук:** [frontend/shared/hooks/useAuthRefresh.ts](../frontend/shared/hooks/useAuthRefresh.ts)

**Что делает:**
1. ⏰ Проверяет время жизни `initData` каждую минуту
2. 📊 Вычисляет оставшееся время до истечения
3. 🔔 Показывает уведомления в зависимости от статуса
4. 🔄 Автоматически обновляет приложение при истечении

**Пороги уведомлений:**

| Время до истечения | Действие | Тип уведомления |
|-------------------|----------|-----------------|
| **> 1 часа** | Ничего | - |
| **< 1 часа** | Предупреждение (1 раз) | ⚠️ "Сессия активна ещё Xч Yм" |
| **< 15 минут** | Критическое предупреждение | 🚨 "Сессия скоро истечет!" |
| **0 (истекла)** | Автоматическое обновление | ⏰ "Сессия истекла. Обновляю..." |

---

### 3. Toast Уведомления

**Провайдер:** [frontend/components/providers/ToastProvider.tsx](../frontend/components/providers/ToastProvider.tsx)

**Типы уведомлений:**

#### ⚠️ Предупреждение (< 1 часа)
```typescript
toast(
  `⚠️ Сессия активна ещё ${formatTimeLeft(timeLeft)}`,
  {
    duration: 5000,
    position: 'top-center',
    icon: '⏳',
  }
);
```
- Показывается **1 раз** когда остается < 1 часа
- Не критично, просто информирует

#### 🚨 Критическое (< 15 минут)
```typescript
toast.error(
  `🚨 Сессия скоро истечет! Осталось: ${formatTimeLeft(timeLeft)}`,
  {
    duration: 10000,
    position: 'top-center',
  }
);
```
- Показывается когда остается < 15 минут
- Красный цвет, более заметное

#### ⏰ Истекла (0 секунд)
```typescript
toast.error(
  '⏰ Сессия истекла. Обновляю приложение...',
  {
    duration: 3000,
    position: 'top-center',
  }
);

// Через 2 секунды - reload
setTimeout(() => {
  window.location.reload();
}, 2000);
```
- Очищает состояние пользователя
- Автоматически обновляет страницу
- Пользователь авторизуется заново

---

## 🏗 Архитектура

```
┌─────────────────────────────────────────────────────────┐
│  Telegram WebApp (Frontend)                             │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  App (page.tsx)                                │    │
│  │                                                 │    │
│  │  useAuthRefresh() ◄───────────────────┐        │    │
│  └────────────────────────────────────────│────────┘    │
│                                           │             │
│  ┌────────────────────────────────────────▼────────┐    │
│  │  useAuthRefresh Hook                           │    │
│  │                                                 │    │
│  │  1. Парсит auth_date из initData              │    │
│  │  2. Вычисляет timeLeft                         │    │
│  │  3. Проверяет каждую минуту                    │    │
│  │  4. Показывает toast уведомления               │    │
│  │  5. Обновляет при истечении                    │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  ToastProvider                                  │    │
│  │                                                 │    │
│  │  - ⚠️ Warning (< 1h)                           │    │
│  │  - 🚨 Critical (< 15m)                         │    │
│  │  - ⏰ Expired (reload)                         │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Backend API (FastAPI)                                   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  validate_telegram_init_data()                  │    │
│  │                                                 │    │
│  │  1. Проверяет HMAC-SHA256 подпись              │    │
│  │  2. Проверяет auth_date                         │    │
│  │  3. Сравнивает с INIT_DATA_EXPIRATION           │    │
│  │     (по умолчанию 24 часа)                      │    │
│  │                                                 │    │
│  │  if time_elapsed > INIT_DATA_EXPIRATION:        │    │
│  │      raise HTTPException(401, "Expired")        │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Environment Variables                                   │
│                                                          │
│  INIT_DATA_EXPIRATION=86400  # 24 часа (секунды)       │
└─────────────────────────────────────────────────────────┘
```

---

## 📦 Компоненты системы

### 1. Backend Валидация

**Файл:** [src/api/auth.py](../src/api/auth.py:21-22,69-76)

```python
# Expiration time для initData (по умолчанию 24 часа = 86400 секунд)
INIT_DATA_EXPIRATION = int(os.getenv('INIT_DATA_EXPIRATION', '86400'))

def validate_telegram_init_data(init_data: str, bot_token: str) -> Dict[str, Any]:
    # ... парсинг ...

    auth_timestamp = int(auth_date)
    current_timestamp = int(time.time())

    # Check if initData is not expired (default: 24 hours = 86400 seconds)
    time_elapsed = current_timestamp - auth_timestamp
    if time_elapsed > INIT_DATA_EXPIRATION:
        hours_elapsed = time_elapsed / 3600
        raise HTTPException(
            status_code=401,
            detail=f"Init data expired ({hours_elapsed:.1f} hours old, limit: {INIT_DATA_EXPIRATION / 3600:.1f} hours)"
        )
```

**Изменения:**
- ✅ Настраиваемый expiration через env
- ✅ Информативное сообщение об ошибке
- ✅ Указывает сколько часов прошло

---

### 2. Frontend Хук

**Файл:** [frontend/shared/hooks/useAuthRefresh.ts](../frontend/shared/hooks/useAuthRefresh.ts)

```typescript
export function useAuthRefresh() {
  const initData = useUserStore((state) => state.initData);
  const clearUser = useUserStore((state) => state.clearUser);

  useEffect(() => {
    if (!initData) return;

    const authDate = parseAuthDate(initData);
    if (!authDate) return;

    const checkAuthStatus = () => {
      const status = getAuthStatus(authDate);

      // 1. Истекла - reload
      if (status.isExpired) {
        toast.error('⏰ Сессия истекла. Обновляю приложение...');
        clearUser();
        setTimeout(() => window.location.reload(), 2000);
        return;
      }

      // 2. Критично (< 15 минут)
      if (status.isCritical) {
        toast.error(`🚨 Сессия скоро истечет! Осталось: ${timeLeft}`);
        return;
      }

      // 3. Предупреждение (< 1 час)
      if (status.shouldWarn) {
        toast(`⚠️ Сессия активна ещё ${timeLeft}`, { icon: '⏳' });
      }
    };

    checkAuthStatus(); // Первая проверка
    const interval = setInterval(checkAuthStatus, 60000); // Каждую минуту

    return () => clearInterval(interval);
  }, [initData, clearUser]);
}
```

**Особенности:**
- ✅ Проверка каждую минуту
- ✅ Умные пороги уведомлений
- ✅ Автоматический reload при истечении
- ✅ Очистка состояния перед reload

---

### 3. Toast Provider

**Файл:** [frontend/components/providers/ToastProvider.tsx](../frontend/components/providers/ToastProvider.tsx)

```typescript
export default function ToastProvider() {
  return (
    <Toaster
      position="top-center"
      toastOptions={{
        // Success toast
        success: {
          style: {
            background: 'linear-gradient(135deg, #10B981 0%, #059669 100%)',
          },
        },
        // Error toast
        error: {
          duration: 5000,
          style: {
            background: 'linear-gradient(135deg, #EF4444 0%, #DC2626 100%)',
          },
        },
      }}
    />
  );
}
```

**Стили:**
- 🎨 Градиентные фоны (Syntra Design System)
- 🌙 Темная тема
- 📱 Мобильно-оптимизированные
- ⚡ Плавные анимации

---

## 🚀 Использование

### Интеграция в приложение

**1. Layout** ([frontend/app/layout.tsx](../frontend/app/layout.tsx))
```typescript
import ToastProvider from "@/components/providers/ToastProvider";

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        <ToastProvider />  {/* ← Добавить один раз */}
        {children}
      </body>
    </html>
  );
}
```

**2. Главная страница** ([frontend/app/page.tsx](../frontend/app/page.tsx))
```typescript
import { useAuthRefresh } from '@/shared/hooks/useAuthRefresh';

export default function Home() {
  // Мониторинг сессии и автоматический refresh
  useAuthRefresh();  // ← Добавить в главную страницу

  // ... остальной код
}
```

**3. Environment Variables** ([.env](../.env.example))
```bash
# Mini App Authentication
# Expiration time для Telegram initData (в секундах)
# По умолчанию: 86400 (24 часа)
INIT_DATA_EXPIRATION=86400
```

---

## ⚙️ Настройка

### Изменение expiration time

**Варианты:**

| Значение | Время | Рекомендация |
|----------|-------|--------------|
| `3600` | 1 час | Документация Telegram (строго) |
| `21600` | 6 часов | Средний баланс |
| **`86400`** | **24 часа** | **По умолчанию (удобно)** |
| `604800` | 7 дней | Очень долго (не рекомендуется) |

**Как изменить:**
```bash
# .env
INIT_DATA_EXPIRATION=21600  # 6 часов
```

Перезапустить backend:
```bash
source .venv/bin/activate
python api_server.py
```

---

### Изменение порогов уведомлений

**Файл:** [frontend/shared/hooks/useAuthRefresh.ts](../frontend/shared/hooks/useAuthRefresh.ts:14-17)

```typescript
// Константы времени (в секундах)
const EXPIRATION_TIME = 24 * 60 * 60; // 24 часа
const WARNING_THRESHOLD = 60 * 60; // ← Предупреждение за 1 час
const CRITICAL_THRESHOLD = 15 * 60; // ← Критично за 15 минут
const CHECK_INTERVAL = 60 * 1000; // ← Проверять каждую минуту
```

**Примеры:**
```typescript
// Более частые проверки (каждые 30 секунд)
const CHECK_INTERVAL = 30 * 1000;

// Раннее предупреждение (за 2 часа)
const WARNING_THRESHOLD = 2 * 60 * 60;

// Более длинное критическое окно (за 30 минут)
const CRITICAL_THRESHOLD = 30 * 60;
```

---

## 📊 Логика работы

### Timeline (24 часа expiration)

```
0h                    23h      23h45m       24h
│─────────────────────│────────│────────────│
│                     │        │            │
│   Нормальная        │ ⚠️     │ 🚨         │ ⏰
│   работа            │Warning │Critical    │Expired
│   (без уведомлений) │(1 раз) │(каждую    │(reload)
│                     │        │ минуту)    │
│◄────── 23 часа ────►│◄─ 1ч ─►│◄── 15м ───►│
```

### Алгоритм

```typescript
function checkAuthStatus() {
  const now = Math.floor(Date.now() / 1000);
  const timeElapsed = now - authDate;
  const timeLeft = EXPIRATION_TIME - timeElapsed;

  if (timeLeft <= 0) {
    // ⏰ Истекла
    showExpiredToast();
    clearUser();
    reload();
  } else if (timeLeft <= 15 * 60) {
    // 🚨 < 15 минут
    if (!hasShownCritical) {
      showCriticalToast(timeLeft);
      hasShownCritical = true;
    }
  } else if (timeLeft <= 60 * 60) {
    // ⚠️ < 1 часа
    if (!hasShownWarning) {
      showWarningToast(timeLeft);
      hasShownWarning = true;
    }
  }
  // else: всё ок, ничего не показываем
}
```

---

## 🧪 Тестирование

### 1. Тест в dev режиме (без Telegram)

```bash
# Terminal 1: Backend
cd /Users/a1/Projects/Syntra\ Trade\ Consultant
source .venv/bin/activate
python api_server.py

# Terminal 2: Frontend
cd /Users/a1/Projects/Syntra\ Trade\ Consultant/frontend
npm run dev
```

**Открыть:** http://localhost:3000

**Что проверять:**
- ✅ Toast Provider загружается
- ✅ Нет ошибок в консоли
- ✅ Хук не ломается без initData

---

### 2. Тест с коротким expiration (имитация истечения)

**Временно изменить:**

```bash
# .env
INIT_DATA_EXPIRATION=300  # 5 минут для теста
```

```typescript
// frontend/shared/hooks/useAuthRefresh.ts
const EXPIRATION_TIME = 5 * 60; // 5 минут
const WARNING_THRESHOLD = 3 * 60; // Предупреждение за 3 минуты
const CRITICAL_THRESHOLD = 1 * 60; // Критично за 1 минуту
const CHECK_INTERVAL = 10 * 1000; // Проверять каждые 10 секунд
```

**Перезапустить backend и frontend**

**Timeline теста:**
```
0m     2m      4m       5m
│──────│───────│────────│
│      │ ⚠️    │ 🚨     │ ⏰
│      │Warning│Critical│Expired
```

**Ожидаемое поведение:**
- **2 минуты:** Toast "⚠️ Сессия активна ещё 3м"
- **4 минуты:** Toast "🚨 Сессия скоро истечет! Осталось: 1м"
- **5 минут:** Toast "⏰ Сессия истекла. Обновляю..." → reload

---

### 3. Тест с реальным Telegram

**Использовать ngrok:**
```bash
# Terminal 3
ngrok http 3000

# Скопировать URL вида: https://xxxx-xxxx.ngrok.io
```

**Обновить .env:**
```bash
WEBAPP_URL=https://xxxx-xxxx.ngrok.io
```

**Перезапустить бота и открыть через Telegram**

**Проверить:**
- ✅ Авторизация работает
- ✅ initData передается
- ✅ Хук активируется
- ✅ Через 23 часа - предупреждение
- ✅ Через 24 часа - reload

---

## 🐛 Troubleshooting

### Проблема: Toast не показываются

**Решение:**
1. Проверить что ToastProvider добавлен в layout.tsx
2. Проверить консоль браузера на ошибки
3. Убедиться что react-hot-toast установлен:
   ```bash
   npm list react-hot-toast
   ```

---

### Проблема: Сессия истекает слишком быстро

**Решение:**
1. Проверить .env:
   ```bash
   cat .env | grep INIT_DATA_EXPIRATION
   ```
2. Проверить что backend читает правильное значение:
   ```python
   print(f"INIT_DATA_EXPIRATION: {INIT_DATA_EXPIRATION}")
   ```
3. Убедиться что backend перезапущен после изменения .env

---

### Проблема: Уведомления показываются слишком часто

**Решение:**
Проверить что используются ref для отслеживания показанных уведомлений:
```typescript
const lastWarningRef = useRef<'none' | 'warning' | 'critical'>('none');
const hasShownExpiredRef = useRef(false);
```

Эти ref предотвращают повторные показы.

---

## 📝 Changelog

### v1.0.0 (2025-11-18)

**Добавлено:**
- ✅ Увеличен expiration до 24 часов (настраиваемый)
- ✅ Хук `useAuthRefresh` для мониторинга
- ✅ Toast уведомления (warning, critical, expired)
- ✅ Автоматический reload при истечении
- ✅ ToastProvider с Syntra Design System
- ✅ Документация

**Файлы:**
- `src/api/auth.py` - backend валидация
- `.env.example` - конфигурация
- `frontend/shared/hooks/useAuthRefresh.ts` - хук
- `frontend/components/providers/ToastProvider.tsx` - провайдер
- `frontend/app/layout.tsx` - интеграция ToastProvider
- `frontend/app/page.tsx` - использование хука

---

## 🔮 Будущие улучшения

### 1. Silent Refresh (без reload)
- Обновлять initData без перезагрузки страницы
- Требует поддержку со стороны Telegram

### 2. Показ прогресс-бара
```typescript
<SessionProgressBar timeLeft={timeLeft} total={EXPIRATION_TIME} />
```

### 3. Настройка уведомлений
```typescript
interface UserSettings {
  notificationsEnabled: boolean;
  warningThreshold: number; // в минутах
  criticalThreshold: number; // в минутах
}
```

### 4. Analytics
```typescript
// Отслеживать сколько раз пользователь получает истечение
logEvent('session_expired', {
  timeElapsed: timeElapsed,
  lastActivity: lastActivityTimestamp,
});
```

---

## 📚 Связанные документы

- [MINI_APP_AUTH_AUDIT.md](./MINI_APP_AUTH_AUDIT.md) - Полный аудит авторизации
- [MINI_APP_DEVELOPMENT_PLAN.md](./MINI_APP_DEVELOPMENT_PLAN.md) - План разработки Mini App
- [MINI_APP_REDESIGN_PLAN.md](./MINI_APP_REDESIGN_PLAN.md) - Дизайн и архитектура

---

**Автор:** Claude (Sonnet 4.5)
**Дата:** 2025-11-18
**Версия:** 1.0.0
