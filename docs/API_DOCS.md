# API DOCUMENTATION - Syntra Trade Consultant

> Документация по всем используемым API и интеграциям

## Содержание
- [OpenAI API](#openai-api)
- [OpenAI Vision API](#openai-vision-api)
- [CoinGecko API](#coingecko-api)
- [CryptoPanic API](#cryptopanic-api)
- [Telegram Bot API](#telegram-bot-api)

---

## OpenAI API

### Базовая информация

- **Base URL:** `https://api.openai.com/v1`
- **Аутентификация:** Bearer token
- **Документация:** https://platform.openai.com/docs/api-reference

### Используемые модели

| Модель | Использование | Цена (input/output) |
|--------|---------------|---------------------|
| gpt-4o | Сложные запросы (>500 tokens) | $3/$10 per 1M tokens |
| gpt-4o-mini | Простые запросы (<500 tokens) | ~$0.15/$0.60 per 1M tokens |

### Chat Completions Endpoint

**POST** `/v1/chat/completions`

**Request:**
```json
{
  "model": "gpt-4o",
  "messages": [
    {
      "role": "system",
      "content": "Ты - Syntra, профессиональный криптоаналитик..."
    },
    {
      "role": "user",
      "content": "Проанализируй Bitcoin"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": false
}
```

**Response:**
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "gpt-4o",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Анализ Bitcoin:\n\n📊 Технический анализ:\n..."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 300,
    "total_tokens": 450
  }
}
```

### Streaming

**Request:**
```json
{
  "model": "gpt-4o",
  "messages": [...],
  "stream": true
}
```

**Response (Server-Sent Events):**
```
data: {"choices":[{"delta":{"content":"Анализ"}}]}

data: {"choices":[{"delta":{"content":" Bitcoin"}}]}

data: {"choices":[{"delta":{"content":":\n\n"}}]}

...

data: [DONE]
```

### Python Implementation

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Non-streaming
response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ],
    temperature=0.7,
    max_tokens=1000
)

answer = response.choices[0].message.content
tokens_used = response.usage.total_tokens

# Streaming
stream = await client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    stream=True
)

async for chunk in stream:
    content = chunk.choices[0].delta.content
    if content:
        print(content, end='')
```

### Rate Limits

| Tier | RPM | TPM (gpt-4o) |
|------|-----|--------------|
| Free | 3 | 200,000 |
| Tier 1 | 500 | 500,000 |
| Tier 2 | 5,000 | 2,000,000 |
| Tier 5 | 10,000 | 10,000,000 |

**Headers в ответе:**
- `x-ratelimit-limit-requests`
- `x-ratelimit-remaining-requests`
- `x-ratelimit-limit-tokens`
- `x-ratelimit-remaining-tokens`

### Error Codes

| Code | Значение | Действие |
|------|----------|----------|
| 401 | Неверный API key | Проверить OPENAI_API_KEY |
| 429 | Rate limit exceeded | Retry с backoff |
| 500 | Server error | Retry |
| 503 | Service unavailable | Retry |

### Best Practices

1. **Retry Logic:**
```python
from tenacity import retry, wait_random_exponential, stop_after_attempt

@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(6)
)
async def get_completion(**kwargs):
    return await client.chat.completions.create(**kwargs)
```

2. **Token Counting:**
```python
import tiktoken

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))
```

3. **Cost Calculation:**
```python
def calculate_cost(usage: dict, model: str) -> float:
    prices = {
        "gpt-4o": {"input": 3.0, "output": 10.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60}
    }

    input_cost = (usage['prompt_tokens'] / 1_000_000) * prices[model]['input']
    output_cost = (usage['completion_tokens'] / 1_000_000) * prices[model]['output']

    return input_cost + output_cost
```

---

## OpenAI Vision API

### Базовая информация

- **Base URL:** `https://api.openai.com/v1`
- **Аутентификация:** Bearer token (тот же OPENAI_API_KEY)
- **Документация:** https://platform.openai.com/docs/guides/vision

### Возможности Vision API

GPT-4o поддерживает анализ изображений со следующими возможностями:

**Основные возможности:**
- Распознавание объектов, сцен и паттернов
- OCR (извлечение текста с изображений)
- Анализ графиков и диаграмм
- Определение пространственных отношений
- Анализ нескольких изображений одновременно (до 10 за запрос)

**Для криптоанализа:**
- Анализ свечных графиков
- Распознавание паттернов (голова-плечи, треугольники, флаги)
- Определение уровней поддержки/сопротивления
- Чтение индикаторов (RSI, MACD, объемы)

### Chat Completions (Vision)

**POST** `/v1/chat/completions`

**Request с URL изображения:**
```json
{
  "model": "gpt-4o",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Проанализируй этот график криптовалюты. Определи тренд, уровни поддержки и сопротивления, свечные паттерны."
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "https://example.com/chart.png",
            "detail": "high"
          }
        }
      ]
    }
  ],
  "max_tokens": 1000
}
```

**Request с Base64 изображением:**
```json
{
  "model": "gpt-4o",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "Проанализируй этот график. Определи тренд, уровни поддержки и сопротивления."
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
            "detail": "high"
          }
        }
      ]
    }
  ],
  "max_tokens": 1000
}
```

**Response:**
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "gpt-4o",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "📊 Анализ графика:\n\n1. **Тренд:** Восходящий тренд с недавней консолидацией\n2. **Поддержка:** $44,000 - сильный уровень\n3. **Сопротивление:** $48,000 - зона сопротивления\n4. **Паттерн:** Формируется восходящий треугольник\n5. **Объемы:** Увеличение на росте - бычий сигнал"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 850,
    "completion_tokens": 150,
    "total_tokens": 1000
  }
}
```

### Python Implementation

```python
import base64
from openai import AsyncOpenAI
from io import BytesIO

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Convert image to base64
def encode_image(image_bytes: bytes) -> str:
    """Encode image bytes to base64 string"""
    return base64.b64encode(image_bytes).decode('utf-8')

# Vision analysis from bytes
async def analyze_chart(
    image_bytes: bytes,
    prompt: str = "Проанализируй этот график криптовалюты. Определи тренд, уровни поддержки/сопротивления, свечные паттерны.",
    detail: str = "high"
) -> str:
    """
    Analyze chart image using GPT-4o Vision

    Args:
        image_bytes: Image file content as bytes
        prompt: Analysis prompt
        detail: "low", "high", or "auto" (affects token cost and quality)

    Returns:
        Analysis text from GPT-4o
    """
    base64_image = encode_image(image_bytes)

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                        "detail": detail
                    }
                }
            ]
        }],
        max_tokens=1000,
        temperature=0.7
    )

    return response.choices[0].message.content

# With system prompt (для персоны Syntra)
async def analyze_chart_with_persona(
    image_bytes: bytes,
    system_prompt: str
) -> str:
    """Analyze chart with Syntra persona"""
    base64_image = encode_image(image_bytes)

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Проанализируй этот график"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ],
        max_tokens=1000,
        temperature=0.7
    )

    return response.choices[0].message.content
```

### Image Requirements

**Форматы:**
- JPEG, PNG, WebP, GIF (non-animated)

**Размеры:**
- **Максимальный размер файла:** 20 MB (для base64)
- **Рекомендация:** Оптимизировать до 2-5 MB для быстрой обработки

**Detail Parameter:**
- `"low"` - 512x512 px, быстрее и дешевле (базовый анализ)
- `"high"` - до 2048x2048 px, детальный анализ (для графиков)
- `"auto"` - автоматический выбор (по умолчанию)

### Token Calculation for Images

Токены для изображений рассчитываются по формуле:

**Low detail mode:**
- Фиксированная стоимость: ~85 tokens

**High detail mode:**
- Изображение масштабируется до 2048x2048 px
- Делится на тайлы 512x512 px
- Каждый тайл: ~170 tokens
- Базовый тайл: 85 tokens
- **Формула:** `85 + (170 * количество_тайлов)`

**Пример для 1024x1024 изображения:**
- High detail: 85 + (170 * 4) = 765 tokens

### Pricing

**GPT-4o with Vision:**
- Стоимость та же, что у обычного GPT-4o
- **Input:** $3.00 per 1M tokens (включая токены изображений)
- **Output:** $10.00 per 1M tokens

**Пример расчета:**
```python
# Для изображения 1024x1024 в high detail:
# Image tokens: ~765
# Text prompt: ~100 tokens
# Total input: ~865 tokens
# Response: ~200 tokens

input_cost = (865 / 1_000_000) * 3.00   # $0.002595
output_cost = (200 / 1_000_000) * 10.00  # $0.002
total_cost = input_cost + output_cost    # $0.004595 (~$0.005 per analysis)
```

**Оптимизация стоимости:**
1. Уменьшайте размер изображений перед отправкой
2. Используйте `detail="low"` для простых задач
3. Сжимайте JPEG с качеством 85-90%

### Rate Limits

Те же, что у обычного GPT-4o API:
- Зависит от tier аккаунта
- Free tier: 3 RPM, 200K TPM
- Tier 1: 500 RPM, 500K TPM
- Tier 5: 10,000 RPM, 10M TPM

### Best Practices

**Для анализа крипто-графиков:**

1. **Подготовка изображения:**
   ```python
   # Оптимальный размер: 1024x768 или 1920x1080
   # Формат: JPEG с качеством 85%
   # Detail: "high" для детального анализа
   ```

2. **Промпт-инжиниринг:**
   ```python
   prompt = """
   Проанализируй график криптовалюты и предоставь:
   1. Текущий тренд (восходящий/нисходящий/боковой)
   2. Ключевые уровни поддержки и сопротивления
   3. Свечные паттерны (если видны)
   4. Индикаторы (RSI, MACD, объемы) - если отображены
   5. Краткий прогноз на основе технического анализа

   Формат ответа: структурированный, с эмодзи.
   """
   ```

3. **Обработка ошибок:**
   ```python
   try:
       analysis = await analyze_chart(image_bytes)
   except openai.BadRequestError as e:
       # Возможные причины:
       # - Изображение слишком большое
       # - Неподдерживаемый формат
       # - Поврежденный файл
       logger.error(f"Vision API error: {e}")
   ```

4. **Кэширование:**
   - Не кэшируйте результаты анализа графиков (они быстро устаревают)
   - Кэшируйте только статические изображения (логотипы, инфографика)

### Multiple Images

GPT-4o поддерживает анализ нескольких изображений:

```python
messages = [{
    "role": "user",
    "content": [
        {"type": "text", "text": "Сравни эти два графика BTC"},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img1}"}},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img2}"}}
    ]
}]
```

**Лимит:** До 10 изображений за один запрос

---

## CoinGecko API

### Базовая информация

- **Base URL:** `https://api.coingecko.com/api/v3`
- **Аутентификация:** API key (опционально для Pro)
- **Документация:** https://docs.coingecko.com/

### Rate Limits

| Plan | Calls/minute |
|------|--------------|
| Free | 5-15 |
| Demo | ~30 |
| Paid | 500-1000 |

**⚠️ КРИТИЧНО: Обязательно кэшировать (TTL 60 сек)**

### Simple Price

**GET** `/simple/price`

**Parameters:**
- `ids` - coin IDs (bitcoin, ethereum, solana)
- `vs_currencies` - валюты (usd, eur, rub)
- `include_market_cap` - true/false
- `include_24hr_vol` - true/false
- `include_24hr_change` - true/false

**Request:**
```
GET /api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_market_cap=true&include_24hr_vol=true&include_24hr_change=true
```

**Response:**
```json
{
  "bitcoin": {
    "usd": 45000,
    "usd_market_cap": 850000000000,
    "usd_24h_vol": 25000000000,
    "usd_24h_change": 2.5
  }
}
```

### Coins Markets

**GET** `/coins/markets`

**Parameters:**
- `vs_currency` - валюта (usd)
- `order` - market_cap_desc, volume_desc
- `per_page` - количество (макс 250)
- `page` - страница

**Request:**
```
GET /api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1
```

**Response:**
```json
[
  {
    "id": "bitcoin",
    "symbol": "btc",
    "name": "Bitcoin",
    "current_price": 45000,
    "market_cap": 850000000000,
    "total_volume": 25000000000,
    "price_change_percentage_24h": 2.5,
    "circulating_supply": 19000000,
    "ath": 69000,
    "atl": 67.81
  },
  ...
]
```

### OHLC (Historical)

**GET** `/coins/{id}/ohlc`

**Parameters:**
- `vs_currency` - валюта (usd)
- `days` - период (1, 7, 14, 30, 90, 180, 365, max)

**Request:**
```
GET /api/v3/coins/bitcoin/ohlc?vs_currency=usd&days=7
```

**Response:**
```json
[
  [1640000000000, 46000, 47500, 45500, 47000],
  [1640086400000, 47000, 48000, 46500, 47800],
  ...
]
// [timestamp, open, high, low, close]
```

**Гранулярность:**
- 1-2 дня: 30 минут
- 3-30 дней: 4 часа
- 31+ дней: дневные свечи

### Market Chart

**GET** `/coins/{id}/market_chart`

**Parameters:**
- `vs_currency` - валюта
- `days` - период

**Request:**
```
GET /api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=7
```

**Response:**
```json
{
  "prices": [
    [1640000000000, 46000],
    [1640086400000, 47000],
    ...
  ],
  "market_caps": [...],
  "total_volumes": [...]
}
```

### Python Implementation

```python
from pycoingecko import CoinGeckoAPI
from utils.cache import SimpleCache

cg = CoinGeckoAPI()
cache = SimpleCache(ttl_seconds=60)

async def get_price(coin_id: str):
    """Получить цену с кэшированием"""
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
        return None  # Coin not found
    except Exception as e:
        logger.error(f"CoinGecko error: {e}")
        return None

async def get_ohlc(coin_id: str, days: int = 7):
    """Получить OHLC данные для TA"""
    import pandas as pd

    ohlc = cg.get_coin_ohlc_by_id(
        id=coin_id,
        vs_currency='usd',
        days=days
    )

    df = pd.DataFrame(
        ohlc,
        columns=['timestamp', 'open', 'high', 'low', 'close']
    )
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    return df
```

### Error Handling

```python
from requests.exceptions import HTTPError, RequestException

try:
    price = cg.get_price(ids='bitcoin', vs_currencies='usd')
except HTTPError as e:
    if e.response.status_code == 429:
        logger.warning("Rate limit exceeded")
        # Wait and retry
    else:
        logger.error(f"HTTP error: {e}")
except RequestException as e:
    logger.error(f"Network error: {e}")
```

---

## CryptoPanic API

### Базовая информация

- **Base URL:** `https://cryptopanic.com/api/v1`
- **Аутентификация:** Token в query params
- **Документация:** https://cryptopanic.com/developers/api/

### Posts Endpoint

**GET** `/posts/`

**Parameters:**
- `auth_token` - ваш токен (обязательно)
- `public` - true (для публичных новостей)
- `currencies` - фильтр по монетам (BTC, ETH, SOL)
- `kind` - news, media, all
- `filter` - hot, rising, bullish, bearish, important, lol

**Request:**
```
GET /api/v1/posts/?auth_token=YOUR_TOKEN&public=true&currencies=BTC,ETH&filter=rising
```

**Response:**
```json
{
  "count": 1234,
  "next": "https://...",
  "previous": null,
  "results": [
    {
      "id": 12345,
      "title": "Bitcoin Breaks $50,000",
      "url": "https://...",
      "source": {
        "title": "CoinDesk",
        "domain": "coindesk.com"
      },
      "published_at": "2024-01-15T12:00:00Z",
      "currencies": [
        {
          "code": "BTC",
          "title": "Bitcoin"
        }
      ],
      "votes": {
        "positive": 150,
        "negative": 5,
        "important": 20,
        "liked": 30,
        "disliked": 2,
        "lol": 5,
        "toxic": 0
      }
    },
    ...
  ]
}
```

### Python Implementation

```python
import aiohttp
from utils.cache import SimpleCache

cache = SimpleCache(ttl_seconds=300)  # 5 минут

async def get_news(
    currencies: list[str] = None,
    filter_: str = 'rising',
    limit: int = 10
):
    """Получить новости с кэшированием"""
    cache_key = f"news_{'_'.join(currencies or [])}_{filter_}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    url = "https://cryptopanic.com/api/v1/posts/"
    params = {
        'auth_token': CRYPTOPANIC_TOKEN,
        'public': 'true',
        'filter': filter_
    }

    if currencies:
        params['currencies'] = ','.join(currencies)

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            data = await response.json()
            results = data['results'][:limit]

            cache.set(cache_key, results)
            return results

# Использование
news = await get_news(currencies=['BTC', 'ETH'], filter_='rising', limit=5)

for item in news:
    print(f"📰 {item['title']}")
    print(f"   {item['url']}")
    print(f"   👍 {item['votes']['positive']} 👎 {item['votes']['negative']}")
```

### Filters

| Filter | Описание |
|--------|----------|
| hot | Горячие новости |
| rising | Растущие по популярности |
| bullish | Бычьи настроения |
| bearish | Медвежьи настроения |
| important | Важные новости |
| lol | Забавные |

### Rate Limits

**Free tier:** Не указано точно, рекомендуется кэшировать (5 мин)

---

## Telegram Bot API

### Базовая информация

- **Documentation:** https://core.telegram.org/bots/api
- **aiogram docs:** https://docs.aiogram.dev/

### File Size Limits

| Операция | Лимит |
|----------|-------|
| Download | 20 MB |
| Upload | 50 MB |
| Photo (URL) | 5 MB |
| Other files (URL) | 20 MB |

### Get Chat Member

**Использование:** Проверка подписки на канал

```python
from aiogram import Bot
from aiogram.types import ChatMemberStatus

async def check_subscription(user_id: int, bot: Bot) -> bool:
    try:
        member = await bot.get_chat_member(
            chat_id="@your_channel",  # или -1001234567890
            user_id=user_id
        )

        return member.status in [
            ChatMemberStatus.CREATOR,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER
        ]
    except Exception:
        return False
```

**⚠️ ТРЕБОВАНИЕ:** Бот должен быть администратором канала!

### Download File

```python
from aiogram import Bot
from io import BytesIO

@router.message(F.photo)
async def handle_photo(message: Message, bot: Bot):
    # Получаем самое большое фото
    photo = message.photo[-1]
    file_id = photo.file_id

    # Получаем информацию о файле
    file = await bot.get_file(file_id)
    file_path = file.file_path

    # Скачивание в BytesIO
    photo_bytes = BytesIO()
    await bot.download_file(file_path, destination=photo_bytes)

    # Или на диск
    await bot.download_file(file_path, destination="photo.jpg")
```

### Send Chat Action

```python
from aiogram.utils.chat_action import ChatActionSender

# Typing indicator
async with ChatActionSender.typing(bot=bot, chat_id=chat_id):
    # Долгая операция
    result = await long_operation()
    await message.answer(result)

# Доступные действия:
# - typing
# - upload_photo
# - upload_document
# - upload_video
# - record_video
# - choose_sticker
```

---

## Общие Best Practices

### 1. Retry Logic

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type
)

@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(6),
    retry=retry_if_exception_type((ConnectionError, TimeoutError))
)
async def api_call_with_retry():
    # API call
    pass
```

### 2. Кэширование

```python
from datetime import datetime, timedelta

class SimpleCache:
    def __init__(self, ttl_seconds: int):
        self.cache = {}
        self.ttl = timedelta(seconds=ttl_seconds)

    def get(self, key: str):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.ttl:
                return data
            del self.cache[key]
        return None

    def set(self, key: str, value):
        self.cache[key] = (value, datetime.now())
```

### 3. Error Handling

```python
from aiohttp import ClientError
import logging

logger = logging.getLogger(__name__)

async def safe_api_call(url: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                response.raise_for_status()
                return await response.json()
    except ClientError as e:
        logger.error(f"API error for {url}: {e}")
        return None
    except Exception as e:
        logger.exception("Unexpected error")
        return None
```

### 4. Rate Limiting

```python
import asyncio
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_calls: int, period: int):
        self.max_calls = max_calls
        self.period = period
        self.calls = []

    async def acquire(self):
        now = datetime.now()
        # Удаляем старые вызовы
        self.calls = [c for c in self.calls if now - c < timedelta(seconds=self.period)]

        if len(self.calls) >= self.max_calls:
            # Ждем
            sleep_time = (self.calls[0] + timedelta(seconds=self.period) - now).total_seconds()
            await asyncio.sleep(sleep_time)

        self.calls.append(now)

# Использование
limiter = RateLimiter(max_calls=10, period=60)  # 10 calls per minute

async def api_call():
    await limiter.acquire()
    # Make API call
```

---

## Environment Variables

```bash
# .env file
OPENAI_API_KEY=sk-...
TOGETHER_API_KEY=...
COINGECKO_API_KEY=  # optional
CRYPTOPANIC_TOKEN=...
BOT_TOKEN=...
```

---

## Мониторинг использования

### Cost Tracking

```python
# Сохранение в БД
async def track_cost(
    session: AsyncSession,
    user_id: int,
    service: str,  # openai, together
    tokens: int,
    cost: float
):
    cost_record = CostTracking(
        user_id=user_id,
        service=service,
        tokens=tokens,
        cost=cost
    )
    session.add(cost_record)
    await session.commit()
```

### Daily Report

```python
from sqlalchemy import func, select
from datetime import date

async def get_daily_costs(session: AsyncSession):
    stmt = select(
        CostTracking.service,
        func.sum(CostTracking.cost).label('total_cost'),
        func.sum(CostTracking.tokens).label('total_tokens')
    ).where(
        func.date(CostTracking.timestamp) == date.today()
    ).group_by(CostTracking.service)

    result = await session.execute(stmt)
    return result.all()
```

---

Документация обновляется по мере интеграции новых API и сервисов.
