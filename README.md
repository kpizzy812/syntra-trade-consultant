<p align="center">
  <img src="assets/banner.jpeg" alt="SyntraAI Banner" width="100%">
</p>

# SyntraAI

> AI-powered crypto trading assistant with real-time market data and unique personality

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://postgresql.org)

**[Website](https://ai.syntratrade.xyz)** | **[Telegram Mini App](https://t.me/SyntraAI_bot?startapp)** | [Russian version](README_RU.md)

## Overview

**SyntraAI** is an AI-powered crypto trading assistant with a distinctive sarcastic personality. Unlike generic chatbots, Syntra provides real-time market analysis using **OpenAI Function Calling** to fetch live data from multiple sources, combines professional-grade technical analysis with cynical humor, and offers advanced features like futures scenario generation and paper trading.

### What Makes Syntra Different

- **Real Personality** — Not a generic bot. Syntra is a self-aware, cynical AI analyst who delivers serious insights with sharp wit
- **Live Data via Tool Calling** — AI fetches real-time prices, indicators, news through function calling (not static responses)
- **Multi-Source Intelligence** — CoinGecko, Binance, CryptoPanic, DexScreener, CoinMetrics combined
- **Context Memory** — Remembers conversation history for coherent multi-turn analysis
- **Professional + Fun** — Technical analysis with personality (think: Bloomberg Terminal meets a sarcastic friend)

## Features

### AI Chat Assistant
- **GPT-5.2 / GPT-5.1** powered conversations with memory
- **OpenAI Function Calling** for real-time data retrieval
- Unique cynical personality with professional insights
- Multi-language support (English, Russian)

### Real-Time Market Data (Tool Calling)
- **Live Prices** — Any crypto via CoinGecko, CoinMarketCap, DexScreener
- **Technical Indicators** — RSI, MACD, Bollinger Bands, Moving Averages
- **Candlestick Patterns** — Doji, Hammer, Engulfing, Morning Star, etc.
- **Fear & Greed Index** — Market sentiment
- **Crypto News** — Latest headlines from CryptoPanic
- **Funding Rates** — Binance Futures sentiment
- **On-Chain Metrics** — Active addresses, exchange flows (CoinMetrics)
- **Market Cycles** — Rainbow Chart, Pi Cycle Top indicator

### Chart Analysis (Vision)
- Screenshot analysis with GPT-4 Vision
- Automatic coin detection from charts
- Pattern recognition with real market data overlay

### Futures Scenarios (Premium)
- AI-generated trading scenarios with entry/exit points
- TP1/TP2/TP3 targets and stop-loss levels
- Risk/Reward analysis
- Confidence scoring based on market conditions

### Paper Trading (Forward Test)
- Test scenarios without real money
- Simulated order fills
- Portfolio tracking with margin monitoring
- Performance statistics and win rate

### Platform
- **Telegram Mini App** — Primary interface inside Telegram
- **Web Application** — Responsive Next.js interface
- **Landing Page** — Marketing site at ai.syntratrade.xyz

## AI Models

| Tier | Models | Use Case |
|------|--------|----------|
| Free/Basic | GPT-4o-mini + DeepSeek | Chat, basic analysis |
| Premium | GPT-5-mini + GPT-5.1 | Advanced analysis, futures |
| VIP | GPT-5.1 + o4-mini UltraThink | Deep reasoning, priority |

**Scenario Generation:** GPT-5.2 (heavy reasoning)

## Tech Stack

### Backend
| Technology | Purpose |
|------------|---------|
| Python 3.12 | Core language |
| FastAPI | REST API + WebSocket |
| SQLAlchemy 2.0 | Async ORM |
| PostgreSQL 16 | Primary database |
| Redis | Caching layer |
| Alembic | Database migrations |

### Frontend
| Technology | Purpose |
|------------|---------|
| Next.js 14 | React framework |
| TypeScript | Type safety |
| Tailwind CSS | Styling |
| Lightweight Charts | Trading charts |
| TonConnect | Web3 wallet |

### Integrations
| Service | Purpose |
|---------|---------|
| OpenAI | GPT-5.x, Vision, Function Calling |
| DeepSeek | Cost-effective AI for lower tiers |
| Binance API | OHLC, funding rates, liquidations |
| CoinGecko | Prices, market cap, historical data |
| CoinMarketCap | Backup price source |
| DexScreener | DEX token data |
| CryptoPanic | Crypto news aggregation |
| CoinMetrics | On-chain analytics |

### Payments
- Telegram Stars
- TON blockchain
- NOWPayments (crypto)

## Architecture

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
│  │    Auth    │  │  AI Chat   │  │   Market Data APIs     │ │
│  │  (OAuth2)  │  │ (Streaming)│  │   (Tool Calling)       │ │
│  └────────────┘  └────────────┘  └────────────────────────┘ │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   BUSINESS LOGIC LAYER                       │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │ OpenAI Service │  │  Crypto Tools  │  │   Technical   │  │
│  │ (Function Call)│  │  (10+ sources) │  │   Analysis    │  │
│  └────────────────┘  └────────────────┘  └───────────────┘  │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │ Futures Engine │  │  Forward Test  │  │   Payments    │  │
│  │ (Scenarios)    │  │  (Paper Trade) │  │   Gateway     │  │
│  └────────────────┘  └────────────────┘  └───────────────┘  │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA ACCESS LAYER                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  PostgreSQL  │  │    Redis     │  │  External APIs   │   │
│  │  (Primary)   │  │   (Cache)    │  │  (10+ services)  │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
SyntraAI/
├── src/
│   ├── api/                  # FastAPI routes (30+ endpoints)
│   │   ├── chat.py           # AI chat with streaming
│   │   ├── market.py         # Market data endpoints
│   │   ├── futures_*.py      # Futures scenarios
│   │   └── ...
│   ├── services/
│   │   ├── openai_service.py # AI with function calling
│   │   ├── crypto_tools.py   # 10+ tool definitions
│   │   ├── coingecko_service.py
│   │   ├── binance_service.py
│   │   ├── technical_indicators.py
│   │   ├── candlestick_patterns.py
│   │   └── ...
│   ├── database/             # SQLAlchemy models
│   └── cache/                # Redis caching
├── frontend/                 # Next.js application
├── config/
│   ├── prompts.py            # Syntra personality
│   ├── limits.py             # Tier limits
│   └── model_router.py       # AI model selection
├── alembic/                  # DB migrations (60+)
└── tests/                    # Test suite
```

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js 18+
- PostgreSQL 16
- Redis

### Quick Start

```bash
# Clone
git clone https://github.com/your-username/SyntraAI.git
cd SyntraAI

# Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Configure API keys
alembic upgrade head
python api_server.py

# Frontend
cd frontend
npm install
npm run dev
```

## Subscription Tiers

| Tier | Price | Requests | Features |
|------|-------|----------|----------|
| Free | $0 | 2/day | Basic chat, prices, news |
| Basic | $9.99/mo | 10/day | + Patterns, funding rates, memory |
| Premium | $24.99/mo | 15/day | + Futures signals, full analysis |
| VIP | $49.99/mo | 30/day | + UltraThink reasoning, priority |

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API Documentation](docs/API_DOCS.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [Deployment](docs/DEPLOYMENT.md)

## License

Proprietary — All rights reserved
