<p align="center">
  <img src="assets/banner.jpeg" alt="SyntraAI Banner" width="100%">
</p>

# SyntraAI

> AI-powered cryptocurrency trading platform with Telegram Mini App interface

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://postgresql.org)

**[Live Demo](https://ai.syntratrade.xyz)** | [Russian version](README_RU.md)

## Overview

**SyntraAI** is a full-stack SaaS platform for cryptocurrency traders, combining AI-powered market analysis with an intuitive Telegram Mini App interface. The system generates actionable trading scenarios for futures markets using latest AI models (GPT-5.2, o4-mini UltraThink), provides real-time portfolio tracking, and includes a comprehensive paper trading (forward testing) engine.

### Key Highlights

- **AI Trading Engine** — GPT-5.2 powered scenario generation with entry/exit points, risk/reward analysis
- **UltraThink Reasoning** — o4-mini deep reasoning mode for complex market analysis (VIP tier)
- **Paper Trading** — Forward testing system with simulated order fills and performance tracking
- **Multi-Platform** — Telegram Mini App + responsive web interface
- **Real-time Data** — Integration with Binance, CoinGecko, CryptoPanic for live market data
- **Payment System** — Telegram Stars, TON blockchain, and crypto payment gateways

## Features

### AI & Analysis
- **GPT-5.2** for futures scenario generation (heavy reasoning)
- **GPT-5.1** flagship model for Premium/VIP analysis
- **o4-mini UltraThink** reasoning mode for deep market insights
- **DeepSeek Reasoner** for cost-effective analysis
- Vision API for chart pattern recognition
- Supervisor AI for macro-level market analysis
- Technical indicators (RSI, MACD, Bollinger Bands, Moving Averages)
- Candlestick pattern detection (Doji, Hammer, Engulfing, etc.)

### Trading Tools
- Futures scenarios with entry, TP1/TP2/TP3, and stop-loss levels
- Portfolio tracking with margin and unrealized P&L monitoring
- Risk/Reward ratio analysis per position
- Forward testing with simulated trade execution
- Performance statistics and win rate tracking

### Platform
- Telegram Mini App (WebApp inside Telegram)
- Responsive web interface for desktop
- Real-time WebSocket updates
- Multi-language support (English, Russian)
- Referral system with revenue share
- Gamification with SYNTRA points

## Tech Stack

### Backend
| Technology | Purpose |
|------------|---------|
| Python 3.12 | Core language |
| FastAPI | REST API framework |
| SQLAlchemy 2.0 | Async ORM |
| PostgreSQL 16 | Primary database |
| Redis | Caching layer |
| Alembic | Database migrations |
| Uvicorn | ASGI server |

### Frontend
| Technology | Purpose |
|------------|---------|
| Next.js 14 | React framework |
| TypeScript | Type safety |
| Tailwind CSS | Styling |
| Lightweight Charts | Trading charts |
| TonConnect | Web3 wallet integration |

### External APIs
| Service | Purpose |
|---------|---------|
| OpenAI GPT-5.2/5.1 | Scenario generation, analysis |
| OpenAI o4-mini | UltraThink reasoning mode |
| DeepSeek | Cost-effective AI (Free/Basic tiers) |
| OpenAI Vision | Chart pattern recognition |
| Binance API | OHLC data, funding rates |
| CoinGecko | Price data, market cap |
| CryptoPanic | Crypto news feed |
| Telegram Bot API | Bot & Mini App |

### Subscription Tiers
| Tier | Price | AI Models | Features |
|------|-------|-----------|----------|
| Free | $0 | GPT-4o-mini + DeepSeek | Basic analysis, 2 req/day |
| Basic | $9.99/mo | + DeepSeek Reasoner | Patterns, funding rates, 10 req/day |
| Premium | $24.99/mo | GPT-5-mini + GPT-5.1 | Full features, futures signals |
| VIP | $49.99/mo | GPT-5.1 + o4-mini UltraThink | Priority, deep reasoning, 30 req/day |

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
│  │    Auth    │  │   Trading  │  │   WebSocket Events     │ │
│  │  (OAuth2)  │  │    API     │  │   (Real-time updates)  │ │
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

## Project Structure

```
SyntraAI/
├── src/                      # Backend source code
│   ├── api/                  # FastAPI routes (30+ endpoints)
│   ├── services/             # Business logic (50+ services)
│   │   ├── futures_analysis/ # AI scenario generation
│   │   ├── forward_test/     # Paper trading engine
│   │   └── stats/            # Trading statistics
│   ├── database/             # SQLAlchemy models & CRUD
│   ├── learning/             # ML models & calibration
│   └── cache/                # Redis caching layer
├── frontend/                 # Next.js application
│   ├── app/                  # App router pages
│   ├── components/           # React components
│   └── lib/                  # Utilities & hooks
├── config/                   # Configuration files
├── alembic/                  # Database migrations (60+)
├── tests/                    # Test suite (38+ tests)
├── docs/                     # Documentation
├── api_server.py             # FastAPI entry point
├── bot.py                    # Telegram bot entry point
├── docker-compose.yml        # Docker configuration
└── requirements.txt          # Python dependencies
```

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js 18+
- PostgreSQL 16
- Redis

### Backend Setup

```bash
# Clone repository
git clone https://github.com/your-username/SyntraAI.git
cd SyntraAI

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run migrations
alembic upgrade head

# Start API server
python api_server.py
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Docker

```bash
# Start all services
docker-compose up -d

# Apply migrations
docker-compose exec api alembic upgrade head
```

## API Endpoints

### Trading
- `POST /api/futures/scenarios` — Generate AI trading scenarios
- `GET /api/futures/scenarios/{coin}` — Get scenarios for a coin
- `POST /api/forward-test/start` — Start paper trading session

### Portfolio
- `GET /api/portfolio/positions` — Active positions
- `GET /api/portfolio/margin` — Margin & unrealized P&L
- `GET /api/stats/trading` — Trading statistics

### Market Data
- `GET /api/market/price/{coin}` — Current price
- `GET /api/market/analysis/{coin}` — Full market analysis
- `GET /api/market/news` — Latest crypto news

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — System design & components
- [API Documentation](docs/API_DOCS.md) — Endpoint specifications
- [Development Guide](docs/DEVELOPMENT.md) — Code style & best practices
- [Deployment](docs/DEPLOYMENT.md) — Production deployment guide

## License

Proprietary — All rights reserved

## Contact

For questions and collaboration inquiries, reach out via GitHub issues.
