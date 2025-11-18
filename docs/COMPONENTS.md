# COMPONENTS REFERENCE - Syntra Trade Consultant

> Детальное описание всех компонентов системы

## Содержание
- [Handlers](#handlers)
- [Services](#services)
- [Middleware](#middleware)
- [Database](#database)
- [Config](#config)
- [Utils](#utils)

---

## Handlers

### start.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/bot/handlers/start.py`

**Назначение:** Обработка команды /start

**Функции:**
- `cmd_start(message: Message, session: AsyncSession, language: str)` - Приветствие пользователя и регистрация в БД

**Зависимости:**
- Database: User model, get_or_create_user()
- Config: REQUIRED_CHANNEL
- Localization: i18n

**Особенности:**
- Создает пользователя в БД при первом использовании
- Показывает приветственное сообщение с функциями бота (на выбранном языке)
- Отображает интерактивное меню с кнопками
- Напоминает о необходимости подписки на канал

---

### help_cmd.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/bot/handlers/help_cmd.py`

**Назначение:** Обработка команды /help

**Функции:**
- `cmd_help(message: Message, session: AsyncSession, language: str)` - Справка по командам и показ лимитов

**Зависимости:**
- Database: get_request_limit()
- Config: REQUEST_LIMIT_PER_DAY
- Localization: i18n

**Особенности:**
- Показывает список доступных команд (на выбранном языке)
- Отображает оставшиеся запросы (X/5)
- Показывает время до сброса лимитов
- Мультиязычная поддержка

---

### limits.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/bot/handlers/limits.py`

**Назначение:** Обработка команды /limits

**Функции:**
- `cmd_limits(message: Message, session: AsyncSession, language: str)` - Проверка лимитов запросов

**Зависимости:**
- Database: get_request_limit()
- Config: REQUEST_LIMIT_PER_DAY
- Localization: i18n

**Особенности:**
- Показывает детальную информацию о лимитах
- Отображает количество использованных запросов
- Показывает время до обновления лимитов
- Форматированный вывод с прогресс-баром

---

### menu.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/bot/handlers/menu.py`

**Назначение:** Интерактивное меню навигации

**Функции:**
- Callback handlers для кнопок меню
- `show_main_menu()` - Показ главного меню
- `show_crypto_menu()` - Меню криптовалютных функций
- `show_help_menu()` - Меню справки

**Зависимости:**
- aiogram InlineKeyboardMarkup
- Localization: i18n

**Особенности:**
- Inline keyboard для удобной навигации
- Мультиязычная поддержка
- Callback query handlers
- Быстрый доступ к основным функциям

---

### chat.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/bot/handlers/chat.py`

**Назначение:** Обработка текстовых сообщений пользователя (AI chat)

**Функции:**
- `handle_message(message: Message, session: AsyncSession, bot: Bot)` - Обработка текстовых сообщений с AI

**Зависимости:**
- Services: OpenAIService
- Database: chat history management
- Config: streaming settings

**Особенности:**
- Streaming responses (плавная анимация печатания)
- Сохранение контекста разговора (последние 5 сообщений)
- Умная маршрутизация моделей (gpt-4o / gpt-4o-mini)
- Cost tracking для каждого запроса
- Показ "typing..." индикатора

**Алгоритм:**
1. Получить сообщение пользователя
2. Показать "typing..." индикатор
3. Загрузить контекст из БД (последние 5 сообщений)
4. Выбрать модель (на основе сложности)
5. Стримить ответ от OpenAI
6. Обновлять сообщение каждые 30 символов
7. Сохранить в БД (user + assistant messages)
8. Записать cost tracking

---

### vision.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/bot/handlers/vision.py`

**Назначение:** Обработка фото (анализ графиков криптовалют)

**Функции:**
- `handle_photo(message: Message, session: AsyncSession, bot: Bot)` - Анализ графиков с Vision API

**Зависимости:**
- Services: OpenAIService (Vision), CoinGeckoService
- Utils: coin_parser, vision_tokens
- Database: cost tracking

**Особенности:**
- Автоматическое определение монеты на графике (Vision API)
- Получение актуальных данных из CoinGecko
- Объединение визуального анализа с рыночными данными
- Точный расчет токенов (image tokens + text tokens)
- Enhanced prompts с актуальными ценами

**Алгоритм:**
1. Скачать фото (bot.download_file)
2. Определить монету (Vision API с low detail для скорости)
3. Если монета найдена → получить данные из CoinGecko
4. Сформировать enhanced prompt с рыночными данными
5. Отправить на анализ (Vision API с high detail)
6. Стримить ответ пользователю
7. Записать cost tracking (включая image tokens)

---

### crypto.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/bot/handlers/crypto.py`

**Назначение:** Обработка команд для криптовалют

**Функции:**
- `cmd_price(message: Message)` - Показать цену монеты
- `cmd_analyze(message: Message, session: AsyncSession, bot: Bot)` - Полный анализ монеты
- `cmd_market(message: Message)` - Топ-10 монет по капитализации
- `cmd_news(message: Message)` - Последние новости по монете

**Зависимости:**
- Services: CoinGeckoService, CryptoPanicService, OpenAIService
- Utils: coin_parser
- Database: cost tracking

**Особенности:**
- Кэширование данных CoinGecko (60 сек)
- Кэширование новостей (5 мин)
- Форматированный вывод с эмодзи
- Интеграция с AI для аналитики

**Примеры команд:**
```
/price bitcoin
/analyze eth
/market
/news btc
```

---

## Services

### openai_service.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/services/openai_service.py`

**Класс:** `OpenAIService`

**Назначение:** Интеграция с OpenAI API (Text + Vision)

**Методы:**

#### Text API
- `count_tokens(text: str) -> int` - Подсчет токенов
- `select_model(user_message: str, history_tokens: int) -> str` - Выбор модели
- `get_context_messages(session, user_id, current_message, max_history=5)` - Формирование контекста
- `stream_completion(session, user_id, user_message, model=None)` - Streaming ответ
- `simple_completion(prompt, model, temperature)` - Простой запрос без streaming
- `calculate_cost(model, input_tokens, output_tokens) -> float` - Расчет стоимости

#### Vision API
- `encode_image(image_bytes: bytes) -> str` - Конвертация в base64
- `detect_coin_from_image(image_bytes) -> Optional[str]` - Определение монеты
- `stream_image_analysis(session, user_id, image_bytes, user_prompt, detail, market_data)` - Streaming анализ
- `analyze_image(session, user_id, image_bytes, user_prompt, detail, market_data)` - Анализ без streaming
- `calculate_vision_cost(input_tokens, output_tokens) -> float` - Расчет стоимости Vision

**Особенности:**
- Automatic retry с exponential backoff (3 попытки)
- Token counting с tiktoken
- Cost tracking в БД
- Умная маршрутизация (gpt-4o / gpt-4o-mini)
- Vision integration с market data

**Модели:**
- `gpt-4o` - сложные запросы (>500 tokens)
- `gpt-4o-mini` - простые запросы (<500 tokens)

---

### coingecko_service.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/services/coingecko_service.py`

**Класс:** `CoinGeckoService`

**Назначение:** Интеграция с CoinGecko API для получения данных о криптовалютах

**Методы:**
- `get_price(coin_id: str) -> Optional[dict]` - Получить цену монеты
- `get_market_data(coin_id: str) -> Optional[dict]` - Полные рыночные данные
- `get_top_coins(limit: int = 10) -> List[dict]` - Топ монет
- `search_coin(query: str) -> Optional[str]` - Поиск ID монеты по названию

**Особенности:**
- In-memory кэш с TTL 60 секунд (обязательно для rate limits)
- Обработка ошибок (KeyError, HTTPError)
- Автоматическая конвертация названий (BTC → bitcoin)
- Поддержка дополнительных данных (market cap, volume, change)

**Rate Limits:**
- Free tier: 10-15 calls/min
- Кэширование критично!

---

### cryptopanic_service.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/services/cryptopanic_service.py`

**Класс:** `CryptoPanicService`

**Назначение:** Интеграция с CryptoPanic API для новостей

**Методы:**
- `get_news(currencies: List[str], filter: str, limit: int) -> List[dict]` - Получить новости
- `format_news(news: List[dict]) -> str` - Форматирование для Telegram

**Особенности:**
- Кэширование с TTL 5 минут
- Фильтры: hot, rising, bullish, bearish, important
- Поддержка множества монет одновременно
- Показ sentiment (votes)

**Фильтры:**
- `rising` - растущие по популярности
- `hot` - горячие новости
- `bullish` - бычьи настроения
- `bearish` - медвежьи настроения
- `important` - важные новости

---

### crypto_tools.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/services/crypto_tools.py`

**Назначение:** Утилиты для работы с крипто-данными

**Функции:**
- `format_price(price: float) -> str` - Форматирование цены
- `format_percentage(percent: float) -> str` - Форматирование процентов
- `format_market_cap(mcap: float) -> str` - Форматирование капитализации
- `format_volume(volume: float) -> str` - Форматирование объемов

**Особенности:**
- Adaptive formatting (разные форматы для разных величин)
- Эмодзи для трендов (📈 📉)
- Human-readable numbers ($1.2B вместо $1,234,567,890)

---

### binance_service.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/services/binance_service.py`

**Класс:** `BinanceService`

**Назначение:** Интеграция с Binance API (Spot + Futures)

**Методы:**
- `get_ticker_24h(symbol: str)` - Получить 24h статистику тикера
- `get_orderbook_depth(symbol: str)` - Получить глубину стакана заявок
- `get_klines(symbol: str, interval: str)` - Получить OHLC данные
- `get_funding_rate(symbol: str, limit: int)` - История ставок финансирования (Futures)
- `get_latest_funding_rate(symbol: str)` - Текущая ставка финансирования
- `get_open_interest(symbol: str)` - Open Interest фьючерсов

**Особенности:**
- Дополняет данные CoinGecko
- Более точные цены и объемы
- Real-time данные
- **Funding Rates** - индикатор настроений трейдеров (положительный = bulls, отрицательный = bears)
- **Open Interest** - общий объем открытых позиций

---

### coinmetrics_service.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/services/coinmetrics_service.py`

**Класс:** `CoinMetricsService`

**Назначение:** On-chain метрики через CoinMetrics Community API

**Методы:**
- `get_asset_id(coin_id: str)` - Конвертация CoinGecko ID → CoinMetrics ID
- `get_asset_metrics(asset: str, metrics: List[str])` - Получить метрики
- `get_network_health(asset: str)` - Здоровье сети (активные адреса, транзакции)
- `get_exchange_flows(asset: str)` - Потоки с/на биржи (inflow/outflow)

**Метрики:**
- `AdrActCnt` - Активные адреса (24h)
- `TxCnt` - Количество транзакций (24h)
- `FlowInExNtv` / `FlowOutExNtv` - Потоки с бирж
- `HashRate` - Хешрейт сети (для PoW)

**Особенности:**
- **БЕСПЛАТНЫЙ API** (Community endpoint)
- Rate limit: 10 req/6sec
- Автоматический retry с exponential backoff
- Exchange flows sentiment (inflow = bearish, outflow = bullish)

**Поддерживаемые активы:**
- Bitcoin (btc), Ethereum (eth), Solana (sol), Cardano (ada), XRP (xrp), и др.

---

### cycle_analysis_service.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/services/cycle_analysis_service.py`

**Класс:** `CycleAnalysisService`

**Назначение:** Анализ рыночных циклов криптовалют

**Методы:**
- `calculate_days_since_genesis(date: datetime)` - Дни с Genesis Block Bitcoin
- `calculate_rainbow_price(days: int, band: str)` - Расчет цены для Rainbow Chart
- `get_rainbow_chart_data(current_price: float)` - Полные данные Rainbow Chart
- `determine_current_band(price: float, bands: dict)` - Определение текущего band
- `get_sentiment_from_band(band: str)` - Sentiment по band
- `calculate_pi_cycle_top(prices_df: DataFrame)` - Pi Cycle Top индикатор
- `calculate_200_week_ma(prices_df: DataFrame)` - 200 Week MA
- `detect_market_cycle_phase(...)` - Определение фазы цикла

**Rainbow Chart Bands:**
- `maximum_bubble` 🔴 - Экстремальная жадность (продавать)
- `sell` 🟠 - Зона продажи
- `fomo_intensifies` 🟡 - FOMO зона
- `hodl` 🔵 - Справедливая цена (центральная линия)
- `buy` 🟢 - Зона покупки
- `basically_a_fire_sale` 🟢 - Огненная распродажа

**Индикаторы:**
- **Rainbow Chart** - Логарифмическая регрессия цены BTC (формула Bitbo 2025)
- **Pi Cycle Top** - MA 111 / MA 350*2 кроссовер (сигнал вершины рынка)
- **200 Week MA** - Долгосрочный floor цены Bitcoin

**Фазы цикла:**
- `accumulation` 🟢 - Накопление (хорошее время для покупки)
- `markup` 🔵 - Рост (бычий рынок)
- `distribution` 🟡 - Распределение (близко к вершине)
- `markdown` 🔴 - Падение (медвежий рынок)

**Особенности:**
- Только для Bitcoin (Rainbow Chart)
- Основано на исторических данных с 2009 года
- Высокая точность определения топов/дна рынка

---

### historical_data_service.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/services/historical_data_service.py`

**Класс:** `HistoricalDataService`

**Назначение:** Управление историческими данными цен

**Методы:**
- `fetch_and_store_historical(session, coin_id: str, days: int)` - Загрузить OHLC
- `get_price_at_time(session, coin_id: str, days_ago: int)` - Цена X дней назад
- `get_price_change_since(session, coin_id: str, days_ago: int)` - Изменение цены

**Особенности:**
- Сохранение исторических данных в PostgreSQL
- Быстрые запросы для анализа трендов
- Сравнение текущей цены с прошлой

---

### analytics_aggregator.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/services/analytics_aggregator.py`

**Класс:** `AnalyticsAggregator`

**Назначение:** Сбор всей доступной аналитики в одном месте

**Методы:**
- `get_full_analytics(coin_id: str)` - Собрать ВСЮ доступную аналитику

**Источники данных:**
1. CoinGecko - базовые цены и market data
2. Binance Futures - funding rates, open interest
3. CoinMetrics - on-chain метрики
4. Cycle Analysis - Rainbow Chart (для Bitcoin)
5. Fear & Greed Index

**Особенности:**
- Параллельный сбор данных (asyncio.gather)
- Graceful degradation (если один источник недоступен, продолжаем)
- Форматированный summary для AI

---

### fear_greed_service.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/services/fear_greed_service.py`

**Класс:** `FearGreedService`

**Назначение:** Получение индекса страха и жадности

**Методы:**
- `get_fear_greed_index()` - Получить текущий Fear & Greed Index
- `format_fear_greed(data: dict)` - Форматирование для отображения

**Особенности:**
- Индикатор настроений крипторынка
- Значения от 0 (Extreme Fear) до 100 (Extreme Greed)
- Кэширование на 1 час
- Исторические данные

---

### technical_indicators.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/services/technical_indicators.py`

**Назначение:** Расчет технических индикаторов

**Функции:**
- `calculate_rsi(prices: list, period: int = 14) -> float` - RSI индикатор
- `calculate_macd(prices: list)` - MACD индикатор
- `calculate_bollinger_bands(prices: list, period: int = 20)` - Bollinger Bands
- `calculate_sma(prices: list, period: int)` - Simple Moving Average
- `calculate_ema(prices: list, period: int)` - Exponential Moving Average

**Особенности:**
- Профессиональные TA индикаторы
- Используется библиотека `ta`
- Работа с pandas DataFrame
- Точные математические расчеты

---

### candlestick_patterns.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/services/candlestick_patterns.py`

**Назначение:** Определение свечных паттернов

**Функции:**
- `is_doji(candle: dict) -> bool` - Паттерн Doji
- `is_hammer(candle: dict) -> bool` - Паттерн Hammer
- `is_shooting_star(candle: dict) -> bool` - Паттерн Shooting Star
- `is_engulfing(prev: dict, curr: dict) -> str` - Bullish/Bearish Engulfing
- `is_morning_star(candles: list) -> bool` - Morning Star
- `is_evening_star(candles: list) -> bool` - Evening Star

**Особенности:**
- Определение классических свечных паттернов
- Бычьи и медвежьи сигналы
- Математическая валидация паттернов
- Возврат уверенности (confidence score)

---

### retention_service.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/services/retention_service.py`

**Класс:** `RetentionService`

**Назначение:** Воронка удержания пользователей

**Функции:**
- `start_retention_service(bot: Bot)` - Запуск retention scheduler
- `stop_retention_service()` - Остановка scheduler
- `send_retention_message(user_id: int, message_type: str)` - Отправка сообщения
- `process_unsubscribed_users()` - Обработка неподписанных пользователей

**Особенности:**
- APScheduler для планирования
- Автоматические рассылки через 1 час, 24 часа, 7 дней
- Персонализированные сообщения
- Отслеживание конверсии
- Мягкие напоминания о подписке

---

## Middleware

### database.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/bot/middleware/database.py`

**Класс:** `DatabaseMiddleware`

**Назначение:** Инжекция DB session в handlers

**Механизм:**
```python
async def __call__(self, handler, event, data):
    async with AsyncSessionLocal() as session:
        data['session'] = session
        return await handler(event, data)
```

**Особенности:**
- Автоматическое создание и закрытие сессии
- Session доступна в handlers через параметр
- Connection pooling управляется engine

---

### subscription.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/bot/middleware/subscription.py`

**Класс:** `SubscriptionMiddleware`

**Назначение:** Проверка подписки на канал

**Алгоритм:**
1. Получить user_id
2. Проверить через bot.get_chat_member(REQUIRED_CHANNEL, user_id)
3. Проверить статус: CREATOR, ADMINISTRATOR, MEMBER = OK
4. Если не подписан → показать inline кнопку "Подписаться"
5. Обновить is_subscribed в БД

**Особенности:**
- Inline keyboard с кнопкой подписки
- Callback handler для проверки после подписки
- Обновление статуса в БД
- Пропускает команды /start и /help

**Требования:**
- Бот должен быть администратором канала
- REQUIRED_CHANNEL должен быть настроен

---

### request_limit.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/bot/middleware/request_limit.py`

**Класс:** `RequestLimitMiddleware`

**Назначение:** Контроль лимита 5 запросов/день

**Алгоритм:**
1. Получить текущую дату
2. Найти RequestLimit для user + date
3. Если count >= limit → блокировать
4. Иначе → increment count и пропустить
5. Создать новую запись если нет (первый запрос дня)

**Особенности:**
- Автоматический сброс в 00:00 UTC (новая дата = новая запись)
- Показ оставшихся запросов
- Информирование об обновлении
- Пропускает команды /start, /help

**Лимиты:**
- Default: 5 запросов/день
- Настраивается через REQUEST_LIMIT_PER_DAY
- Для админов (ADMIN_IDS) - без лимитов

---

### logging.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/bot/middleware/logging.py`

**Класс:** `LoggingMiddleware`

**Назначение:** Логирование всех запросов

**Что логируется:**
- User ID и username
- Тип события (message, callback_query)
- Текст сообщения
- Timestamp
- Обработка успешна/ошибка

**Особенности:**
- Structured logging
- Сохранение в файл logs/bot.log
- Опционально сохранение в AdminLog (БД)

---

### admin.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/bot/middleware/admin.py`

**Класс:** `AdminMiddleware`

**Назначение:** Проверка прав администратора

**Алгоритм:**
1. Получить user_id из события
2. Проверить наличие в ADMIN_IDS
3. Добавить флаг is_admin в data

**Особенности:**
- Проверка перед выполнением handler
- Флаг is_admin доступен в handlers
- Используется для доступа к админ-командам
- Не блокирует обычные команды

---

### language.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/bot/middleware/language.py`

**Класс:** `LanguageMiddleware`

**Назначение:** Определение языка пользователя

**Алгоритм:**
1. Получить user_id
2. Загрузить язык из БД (поле language)
3. Если не установлен - использовать language_code из Telegram
4. Fallback на 'ru' если не определен
5. Добавить language в data

**Особенности:**
- Автоматическое определение языка
- Сохранение выбора пользователя в БД
- Поддержка RU/EN
- Используется для локализации ответов
- Интеграция с i18n системой

---

## Database

### models.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/database/models.py`

**Модели:**

#### User
```python
class User(Base):
    id: int (PK)
    telegram_id: int (unique, indexed)
    username: str (nullable)
    first_name: str (nullable)
    last_name: str (nullable)
    created_at: datetime
    is_subscribed: bool (default False)
    last_activity: datetime (auto-update)
    is_admin: bool (default False)
```

#### ChatHistory
```python
class ChatHistory(Base):
    id: int (PK)
    user_id: int (FK → users.id)
    role: str (user, assistant, system)
    content: text
    timestamp: datetime (indexed)
    tokens_used: int (nullable)
    model: str (nullable)
```

#### RequestLimit
```python
class RequestLimit(Base):
    id: int (PK)
    user_id: int (FK → users.id)
    date: date (indexed)
    count: int (default 0)
    limit: int (default 5)

    # Unique constraint: (user_id, date)
```

#### CostTracking
```python
class CostTracking(Base):
    id: int (PK)
    user_id: int (FK → users.id)
    service: str (indexed) # openai, openai_vision
    model: str (nullable)
    tokens: int
    cost: float
    timestamp: datetime (indexed)
    request_type: str (nullable) # chat, vision, price
```

#### AdminLog
```python
class AdminLog(Base):
    id: int (PK)
    admin_id: int (indexed)
    action: str (indexed)
    target_user_id: int (indexed, nullable)
    timestamp: datetime (indexed)
    details: text (nullable)
    success: bool (default True)
```

---

### crud.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/database/crud.py`

**Функции:**

#### User operations
- `get_or_create_user(session, telegram_id, username, first_name, last_name) -> User`
- `get_user_by_telegram_id(session, telegram_id) -> Optional[User]`
- `update_user_subscription(session, telegram_id, is_subscribed) -> bool`
- `update_last_activity(session, telegram_id) -> bool`

#### Chat history
- `add_chat_message(session, user_id, role, content, tokens=None, model=None) -> ChatHistory`
- `get_chat_history(session, user_id, limit=10) -> List[ChatHistory]`
- `clear_chat_history(session, user_id) -> int`

#### Request limits
- `get_request_limit(session, user_id) -> Optional[RequestLimit]`
- `increment_request_count(session, user_id) -> RequestLimit`
- `is_limit_exceeded(session, user_id) -> bool`

#### Cost tracking
- `track_cost(session, user_id, service, model, input_tokens, output_tokens, cost, request_type=None) -> CostTracking`
- `get_user_costs(session, user_id, days=30) -> List[CostTracking]`
- `get_daily_costs(session, date) -> List[dict]`

#### Admin logs
- `log_admin_action(session, admin_id, action, target_user_id=None, details=None, success=True) -> AdminLog`

---

### engine.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/database/engine.py`

**Назначение:** Настройка async engine и session maker

**Функции:**
- `init_db()` - Инициализация БД (создание таблиц)
- `dispose_engine()` - Закрытие connections

**Настройки:**
```python
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # True для DEBUG
    pool_size=5,
    max_overflow=10
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)
```

---

## Config

### config.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/config/config.py`

**Переменные:**
- `BOT_TOKEN` - Telegram bot token
- `REQUIRED_CHANNEL` - Канал для подписки
- `ADMIN_IDS` - List админов
- `DATABASE_URL` - PostgreSQL URL
- `OPENAI_API_KEY` - OpenAI API key
- `CRYPTOPANIC_TOKEN` - CryptoPanic token
- `REQUEST_LIMIT_PER_DAY` - Лимит запросов (default: 5)
- `ENVIRONMENT` - development / production
- `LOG_LEVEL` - INFO / DEBUG / WARNING

**Классы конфигурации:**
- `ModelConfig` - Настройки AI моделей
- `RateLimits` - Rate limits для API
- `Pricing` - Цены на API (для cost tracking)

---

### prompts.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/config/prompts.py`

**Содержимое:**
- `SYNTRA_SYSTEM_PROMPT` - Детальная персона Syntra с адаптивным сарказмом

**Особенности:**
- Саркастичный, но профессиональный тон
- Ирония к человеческим слабостям (FOMO, FUD)
- Краткость (макс 300 слов)
- Сбалансированный анализ (показывает обе стороны)

---

### vision_prompts.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/config/vision_prompts.py`

**Промпты:**
- `COIN_DETECTION_PROMPT` - Определение монеты на графике
- `BASIC_ANALYSIS_PROMPT` - Базовый анализ без market data
- `get_enhanced_analysis_prompt(coin, price, change, volume, mcap)` - Enhanced с данными

---

### logging.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/config/logging.py`

**Функции:**
- `setup_logging(level='INFO')` - Настройка логирования

**Настройки:**
- Формат: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Handlers: FileHandler + StreamHandler
- Файлы: logs/bot.log, logs/error.log

---

### sentry.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/config/sentry.py`

**Функции:**
- `init_sentry()` - Инициализация Sentry для error tracking

**Особенности:**
- Только в production (ENVIRONMENT=production)
- Traces sample rate: 1.0
- Profiles sample rate: 1.0

---

## Utils

### vision_tokens.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/utils/vision_tokens.py`

**Функции:**
- `calculate_image_tokens(image_bytes, detail='high') -> int` - Точный расчет токенов
- `estimate_vision_cost(image_bytes, detail, text_tokens) -> float` - Оценка стоимости

**Алгоритм (по документации OpenAI):**

**Low detail:**
- Fixed: 85 tokens

**High detail:**
1. Scale to 2048x2048 (сохраняя aspect ratio)
2. Scale shortest side to 768px
3. Divide into 512x512 tiles
4. Base tile: 85 tokens
5. Each tile: 170 tokens
6. Formula: `85 + (170 * num_tiles)`

---

### coin_parser.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/utils/coin_parser.py`

**Функции:**
- `parse_coin_name(text: str) -> Optional[str]` - Извлечение названия монеты из текста
- `normalize_coin_id(coin: str) -> str` - Нормализация (BTC → bitcoin)

**Mapping:**
```python
{
    'btc': 'bitcoin',
    'eth': 'ethereum',
    'sol': 'solana',
    'ada': 'cardano',
    # ... и т.д.
}
```

---

### i18n.py
**Путь:** `/Users/a1/Projects/Syntra Trade Consultant/src/utils/i18n.py`

**Функции:**
- `load_locale(language: str) -> dict` - Загрузка языковых файлов
- `get_text(language: str, key: str, **kwargs) -> str` - Получение локализованного текста
- `format_text(template: str, **kwargs) -> str` - Форматирование с подстановкой

**Особенности:**
- Загрузка из JSON файлов (locales/ru.json, locales/en.json)
- Поддержка плейсхолдеров {variable}
- Fallback на русский язык если ключ не найден
- Кэширование загруженных локалей

**Локали:**
- `ru.json` - Русский язык
- `en.json` - Английский язык

**Пример использования:**
```python
# Загрузка текста
text = get_text('ru', 'welcome_message', name='Пользователь')

# Форматирование
formatted = format_text('Привет, {name}!', name='Ivan')
```

---

Это полный справочник по всем компонентам системы Syntra Trade Consultant. Для детальной информации обращайтесь к исходному коду компонентов.
