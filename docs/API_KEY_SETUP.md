# API Key Setup для Trading Bot

**Защита futures endpoints от несанкционированного доступа**

---

## 🔐 Зачем нужен API Key?

Endpoint `/api/calculate-position-size` должен быть доступен **только твоему трейдинг-боту**.

Без защиты кто угодно может:
- ❌ Использовать твой API для расчётов
- ❌ Перегрузить сервер запросами
- ❌ Получить информацию о твоих настройках

С API Key:
- ✅ Только авторизованные запросы
- ✅ Защита от неавторизованного доступа
- ✅ Логирование попыток доступа

---

## 🚀 Quick Start (3 шага)

### 1. Сгенерируй API ключ

```bash
# Вариант 1: OpenSSL (рекомендуется)
openssl rand -hex 32

# Вариант 2: Python
python3 -c "import secrets; print(secrets.token_hex(32))"

# Вариант 3: Online
# https://www.random.org/strings/?num=1&len=64&digits=on&upperalpha=on&loweralpha=on
```

**Пример сгенерированного ключа:**
```
a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456
```

### 2. Добавь ключ в .env

```bash
nano .env
```

Добавь строку:
```bash
TRADING_BOT_API_KEY=a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456
```

Сохрани (Ctrl+O, Enter, Ctrl+X)

### 3. Перезапусти сервер

```bash
# Останови текущий сервер (Ctrl+C)

# Запусти заново
source .venv/bin/activate
python api_server.py
```

**✅ Готово!** Теперь endpoint защищён.

---

## 📡 Использование в Trade Bot

### Python (aiohttp):

```python
import aiohttp

API_KEY = "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"

async def calculate_position(symbol: str, entry: float, stop: float, risk_usd: float):
    """Рассчитать позицию с API key"""

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY  # 🔑 ВАЖНО!
    }

    data = {
        "symbol": symbol,
        "side": "long",
        "entry_price": entry,
        "stop_loss": stop,
        "risk_usd": risk_usd,
        "leverage": 5
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8000/api/calculate-position-size",
            headers=headers,
            json=data
        ) as resp:
            if resp.status == 401:
                print("❌ Invalid API key!")
                return None

            result = await resp.json()
            return result


# Использование
result = await calculate_position("BTCUSDT", 95250, 94300, 10.0)
print(f"Qty: {result['position']['qty']}")
```

### Python (requests):

```python
import requests

API_KEY = "your-api-key-here"

response = requests.post(
    "http://localhost:8000/api/calculate-position-size",
    headers={"X-API-Key": API_KEY},
    json={
        "symbol": "BTCUSDT",
        "side": "long",
        "entry_price": 95250,
        "stop_loss": 94300,
        "risk_usd": 10,
        "leverage": 5
    }
)

if response.status_code == 401:
    print("❌ Invalid API key!")
else:
    data = response.json()
    print(f"Qty: {data['position']['qty']}")
```

### cURL:

```bash
curl -X POST "http://localhost:8000/api/calculate-position-size" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-api-key-here" \
     -d '{
       "symbol": "BTCUSDT",
       "side": "long",
       "entry_price": 95250.0,
       "stop_loss": 94300.0,
       "risk_usd": 10.0,
       "leverage": 5
     }'
```

---

## ❌ Что будет без API Key?

### Запрос без заголовка:

```bash
curl -X POST "http://localhost:8000/api/calculate-position-size" \
     -H "Content-Type: application/json" \
     -d '{"symbol": "BTCUSDT", ...}'
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Missing API key. Provide X-API-Key header."
}
```

### Запрос с неправильным ключом:

```bash
curl -X POST "http://localhost:8000/api/calculate-position-size" \
     -H "X-API-Key: wrong-key" \
     -d '{"symbol": "BTCUSDT", ...}'
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Invalid API key"
}
```

---

## 🔒 Best Practices

### 1. Храни ключ в переменных окружения

**❌ Плохо:**
```python
API_KEY = "a1b2c3d4..."  # Hardcoded в коде
```

**✅ Хорошо:**
```python
import os
API_KEY = os.getenv("TRADING_BOT_API_KEY")
```

### 2. Используй разные ключи для dev/prod

```bash
# .env.development
TRADING_BOT_API_KEY=dev_key_12345

# .env.production
TRADING_BOT_API_KEY=prod_key_67890
```

### 3. Не коммить ключи в Git

```bash
# .gitignore
.env
.env.local
.env.*.local
```

### 4. Ротация ключей раз в 3-6 месяцев

```bash
# Сгенерируй новый ключ
openssl rand -hex 32

# Обнови .env
# Перезапусти сервер
# Обнови Trade Bot
```

---

## 🛠️ Troubleshooting

### Проблема: "API key authentication not configured"

**Причина:** `TRADING_BOT_API_KEY` не задан в `.env`

**Решение:**
```bash
echo "TRADING_BOT_API_KEY=$(openssl rand -hex 32)" >> .env
```

### Проблема: "Invalid API key" (но ключ правильный)

**Причина:** Пробелы или невидимые символы в `.env`

**Решение:**
```bash
# Проверь .env файл
cat .env | grep TRADING_BOT_API_KEY

# Должно быть БЕЗ пробелов:
TRADING_BOT_API_KEY=abc123...

# НЕ:
TRADING_BOT_API_KEY = abc123...  # ❌ пробелы вокруг =
```

### Проблема: Trade Bot получает 401 после рестарта

**Причина:** Сервер не перезапущен после изменения `.env`

**Решение:**
```bash
# Останови сервер (Ctrl+C)
# Запусти заново
python api_server.py
```

---

## 📊 Защищённые Endpoints

Сейчас защищены:
- ✅ `POST /api/calculate-position-size` - расчёт позиции

Публичные (без API key):
- ✅ `POST /api/futures-scenarios` - получение сценариев
- ✅ `GET /api/futures-scenarios/supported-symbols`
- ✅ `GET /api/futures-scenarios/health`

---

## 🔐 Security Tips

1. **Никогда не шари API ключ** в публичных репозиториях
2. **Используй HTTPS** в production (не HTTP)
3. **Мониторь логи** на подозрительные запросы
4. **Rate limiting** для дополнительной защиты (опционально)
5. **Whitelist IP** если Trade Bot на фиксированном IP (опционально)

---

## 📚 Дополнительно

- Исходный код: [api_key_auth.py](../src/api/api_key_auth.py)
- Config: [config.py:81](../config/config.py#L81)
- Example: [.env.example:54](.env.example#L54)

---

**🔐 Твой API защищён!**
