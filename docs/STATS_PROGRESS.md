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
**Status:** PENDING

### Endpoints to create:
- GET /api/stats/trading/overview
- GET /api/stats/trading/outcomes
- GET /api/stats/trading/symbols
- GET /api/stats/learning/archetypes
- GET /api/stats/learning/archetypes/{archetype}
- GET /api/stats/learning/gates
- GET /api/stats/paper/overview
- GET /api/stats/paper/archetypes
- GET /api/stats/conversion

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

---

## Next Steps
1. Phase 4: Создать Stats API endpoints в `src/api/stats.py`
2. Phase 5: Создать StatsClient в Futures Bot
