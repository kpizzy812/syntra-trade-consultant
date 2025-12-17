# Ultrathink - Dynamic Pricing API

## Что реализовано

Создана **система динамического получения pricing и limits данных** вместо хардкода в landing page.

---

## Backend

### 1. API Endpoint: `/api/config/pricing`

**Файл:** [src/api/config.py](../src/api/config.py)

**Public endpoint** - не требует авторизации

#### Response:
```json
{
  "tiers": [
    {
      "name": "free",
      "display_name": "Free",
      "price": 0.00,
      "price_discounted": 0.00,
      "discount_percent": 0,
      "limits": {
        "text_per_day": 1,
        "charts_per_day": 1,
        "vision_per_day": 0
      },
      "features": [
        "1 text requests/day",
        "1 charts/day",
        "Basic price",
        "Basic indicators",
        "News",
        "Fear & Greed Index"
      ],
      "model": {
        "primary": "gpt-4o-mini",
        "reasoning": "deepseek-chat",
        "advanced_routing": false
      }
    },
    {
      "name": "basic",
      "display_name": "Basic",
      "price": 9.99,
      "price_discounted": 7.99,
      "discount_percent": 20,
      "limits": {
        "text_per_day": 10,
        "charts_per_day": 3,
        "vision_per_day": 2
      },
      "features": [
        "10 text requests/day",
        "3 charts/day",
        "2 screenshot analysis/day",
        "Candlestick patterns",
        "Funding rates"
      ],
      "model": {
        "primary": "gpt-4o-mini",
        "reasoning": "deepseek-chat",
        "advanced_routing": false
      }
    },
    {
      "name": "premium",
      "display_name": "Premium",
      "price": 24.99,
      "price_discounted": 19.99,
      "discount_percent": 20,
      "limits": {
        "text_per_day": 30,
        "charts_per_day": 10,
        "vision_per_day": 10
      },
      "features": [
        "30 text requests/day",
        "10 charts/day",
        "10 screenshot analysis/day",
        "Candlestick patterns",
        "Funding rates",
        "On-chain metrics",
        "Liquidation history",
        "Market cycle analysis",
        "GPT-4o for complex queries"
      ],
      "model": {
        "primary": "gpt-4o-mini",
        "reasoning": "gpt-4o",
        "advanced_routing": true
      }
    }
  ],
  "trial": {
    "tier": "premium",
    "duration_days": 7,
    "discount_percent": 20,
    "discount_duration_hours": 48
  },
  "updated_at": "2025-01-18T12:00:00Z"
}
```

#### Источник данных:
- **config/pricing.py:** Цены (9.99, 24.99, 49.99)
- **config/limits.py:** Лимиты (1/10/30 запросов)
- Автоматическая генерация features списка из конфигурации

---

### 2. API Endpoint: `/api/config/features`

**Public endpoint** - список всех доступных фич

#### Response:
```json
{
  "features": [
    {
      "name": "candlestick_patterns",
      "display_name": "Candlestick Patterns",
      "description": "Advanced pattern recognition (Doji, Hammer, Engulfing)",
      "available_in": ["basic", "premium", "vip"]
    },
    {
      "name": "onchain_metrics",
      "display_name": "On-Chain Metrics",
      "description": "Network activity, addresses, transaction volume",
      "available_in": ["premium", "vip"]
    },
    ...
  ]
}
```

---

## Frontend

### Frontend API Client

**Файл:** [frontend/shared/api/client.ts](../frontend/shared/api/client.ts:445-464)

```typescript
api.config.getPricing()  // Получить pricing
api.config.getFeatures() // Получить features
```

#### Пример использования:
```typescript
import { api } from '@/shared/api/client';

// Get pricing data
const { tiers, trial } = await api.config.getPricing();

console.log(tiers[2]); // Premium tier
// {
//   name: 'premium',
//   price: 24.99,
//   limits: { text_per_day: 30, ... },
//   features: ['30 text requests/day', ...]
// }

console.log(trial);
// { tier: 'premium', duration_days: 7, discount_percent: 20 }
```

---

## Как использовать в Landing Page

### Вариант 1: Static Generation (SSG)
```tsx
// landing/page.tsx
export default async function Landing() {
  // Fetch pricing at build time
  const { tiers, trial } = await api.config.getPricing();

  return (
    <section id="pricing">
      {tiers.map(tier => (
        <PricingCard key={tier.name} tier={tier} />
      ))}
    </section>
  );
}
```

### Вариант 2: Client-Side (CSR)
```tsx
'use client';

import { useEffect, useState } from 'react';
import { api } from '@/shared/api/client';

export default function DynamicPricing() {
  const [pricing, setPricing] = useState(null);

  useEffect(() => {
    api.config.getPricing().then(setPricing);
  }, []);

  if (!pricing) return <LoadingSpinner />;

  return (
    <section id="pricing">
      {pricing.tiers.map(tier => (
        <PricingCard key={tier.name} tier={tier} />
      ))}
    </section>
  );
}
```

### Вариант 3: Server Component (RSC) - **Рекомендуется**
```tsx
// landing/page.tsx (Server Component)
async function getPricingData() {
  const res = await fetch('http://localhost:8000/api/config/pricing');
  return res.json();
}

export default async function Landing() {
  const pricing = await getPricingData();

  return <PricingSection pricing={pricing} />;
}
```

---

## Преимущества

### ✅ Централизованное управление
- Изменяешь [config/pricing.py](../config/pricing.py) → обновляется везде
- Нет хардкода на frontend

### ✅ Актуальность
- Pricing всегда синхронизирован с backend
- Trial настройки в одном месте

### ✅ A/B Testing готовность
- Легко добавить эксперименты с ценами
- Можно показывать разные цены разным сегментам

### ✅ Простота обновления
```python
# config/pricing.py
PREMIUM_PRICE = 24.99  # Было
PREMIUM_PRICE = 29.99  # Стало → автоматически обновится на landing
```

---

## Структура файлов

```
Backend:
├── config/
│   ├── pricing.py     # Источник цен (9.99, 24.99, 49.99)
│   └── limits.py      # Источник лимитов (1/10/30 requests)
└── src/api/
    ├── config.py      # API endpoint /config/pricing ✨ NEW
    └── router.py      # Подключение config router

Frontend:
└── shared/api/
    └── client.ts      # api.config.getPricing() ✨ UPDATED
```

---

## API Integration

**Router:** [src/api/router.py](../src/api/router.py:38)
```python
router.include_router(config_router)  # Public config endpoints
```

**Public Access:** ✅ Не требует авторизации
**Caching:** Можно добавить Redis кеш (TTL: 1 час)

---

## Next Steps

### 🔜 TODO для полной интеграции:

1. **Создать компонент `<DynamicPricingSection />`**
   ```tsx
   // components/landing/DynamicPricingSection.tsx
   'use client';

   export default function DynamicPricingSection() {
     const [pricing, setPricing] = useState(null);
     // Fetch from api.config.getPricing()
     // Render pricing cards
   }
   ```

2. **Заменить хардкод в landing/page.tsx**
   ```diff
   - <p className="pricing-price">$24.99/месяц</p>
   + <p className="pricing-price">${tier.price}/месяц</p>
   ```

3. **Добавить кеширование (опционально)**
   ```python
   # src/api/config.py
   from functools import lru_cache

   @lru_cache(maxsize=1)
   def get_pricing_cached():
       return get_pricing()
   ```

4. **Локализация**
   - RU: "30 запросов/день"
   - EN: "30 requests/day"

---

## Тестирование

### Test API endpoint:
```bash
# Start backend
python api_server.py

# Test endpoint
curl http://localhost:8000/api/config/pricing

# Should return JSON with tiers and trial config
```

### Test frontend:
```tsx
import { api } from '@/shared/api/client';

// In browser console
api.config.getPricing().then(console.log);

// Expected: { tiers: [...], trial: {...} }
```

---

## Summary

**Реализовано:**
- ✅ Backend API `/config/pricing` с актуальными данными
- ✅ Backend API `/config/features` со списком фич
- ✅ Frontend API client интеграция
- ✅ Источник данных: config/pricing.py + config/limits.py

**Осталось:**
- ⏳ Создать компонент DynamicPricingSection
- ⏳ Заменить хардкод в landing page
- ⏳ Добавить локализацию (RU/EN)
- ⏳ Добавить кеширование для оптимизации

**Сборка:** ✅ Frontend собран успешно
