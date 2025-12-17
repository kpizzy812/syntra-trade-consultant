# 🔧 Как интегрировать UTM tracking в существующий лендинг

## Изменения в коде

### 1. ✅ Уже сделано

- [x] Создан `lib/analytics/utm-tracker.ts` - основная логика tracking
- [x] Создан `components/analytics/UTMTracker.tsx` - компонент для автоматического отслеживания
- [x] Создан `components/analytics/TrackedLink.tsx` - ссылка с tracking
- [x] Создан `app/landing/layout.tsx` - layout с UTM tracker

### 2. ⚙️ Нужно сделать

Замени обычные `Link` на `TrackedLink` в лендинге:

**Было (в `app/landing/page.tsx`):**
```tsx
import Link from "next/link";

<Link
  href="https://t.me/SyntraAI_bot"
  target="_blank"
  className="btn btn-primary"
>
  🤖 Открыть @SyntraAI_bot
</Link>
```

**Стало:**
```tsx
import TrackedLink from "@/components/analytics/TrackedLink";

<TrackedLink
  href="https://t.me/SyntraAI_bot"
  target="_blank"
  className="btn btn-primary"
>
  🤖 Открыть @SyntraAI_bot
</TrackedLink>
```

---

## Полный пример изменений

Вот какие места в `app/landing/page.tsx` нужно изменить:

### Строка 4 - импорт
```tsx
// Добавь после других импортов:
import TrackedLink from "@/components/analytics/TrackedLink";
```

### Строки 199-206 - главные CTA кнопки
```tsx
<div className="flex flex-wrap gap-4">
  <TrackedLink
    href="https://t.me/SyntraAI_bot"
    target="_blank"
    className="btn btn-primary"
  >
    🤖 Открыть @SyntraAI_bot
  </TrackedLink>

  <TrackedLink
    href="https://t.me/SyntraTrade"
    target="_blank"
    className="btn btn-ghost"
  >
    📢 Канал @SyntraTrade
  </TrackedLink>
</div>
```

### Строка 160 - кнопка в хедере
```tsx
<TrackedLink
  href="https://t.me/SyntraAI_bot"
  target="_blank"
  className="btn btn-primary"
>
  Открыть бота
</TrackedLink>
```

### Строка 499 - pricing секция
```tsx
<TrackedLink
  href="https://t.me/SyntraAI_bot"
  target="_blank"
  className="btn btn-primary btn-full"
>
  Открыть @SyntraAI_bot
</TrackedLink>
```

### Строки 578-591 - финальная CTA
```tsx
<div className="final-actions">
  <TrackedLink
    href="https://t.me/SyntraAI_bot"
    target="_blank"
    className="btn btn-primary"
  >
    🤖 Открыть @SyntraAI_bot
  </TrackedLink>
  <TrackedLink
    href="https://t.me/SyntraTrade"
    target="_blank"
    className="btn btn-ghost"
  >
    📢 Канал @SyntraTrade
  </TrackedLink>
</div>
```

### Footer ссылки тоже можно отследить (опционально)

Обычные Link на Telegraph можно оставить без tracking, но ссылки на бота и канал - заменить.

---

## 📊 Google Analytics 4 Setup

### 1. Создай `.env.local` файл

```env
NEXT_PUBLIC_GA_MEASUREMENT_ID=G-XXXXXXXXXX
```

### 2. Создай файл `lib/analytics/google-analytics.tsx`

Уже создан в предыдущих шагах (см. UTM_TRACKING_GUIDE.md).

### 3. Добавь в `app/layout.tsx`

```tsx
import GoogleAnalytics from '@/lib/analytics/google-analytics';

export default function RootLayout({ children }) {
  return (
    <html lang="ru">
      <body>
        {/* Google Analytics */}
        {process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID && (
          <GoogleAnalytics
            measurementId={process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID}
          />
        )}

        {children}
      </body>
    </html>
  );
}
```

---

## 🧪 Тестирование

### 1. Проверь локально

```bash
npm run dev
```

Открой:
```
http://localhost:3000/landing?utm_source=test&utm_medium=manual&utm_campaign=testing&utm_content=local_test
```

### 2. Проверь в консоли браузера

Открой DevTools (F12):
```
Application → Storage → Session Storage → http://localhost:3000
```

Должен появиться ключ `syntra_utm_params` с твоими параметрами.

### 3. Проверь в Console

```javascript
// В консоли браузера:
JSON.parse(sessionStorage.getItem('syntra_utm_params'))

// Должно вывести:
{
  utm_source: "test",
  utm_medium: "manual",
  utm_campaign: "testing",
  utm_content: "local_test"
}
```

### 4. Кликни на кнопку "Открыть бота"

В консоли должно появиться:
```
📊 Traffic source tracked: {
  utm_source: "test",
  utm_medium: "manual",
  ...
}
```

---

## 📱 Использование в соцсетях

### TikTok - добавь в био:

```
🤖 Крипто AI-помощник:
https://yoursite.com/landing?utm_source=tiktok&utm_medium=bio&utm_campaign=main
```

### Instagram - добавь в био:

```
💎 Твой личный AI по крипте
👇 Бесплатно в Telegram
https://yoursite.com/landing?utm_source=instagram&utm_medium=bio&utm_campaign=main
```

### Telegram канал @SyntraTrade - закрепи пост:

```
🚀 Открой Syntra AI прямо сейчас!

5 бесплатных вопросов каждый день.
Без шарлатанства, только честная аналитика.

👉 https://yoursite.com/landing?utm_source=telegram&utm_medium=pinned&utm_campaign=syntrade

#crypto #ai #trading
```

---

## 📈 Отслеживание результатов

### В Google Analytics 4:

1. **Reports → Acquisition → Traffic acquisition**
   - Смотри колонку "Session source/medium"
   - Увидишь: `tiktok / bio`, `instagram / reels`, `telegram / channel`

2. **Reports → Engagement → Events**
   - Событие `bot_opened` покажет сколько кликов на бота

3. **Explore → Free form**
   - Создай кастомный отчёт:
     - **Dimensions:** utm_source, utm_medium, utm_campaign
     - **Metrics:** Users, Sessions, Conversions

### Пример результатов через неделю:

| Source | Medium | Users | Bot Clicks | Conversion Rate |
|--------|--------|-------|------------|-----------------|
| tiktok | video | 1200 | 60 | 5% |
| instagram | reels | 800 | 120 | 15% |
| telegram | channel | 300 | 90 | 30% |
| instagram | bio | 150 | 45 | 30% |

**Вывод:** Telegram и Instagram bio конвертят лучше всего!

---

## 🎯 Действия по результатам

### Если TikTok приводит много трафика, но мало конверсий:

- Проверь соответствие контента и лендинга
- Измени hook в видео
- Добавь более явный CTA
- Попробуй другой тип контента (tutorial vs entertainment)

### Если Instagram Reels хорошо конвертит:

- Увеличь частоту постинга Reels
- Анализируй, какие темы работают лучше (через `utm_content`)
- Дублируй успешный формат

### Если Telegram канал приводит мало трафика:

- Чаще постинг с CTA на бота
- Добавь закреп с прямой ссылкой
- Запусти welcome message с ссылкой на лендинг

---

## ✅ Финальный чек-лист

- [ ] Создал layout с UTMTracker для `/landing`
- [ ] Заменил все Link на TrackedLink (минимум 7 мест)
- [ ] Добавил Google Analytics в `.env.local`
- [ ] Добавил GoogleAnalytics компонент в root layout
- [ ] Протестировал локально с тестовыми UTM параметрами
- [ ] Проверил в Session Storage что параметры сохраняются
- [ ] Развернул на прод (Vercel/etc)
- [ ] Создал UTM-ссылки для всех соцсетей (TikTok, Instagram, Telegram)
- [ ] Добавил ссылки в био всех соцсетей
- [ ] Настроил событие конверсии в GA4
- [ ] Запланировал еженедельный анализ статистики

---

Готово! Теперь ты будешь точно знать откуда приходят твои пользователи 🎯
