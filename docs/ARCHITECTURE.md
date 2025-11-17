# ARCHITECTURE - Syntra Trade Consultant

> Архитектурная документация проекта

## Содержание
- [Общий обзор](#общий-обзор)
- [Компоненты системы](#компоненты-системы)
- [База данных](#база-данных)
- [Поток данных](#поток-данных)
- [Интеграции](#интеграции)
- [Безопасность](#безопасность)

---

## Общий обзор

### Архитектурный паттерн

Проект использует **многоуровневую архитектуру** с четким разделением ответственности:

```
┌─────────────────────────────────────────────────────┐
│                   Telegram Bot API                  │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│                  aiogram 3.x Layer                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │   Handlers   │  │  Middleware  │  │  Routers  │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│                  Service Layer                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│
│  │  OpenAI  │ │ Together │ │CoinGecko │ │  CRUD  ││
│  └──────────┘ └──────────┘ └──────────┘ └────────┘│
└────────────────────┬────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌────────────────────┐  ┌────────────────────┐
│  External APIs     │  │   PostgreSQL DB    │
│  - OpenAI          │  │   - Users          │
│  - Together        │  │   - Chat History   │
│  - CoinGecko       │  │   - Request Limits │
│  - CryptoPanic     │  │   - Cost Tracking  │
└────────────────────┘  └────────────────────┘
```

### Основные принципы

1. **Separation of Concerns** - каждый слой выполняет свою задачу
2. **Dependency Injection** - зависимости инжектятся через middleware
3. **Async First** - все операции I/O асинхронные
4. **Error Resilience** - retry logic, fallback механизмы
5. **Cost Optimization** - кэширование, роутинг моделей

---

## Компоненты системы

### 1. Presentation Layer (Handlers)

**Ответственность:**
- Обработка команд пользователя
- Валидация ввода
- Форматирование ответов
- Управление состояниями (FSM)

**Компоненты:**
- `handlers/start.py` - /start команда, приветствие
- `handlers/help_cmd.py` - /help команда, справка
- `handlers/limits.py` - /limits команда, проверка лимитов
- `handlers/chat.py` - AI-чат с контекстом
- `handlers/crypto.py` - /price, /analyze, /market, /news
- `handlers/vision.py` - анализ графиков (Vision API)
- `handlers/menu.py` - интерактивное меню навигации
- `handlers/admin.py` - админ-панель (/admin, /admin_stats, /admin_users, /admin_costs)

**Пример:**
```python
@router.message(Command("price"))
async def cmd_price(
    message: Message,
    session: AsyncSession  # Injected by middleware
):
    # 1. Validate input
    coin_id = extract_coin_id(message.text)

    # 2. Call service
    price = await coingecko_service.get_price(coin_id)

    # 3. Format and respond
    await message.answer(format_price_response(price))
```

### 2. Middleware Layer

**Ответственность:**
- Инжекция зависимостей
- Аутентификация и авторизация
- Логирование
- Контроль лимитов

**Компоненты:**

#### DatabaseMiddleware
```python
class DatabaseMiddleware(BaseMiddleware):
    """Инжектит DB session в каждый handler"""
    async def __call__(self, handler, event, data):
        async with AsyncSessionLocal() as session:
            data['session'] = session
            return await handler(event, data)
```

#### SubscriptionMiddleware
```python
class SubscriptionMiddleware(BaseMiddleware):
    """Проверяет подписку на канал"""
    async def __call__(self, handler, event, data):
        if not await check_subscription(event.from_user.id):
            await event.answer("❌ Подпишитесь на канал")
            return
        return await handler(event, data)
```

#### RequestLimitMiddleware
```python
class RequestLimitMiddleware(BaseMiddleware):
    """Контролирует лимит 5 запросов/день"""
    async def __call__(self, handler, event, data):
        session: AsyncSession = data['session']
        user_id = event.from_user.id

        # Check limit
        if await is_limit_exceeded(session, user_id):
            await event.answer("❌ Лимит запросов исчерпан")
            return

        # Increment counter
        await increment_request_count(session, user_id)

        return await handler(event, data)
```

#### AdminMiddleware
```python
class AdminMiddleware(BaseMiddleware):
    """Проверка прав администратора"""
    async def __call__(self, handler, event, data):
        from config.config import ADMIN_IDS

        user_id = event.from_user.id
        data['is_admin'] = user_id in ADMIN_IDS

        return await handler(event, data)
```

#### LanguageMiddleware
```python
class LanguageMiddleware(BaseMiddleware):
    """Определение языка пользователя"""
    async def __call__(self, handler, event, data):
        session: AsyncSession = data['session']
        user_id = event.from_user.id

        # Получить язык пользователя из БД или language_code из Telegram
        user = await get_user_by_telegram_id(session, user_id)
        language = user.language if user and user.language else 'ru'

        # Добавляем в data для использования в handlers
        data['language'] = language

        return await handler(event, data)
```

### 3. Service Layer

**Ответственность:**
- Бизнес-логика
- Интеграция с внешними API
- Обработка ошибок
- Кэширование

**Компоненты:**

#### OpenAI Service
```python
class OpenAIService:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    @retry(wait=wait_exponential(min=1, max=60))
    async def get_completion(
        self,
        messages: list,
        stream: bool = False
    ):
        """Получить ответ от GPT с retry logic"""
        # Model routing
        model = self._select_model(messages)

        return await self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=stream
        )

    def _select_model(self, messages: list) -> str:
        """Роутинг: gpt-4o для сложных, gpt-4o-mini для простых"""
        total_tokens = sum(count_tokens(m['content']) for m in messages)
        # Оптимизированный порог: 1500 токенов (экономия 25-35%)
        return "gpt-4o" if total_tokens > 1500 else "gpt-4o-mini"
```

#### CoinGecko Service
```python
class CoinGeckoService:
    def __init__(self):
        self.cg = CoinGeckoAPI()
        self.cache = SimpleCache(ttl_seconds=60)

    async def get_price(self, coin_id: str):
        """Получить цену с кэшированием"""
        cached = self.cache.get(f'price_{coin_id}')
        if cached:
            return cached

        price = await self._fetch_price(coin_id)
        self.cache.set(f'price_{coin_id}', price)
        return price
```

#### Binance Service
```python
class BinanceService:
    """Дополнительные данные от Binance API для точных цен и объемов"""
    async def get_ticker_24h(self, symbol: str):
        """Получить 24h статистику тикера"""
        pass

    async def get_klines(self, symbol: str, interval: str):
        """Получить данные свечей для TA"""
        pass
```

#### Technical Indicators
```python
class TechnicalIndicators:
    """Расчет технических индикаторов"""
    @staticmethod
    def calculate_rsi(prices: list, period: int = 14) -> float:
        """Relative Strength Index"""
        pass

    @staticmethod
    def calculate_macd(prices: list):
        """MACD индикатор"""
        pass

    @staticmethod
    def calculate_bollinger_bands(prices: list, period: int = 20):
        """Bollinger Bands"""
        pass

    @staticmethod
    def calculate_ema(prices: list, period: int) -> float:
        """Exponential Moving Average"""
        pass
```

#### Candlestick Patterns
```python
class CandlestickPatterns:
    """Определение свечных паттернов"""
    @staticmethod
    def is_doji(candle: dict) -> bool:
        """Проверка паттерна Doji"""
        pass

    @staticmethod
    def is_hammer(candle: dict) -> bool:
        """Проверка паттерна Hammer"""
        pass

    @staticmethod
    def is_engulfing(prev_candle: dict, curr_candle: dict) -> str:
        """Проверка паттернов Bullish/Bearish Engulfing"""
        pass
```

#### Retention Service
```python
class RetentionService:
    """Воронка удержания пользователей"""
    async def start_retention_service(self, bot: Bot):
        """Запуск retention scheduler"""
        pass

    async def send_retention_message(self, user_id: int, message_type: str):
        """Отправка retention сообщения"""
        pass

    async def process_unsubscribed_users(self):
        """Обработка неподписанных пользователей"""
        pass
```

#### Fear & Greed Service
```python
class FearGreedService:
    """Получение индекса страха и жадности"""
    async def get_fear_greed_index(self):
        """Получить текущий Fear & Greed Index"""
        pass
```

#### CryptoPanic Service
```python
class CryptoPanicService:
    """Криптовалютные новости"""
    async def get_news(self, currencies: list, filter_type: str):
        """Получить новости по монетам"""
        pass

    async def format_news_for_telegram(self, news: list) -> str:
        """Форматирование новостей для Telegram"""
        pass
```

### 4. Data Layer

**Ответственность:**
- CRUD операции
- Работа с БД
- Транзакции

**Компоненты:**
```python
# database/crud.py
async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str = None
) -> User:
    """Get existing user or create new"""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return user
```

---

## База данных

### ER-диаграмма

```
┌────────────────────┐
│       users        │
├────────────────────┤
│ id (PK)            │
│ telegram_id (UQ)   │◄─────┐
│ username           │      │
│ created_at         │      │
│ is_subscribed      │      │
│ last_activity      │      │
└────────────────────┘      │
                            │
                            │
┌────────────────────┐      │
│   chat_history     │      │
├────────────────────┤      │
│ id (PK)            │      │
│ user_id (FK) ──────┼──────┘
│ role               │
│ content            │
│ timestamp          │
│ tokens_used        │
└────────────────────┘

┌────────────────────┐      ┌────────────────────┐
│  request_limits    │      │   cost_tracking    │
├────────────────────┤      ├────────────────────┤
│ id (PK)            │      │ id (PK)            │
│ user_id (FK) ──────┼──┐   │ user_id (FK) ──────┼──┐
│ date               │  │   │ service            │  │
│ count              │  │   │ tokens             │  │
│ limit              │  │   │ cost               │  │
└────────────────────┘  │   │ timestamp          │  │
                        │   └────────────────────┘  │
                        │                           │
                        └───────────┬───────────────┘
                                    │
                         ┌──────────▼─────────┐
                         │       users        │
                         └────────────────────┘
```

### Модели SQLAlchemy

```python
class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        index=True
    )
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    is_subscribed: Mapped[bool] = mapped_column(default=False)
    last_activity: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    chat_history = relationship("ChatHistory", back_populates="user")
    request_limits = relationship("RequestLimit", back_populates="user")
    cost_tracking = relationship("CostTracking", back_populates="user")


class ChatHistory(Base):
    __tablename__ = 'chat_history'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey('users.id'),
        index=True
    )
    role: Mapped[str] = mapped_column(String(50))  # user, assistant, system
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=True)

    # Relationship
    user = relationship("User", back_populates="chat_history")


class RequestLimit(Base):
    __tablename__ = 'request_limits'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey('users.id'),
        index=True
    )
    date: Mapped[date] = mapped_column(Date, default=date.today)
    count: Mapped[int] = mapped_column(Integer, default=0)
    limit: Mapped[int] = mapped_column(Integer, default=5)

    # Relationship
    user = relationship("User", back_populates="request_limits")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='uix_user_date'),
    )


class CostTracking(Base):
    __tablename__ = 'cost_tracking'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey('users.id'),
        index=True
    )
    service: Mapped[str] = mapped_column(String(50))  # openai, together
    tokens: Mapped[int] = mapped_column(Integer)
    cost: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    # Relationship
    user = relationship("User", back_populates="cost_tracking")


class AdminLog(Base):
    __tablename__ = 'admin_logs'

    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(100))
    target_user_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    details: Mapped[str] = mapped_column(Text, nullable=True)
```

### Индексы

```sql
-- Автоматически созданные через mapped_column(index=True)
CREATE INDEX ix_users_telegram_id ON users(telegram_id);
CREATE INDEX ix_chat_history_user_id ON chat_history(user_id);
CREATE INDEX ix_request_limits_user_id ON request_limits(user_id);
CREATE INDEX ix_cost_tracking_user_id ON cost_tracking(user_id);

-- Дополнительные индексы (через миграции)
CREATE INDEX ix_chat_history_timestamp ON chat_history(timestamp DESC);
CREATE INDEX ix_request_limits_date ON request_limits(date);
CREATE INDEX ix_cost_tracking_service ON cost_tracking(service);
```

---

## Поток данных

### 1. Обработка AI-запроса

```
┌──────────┐
│  User    │ /analyze bitcoin
└────┬─────┘
     │
     ▼
┌──────────────────────────────────┐
│  Telegram Bot API                │
└────┬─────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│  aiogram Dispatcher              │
│  - Update routing                │
└────┬─────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│  Middleware Chain                │
│  1. DatabaseMiddleware           │  ← Inject DB session
│  2. SubscriptionMiddleware       │  ← Check subscription
│  3. RequestLimitMiddleware       │  ← Check & increment limit
│  4. LoggingMiddleware            │  ← Log request
└────┬─────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│  Handler: cmd_analyze            │
│  1. Extract coin_id from message │
│  2. Fetch price (CoinGecko)      │
│  3. Fetch news (CryptoPanic)     │
│  4. Form AI prompt               │
│  5. Call OpenAI (streaming)      │
│  6. Save to ChatHistory          │
│  7. Track costs                  │
└────┬─────────────────────────────┘
     │
     ├──────────────┐
     │              │
     ▼              ▼
┌─────────────┐  ┌─────────────┐
│  CoinGecko  │  │  OpenAI     │
│  Service    │  │  Service    │
│  - Cache    │  │  - Stream   │
│  - Retry    │  │  - Retry    │
└─────────────┘  └────┬────────┘
                      │
                      ▼
            ┌──────────────────┐
            │  Streaming       │
            │  Response        │
            │  to User         │
            └──────────────────┘
```

### 2. Vision Analysis (График)

```
┌──────────┐
│  User    │ [Sends photo]
└────┬─────┘
     │
     ▼
┌──────────────────────────────────┐
│  Handler: handle_photo           │
│  1. Download photo (bot.download)│
│  2. Convert to base64            │
│  3. Send to Together API         │
│  4. Parse vision response        │
│  5. Format TA output             │
│  6. Save to DB                   │
└────┬─────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│  Together Service (Qwen 2.5 VL)  │
│  - Vision analysis               │
│  - Pattern recognition           │
│  - Support/Resistance levels     │
└────┬─────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│  Response to User                │
│  📊 Технический анализ:          │
│  - Тренд: восходящий             │
│  - Поддержка: $44,000            │
│  - Сопротивление: $48,000        │
└──────────────────────────────────┘
```

### 3. Воронка удержания

```
┌──────────────────────────────────┐
│  APScheduler                     │
│  - Runs every hour               │
└────┬─────────────────────────────┘
     │
     ▼
┌──────────────────────────────────┐
│  Retention Service               │
│  1. Query unsubscribed users     │
│  2. Check time since /start      │
│  3. Select message template      │
└────┬─────────────────────────────┘
     │
     ├─────────┬─────────┬──────────┐
     ▼         ▼         ▼          ▼
   1 hour   24 hours  7 days   14 days
   "Привет! "Скучаем" "Что-то  "Последний
    Попробуй          случилось? шанс!"
    бота!"            Вернись!"
```

---

## Интеграции

### OpenAI API

**Endpoint:** `https://api.openai.com/v1/chat/completions`

**Модели:**
- `gpt-4o` - сложные запросы (>500 токенов в промпте)
- `gpt-4o-mini` - простые запросы

**Rate Limits:**
- Зависит от tier (500K-10M TPM)
- Retry с exponential backoff

**Cost Optimization:**
- Роутинг моделей по сложности
- Кэширование однотипных запросов (не используется, т.к. запросы уникальны)
- Ограничение max_tokens
- Суммаризация длинных контекстов

### Together API

**Endpoint:** `https://api.together.xyz/v1/chat/completions`

**Модель:**
- `Qwen/Qwen2-VL-72B-Instruct` (или аналог)

**Использование:**
- Vision analysis (анализ графиков)
- Распознавание паттернов
- OCR текста на графике

### CoinGecko API

**Endpoint:** `https://api.coingecko.com/api/v3/`

**Endpoints:**
- `/simple/price` - текущая цена
- `/coins/{id}/ohlc` - OHLC для TA
- `/coins/markets` - топ монет

**Rate Limits:**
- Free: 5-15 calls/min
- **MUST CACHE** (60 секунд TTL)

### CryptoPanic API

**Endpoint:** `https://cryptopanic.com/api/v1/posts/`

**Parameters:**
- `currencies` - фильтр по монетам (BTC, ETH)
- `filter` - hot, rising, bullish, bearish

**Кэширование:**
- 5 минут TTL

---

## Безопасность

### 1. Переменные окружения

```python
# ❌ НЕ ДЕЛАЙТЕ ТАК
OPENAI_API_KEY = "sk-1234567890..."

# ✅ ПРАВИЛЬНО
from dotenv import load_dotenv
import os

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
```

### 2. SQL Injection Protection

SQLAlchemy автоматически экранирует параметры:

```python
# ✅ Безопасно
stmt = select(User).where(User.username == user_input)

# ❌ НЕ ИСПОЛЬЗУЙТЕ RAW SQL с user input
# query = f"SELECT * FROM users WHERE username = '{user_input}'"
```

### 3. Rate Limiting

```python
# Защита от спама
@router.message(Command("analyze"))
@rate_limit(max_calls=5, period=60)  # 5 calls per minute
async def cmd_analyze(message: Message):
    ...
```

### 4. Admin Authorization

```python
ADMIN_IDS = [123456789, 987654321]

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(Command("admin_stats"))
async def cmd_admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return
    # Admin logic...
```

### 5. Data Sanitization

```python
from html import escape

async def safe_answer(message: Message, text: str):
    # Escape HTML entities
    safe_text = escape(text)
    await message.answer(safe_text)
```

---

## Масштабирование

### Горизонтальное масштабирование

**Проблема:** aiogram использует long polling - нельзя запустить несколько инстансов

**Решение:**
1. **Webhooks** вместо polling
2. **Load Balancer** (nginx) для распределения запросов
3. **Redis** для shared state (FSM storage)

```python
# Webhook mode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Webhook URL
    WEBHOOK_URL = "https://yourdomain.com/webhook"

    # Start webhook
    await bot.set_webhook(WEBHOOK_URL)

    # aiohttp app
    app = web.Application()
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot
    ).register(app, path="/webhook")

    web.run_app(app, host="0.0.0.0", port=8000)
```

### Database Scaling

**Connection Pooling:**
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,  # Увеличить для prod
    max_overflow=40
)
```

**Read Replicas** (для высокой нагрузки):
```python
# Master для записи
write_engine = create_async_engine(WRITE_DB_URL)

# Replica для чтения
read_engine = create_async_engine(READ_DB_URL)
```

### Caching Strategy

```
┌──────────────┐
│   Request    │
└──────┬───────┘
       │
       ▼
 ┌─────────────┐
 │ Redis Cache │ ← L1 Cache (shared)
 └─────┬───────┘
       │ miss
       ▼
┌──────────────┐
│ In-Memory    │ ← L2 Cache (per-instance)
└──────┬───────┘
       │ miss
       ▼
┌──────────────┐
│ External API │
└──────────────┘
```

---

## Диаграмма деплоя

```
┌────────────────────────────────────────────────┐
│                   Internet                     │
└──────────────────┬─────────────────────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │   Telegram Servers   │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │   nginx (optional)   │ ← Webhook mode
        └──────────┬───────────┘
                   │
        ┌──────────┴───────────┐
        │                      │
        ▼                      ▼
┌──────────────┐      ┌──────────────┐
│  Bot         │      │  Bot         │
│  Instance 1  │      │  Instance 2  │ ← Horizontal scaling
└───┬──────────┘      └───┬──────────┘
    │                     │
    └──────────┬──────────┘
               │
    ┌──────────┴──────────┐
    │                     │
    ▼                     ▼
┌─────────┐         ┌──────────┐
│ Postgres│         │  Redis   │
└─────────┘         └──────────┘
```

---

## Мониторинг и логирование

### Логи

```
logs/
├── bot.log          # Основные логи
├── error.log        # Только ошибки
└── access.log       # Access logs (webhook mode)
```

### Метрики

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

# Counters
requests_total = Counter(
    'bot_requests_total',
    'Total requests',
    ['command', 'status']
)

# Histogram
response_time = Histogram(
    'bot_response_seconds',
    'Response time'
)

# Gauge
active_users = Gauge(
    'bot_active_users',
    'Active users in last 24h'
)
```

---

## Заключение

Архитектура спроектирована с учетом:
- ✅ Масштабируемости
- ✅ Надежности (retry, fallback)
- ✅ Экономичности (кэширование, роутинг)
- ✅ Поддерживаемости (чистая архитектура)
- ✅ Безопасности (env vars, SQL injection protection)
