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
**Status:** PENDING

### Files:
- `services/stats_client.py`
- Update `config.py`

---

## Phase 6: Telegram Inline UI
**Status:** PENDING

### Files:
- `bot/handlers/stats.py`
- `bot/keyboards/stats_kb.py`

---

## Phase 7: Cache Invalidation
**Status:** PENDING

---

## Change Log

| Date | Phase | Change |
|------|-------|--------|
| 2025-12-20 | 1 | Phase 1 COMPLETED - enums, fields, migration |
| 2025-12-20 | 2 | Phase 2 COMPLETED - indexes applied |
| 2025-12-20 | 3 | Phase 3 COMPLETED - Stats Service module |
| 2025-12-20 | 4 | Phase 4 COMPLETED - Stats API endpoints |

---

## Next Steps
1. Phase 5: Создать StatsClient в Futures Bot
2. Phase 6: Telegram Inline UI
3. Phase 7: Cache Invalidation
