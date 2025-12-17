# Top Movers и Market Overview - Исправление пустых данных

**Дата:** 2025-12-03
**Проблема:** При смене таймфрейма в Top Movers секции данные пропадали. Market Overview показывал нули для BTC Dom, ETH Dom и Volume.

## Проблемы

### 1. Top Movers - отсутствие данных для 1h и 7d

**Причина:**
- CoinGecko API по умолчанию возвращает только `price_change_percentage_24h`
- Для получения данных за 1h и 7d нужно передавать параметр `price_change_percentage=1h,24h,7d`

**Решение:**
```python
# src/services/coingecko_service.py:684
async def get_top_coins(
    self, vs_currency: str = "usd", limit: int = 10, include_1h_7d_change: bool = True
) -> Optional[List[Dict[str, Any]]]:
    params = {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": limit,
        "page": 1,
        "sparkline": "false",
    }

    # Add price change percentages for 1h and 7d timeframes
    if include_1h_7d_change:
        params["price_change_percentage"] = "1h,24h,7d"

    return await self._make_request("/coins/markets", params)
```

### 2. Market Overview - неправильная структура данных

**Причина:**
- Метод `CoinGeckoService.get_global_market_data()` возвращает обработанные данные напрямую
- Код в `market.py` ожидал структуру с `"data"` полем от raw API response

**До (неправильно):**
```python
# src/api/market.py:76 - OLD
if global_data and "data" in global_data:
    data = global_data["data"]
    total_market_cap_usd = data.get("total_market_cap", {}).get("usd", 0)
    total_volume_usd = data.get("total_volume", {}).get("usd", 0)
    # ...
```

**После (правильно):**
```python
# src/api/market.py:76 - NEW
# CoinGeckoService.get_global_market_data() returns processed data directly
if global_data:
    total_market_cap_usd = global_data.get("total_market_cap_usd", 0)
    total_volume_usd = global_data.get("total_volume_24h_usd", 0)
    market_cap_change = global_data.get("market_cap_change_24h", 0)
    # ...
    response["global"] = {
        "btc_dominance": round(global_data.get("btc_dominance", 0), 2),
        "eth_dominance": round(global_data.get("eth_dominance", 0), 2),
        # ...
    }
```

## Изменённые файлы

### Backend

1. **src/services/coingecko_service.py**
   - Добавлен параметр `include_1h_7d_change` в метод `get_top_coins()`
   - Параметр добавляет `price_change_percentage=1h,24h,7d` в запрос к API

2. **src/api/market.py**
   - Исправлена обработка данных от `get_global_market_data()`
   - Убрана проверка на `"data"` поле, данные берутся напрямую

### Frontend

3. **frontend/components/sections/TopMoversSection.tsx**
   - Добавлено логирование API ответов для отладки
   - Добавлена валидация структуры ответа
   - **Добавлена локализация (EN/RU)** через `useTranslations('home.market')`

4. **frontend/components/cards/MarketOverviewCard.tsx**
   - Добавлено логирование API ответов для отладки
   - Добавлена валидация структуры ответа
   - **Добавлена локализация (EN/RU)** через `useTranslations('home.market')`

### Локализация

5. **frontend/messages/en.json**
   - Добавлена секция `home.market` с переводами:
     - `overview_title`, `top_movers_title`, `fear_greed`
     - `total_market_cap`, `volume_24h`, `btc_dominance`, `eth_dominance`
     - `gainers`, `losers`, `show_more`, `show_less`, `now`
     - `active_cryptocurrencies`

6. **frontend/messages/ru.json**
   - Добавлена секция `home.market` с русскими переводами
   - Все ключи локализованы для русского языка

## Тестирование

### Сервисный уровень
```bash
python tests/test_market_endpoints.py
```

Результаты:
- ✅ Top Movers 1h: 100/100 монет с данными
- ✅ Top Movers 24h: 100/100 монет с данными
- ✅ Top Movers 7d: 100/100 монет с данными
- ✅ Market Overview: Все данные корректны (BTC Dom 57.31%, ETH Dom 11.35%, Market Cap $3.17T)

### API endpoint уровень
```bash
python tests/test_market_api_endpoints.py
```

Требует запущенный сервер на `http://localhost:8000`

## Что дальше

1. **Перезапустить сервер** для применения изменений:
   ```bash
   ./manage.sh restart
   ```

2. **Собрать и задеплоить фронтенд**:
   ```bash
   cd frontend && npm run build
   ```

3. **Проверить в браузере**:
   - Открыть Mini App
   - Переключить таймфреймы в Top Movers (1h, 24h, 7d)
   - Проверить, что Market Overview показывает корректные данные

## Debug в консоли браузера

После открытия Mini App в консоли должны появиться логи:
```
Market Overview API Response: { fear_greed: {...}, global: {...} }
Top Movers API Response (24h): { timeframe: "24h", gainers: [...], losers: [...] }
```

Если данные пустые - проверьте Network tab для деталей ошибки.

## Локализация

Все текстовые элементы теперь поддерживают английский и русский языки:

### Английский (EN)
- **Market Overview** → "Market Overview"
- **Top Movers** → "Top Movers"
- **Fear & Greed** → "Fear & Greed"
- **Gainers** → "Gainers"
- **Losers** → "Losers"
- **Show More** → "Show More (10 each)"

### Русский (RU)
- **Market Overview** → "Обзор рынка"
- **Top Movers** → "Топ движения"
- **Fear & Greed** → "Страх и жадность"
- **Gainers** → "Растут"
- **Losers** → "Падают"
- **Show More** → "Показать ещё (по 10)"

Язык автоматически определяется из настроек пользователя через `useTranslations('home.market')`.

## Итог

✅ **Top Movers** теперь работает со всеми таймфреймами (1h, 24h, 7d)
✅ **Market Overview** показывает корректные данные (BTC/ETH dominance, volume, market cap)
✅ **Добавлена полная локализация** (английский и русский языки)
✅ **Добавлены тесты** для проверки функциональности
✅ **Добавлено логирование** для отладки в production
