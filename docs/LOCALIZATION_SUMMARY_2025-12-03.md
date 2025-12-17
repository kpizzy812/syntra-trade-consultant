# Локализация Top Movers и Market Overview

**Дата:** 2025-12-03
**Что сделано:** Добавлена полная поддержка английского и русского языков для компонентов Top Movers и Market Overview

## Изменения

### 1. Файлы локализации

#### frontend/messages/en.json
Добавлена секция `home.market`:
```json
"market": {
  "overview_title": "Market Overview",
  "top_movers_title": "Top Movers",
  "fear_greed": "Fear & Greed",
  "total_market_cap": "Total Market Cap",
  "volume_24h": "24h Volume",
  "btc_dominance": "BTC Dom",
  "eth_dominance": "ETH Dom",
  "gainers": "Gainers",
  "losers": "Losers",
  "show_more": "Show More ({count} each)",
  "show_less": "Show Less",
  "now": "Now",
  "active_cryptocurrencies": "{count} active cryptocurrencies"
}
```

#### frontend/messages/ru.json
Добавлена секция `home.market`:
```json
"market": {
  "overview_title": "Обзор рынка",
  "top_movers_title": "Топ движения",
  "fear_greed": "Страх и жадность",
  "total_market_cap": "Общая капитализация",
  "volume_24h": "Объём 24ч",
  "btc_dominance": "BTC дом.",
  "eth_dominance": "ETH дом.",
  "gainers": "Растут",
  "losers": "Падают",
  "show_more": "Показать ещё (по {count})",
  "show_less": "Свернуть",
  "now": "Сейчас",
  "active_cryptocurrencies": "{count} активных криптовалют"
}
```

### 2. Обновленные компоненты

#### TopMoversSection.tsx
**Было:**
```tsx
<h2>🔥 Top Movers</h2>
<span>Gainers</span>
<span>Losers</span>
<button>{showAll ? '↑ Show Less' : '↓ Show More (10 each)'}</button>
```

**Стало:**
```tsx
const t = useTranslations('home.market');

<h2>🔥 {t('top_movers_title')}</h2>
<span>{t('gainers')}</span>
<span>{t('losers')}</span>
<button>
  {showAll ? `↑ ${t('show_less')}` : `↓ ${t('show_more', { count: 10 })}`}
</button>
```

#### MarketOverviewCard.tsx
**Было:**
```tsx
<h2>🌍 Market Overview</h2>
<div>Fear & Greed</div>
<div>Total Market Cap</div>
<div>24h Volume</div>
<span>Now</span>
```

**Стало:**
```tsx
const t = useTranslations('home.market');

<h2>🌍 {t('overview_title')}</h2>
<div>{t('fear_greed')}</div>
<div>{t('total_market_cap')}</div>
<div>{t('volume_24h')}</div>
<span>{t('now')}</span>
```

## Результат

### На английском языке
- **Market Overview** → Market Overview
- **Top Movers** → Top Movers
- **Fear & Greed** → Fear & Greed
- **Total Market Cap** → Total Market Cap
- **24h Volume** → 24h Volume
- **BTC Dom** → BTC Dom
- **ETH Dom** → ETH Dom
- **Gainers** → Gainers
- **Losers** → Losers
- **Show More (10 each)** → Show More (10 each)
- **Show Less** → Show Less
- **Now** → Now
- **12,543 active cryptocurrencies** → 12,543 active cryptocurrencies

### На русском языке
- **Market Overview** → Обзор рынка
- **Top Movers** → Топ движения
- **Fear & Greed** → Страх и жадность
- **Total Market Cap** → Общая капитализация
- **24h Volume** → Объём 24ч
- **BTC Dom** → BTC дом.
- **ETH Dom** → ETH дом.
- **Gainers** → Растут
- **Losers** → Падают
- **Show More (10 each)** → Показать ещё (по 10)
- **Show Less** → Свернуть
- **Now** → Сейчас
- **12,543 active cryptocurrencies** → 12,543 активных криптовалют

## Как это работает

1. Язык автоматически определяется из настроек пользователя
2. `useTranslations('home.market')` загружает нужные переводы
3. `t('key')` возвращает перевод для текущего языка
4. `t('key', { param: value })` поддерживает параметры (например, count)

## Применение изменений

```bash
# Frontend собран
cd frontend && npm run build

# Для применения изменений перезапустите сервер
./manage.sh restart
```

## Проверка

Откройте Mini App и:
1. Проверьте язык в настройках профиля
2. Переключите язык (EN ↔ RU)
3. Убедитесь, что Top Movers и Market Overview отображаются на выбранном языке

## Итог

✅ Добавлена полная локализация для EN и RU
✅ Все хардкод строки заменены на переводы
✅ Поддержка параметров в переводах (например, {count})
✅ Автоматическое определение языка из настроек пользователя
