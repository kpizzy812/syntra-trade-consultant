# 🗄️ Database Partitioning Strategy

**Дата**: 2025-01-25
**Статус**: 📋 Стратегический план (не реализовано)
**База данных**: PostgreSQL 14+

---

## 🎯 Цель

Подготовить базу данных к масштабированию до **100,000+ пользователей** и **миллионов сообщений**.

**Проблема**: По мере роста пользователей, таблицы `chat_history` и `cost_tracking` вырастут до миллионов строк, что приведёт к:
- 🐌 Медленным запросам (full table scans)
- 💾 Большим индексам (B-tree индексы перестанут помещаться в RAM)
- 🔧 Сложному обслуживанию (VACUUM, backups займут часы)

**Решение**: Time-based partitioning (разделение по времени).

---

## 📊 Анализ таблиц

### 1. 🔥 **chat_history** (HIGH PRIORITY)

**Текущая структура**:
```sql
CREATE TABLE chat_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    role VARCHAR(20),
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Рост данных**:
- 1,000 users × 5 messages/day = 5,000 messages/day
- 10,000 users × 5 messages/day = 50,000 messages/day
- 100,000 users × 5 messages/day = 500,000 messages/day

**Годовой объём (100K users)**:
- 500K × 365 = **182 million rows/year** 🚨

**Размер данных**:
- Average message: 500 chars = ~500 bytes
- 182M rows × 500 bytes = **~91 GB/year**
- + индексы (~30%) = **~118 GB/year**

**Вывод**: КРИТИЧНО для partitioning! 🔥

---

### 2. 🔥 **cost_tracking** (HIGH PRIORITY)

**Текущая структура**:
```sql
CREATE TABLE cost_tracking (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    model VARCHAR(50),
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd NUMERIC(10, 6),
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Рост данных**:
- 100,000 users × 5 requests/day = 500,000 rows/day
- 500K × 365 = **182 million rows/year** 🚨

**Размер данных**:
- Row size: ~100 bytes
- 182M × 100 bytes = **~18 GB/year**
- + индексы = **~23 GB/year**

**Вывод**: Также критично для partitioning! 🔥

---

### 3. ⚠️ **balance_transactions** (MEDIUM PRIORITY)

**Рост данных**:
- Растёт с каждой транзакцией (earn/withdraw/spend)
- Медленнее чем chat/cost (~1,000 transactions/day max)
- 365K rows/year = **небольшая таблица**

**Вывод**: Можно отложить partitioning до 1M+ rows.

---

### 4. ✅ **Остальные таблицы** (LOW PRIORITY)

**Медленный рост**:
- `users` - растёт линейно (1 row = 1 user)
- `subscriptions` - 1 row per user
- `payments` - небольшой volume (~1-2K/day max)
- `referrals` - медленный рост

**Вывод**: Партиционирование НЕ требуется в ближайшие 2-3 года.

---

## 🛠️ Partitioning Strategy

### Выбор метода: **Time-based Partitioning (по месяцам)**

**Почему по месяцам?**
- ✅ Легко удалять старые данные (DROP partition вместо DELETE)
- ✅ Быстрые запросы (PostgreSQL автоматически выбирает нужные партиции)
- ✅ Меньшие индексы (индексы создаются per partition)
- ✅ Проще backup (можно бэкапить только новые партиции)

**Альтернативы (НЕ выбраны)**:
- ❌ По дням - слишком много партиций (365/year)
- ❌ По годам - партиции всё равно будут огромными
- ❌ По user_id ranges - неравномерное распределение (VIP users генерируют больше данных)

---

## 📝 Implementation Plan

### Phase 1: chat_history Partitioning

#### Step 1: Создать partitioned table

```sql
-- 1. Переименовать существующую таблицу
ALTER TABLE chat_history RENAME TO chat_history_old;

-- 2. Создать новую partitioned table
CREATE TABLE chat_history (
    id BIGSERIAL,
    user_id INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- 3. Создать индексы на partitioned table
CREATE INDEX idx_chat_history_user_created ON chat_history (user_id, created_at DESC);
CREATE INDEX idx_chat_history_created ON chat_history (created_at DESC);
```

#### Step 2: Создать партиции (retroactive + future)

```sql
-- Создать партиции для прошлых месяцев (если есть старые данные)
CREATE TABLE chat_history_2025_01 PARTITION OF chat_history
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE chat_history_2025_02 PARTITION OF chat_history
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');

-- Создать партиции на будущее (на 3-6 месяцев вперёд)
CREATE TABLE chat_history_2025_03 PARTITION OF chat_history
    FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');

CREATE TABLE chat_history_2025_04 PARTITION OF chat_history
    FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');

-- ... и так далее
```

#### Step 3: Миграция данных

```sql
-- Копировать данные из старой таблицы в новую (partitioned)
INSERT INTO chat_history
SELECT * FROM chat_history_old
ORDER BY created_at;  -- Важно для эффективной вставки в партиции

-- Проверить что все данные скопированы
SELECT COUNT(*) FROM chat_history_old;
SELECT COUNT(*) FROM chat_history;

-- Если всё ок - удалить старую таблицу (ОСТОРОЖНО!)
-- DROP TABLE chat_history_old;
```

**⚠️ ВАЖНО**: Миграцию делать в maintenance window (ночью/выходные), так как это долгая операция.

#### Step 4: Автоматическое создание партиций

**Проблема**: Нужно создавать новые партиции каждый месяц.

**Решение 1: pg_partman extension**
```sql
-- Установить pg_partman (автоматическое управление партициями)
CREATE EXTENSION pg_partman;

-- Настроить автоматическое создание партиций
SELECT partman.create_parent(
    'public.chat_history',
    'created_at',
    'native',
    'monthly'
);

-- Запланировать создание партиций на 3 месяца вперёд
UPDATE partman.part_config
SET premake = 3,
    optimize_constraint = 10
WHERE parent_table = 'public.chat_history';
```

**Решение 2: Cron job (если нет pg_partman)**
```python
# scripts/create_partitions.py
import psycopg2
from datetime import datetime, timedelta

def create_next_partition():
    # Создать партицию на следующий месяц
    next_month = datetime.now() + timedelta(days=32)
    partition_name = f"chat_history_{next_month.strftime('%Y_%m')}"

    sql = f"""
    CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF chat_history
        FOR VALUES FROM ('{next_month.strftime('%Y-%m-01')}')
        TO ('{(next_month + timedelta(days=31)).strftime('%Y-%m-01')}');
    """
    # Execute SQL...
```

**Crontab**:
```bash
# Запускать каждый месяц 1-го числа в 00:00
0 0 1 * * /path/to/venv/bin/python /path/to/create_partitions.py
```

---

### Phase 2: cost_tracking Partitioning

**Аналогично chat_history**:

```sql
-- 1. Rename old table
ALTER TABLE cost_tracking RENAME TO cost_tracking_old;

-- 2. Create partitioned table
CREATE TABLE cost_tracking (
    id BIGSERIAL,
    user_id INTEGER NOT NULL,
    model VARCHAR(50) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd NUMERIC(10, 6) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- 3. Create indexes
CREATE INDEX idx_cost_tracking_user_created ON cost_tracking (user_id, created_at DESC);
CREATE INDEX idx_cost_tracking_created ON cost_tracking (created_at DESC);

-- 4. Create partitions (same as chat_history)
CREATE TABLE cost_tracking_2025_01 PARTITION OF cost_tracking
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
-- ...

-- 5. Migrate data
INSERT INTO cost_tracking SELECT * FROM cost_tracking_old ORDER BY created_at;
```

---

## 📈 Benefits of Partitioning

### Before (non-partitioned):

```sql
-- Query: Get user's recent chat (last 7 days)
SELECT * FROM chat_history
WHERE user_id = 12345
  AND created_at > NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;

-- PostgreSQL must:
-- 1. Scan B-tree index for user_id (slow if table is large)
-- 2. Filter by created_at
-- 3. Sort results
-- Query time: ~500ms for 100M rows table
```

### After (partitioned by month):

```sql
-- Same query
SELECT * FROM chat_history
WHERE user_id = 12345
  AND created_at > NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;

-- PostgreSQL automatically:
-- 1. Identifies relevant partition (current month only)
-- 2. Scans ONLY that partition (~4M rows instead of 100M)
-- 3. Uses smaller index (fits in RAM)
-- Query time: ~50ms (10x faster!)
```

**Impact**:
- ✅ **10-100x faster queries** (depends on query selectivity)
- ✅ **Smaller indexes** (each partition has own index)
- ✅ **Faster VACUUM** (per partition instead of whole table)
- ✅ **Easy data retention** (DROP old partitions instead of DELETE)

---

## 🗑️ Data Retention Strategy

### Automatic Old Data Cleanup

**Требование**: Хранить chat history только за последние **6 месяцев**.

**Старые данные** (>6 months):
- Можно удалить (DROP partition)
- Или архивировать (DETACH + export to S3)

**Implementation**:

```sql
-- Удаление партиции (быстро, без нагрузки на БД)
DROP TABLE chat_history_2024_06;  -- Удаляет все данные за июнь 2024

-- ИЛИ архивирование (для соблюдения законов о хранении данных)
-- 1. DETACH partition (отсоединить от родительской таблицы)
ALTER TABLE chat_history DETACH PARTITION chat_history_2024_06;

-- 2. Export to CSV
COPY chat_history_2024_06 TO '/backups/chat_history_2024_06.csv' CSV HEADER;

-- 3. Upload to S3
-- aws s3 cp /backups/chat_history_2024_06.csv s3://syntra-archives/

-- 4. Drop local table
DROP TABLE chat_history_2024_06;
```

**Cron job для автоматической очистки**:
```python
# scripts/cleanup_old_partitions.py
from datetime import datetime, timedelta

# Удалить партиции старше 6 месяцев
retention_months = 6
cutoff_date = datetime.now() - timedelta(days=retention_months * 30)

# Find and drop old partitions
old_partition = f"chat_history_{cutoff_date.strftime('%Y_%m')}"
execute_sql(f"DROP TABLE IF EXISTS {old_partition} CASCADE;")
```

**Crontab**:
```bash
# Запускать каждый месяц 1-го числа в 01:00 (после создания новых партиций)
0 1 1 * * /path/to/venv/bin/python /path/to/cleanup_old_partitions.py
```

---

## 🚀 Migration Timeline

### Recommended Schedule:

**Milestone 1: При достижении 10,000 users**
- ✅ Начать планирование partitioning
- ✅ Тестировать на staging
- ⏳ Подготовить migration scripts

**Milestone 2: При достижении 50,000 users ИЛИ 10M rows в chat_history**
- 🚨 **ОБЯЗАТЕЛЬНО** внедрить partitioning
- Причина: После этого миграция станет очень долгой (часы)

**Milestone 3: При достижении 100,000+ users**
- ✅ Partitioning уже работает
- ✅ Регулярная очистка старых партиций
- ✅ Мониторинг размера партиций

---

## 📊 Monitoring & Maintenance

### Key Metrics to Track:

**1. Partition Size Monitoring**
```sql
-- Размер каждой партиции
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE tablename LIKE 'chat_history_%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**2. Query Performance**
```sql
-- Enable query tracking
ALTER DATABASE syntraai_bot SET log_min_duration_statement = 1000;  -- Log queries >1s

-- Check slow queries
SELECT query, calls, mean_exec_time, max_exec_time
FROM pg_stat_statements
WHERE query LIKE '%chat_history%'
ORDER BY mean_exec_time DESC
LIMIT 10;
```

**3. Partition Coverage**
```sql
-- Проверить что есть партиции на следующие 3 месяца
SELECT tablename
FROM pg_tables
WHERE tablename LIKE 'chat_history_%'
ORDER BY tablename DESC
LIMIT 6;
```

**Alert Rules (Grafana/Prometheus)**:
- 🚨 Alert if partition size > 10GB (создать индекс на большой партиции долго)
- 🚨 Alert if missing future partitions (<2 months ahead)
- 🚨 Alert if query time > 500ms (партиции не помогают?)

---

## 🛡️ Rollback Plan

**Если что-то пошло не так при миграции:**

```sql
-- 1. STOP application (чтобы новые данные не писались)

-- 2. Restore old table
DROP TABLE IF EXISTS chat_history;
ALTER TABLE chat_history_old RENAME TO chat_history;

-- 3. Recreate indexes
CREATE INDEX idx_chat_history_user_created ON chat_history (user_id, created_at DESC);

-- 4. START application

-- 5. Investigate issue, fix, retry migration
```

**Backup BEFORE migration**:
```bash
# Full backup перед миграцией
pg_dump -h localhost -U syntraai -d syntraai_bot -t chat_history -Fc -f chat_history_backup_$(date +%Y%m%d).dump

# Restore if needed:
# pg_restore -h localhost -U syntraai -d syntraai_bot -t chat_history chat_history_backup_20250125.dump
```

---

## 💡 Alternative: Third-party Solutions

Если не хотим управлять партициями вручную:

### 1. **TimescaleDB** (рекомендуется!)
- PostgreSQL extension для time-series data
- **Автоматический** partitioning
- Compression (экономия до 90% места)
- Continuous aggregates (precomputed stats)

**Pros**:
- ✅ Полностью автоматическое управление партициями
- ✅ Compression из коробки
- ✅ Совместимость с PostgreSQL

**Cons**:
- ❌ Requires extension install
- ❌ Небольшой overhead на learning curve

### 2. **Citus** (для масштабирования на несколько серверов)
- Distributed PostgreSQL
- Sharding + partitioning

**Pros**:
- ✅ Горизонтальное масштабирование (multi-server)

**Cons**:
- ❌ Очень сложная настройка
- ❌ Overkill для <1M users

---

## ✅ Summary

### Current Status (до 10K users):
- ✅ Single PostgreSQL instance БЕЗ partitioning
- ✅ Нормальная производительность

### Action Required (10K-50K users):
- ⏳ Подготовить partitioning scripts
- ⏳ Тестировать на staging

### Critical (>50K users OR >10M rows):
- 🚨 **ОБЯЗАТЕЛЬНО** внедрить partitioning
- 🚨 Иначе: медленные запросы, большие бэкапы, сложное обслуживание

### Recommended Stack:
- **PostgreSQL 14+** (native partitioning)
- **pg_partman** extension (автоматическое управление)
- **Cron jobs** для cleanup старых партиций
- **TimescaleDB** (опционально, если нужен compression)

---

**📅 Next Steps**:
1. [ ] Install pg_partman extension на production server
2. [ ] Написать migration scripts для chat_history
3. [ ] Протестировать migration на staging с реальными данными
4. [ ] Запланировать maintenance window для production migration
5. [ ] Setup monitoring (partition sizes, query performance)

**Время до реализации**: Когда достигнем **50K users** или **10M rows** в chat_history (что наступит раньше).
