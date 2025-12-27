<p align="center">
  <img src="assets/banner.jpeg" alt="SyntraAI Banner" width="100%">
</p>

# SyntraAI

> AI-платформа для криптотрейдинга с интерфейсом Telegram Mini App

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://postgresql.org)

**[Сайт](https://ai.syntratrade.xyz)** | **[Telegram Mini App](https://t.me/SyntraAI_bot?startapp)** | [English version](README.md)

## Обзор

**SyntraAI** — полнофункциональная SaaS-платформа для криптотрейдеров, объединяющая AI-анализ рынка с интуитивным интерфейсом Telegram Mini App. Система генерирует торговые сценарии для фьючерсных рынков с помощью новейших AI моделей (GPT-5.2, o4-mini UltraThink), обеспечивает отслеживание портфеля в реальном времени и включает движок для бумажной торговли (forward testing).

### Ключевые особенности

- **AI Trading Engine** — Генерация сценариев на GPT-5.2 с точками входа/выхода и анализом риска
- **UltraThink Reasoning** — o4-mini режим глубокого рассуждения для сложного анализа (VIP)
- **Paper Trading** — Система форвард-тестирования с симуляцией исполнения ордеров
- **Мультиплатформенность** — Telegram Mini App + адаптивный веб-интерфейс
- **Real-time данные** — Интеграция с Binance, CoinGecko, CryptoPanic
- **Платежи** — Telegram Stars, TON blockchain, криптоплатежи

## Возможности

### AI и Аналитика
- **GPT-5.2** для генерации фьючерсных сценариев (глубокий анализ)
- **GPT-5.1** флагманская модель для Premium/VIP анализа
- **o4-mini UltraThink** режим рассуждений для глубоких инсайтов
- **DeepSeek Reasoner** для экономичного анализа
- Vision API для распознавания паттернов на графиках
- Supervisor AI для макро-анализа рынка
- Технические индикаторы (RSI, MACD, Bollinger Bands, Moving Averages)
- Распознавание свечных паттернов (Doji, Hammer, Engulfing и др.)

### Торговые инструменты
- Фьючерсные сценарии с entry, TP1/TP2/TP3 и stop-loss уровнями
- Отслеживание портфеля с мониторингом маржи и нереализованного P&L
- Анализ Risk/Reward для каждой позиции
- Forward testing с симуляцией сделок
- Статистика производительности и win rate

### Платформа
- Telegram Mini App (WebApp внутри Telegram)
- Адаптивный веб-интерфейс для десктопа
- Real-time обновления через WebSocket
- Мультиязычность (English, Русский)
- Реферальная система с revenue share
- Геймификация с SYNTRA points

## Технологический стек

### Backend
| Технология | Назначение |
|------------|------------|
| Python 3.12 | Основной язык |
| FastAPI | REST API фреймворк |
| SQLAlchemy 2.0 | Async ORM |
| PostgreSQL 16 | Основная БД |
| Redis | Кэширование |
| Alembic | Миграции БД |
| Uvicorn | ASGI сервер |

### Frontend
| Технология | Назначение |
|------------|------------|
| Next.js 14 | React фреймворк |
| TypeScript | Типизация |
| Tailwind CSS | Стилизация |
| Lightweight Charts | Торговые графики |
| TonConnect | Web3 интеграция |

### Внешние API
| Сервис | Назначение |
|--------|------------|
| OpenAI GPT-5.2/5.1 | Генерация сценариев, анализ |
| OpenAI o4-mini | UltraThink режим рассуждений |
| DeepSeek | Экономичный AI (Free/Basic) |
| OpenAI Vision | Распознавание паттернов на графиках |
| Binance API | OHLC данные, funding rates |
| CoinGecko | Цены, капитализация |
| CryptoPanic | Криптоновости |
| Telegram Bot API | Бот и Mini App |

### Тарифы
| Тариф | Цена | AI модели | Возможности |
|-------|------|-----------|-------------|
| Free | $0 | GPT-4o-mini + DeepSeek | Базовый анализ, 2 запроса/день |
| Basic | $9.99/мес | + DeepSeek Reasoner | Паттерны, funding rates, 10 запросов |
| Premium | $24.99/мес | GPT-5-mini + GPT-5.1 | Все функции, фьючерс сигналы |
| VIP | $49.99/мес | GPT-5.1 + o4-mini UltraThink | Приоритет, глубокий анализ, 30 запросов |

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Telegram   │  │   Next.js   │  │   Telegram Bot      │  │
│  │  Mini App   │  │   Web App   │  │   (Notifications)   │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼────────────────┼────────────────────┼─────────────┘
          │                │                    │
          ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                      API LAYER (FastAPI)                     │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐ │
│  │    Auth    │  │   Trading  │  │   WebSocket Events     │ │
│  │  (OAuth2)  │  │    API     │  │   (Real-time)          │ │
│  └────────────┘  └────────────┘  └────────────────────────┘ │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   BUSINESS LOGIC LAYER                       │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │ Futures        │  │  Forward Test  │  │   Payments    │  │
│  │ Analysis       │  │  Engine        │  │   Gateway     │  │
│  │ (AI Scenarios) │  │  (Paper Trade) │  │               │  │
│  └────────────────┘  └────────────────┘  └───────────────┘  │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │ Supervisor AI  │  │  Statistics    │  │   Referral    │  │
│  │ (Macro View)   │  │  & Analytics   │  │   System      │  │
│  └────────────────┘  └────────────────┘  └───────────────┘  │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA ACCESS LAYER                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  PostgreSQL  │  │    Redis     │  │  External APIs   │   │
│  │  (Primary)   │  │   (Cache)    │  │  (Binance, etc.) │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Структура проекта

```
SyntraAI/
├── src/                      # Backend исходный код
│   ├── api/                  # FastAPI маршруты (30+ endpoints)
│   ├── services/             # Бизнес-логика (50+ сервисов)
│   │   ├── futures_analysis/ # AI генерация сценариев
│   │   ├── forward_test/     # Движок paper trading
│   │   └── stats/            # Торговая статистика
│   ├── database/             # SQLAlchemy модели и CRUD
│   ├── learning/             # ML модели и калибровка
│   └── cache/                # Redis кэширование
├── frontend/                 # Next.js приложение
│   ├── app/                  # App router страницы
│   ├── components/           # React компоненты
│   └── lib/                  # Утилиты и хуки
├── config/                   # Конфигурационные файлы
├── alembic/                  # Миграции БД (60+)
├── tests/                    # Тесты (38+)
├── docs/                     # Документация
├── api_server.py             # FastAPI entry point
├── bot.py                    # Telegram bot entry point
├── docker-compose.yml        # Docker конфигурация
└── requirements.txt          # Python зависимости
```

## Быстрый старт

### Требования
- Python 3.12+
- Node.js 18+
- PostgreSQL 16
- Redis

### Настройка Backend

```bash
# Клонирование репозитория
git clone https://github.com/your-username/SyntraAI.git
cd SyntraAI

# Создание виртуального окружения
python3 -m venv .venv
source .venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Настройка окружения
cp .env.example .env
# Отредактируйте .env с вашими API ключами

# Применение миграций
alembic upgrade head

# Запуск API сервера
python api_server.py
```

### Настройка Frontend

```bash
cd frontend

# Установка зависимостей
npm install

# Запуск dev сервера
npm run dev
```

### Docker

```bash
# Запуск всех сервисов
docker-compose up -d

# Применение миграций
docker-compose exec api alembic upgrade head
```

## API Endpoints

### Торговля
- `POST /api/futures/scenarios` — Генерация AI торговых сценариев
- `GET /api/futures/scenarios/{coin}` — Получить сценарии для монеты
- `POST /api/forward-test/start` — Начать paper trading сессию

### Портфель
- `GET /api/portfolio/positions` — Активные позиции
- `GET /api/portfolio/margin` — Маржа и нереализованный P&L
- `GET /api/stats/trading` — Торговая статистика

### Рыночные данные
- `GET /api/market/price/{coin}` — Текущая цена
- `GET /api/market/analysis/{coin}` — Полный анализ рынка
- `GET /api/market/news` — Криптоновости

## Документация

- [Архитектура](docs/ARCHITECTURE.md) — Дизайн системы и компоненты
- [API Документация](docs/API_DOCS.md) — Спецификации endpoints
- [Руководство разработчика](docs/DEVELOPMENT.md) — Code style и best practices
- [Деплоймент](docs/DEPLOYMENT.md) — Руководство по развёртыванию

## Лицензия

Proprietary — Все права защищены

## Контакты

По вопросам и предложениям о сотрудничестве — GitHub issues.
