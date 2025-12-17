# 📊 Руководство по отслеживанию трафика Syntra AI

## 🎯 Готовые UTM-ссылки для соцсетей

### TikTok

**Для био:**
```
https://yoursite.com/landing?utm_source=tiktok&utm_medium=bio&utm_campaign=main_bio
```

**Для конкретного видео:**
```
https://yoursite.com/landing?utm_source=tiktok&utm_medium=video&utm_campaign=december_content&utm_content=bitcoin_analysis_v1
```

**Для рекламы:**
```
https://yoursite.com/landing?utm_source=tiktok&utm_medium=paid_ad&utm_campaign=december_ads&utm_content=creative_a&utm_term=crypto_trading
```

### Instagram

**Для био:**
```
https://yoursite.com/landing?utm_source=instagram&utm_medium=bio&utm_campaign=main_bio
```

**Для Reels:**
```
https://yoursite.com/landing?utm_source=instagram&utm_medium=reels&utm_campaign=december_reels&utm_content=solana_breakdown
```

**Для Stories:**
```
https://yoursite.com/landing?utm_source=instagram&utm_medium=story&utm_campaign=december_stories&utm_content=daily_tip_nov25
```

**Для постов:**
```
https://yoursite.com/landing?utm_source=instagram&utm_medium=post&utm_campaign=december_feed&utm_content=market_update
```

### Telegram

**Для канала @SyntraTrade:**
```
https://yoursite.com/landing?utm_source=telegram&utm_medium=channel_post&utm_campaign=syntrade_channel&utm_content=weekly_review
```

**Для закрепленного сообщения:**
```
https://yoursite.com/landing?utm_source=telegram&utm_medium=pinned&utm_campaign=syntrade_channel&utm_content=main_pinned
```

**Для бота (при отправке ссылок из бота):**
```
https://yoursite.com/landing?utm_source=telegram&utm_medium=bot_message&utm_campaign=syntra_bot&utm_content=welcome_message
```

### YouTube

**Для описания:**
```
https://yoursite.com/landing?utm_source=youtube&utm_medium=description&utm_campaign=december_videos&utm_content=crypto_guide_ep1
```

**Для закрепленного комментария:**
```
https://yoursite.com/landing?utm_source=youtube&utm_medium=pinned_comment&utm_campaign=december_videos&utm_content=video_title
```

### Twitter/X

**Для био:**
```
https://yoursite.com/landing?utm_source=twitter&utm_medium=bio&utm_campaign=main_bio
```

**Для твита:**
```
https://yoursite.com/landing?utm_source=twitter&utm_medium=tweet&utm_campaign=december_tweets&utm_content=market_analysis_1
```

---

## 🔧 Интеграция в лендинг

### 1. Добавь UTMTracker в layout

Отредактируй `frontend/app/landing/layout.tsx` (или создай, если нет):

```tsx
import UTMTracker from '@/components/analytics/UTMTracker';

export default function LandingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <UTMTracker />
      {children}
    </>
  );
}
```

### 2. Замени обычные Link на TrackedLink

Для всех ссылок на бота используй `TrackedLink`:

```tsx
import TrackedLink from '@/components/analytics/TrackedLink';

// Вместо:
<Link href="https://t.me/SyntraAI_bot" target="_blank">
  Открыть бота
</Link>

// Используй:
<TrackedLink href="https://t.me/SyntraAI_bot" target="_blank">
  Открыть бота
</TrackedLink>
```

---

## 📈 Google Analytics 4 Setup

### 1. Создай GA4 Property

1. Зайди на [Google Analytics](https://analytics.google.com/)
2. Admin → Create Property
3. Выбери "Web" и введи URL сайта
4. Получи Measurement ID (формат: `G-XXXXXXXXXX`)

### 2. Добавь GA4 на сайт

Создай `frontend/lib/analytics/google-analytics.tsx`:

```tsx
"use client";

import Script from 'next/script';

export default function GoogleAnalytics({ measurementId }: { measurementId: string }) {
  return (
    <>
      <Script
        src={`https://www.googletagmanager.com/gtag/js?id=${measurementId}`}
        strategy="afterInteractive"
      />
      <Script id="google-analytics" strategy="afterInteractive">
        {`
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', '${measurementId}', {
            page_path: window.location.pathname,
          });
        `}
      </Script>
    </>
  );
}
```

Добавь в `app/layout.tsx`:

```tsx
import GoogleAnalytics from '@/lib/analytics/google-analytics';

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        <GoogleAnalytics measurementId="G-XXXXXXXXXX" />
        {children}
      </body>
    </html>
  );
}
```

### 3. Добавь переменные окружения

В `.env.local`:

```env
NEXT_PUBLIC_GA_MEASUREMENT_ID=G-XXXXXXXXXX
```

И используй:

```tsx
<GoogleAnalytics measurementId={process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID!} />
```

---

## 📊 Как смотреть статистику в GA4

### Основные отчёты:

1. **Acquisition → Traffic acquisition**
   - Смотри `Session source/medium` - увидишь `tiktok/video`, `instagram/reels`, etc.

2. **Acquisition → User acquisition**
   - Первые источники пользователей

3. **Custom Reports**
   - Создай отчёт с измерениями:
     - `utm_source`
     - `utm_medium`
     - `utm_campaign`
     - `utm_content`

### Полезные метрики:

- **Users** - уникальные пользователи
- **Sessions** - сессии
- **Engagement rate** - вовлеченность
- **Conversions** - конверсии (клики на бота)

---

## 🎨 Генератор UTM-ссылок

Используй [Campaign URL Builder](https://ga-dev-tools.google/campaign-url-builder/) от Google

Или создай свой Excel/Google Sheets с формулой:

```
=CONCATENATE("https://yoursite.com/landing?utm_source=", A2, "&utm_medium=", B2, "&utm_campaign=", C2, "&utm_content=", D2)
```

Где:
- A2 - источник (tiktok, instagram)
- B2 - medium (video, reels)
- C2 - campaign (december_content)
- D4 - content (video_title)

---

## 🔍 Отслеживание конверсий

### Настрой события "bot_click" в GA4:

1. В GA4: **Admin → Events → Create event**
2. Название: `bot_click`
3. Mark as conversion: ✅

Событие автоматически отправляется через `trackBotOpened()` в коде.

### Смотри конверсии:

**Reports → Engagement → Conversions**

Там увидишь:
- Сколько людей кликнули на бота
- Из каких источников больше конверсий
- Какие UTM-параметры приводят к лучшим результатам

---

## 📱 Backend Integration (опционально)

Можно сохранять UTM в базу данных при регистрации пользователя.

### API endpoint для сохранения UTM:

```python
# src/api/analytics.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.post("/track-landing")
async def track_landing_visit(
    utm_data: dict,
    db: Session = Depends(get_db)
):
    """Сохраняет источник трафика в базу"""
    # Сохрани в таблицу traffic_sources
    pass
```

### Миграция для таблицы:

```sql
CREATE TABLE traffic_sources (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    utm_source VARCHAR(100),
    utm_medium VARCHAR(100),
    utm_campaign VARCHAR(200),
    utm_content VARCHAR(200),
    utm_term VARCHAR(200),
    referrer TEXT,
    landing_page VARCHAR(500),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Связь с пользователем:

При старте бота в Telegram, можно передать UTM через deep link:

```
https://t.me/SyntraAI_bot?start=utm_tiktok_video_dec
```

И в боте распарсить `start` параметр для связи с источником.

---

## 📋 Чек-лист запуска

- [ ] Добавил `UTMTracker` в layout
- [ ] Заменил Link на TrackedLink для всех ссылок на бота
- [ ] Настроил Google Analytics 4
- [ ] Добавил GA Measurement ID в `.env.local`
- [ ] Создал UTM-ссылки для каждой соцсети
- [ ] Добавил UTM-ссылки в био TikTok/Instagram
- [ ] Настроил событие конверсии `bot_click` в GA4
- [ ] Протестировал: открыл ссылку с UTM, проверил в консоли браузера

---

## 🚀 Примеры использования

### A/B тестирование креативов:

```
Вариант A: utm_content=creative_a_short_hook
Вариант B: utm_content=creative_b_long_story
```

Смотри в GA4, какой приводит больше кликов на бота.

### Отслеживание эффективности платформ:

После недели сравни в GA4:
- `tiktok/video` - 1000 переходов, 50 кликов на бота (5%)
- `instagram/reels` - 500 переходов, 100 кликов на бота (20%)

**Вывод:** Instagram Reels конвертит лучше → сфокусируйся на нём.

---

## 🎯 Рекомендации

1. **Единая система именования** - всегда используй lowercase, без пробелов
   - ✅ `utm_source=tiktok`
   - ❌ `utm_source=TikTok`

2. **Не меняй названия** - если начал использовать `december_content`, используй везде

3. **Документируй** - веди таблицу всех UTM-кампаний

4. **Тестируй** - перед массовой публикацией открой ссылку сам, проверь в GA4 через 24 часа

5. **Анализируй еженедельно** - смотри, что работает, что нет

---

Успехов с аналитикой! 🚀
