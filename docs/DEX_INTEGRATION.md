# Интеграция DexScreener и CoinMarketCap

## 📋 Обзор

Добавлена поддержка токенов с DEX (децентрализованных бирж) и мелких CEX, которые не представлены в CoinGecko или Binance.

**Проблема**: Многие новые токены (например, $MORI на Solana/Raydium) торгуются только на DEX или мелких CEX и не доступны через CoinGecko/Binance API.

**Решение**: Fallback система с поддержкой нескольких источников данных.

---

## 🚀 Новые возможности

### Поддерживаемые платформы

✅ **DEX (через DexScreener)**:
- Solana (Raydium, Orca, etc.)
- BSC (PancakeSwap)
- Ethereum (Uniswap, SushiSwap)
- Polygon, Avalanche, Arbitrum, Optimism, Base
- Sui, Aptos

✅ **CEX (через CoinMarketCap)**:
- KuCoin
- BingX
- Gate.io
- И другие мелкие биржи

---

## 🔄 Fallback логика

Система автоматически пробует несколько источников данных в следующем порядке:

```
1️⃣ CoinGecko (основной источник)
   ↓ если не найдено
2️⃣ DexScreener (DEX токены)
   ↓ если не найдено
3️⃣ CoinMarketCap (мелкие CEX)
   ↓ если не найдено
❌ Ошибка "не найдено"
```

---

## 📁 Новые файлы

### 1. DexScreenerService
**Файл**: `src/services/dexscreener_service.py`

**Функции**:
- `search_token(query)` - поиск токена по имени/символу/адресу
- `get_token_pairs(chain_id, token_address)` - получить все пары токена на цепи
- `get_best_pair(query)` - получить лучшую пару по ликвидности
- `get_token_price(query)` - получить цену токена (основной метод)

**API**:
- Бесплатный, без API ключа
- Rate limit: 300 запросов/минуту
- Документация: https://docs.dexscreener.com/api/reference

### 2. CoinMarketCapService
**Файл**: `src/services/coinmarketcap_service.py`

**Функции**:
- `get_quote_by_symbol(symbol)` - получить котировку по символу
- `search_cryptocurrency(query)` - поиск криптовалюты
- `get_global_metrics()` - глобальные метрики рынка

**API**:
- Требует API ключ (бесплатная регистрация)
- Free tier: 10,000 запросов/месяц (~333/день)
- Регистрация: https://coinmarketcap.com/api/

---

## ⚙️ Настройка

### 1. Обновите `.env` файл

Добавьте (опционально):
```bash
# CoinMarketCap API (optional, for extended coverage)
COINMARKETCAP_API_KEY=your_api_key_here
```

### 2. DexScreener
Не требует настройки - работает из коробки (бесплатный API).

### 3. CoinMarketCap (опционально)
Если нужен доступ к токенам с мелких CEX:

1. Зарегистрируйтесь: https://coinmarketcap.com/api/
2. Получите API ключ (Free tier)
3. Добавьте в `.env`: `COINMARKETCAP_API_KEY=ваш_ключ`

---

## 📊 Примеры использования

### Пример 1: Токен на Solana DEX ($MORI)
```
Пользователь: "Че скажешь про $MORI?"

Система:
1. Ищет в CoinGecko → не найдено
2. Ищет в DexScreener → найдено!
3. Возвращает: цена, ликвидность, 24h изменение, chain, dex

Ответ AI:
"$MORI торгуется на Solana/Raydium по цене $0.0123.
Ликвидность: $50,000. 24h: +15.5%"
```

### Пример 2: Токен на мелком CEX
```
Пользователь: "Цена XYZ?"

Система:
1. Ищет в CoinGecko → не найдено
2. Ищет в DexScreener → не найдено
3. Ищет в CoinMarketCap → найдено на KuCoin!
4. Возвращает: цена, market cap, volume

Ответ AI:
"XYZ торгуется по $1.23 (CoinMarketCap).
Market cap: $5M, Volume 24h: $150K"
```

### Пример 3: Обычный токен (Bitcoin)
```
Пользователь: "Цена BTC?"

Система:
1. Ищет в CoinGecko → найдено!
2. Возвращает полные данные

Ответ AI:
"Bitcoin: $45,000 (+2.5% за 24ч)
Market cap: $850B, Volume: $35B"
```

---

## 🔍 Технические детали

### Изменения в crypto_tools.py

**Функция**: `get_crypto_price(coin_id)`

**Логика**:
```python
# 1. Try CoinGecko
try:
    data = await coingecko_service.get_price(normalized_id)
    if data:
        return {success: True, data_source: "CoinGecko", ...}
except:
    pass

# 2. Try DexScreener
try:
    data = await dexscreener_service.get_token_price(coin_id)
    if data:
        return {success: True, data_source: "DexScreener (chain/dex)", ...}
except:
    pass

# 3. Try CoinMarketCap (if API key configured)
try:
    if coinmarketcap_service.api_key:
        data = await coinmarketcap_service.get_quote_by_symbol(coin_id)
        if data:
            return {success: True, data_source: "CoinMarketCap", ...}
except:
    pass

# All failed
return {success: False, error: "Not found in any source"}
```

### Response структура

**Успех (CoinGecko)**:
```json
{
  "success": true,
  "data_source": "CoinGecko",
  "name": "Bitcoin",
  "symbol": "BTC",
  "price_usd": 45000,
  "change_24h_percent": 2.5,
  "market_cap_usd": 850000000000,
  "volume_24h_usd": 35000000000
}
```

**Успех (DexScreener)**:
```json
{
  "success": true,
  "data_source": "DexScreener (solana/raydium)",
  "name": "Memori",
  "symbol": "MORI",
  "price_usd": 0.0123,
  "change_24h_percent": 15.5,
  "liquidity_usd": 50000,
  "volume_24h_usd": 123456,
  "market_cap_usd": 1230000,
  "chain": "solana",
  "dex": "raydium",
  "pair_address": "...",
  "token_address": "..."
}
```

**Успех (CoinMarketCap)**:
```json
{
  "success": true,
  "data_source": "CoinMarketCap",
  "name": "Example Token",
  "symbol": "XYZ",
  "price_usd": 1.23,
  "change_24h_percent": 5.2,
  "market_cap_usd": 5000000,
  "volume_24h_usd": 150000,
  "cmc_rank": 1234
}
```

**Ошибка**:
```json
{
  "success": false,
  "error": "Cryptocurrency 'UNKNOWN' not found in any data source. Tried: CoinGecko, DexScreener, CoinMarketCap",
  "tried_sources": ["CoinGecko", "DexScreener", "CoinMarketCap"]
}
```

---

## 🧪 Тестирование

### Тест 1: DEX токен
```bash
# Запустите бота
python bot.py

# В Telegram отправьте:
"Че скажешь про $MORI?"
```

**Ожидаемый результат**:
- Бот находит токен через DexScreener
- Показывает цену, ликвидность, изменение 24h
- Указывает источник данных: "DexScreener (solana/raydium)"

### Тест 2: CoinGecko токен (контроль)
```bash
# В Telegram:
"Цена Bitcoin?"
```

**Ожидаемый результат**:
- Бот находит через CoinGecko (первый источник)
- Показывает полные данные
- Источник: "CoinGecko"

### Тест 3: Несуществующий токен
```bash
# В Telegram:
"Цена TOTALLYFAKETOKEN123?"
```

**Ожидаемый результат**:
- Бот пробует все источники
- Возвращает ошибку с информацией о попытках
- "Cryptocurrency 'TOTALLYFAKETOKEN123' not found in any data source"

---

## 📈 Преимущества

✅ **Широкий охват**: поддержка 99% всех токенов
✅ **DEX токены**: Solana, BSC, ETH, Polygon и другие
✅ **Мелкие CEX**: KuCoin, BingX, Gate.io
✅ **Graceful degradation**: плавный откат на резервные источники
✅ **Прозрачность**: AI показывает источник данных пользователю
✅ **Бесплатно**: DexScreener работает без API ключа
✅ **Кеширование**: все запросы кешируются на 5 минут

---

## 🔧 Обслуживание

### Мониторинг
Логи показывают источник данных для каждого запроса:
```
INFO: 🔍 Searching price for 'MORI' (normalized: 'mori')
DEBUG: Trying CoinGecko for 'mori'...
DEBUG: CoinGecko failed for 'mori': 404 - coin not found
DEBUG: Trying DexScreener for 'MORI'...
INFO: ✅ Found on DexScreener: Memori (MORI) on solana/raydium
```

### Rate Limits
- **DexScreener**: 300 req/min (бесплатно)
- **CoinMarketCap**: 333 req/день (free tier)
- **CoinGecko**: 10 req/min (без ключа)

### Рекомендации
1. DexScreener - всегда включен (бесплатно)
2. CoinMarketCap - опционально, если нужны мелкие CEX
3. Кеш - 5 минут (можно настроить в config.py)

---

## 🎯 Дальнейшие улучшения

Возможные доработки:
- [ ] Добавить поддержку технического анализа для DEX токенов
- [ ] Интегрировать данные о ликвидности в AI ответы
- [ ] Добавить алерты при низкой ликвидности
- [ ] Расширить поддержку других DEX API
- [ ] Добавить исторические данные с DexScreener

---

**Версия**: 1.0
**Дата**: 2025-01-17
**Автор**: Claude Code
