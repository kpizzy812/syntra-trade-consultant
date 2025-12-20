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
- [x] Добавить новые поля в TradeOutcome model:
  - [x] `origin: TradeOrigin` (nullable для backward compat)
  - [x] `payload_hash: str` (sha256[:32] канонического payload)
  - [x] `hit_tp1, hit_tp2, hit_tp3: bool` (факт достижения TP)
  - [x] `tp1_price, tp2_price, tp3_price: float` (цены TP)
  - [x] `invalidated: bool` (soft delete)
  - [x] `replaced_by_id: int` (FK для audit trail)
  - [x] `invalidation_reason: str`
  - [x] `exchange: str` (для фильтров)
  - [x] `account_id: str`
  - [x] `qty, notional_usd: float` (размер позиции)
  - [x] `opened_at, closed_at: datetime` (время сделки)
  - [x] `fees_usd: float` (комиссии)
- [x] Создать Alembic миграцию

### Created Files:
- `src/core/__init__.py`
- `src/core/enums.py` - OutcomeType, TradeOrigin, FunnelStage, SuppressionReason, ViewedReason
- `alembic/versions/c3d4e5f6g7h9_add_stats_system_fields.py`

### Modified Files:
- `src/database/models.py` - добавлены поля в TradeOutcome + новые индексы

### New Indexes:
- `ix_outcomes_closed_at` - основной индекс для time-based queries
- `ix_outcomes_origin_closed` - фильтр по origin + time
- `ix_outcomes_exchange_closed` - фильтр по exchange + time
- `ix_outcomes_origin` - фильтр по origin
- `ix_outcomes_exchange` - фильтр по exchange

---

## Phase 2: Database Indexes
**Status:** INCLUDED IN PHASE 1

Индексы добавлены в миграцию Phase 1:
- [x] Индексы для stats queries включены в c3d4e5f6g7h9 миграцию
- [ ] Применить миграцию: `alembic upgrade head`
- [ ] Проверить EXPLAIN на тестовых запросах

---

## Phase 3: Stats Service в SyntraAI
**Status:** PENDING

### Files to create:
- `src/services/stats/__init__.py`
- `src/services/stats/service.py`
- `src/services/stats/trading.py`
- `src/services/stats/learning.py`
- `src/services/stats/funnel.py`
- `src/services/stats/cache.py`
- `src/services/stats/schemas.py`

---

## Phase 4: Stats API Endpoints
**Status:** PENDING

### Endpoints:
- GET /api/stats/trading/overview
- GET /api/stats/trading/outcomes
- GET /api/stats/learning/archetypes
- GET /api/stats/learning/archetypes/{archetype}
- GET /api/stats/learning/gates
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
| 2025-12-20 | 1 | Started Phase 1 implementation |
| 2025-12-20 | 1 | Created src/core/enums.py with all enums |
| 2025-12-20 | 1 | Added Stats System fields to TradeOutcome model |
| 2025-12-20 | 1 | Created Alembic migration c3d4e5f6g7h9 |
| 2025-12-20 | 1 | Phase 1 COMPLETED |

---

## Next Steps
1. Применить миграцию: `cd SyntraAI && alembic upgrade head`
2. Начать Phase 3: создание Stats Service
