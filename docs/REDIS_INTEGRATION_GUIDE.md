# Redis Integration Guide - Syntra Trade Consultant

## ✅ Что сделано

### Инфраструктура кэширования

1. **Зависимости** (`requirements.txt`)
   - ✅ Добавлен `redis[hiredis]>=5.0.0` с async поддержкой

2. **Конфигурация** (`config/cache_config.py`)
   - ✅ `CacheTTL` - TTL для всех типов данных
   - ✅ `CacheConfig` - настройки Redis подключения
   - ✅ Все TTL настраиваемые через env переменные

3. **Модуль кэширования** (`src/cache/`)
   - ✅ `redis_manager.py` - централизованный менеджер Redis
   - ✅ `cache_keys.py` - генерация ключей кэша
   - ✅ `cache_decorators.py` - декораторы для автоматического кэширования

### Основные возможности

- ✅ Connection pooling для эффективного использования соединений
- ✅ Graceful degradation - бот работает без Redis
- ✅ Автоматическая JSON сериализация/десериализация
- ✅ Namespace для ключей (`syntra:service:method:params`)
- ✅ Метрики кэша (hits, misses, hit rate)
- ✅ Логирование операций кэша

## 🚀 Установка и запуск

### 1. Установка Redis

#### macOS
```bash
brew install redis
brew services start redis
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

#### Docker
```bash
docker run -d --name redis -p 6379:6379 redis:latest
```

### 2. Установка Python зависимостей

Через виртуальное окружение (как указано в CLAUDE.md):

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Конфигурация

Добавь в `.env`:

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Cache Settings (optional, defaults shown)
CACHE_ENABLED=true
CACHE_NAMESPACE=syntra

# Cache TTLs - можно настроить под свои нужды
CACHE_TTL_COINGECKO_PRICE=90
CACHE_TTL_BINANCE_KLINES_1H=600
CACHE_TTL_FEAR_GREED_INDEX=3600
```

### 4. Проверка работы Redis

```bash
redis-cli ping
# Должен вернуть: PONG
```

## 💡 Примеры использования

### Вариант 1: Использование декоратора (рекомендуется)

```python
from src.cache.cache_decorators import cached_binance
from config.cache_config import CacheTTL

class BinanceService:
    @cached_binance('klines', ttl=CacheTTL.BINANCE_KLINES_1H)
    async def get_klines(self, symbol: str, interval: str, limit: int):
        """
        Автоматически кэшируется в Redis
        Ключ: syntra:binance:klines:BTCUSDT_1h_100
        """
        # Оригинальная логика API запроса
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                return await response.json()
```

### Вариант 2: Прямое использование RedisManager

```python
from src.cache import get_redis_manager, CacheKeyBuilder
from config.cache_config import CacheTTL

async def get_fear_greed():
    redis_mgr = get_redis_manager()
    cache_key = CacheKeyBuilder.build("feargreed", "current")

    # Попытка получить из кэша
    cached = await redis_mgr.get(cache_key)
    if cached:
        return cached

    # Запрос к API
    data = await fetch_from_api()

    # Сохранить в кэш
    await redis_mgr.set(cache_key, data, ttl=CacheTTL.FEAR_GREED_INDEX)
    return data
```

### Вариант 3: Context manager

```python
from src.cache import redis_lifespan

async def main():
    async with redis_lifespan() as redis_mgr:
        # Redis автоматически инициализируется и закрывается
        await redis_mgr.set("key", {"data": "value"}, ttl=300)
        value = await redis_mgr.get("key")
```

## 🔄 Миграция существующих сервисов

### Пример: Binance Service

**До:**
```python
async def get_klines(self, symbol: str, interval: str, limit: int):
    # Прямой запрос к API без кэширования
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            return await response.json()
```

**После:**
```python
from src.cache.cache_decorators import cached_binance
from config.cache_config import CacheTTL

@cached_binance('klines', ttl=CacheTTL.BINANCE_KLINES_1H)
async def get_klines(self, symbol: str, interval: str, limit: int):
    # Точно такой же код! Декоратор автоматически кэширует результат
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            return await response.json()
```

### Пример: Fear & Greed Service

**До:**
```python
async def get_current(self):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

**После:**
```python
from src.cache.cache_decorators import cached_feargreed

@cached_feargreed()  # TTL=3600s по умолчанию
async def get_current(self):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
```

## 📊 Мониторинг

### Просмотр статистики кэша

```python
from src.cache import get_redis_manager

redis_mgr = get_redis_manager()
stats = redis_mgr.get_stats()
print(stats)

# Вывод:
# {
#     "hits": 150,
#     "misses": 30,
#     "errors": 0,
#     "sets": 30,
#     "deletes": 5,
#     "total_requests": 180,
#     "hit_rate": 0.83,
#     "is_available": True
# }
```

### Просмотр ключей в Redis

```bash
# Все ключи Syntra
redis-cli KEYS "syntra:*"

# Только CoinGecko
redis-cli KEYS "syntra:coingecko:*"

# Только цены Binance
redis-cli KEYS "syntra:binance:price:*"
```

### Очистка кэша

```python
from src.cache import get_redis_manager, CacheKeyBuilder

redis_mgr = get_redis_manager()

# Очистить весь кэш CoinGecko
pattern = CacheKeyBuilder.pattern("coingecko")
await redis_mgr.delete_pattern(pattern)

# Очистить только цены CoinGecko
pattern = CacheKeyBuilder.pattern("coingecko", "price")
await redis_mgr.delete_pattern(pattern)
```

## ⚙️ Настройка TTL

Все TTL настраиваются через env переменные или `config/cache_config.py`:

```python
# config/cache_config.py
class CacheTTL:
    # CoinGecko
    COINGECKO_PRICE = 90          # 90 секунд
    COINGECKO_MARKET_DATA = 300   # 5 минут

    # Binance
    BINANCE_KLINES_1H = 600       # 10 минут
    BINANCE_KLINES_1D = 3600      # 1 час

    # Fear & Greed
    FEAR_GREED_INDEX = 3600       # 1 час (обновляется раз в день)
```

Переопределить через `.env`:

```bash
CACHE_TTL_COINGECKO_PRICE=120  # Изменить на 2 минуты
CACHE_TTL_BINANCE_KLINES_1H=900  # Изменить на 15 минут
```

## 🛡️ Graceful Degradation

Бот работает **без Redis**! Если Redis недоступен:

1. Логируется предупреждение
2. Функции продолжают работать (делают прямые API запросы)
3. Никаких ошибок для пользователей

Пример лога:
```
WARNING | Redis connection failed: Connection refused. Bot will work without cache.
```

## 🧪 Тестирование

```bash
# Запустить тесты (когда они будут созданы)
source .venv/bin/activate
pytest tests/test_redis_cache.py -v
```

## 📈 Ожидаемые улучшения

### Экономия API лимитов

- **CoinGecko**: Экономия ~60-70% запросов (hit rate ~0.65-0.75)
- **CoinMarketCap**: Экономия ~80-90% запросов (критично важно)
- **Binance**: Экономия ~40-50% запросов (не критично, но полезно)

### Производительность

- **Скорость**: Ответы из кэша **в 10-50 раз быстрее** API запросов
- **Латентность**: Redis ~1-5ms vs API 100-500ms

## 🔧 Troubleshooting

### Redis не подключается

```bash
# Проверить статус
redis-cli ping

# Если не работает, перезапустить
brew services restart redis  # macOS
sudo systemctl restart redis # Linux
```

### Ошибка "module 'redis.asyncio' has no attribute 'Redis'"

Обновить redis-py:
```bash
pip install --upgrade redis
```

### Большой размер кэша

Проверить размер:
```bash
redis-cli INFO memory
```

Очистить весь кэш:
```bash
redis-cli FLUSHDB
```

## 📚 Следующие шаги

### Фаза 1: Приоритетные сервисы (рекомендуется сделать первым)
1. ✅ Инфраструктура готова
2. 🔄 Мигрировать **Binance Service** (нет кэша сейчас)
3. 🔄 Мигрировать **Fear & Greed Service** (нет кэша сейчас)

### Фаза 2: Замена in-memory кэша
4. 🔄 Мигрировать CoinGecko (заменить in-memory на Redis)
5. 🔄 Мигрировать DexScreener
6. 🔄 Мигрировать CoinMarketCap
7. 🔄 Мигрировать CryptoPanic

### Фаза 3: Тестирование
8. 🔄 Написать unit тесты
9. 🔄 Написать integration тесты
10. 🔄 Load testing

## 🎯 Готовый пример миграции

Давай я покажу как мигрировать **FearGreedService** прямо сейчас?

1. Открыть `src/services/fear_greed_service.py`
2. Импортировать декоратор:
   ```python
   from src.cache.cache_decorators import cached_feargreed
   ```
3. Добавить декоратор к методу `get_current`:
   ```python
   @cached_feargreed()
   async def get_current(self):
       # Остальной код без изменений
   ```

Готово! Теперь Fear & Greed Index кэшируется на 1 час.

---

**Автор**: Claude Code
**Дата**: 2025-01-19
**Статус**: Готово к использованию ✅
