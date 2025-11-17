# DEVELOPMENT GUIDE - Syntra Trade Consultant

> Руководство по разработке и best practices для проекта

## Содержание
- [Технологический стек](#технологический-стек)
- [Структура проекта](#структура-проекта)
- [Настройка окружения](#настройка-окружения)
- [Best Practices](#best-practices)
- [Работа с API](#работа-с-api)
- [Тестирование](#тестирование)
- [Деплой](#деплой)

---

## Технологический стек

### Backend
- **Python:** 3.11+
- **Telegram Bot:** aiogram 3.22.0
- **Database:** PostgreSQL 16
- **ORM:** SQLAlchemy 2.0 + asyncpg
- **Migrations:** Alembic

### AI & ML
- **Text AI:** OpenAI API (gpt-4o, gpt-4o-mini)
- **Vision AI:** Together API (Qwen 2.5 VL)
- **Token Management:** tiktoken

### Data Sources
- **Crypto Prices:** CoinGecko API
- **Crypto News:** CryptoPanic API

### Utilities
- **Async HTTP:** aiohttp
- **Retry Logic:** tenacity
- **Scheduling:** APScheduler
- **Config:** python-dotenv
- **Cache:** Redis (optional, in-memory for dev)

### DevOps
- **Containerization:** Docker + docker-compose
- **Testing:** pytest, pytest-asyncio
- **CI/CD:** GitHub Actions (planned)
- **Monitoring:** Sentry (planned)

---

## Структура проекта

```
syntra-bot/
├── src/
│   ├── __init__.py
│   ├── bot.py                  # Точка входа
│   ├── handlers/               # Обработчики команд
│   │   ├── __init__.py
│   │   ├── start.py           # /start, /help
│   │   ├── ai.py              # AI-чат
│   │   ├── crypto.py          # /price, /analyze, /market
│   │   ├── vision.py          # Анализ графиков
│   │   └── admin.py           # Админ-команды
│   ├── middleware/             # Middleware
│   │   ├── __init__.py
│   │   ├── database.py        # DB sessions
│   │   ├── subscription.py    # Проверка подписки
│   │   ├── request_limit.py   # Лимиты запросов
│   │   └── logging.py         # Логирование
│   ├── services/               # Бизнес-логика
│   │   ├── __init__.py
│   │   ├── openai_service.py  # OpenAI integration
│   │   ├── together_service.py # Together API (vision)
│   │   ├── coingecko_service.py # CoinGecko
│   │   ├── cryptopanic_service.py # News
│   │   ├── technical_analysis.py # TA calculations
│   │   ├── scheduler_service.py # APScheduler
│   │   ├── retention_service.py # Воронка удержания
│   │   └── alerts_service.py  # Админ-алерты
│   ├── database/               # Database layer
│   │   ├── __init__.py
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── crud.py            # CRUD operations
│   │   └── engine.py          # DB engine setup
│   └── utils/                  # Утилиты
│       ├── __init__.py
│       ├── cache.py           # Кэширование
│       ├── helpers.py         # Вспомогательные функции
│       └── formatters.py      # Форматирование вывода
├── config/
│   ├── config.py              # Конфигурация
│   ├── prompts.py             # System prompts
│   └── logging.py             # Logging config
├── alembic/                    # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── tests/                      # Тесты
│   ├── __init__.py
│   ├── test_handlers/
│   ├── test_services/
│   └── test_database/
├── docs/                       # Документация
│   ├── TODO.md
│   ├── DEVELOPMENT.md         # Этот файл
│   ├── ARCHITECTURE.md
│   ├── API_DOCS.md
│   ├── PROGRESS.md
│   └── SYNTRA_PERSONA.md
├── .env.example                # Пример переменных окружения
├── .gitignore
├── requirements.txt            # Python dependencies
├── docker-compose.yml          # Docker setup
├── Dockerfile                  # Docker image
└── README.md                   # Описание проекта
```

---

## Настройка окружения

### 1. Клонирование и установка зависимостей

```bash
# Python 3.11+
python --version

# Виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

```bash
# Копировать шаблон
cp .env.example .env

# Заполнить значения
nano .env
```

**.env переменные:**
```env
# Telegram
BOT_TOKEN=your_telegram_bot_token
REQUIRED_CHANNEL=@your_channel  # или -1001234567890
ADMIN_IDS=123456789,987654321  # через запятую

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/syntra_bot

# OpenAI
OPENAI_API_KEY=sk-...

# Together AI
TOGETHER_API_KEY=your_together_api_key

# CoinGecko
COINGECKO_API_KEY=  # опционально для Pro

# CryptoPanic
CRYPTOPANIC_TOKEN=your_cryptopanic_token

# Limits
REQUEST_LIMIT_PER_DAY=5

# Environment
ENVIRONMENT=development  # development, production
LOG_LEVEL=INFO
```

### 3. Запуск PostgreSQL

```bash
# Через docker-compose
docker-compose up -d postgres

# Проверка
docker ps
```

### 4. Миграции базы данных

```bash
# Инициализация (только первый раз)
alembic init alembic

# Создание миграции
alembic revision --autogenerate -m "Initial tables"

# Применение миграций
alembic upgrade head
```

### 5. Запуск бота

```bash
# Development
python src/bot.py

# Production (через systemd или Docker)
```

---

## Best Practices

### Code Style

**PEP 8 + Type Hints:**
```python
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

async def get_user_by_telegram_id(
    session: AsyncSession,
    telegram_id: int
) -> Optional[User]:
    """
    Получить пользователя по Telegram ID.

    Args:
        session: Async DB session
        telegram_id: Telegram user ID

    Returns:
        User model или None
    """
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
```

**Async/Await:**
```python
# ✅ ПРАВИЛЬНО
async def fetch_price(coin_id: str) -> float:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return data['price']

# ❌ НЕПРАВИЛЬНО - блокирует event loop
def fetch_price_sync(coin_id: str) -> float:
    response = requests.get(url)  # Синхронный запрос!
    return response.json()['price']
```

### Database

**Всегда используйте async with:**
```python
# ✅ ПРАВИЛЬНО
async def create_user(telegram_id: int):
    async with AsyncSessionLocal() as session:
        user = User(telegram_id=telegram_id)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
    # Сессия автоматически закрыта

# ❌ НЕПРАВИЛЬНО - утечка соединений
async def create_user_bad(telegram_id: int):
    session = AsyncSessionLocal()
    user = User(telegram_id=telegram_id)
    session.add(user)
    await session.commit()
    # Забыли закрыть сессию!
```

**Используйте индексы:**
```python
class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        index=True  # ← Индекс для быстрого поиска
    )
```

### API Calls

**Retry Logic:**
```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential
)

@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(6)
)
async def fetch_with_retry(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()
```

**Кэширование:**
```python
from datetime import datetime, timedelta
from typing import Dict, Any

class SimpleCache:
    def __init__(self, ttl_seconds: int = 60):
        self.cache: Dict[str, tuple[Any, datetime]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)

    def get(self, key: str) -> Any:
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                return data
            del self.cache[key]
        return None

    def set(self, key: str, value: Any):
        self.cache[key] = (value, datetime.now())

# Использование
cache = SimpleCache(ttl_seconds=60)

async def get_price(coin_id: str):
    cached = cache.get(f'price_{coin_id}')
    if cached:
        return cached

    price = await fetch_price_from_api(coin_id)
    cache.set(f'price_{coin_id}', price)
    return price
```

### Error Handling

**Специфичные исключения:**
```python
from openai import RateLimitError, APIError
from aiogram.exceptions import TelegramBadRequest
import logging

logger = logging.getLogger(__name__)

async def safe_ai_request(prompt: str):
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except RateLimitError as e:
        logger.warning(f"Rate limit hit: {e}")
        return "⏳ Превышен лимит запросов. Попробуйте позже."
    except APIError as e:
        logger.error(f"OpenAI API error: {e}")
        return "❌ Ошибка API. Попробуйте позже."
    except Exception as e:
        logger.exception("Unexpected error")
        return "❌ Произошла ошибка."
```

**Global Error Handler:**
```python
from aiogram import Router
from aiogram.types import ErrorEvent

router = Router()

@router.error()
async def error_handler(event: ErrorEvent):
    logger.critical("Critical error", exc_info=event.exception)

    if event.update.message:
        try:
            await event.update.message.answer(
                "❌ Произошла ошибка. Попробуйте позже."
            )
        except Exception:
            pass  # Ignore if can't send message
```

### Logging

**Структурированное логирование:**
```python
import logging
from config.logging import setup_logging

# config/logging.py
def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("bot.log"),
            logging.StreamHandler()
        ]
    )

# В модулях
logger = logging.getLogger(__name__)

# Использование
logger.info(f"User {user_id} requested price for {coin_id}")
logger.warning(f"Rate limit approached for user {user_id}")
logger.error(f"API error: {error}", exc_info=True)
```

---

## Работа с API

### OpenAI API

**Streaming для анимации:**
```python
from aiogram.utils.chat_action import ChatActionSender

async def stream_ai_response(message: Message, prompt: str, bot: Bot):
    sent_msg = await message.answer("⏳ Думаю...")
    full_response = ""
    buffer = ""

    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        stream = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            stream=True,
            temperature=0.7,
            max_tokens=1000
        )

        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                full_response += content
                buffer += content

                # Обновляем каждые ~30 символов
                if len(buffer) >= 30:
                    try:
                        await sent_msg.edit_text(full_response)
                        buffer = ""
                    except Exception:
                        pass  # Игнорируем TelegramBadRequest при быстром редактировании

        # Финальное обновление
        await sent_msg.edit_text(full_response)
```

**Token Management:**
```python
import tiktoken

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

# Перед отправкой
total_tokens = sum(count_tokens(msg['content']) for msg in messages)
if total_tokens > 4000:
    # Сократить контекст
    messages = messages[-5:]  # Последние 5 сообщений
```

### CoinGecko API

**Кэширование обязательно:**
```python
from pycoingecko import CoinGeckoAPI
from utils.cache import SimpleCache

cg = CoinGeckoAPI()
cache = SimpleCache(ttl_seconds=60)

async def get_crypto_price(coin_id: str):
    cached = cache.get(f'price_{coin_id}')
    if cached:
        return cached

    try:
        data = cg.get_price(
            ids=coin_id,
            vs_currencies='usd',
            include_market_cap=True,
            include_24hr_vol=True,
            include_24hr_change=True
        )
        result = data[coin_id]
        cache.set(f'price_{coin_id}', result)
        return result
    except KeyError:
        return None  # Монета не найдена
    except Exception as e:
        logger.error(f"CoinGecko error: {e}")
        return None
```

---

## Тестирование

### Unit Tests

```python
# tests/test_services/test_coingecko.py
import pytest
from unittest.mock import Mock, patch
from services.coingecko_service import get_crypto_price

@pytest.mark.asyncio
async def test_get_crypto_price_success():
    with patch('services.coingecko_service.cg') as mock_cg:
        mock_cg.get_price.return_value = {
            'bitcoin': {'usd': 45000}
        }

        result = await get_crypto_price('bitcoin')

        assert result is not None
        assert result['usd'] == 45000

@pytest.mark.asyncio
async def test_get_crypto_price_not_found():
    with patch('services.coingecko_service.cg') as mock_cg:
        mock_cg.get_price.side_effect = KeyError('bitcoin')

        result = await get_crypto_price('invalid_coin')

        assert result is None
```

### Integration Tests

```python
# tests/test_handlers/test_crypto.py
import pytest
from aiogram.types import Message
from unittest.mock import AsyncMock
from handlers.crypto import cmd_price

@pytest.mark.asyncio
async def test_cmd_price_handler():
    message = AsyncMock(spec=Message)
    message.text = "/price bitcoin"

    await cmd_price(message)

    message.answer.assert_called_once()
    call_args = message.answer.call_args[0][0]
    assert "BTC" in call_args or "bitcoin" in call_args.lower()
```

### Запуск тестов

```bash
# Все тесты
pytest

# С coverage
pytest --cov=src --cov-report=html

# Конкретный файл
pytest tests/test_services/test_coingecko.py

# С verbose
pytest -v
```

---

## Деплой

### Docker

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "src/bot.py"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: syntra
      POSTGRES_PASSWORD: password
      POSTGRES_DB: syntra_bot
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  bot:
    build: .
    env_file: .env
    depends_on:
      - postgres
    restart: unless-stopped

volumes:
  postgres_data:
```

### Systemd Service

```ini
# /etc/systemd/system/syntra-bot.service
[Unit]
Description=Syntra Trade Consultant Bot
After=network.target

[Service]
Type=simple
User=syntra
WorkingDirectory=/opt/syntra-bot
ExecStart=/opt/syntra-bot/venv/bin/python src/bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Управление
sudo systemctl start syntra-bot
sudo systemctl enable syntra-bot
sudo systemctl status syntra-bot
sudo journalctl -u syntra-bot -f  # Логи
```

---

## Мониторинг

### Health Check

```python
# src/utils/health.py
from datetime import datetime

health_status = {
    'last_update': None,
    'db_connected': False,
    'openai_connected': False
}

async def update_health():
    health_status['last_update'] = datetime.now()
    # Проверки...
```

### Metrics

```python
# Prometheus metrics (опционально)
from prometheus_client import Counter, Histogram

request_counter = Counter(
    'bot_requests_total',
    'Total bot requests',
    ['command', 'user_id']
)

response_time = Histogram(
    'bot_response_seconds',
    'Response time in seconds'
)
```

---

## Полезные команды

```bash
# Форматирование кода
black src/
isort src/

# Линтинг
flake8 src/
mypy src/

# Миграции
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1

# Docker
docker-compose up -d
docker-compose logs -f bot
docker-compose restart bot

# Логи
tail -f bot.log
journalctl -u syntra-bot -f
```

---

## Troubleshooting

### Проблемы с БД

```bash
# Проверка подключения
docker exec -it syntra_postgres psql -U syntra -d syntra_bot

# Пересоздание БД
docker-compose down -v
docker-compose up -d postgres
alembic upgrade head
```

### Проблемы с API

```python
# Проверка токенов
python -c "from config.config import OPENAI_API_KEY; print(OPENAI_API_KEY[:10])"

# Тест OpenAI
python -c "from openai import OpenAI; client = OpenAI(); print(client.models.list())"
```

---

## Ссылки на документацию

- [aiogram 3.x docs](https://docs.aiogram.dev/)
- [OpenAI API](https://platform.openai.com/docs/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
- [CoinGecko API](https://docs.coingecko.com/)
- [PostgreSQL](https://www.postgresql.org/docs/)
