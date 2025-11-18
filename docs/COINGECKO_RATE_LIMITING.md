# CoinGecko API: Rate Limiting и Кэширование

**Дата обновления:** 18 ноября 2025
**Статус:** ✅ Реализовано

## Проблема

При использовании бота возникала ошибка **429 (Rate Limit Exceeded)** от CoinGecko API:

```
2025-11-18 18:28:20 | ERROR | CoinGecko API error: 429 - Rate Limit exceeded
```

### Причины:
1. **Недостаточное кэширование** - TTL 60 секунд для всех данных
2. **Отсутствие rate limiting** - нет контроля количества запросов
3. **Нет обработки 429** - при превышении лимита просто возвращался None
4. **Частые запросы** - при каждом обращении пользователя

## Решение

### 1. Rate Limiter с Sliding Window

Реализован класс `RateLimiter` с алгоритмом скользящего окна:

```python
class RateLimiter:
    """Rate limiter using sliding window algorithm"""

    def __init__(self, max_calls: int, time_window: int = 60):
        self.max_calls = max_calls  # Макс. запросов
        self.time_window = time_window  # Временное окно (сек)
        self.calls: deque = deque()  # История запросов
        self._lock = asyncio.Lock()  # Thread-safe

    async def acquire(self) -> None:
        """Ждет, пока не освободится слот для запроса"""
        # Удаляет старые запросы за пределами окна
        # Ждет, если достигнут лимит
```

**Преимущества:**
- ✅ Автоматическая задержка при достижении лимита
- ✅ Точный контроль частоты запросов
- ✅ Thread-safe (asyncio.Lock)

### 2. Дифференцированное Кэширование

Разные типы данных кэшируются на разное время:

```python
CACHE_TTL = {
    "price": 90,           # Цены: 90с (меняются часто)
    "coin_data": 300,      # Детальные данные: 5 мин
    "market_chart": 600,   # Исторические: 10 мин
    "trending": 300,       # Трендовые монеты: 5 мин
    "global": 300,         # Глобальные данные: 5 мин
    "search": 600,         # Поиск: 10 мин
    "default": 180,        # По умолчанию: 3 мин
}
```

**Преимущества:**
- ✅ Снижение нагрузки на API в 3-10 раз
- ✅ Актуальные цены (обновление каждые 90с)
- ✅ Экономия запросов на редко меняющихся данных

### 3. Обработка 429 Ошибки

Добавлена специальная обработка Rate Limit ошибок:

```python
elif response.status == 429:
    # Получаем Retry-After из заголовка
    retry_after = int(response.headers.get("Retry-After", 60))
    wait_time = min(retry_after, 60)  # Макс. 60с

    logger.warning(f"Rate limit (429). Waiting {wait_time}s")

    if attempt < max_retries - 1:
        await asyncio.sleep(wait_time)
        continue  # Повторяем запрос
```

**Преимущества:**
- ✅ Автоматический retry при 429
- ✅ Использование Retry-After заголовка
- ✅ Exponential backoff для других ошибок

### 4. Статистика Использования

Добавлен метод для мониторинга API:

```python
stats = coingecko_service.get_usage_stats()
# {
#     "rate_limiter": {
#         "recent_calls": 8,
#         "max_calls": 10,
#         "usage_percent": 80.0
#     },
#     "cache": {
#         "total_entries": 42,
#         "by_type": {"price": 10, "coin_data": 15}
#     }
# }
```

## Лимиты CoinGecko API (2025)

### Demo API ✅ (текущий план)
- Требует бесплатную регистрацию и API ключ
- **30 запросов/мин**
- **10,000 запросов/месяц**
- Выделенная инфраструктура
- **Настройка:** `COINGECKO_RATE_LIMIT=25` (буфер 5 запросов)

### Public API
- **Без регистрации, без ключа**
- **5-15 запросов/мин** (нестабильно)
- Общая инфраструктура (IP pooling)
- **Настройка:** `COINGECKO_RATE_LIMIT=10` (консервативно)

### Pro API (платный)
- **500-1000 запросов/мин**
- Миллионы запросов в месяц
- Приоритетная поддержка

## Конфигурация

### Переменные окружения (.env)

```bash
# CoinGecko API (Demo API)
COINGECKO_API_KEY=your_api_key_here    # Получить на coingecko.com/en/api
COINGECKO_RATE_LIMIT=25                # 25 для Demo API (30/мин лимит)
# Для Public API без ключа: COINGECKO_RATE_LIMIT=10
```

### Настройки в коде

```python
# config/config.py
class RateLimits:
    COINGECKO_CALLS_PER_MINUTE = int(os.getenv("COINGECKO_RATE_LIMIT", "10"))

# src/services/crypto_tools.py
coingecko_service = CoinGeckoService(
    rate_limit=RateLimits.COINGECKO_CALLS_PER_MINUTE
)
```

## Файлы изменений

### Обновлены:
1. **[src/services/coingecko_service.py](../src/services/coingecko_service.py)**
   - Добавлен `RateLimiter` класс
   - Обновлен `_make_request()` с rate limiting
   - Дифференцированное кэширование
   - Обработка 429 ошибки
   - Метод `get_usage_stats()`

2. **[config/config.py](../config/config.py)**
   - Обновлен `RateLimits.COINGECKO_CALLS_PER_MINUTE` (10 по умолчанию)
   - Добавлены комментарии о разных планах

3. **[src/services/crypto_tools.py](../src/services/crypto_tools.py)**
   - Передача `rate_limit` при инициализации сервиса

## Тестирование

```bash
# Проверка импорта
python -c "from src.services.crypto_tools import coingecko_service; \
           stats = coingecko_service.get_usage_stats(); \
           print(f'Rate limit: {stats[\"rate_limiter\"][\"max_calls\"]} calls/min')"

# Вывод (Demo API):
# ✓ CoinGecko service initialized with 25 calls/min rate limit
# Rate limit: 25 calls/min
# API ключ: установлен
```

## Результаты

### До улучшений:
- ❌ Ошибки 429 при активном использовании
- ❌ TTL кэша 60с для всех данных
- ❌ Нет контроля запросов
- ❌ Плохой UX при превышении лимита

### После улучшений:
- ✅ Автоматический rate limiting (25 запросов/мин для Demo API)
- ✅ Дифференцированный кэш (90с - 10мин)
- ✅ Обработка 429 с retry
- ✅ Снижение нагрузки на API в 3-10 раз
- ✅ Мониторинг использования API
- ✅ Стабильная работа на Demo API (30 calls/min, 10k/month)

## Рекомендации

### Для улучшения производительности:

1. **Мониторинг месячного лимита**
   - Demo API: 10,000 запросов/месяц
   - Добавить логирование расхода месячной квоты
   - При приближении к лимиту - увеличить TTL кэша

2. **Увеличить TTL для редких операций**
   - Исторические данные: 600с → 1800с (30 мин)
   - Поиск: 600с → 3600с (1 час)

3. **Добавить Redis для shared cache**
   - Кэш между несколькими инстансами
   - Персистентность при рестарте

4. **Батчинг запросов**
   - Объединение запросов пользователей
   - Запрос нескольких монет за раз

## Мониторинг

### Логи

```bash
# Успешные запросы
INFO | CoinGecko service initialized with 10 calls/min rate limit
DEBUG | Cache hit for /simple/price... (TTL: 90s, type: price)

# Rate limiting
WARNING | Rate limit reached (10/10), waiting 15.2s

# 429 ошибки
WARNING | Rate limit (429) on attempt 1/3. Waiting 60s before retry
ERROR | Rate limit exceeded after 3 attempts
```

### Метрики для мониторинга:
- Количество 429 ошибок в час
- Hit rate кэша (cache hits / total requests)
- Среднее время ответа API
- Usage percent rate limiter

## Ссылки

- [CoinGecko API Documentation](https://docs.coingecko.com/)
- [Rate Limits Guide](https://docs.coingecko.com/docs/common-errors-rate-limit)
- [Pricing Plans](https://www.coingecko.com/en/api/pricing)
