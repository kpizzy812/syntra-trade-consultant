# Trading Statistics System - Progress Tracker

## Plan Reference
**Source:** `/Users/a1/.claude/plans/ancient-shimmying-pizza.md`

## Architecture: Push Outcomes (Variant A)
- Futures Bot PUSH TradeOutcome в SyntraAI через `/api/feedback/submit`
- SyntraAI = единственный источник истины для статистики
- Futures Bot GET статистику через Stats API

---

## Phase 1: Core Types и Enums
**Status:** COMPLETED

### Tasks:
- [x] Создать `src/core/enums.py` с OutcomeType, TradeOrigin, FunnelStage
- [x] Добавить новые поля в TradeOutcome model
- [x] Создать Alembic миграцию
- [x] Применить миграцию

### Created Files:
- `src/core/__init__.py`
- `src/core/enums.py` - OutcomeType, TradeOrigin, FunnelStage, SuppressionReason, ViewedReason
- `alembic/versions/c3d4e5f6g7h9_add_stats_system_fields.py`

---

## Phase 2: Database Indexes
**Status:** COMPLETED (included in Phase 1)

Индексы добавлены в миграцию Phase 1 и применены.

---

## Phase 3: Stats Service в SyntraAI
**Status:** COMPLETED

### Created Files:
- [x] `src/services/stats/__init__.py` - exports
- [x] `src/services/stats/service.py` - StatsService main class
- [x] `src/services/stats/trading.py` - trading aggregations
- [x] `src/services/stats/learning.py` - archetype stats
- [x] `src/services/stats/paper.py` - forward test stats
- [x] `src/services/stats/funnel.py` - conversion funnel
- [x] `src/services/stats/cache.py` - Redis caching layer
- [x] `src/services/stats/schemas.py` - Pydantic response models

### Key Features:
- TradingOverviewResponse с winrate, expectancy, PF, drawdown, streaks
- OutcomesDistributionResponse с hit_rates
- ArchetypeListResponse / ArchetypeDetailResponse
- ConversionFunnelResponse
- Wilson CI для winrate, t-interval для expectancy
- Versioned cache keys (no wildcard delete)

---

## Phase 4: Stats API Endpoints
**Status:** COMPLETED

### Endpoints created:
- [x] GET /api/stats/trading/overview
- [x] GET /api/stats/trading/outcomes
- [x] GET /api/stats/trading/symbols
- [x] GET /api/stats/learning/archetypes
- [x] GET /api/stats/learning/archetypes/{archetype}
- [x] GET /api/stats/learning/gates
- [x] GET /api/stats/paper/overview
- [x] GET /api/stats/paper/archetypes
- [x] GET /api/stats/conversion

### Created Files:
- `src/api/stats.py` - Stats API router с X-API-Key auth
- Updated `src/api/router.py` - зарегистрирован stats_router

---

## Phase 5: Stats Client в Futures Bot
**Status:** COMPLETED

### Created Files:
- [x] `services/stats_client.py` - StatsClient с production-ready features
- [x] Updated `config.py` - SYNTRA_STATS_* настройки

### Key Features:
- Lazy session init (connection pooling)
- Half-open circuit breaker
- Exponential backoff + jitter
- Graceful degradation (_safe методы)
- Singleton pattern (get_stats_client)
- Lifecycle management (close, context manager)

---

## Phase 6: Telegram Inline UI
**Status:** COMPLETED

### Created Files:
- [x] `bot/keyboards/stats_kb.py` - Stats keyboards (menu, period, pagination)
- [x] `bot/handlers/stats.py` - Stats handlers (overview, outcomes, archetypes, funnel, gates)
- [x] Updated `main.py` - registered stats_handler.router
- [x] Updated `bot/keyboards/settings_kb.py` - added Stats button

### Callback Handlers:
- `show_stats_menu` / `stats:menu` - главное меню
- `stats:overview` - trading overview
- `stats:outcomes` - exit distribution
- `stats:arch:page:{n}` - archetypes list (paginated)
- `stats:arch:detail:{name}` - archetype drilldown
- `stats:funnel` - conversion funnel
- `stats:gates` - EV gates status
- `stats:period:{period}` - period switcher (7d, 30d, 90d, 180d)

### Key Features:
- Period state per user (in-memory)
- Pagination for archetypes (5 per page)
- Graceful error handling (StatsServiceUnavailable)
- HTML formatting with emojis
- Lifecycle: close_stats_client() on shutdown

---

## Phase 7: Cache Invalidation
**Status:** COMPLETED

### Tasks:
- [x] В handler submit_feedback добавить вызов cache invalidation
- [x] Инвалидировать affected keys при получении TradeOutcome

### Modified Files:
- `src/api/feedback.py` - добавлен вызов on_trade_outcome_received после submit

### Key Features:
- Инвалидация при получении outcome данных (финальный submit)
- Пропуск duplicate requests
- Fire-and-forget pattern (не блокирует основной запрос)
- Graceful degradation (если Redis недоступен — просто логируем)
- Инвалидируются: overview, outcomes, archetypes (если есть)

---

## Change Log

| Date | Phase | Change |
|------|-------|--------|
| 2025-12-20 | 1 | Phase 1 COMPLETED - enums, fields, migration |
| 2025-12-20 | 2 | Phase 2 COMPLETED - indexes applied |
| 2025-12-20 | 3 | Phase 3 COMPLETED - Stats Service module |
| 2025-12-20 | 4 | Phase 4 COMPLETED - Stats API endpoints |
| 2025-12-20 | 5 | Phase 5 COMPLETED - StatsClient in Futures Bot |
| 2025-12-20 | 6 | Phase 6 COMPLETED - Telegram Inline UI |
| 2025-12-20 | 7 | Phase 7 COMPLETED - Cache Invalidation |

---

## Summary

All 7 phases of the Trading Statistics System have been completed:

1. ✅ Phase 1: Core Types и Enums
2. ✅ Phase 2: Database Indexes
3. ✅ Phase 3: Stats Service в SyntraAI
4. ✅ Phase 4: Stats API Endpoints
5. ✅ Phase 5: Stats Client в Futures Bot
6. ✅ Phase 6: Telegram Inline UI
7. ✅ Phase 7: Cache Invalidation

**Architecture:** Push Outcomes (Variant A)
- Futures Bot PUSH TradeOutcome в SyntraAI через `/api/feedback/submit`
- SyntraAI = единственный источник истины для статистики
- Futures Bot GET статистику через Stats API
- Versioned cache keys (INCR вместо wildcard DELETE)
