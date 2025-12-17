# Scripts

Утилитные скрипты для обслуживания и миграции данных.

## 📋 Список скриптов

### fix_missing_referral_codes.py

**Назначение**: Генерация referral codes для существующих пользователей без кода.

**Когда использовать**:
- После обновления логики создания пользователей
- При миграции старых пользователей
- Если обнаружены пользователи без referral_code

**Запуск**:
```bash
source .venv/bin/activate
python scripts/fix_missing_referral_codes.py
```

**Что делает**:
1. Находит всех пользователей где `referral_code IS NULL`
2. Генерирует уникальный 8-символьный код для каждого
3. Сохраняет в базу данных
4. Логирует результаты с подробностями

**Безопасность**:
- ✅ Безопасно запускать многократно (идемпотентный)
- ✅ Только обновляет пользователей без кода
- ✅ Проверяет уникальность кодов
- ✅ Транзакционный - откатывается при ошибках

**Пример вывода**:
```
2025-12-04 13:48:23.373 | INFO | 🔍 Checking for users without referral codes...
2025-12-04 13:48:23.590 | INFO | ✅ All users already have referral codes!
```

Или:
```
2025-12-04 13:48:23.373 | INFO | 🔍 Checking for users without referral codes...
2025-12-04 13:48:23.445 | INFO | 📝 Found 5 users without referral code
2025-12-04 13:48:23.500 | INFO | ✅ Generated referral code ABC12XYZ for user 123 (telegram_id=123456, username=@john)
2025-12-04 13:48:23.555 | INFO | ✅ Generated referral code DEF34UVW for user 124 (email=user@example.com, username=N/A)
...
2025-12-04 13:48:23.700 | INFO | 🎉 Successfully generated 5 referral codes!
2025-12-04 13:48:23.750 | INFO | ✅ All users now have referral codes!
```

**Проверка результатов**:
```bash
python -c "
import asyncio
from sqlalchemy import select, func
from src.database.engine import get_session_maker
from src.database.models import User

async def check():
    session_maker = get_session_maker()
    async with session_maker() as session:
        stmt = select(func.count(User.id)).where(User.referral_code.is_(None))
        result = await session.execute(stmt)
        count = result.scalar()
        print(f'Users without referral_code: {count}')

asyncio.run(check())
"
```

---

## 🛠️ Добавление новых скриптов

При создании нового скрипта:

1. **Структура**:
```python
"""
Script description

What it does and when to use it
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.database.engine import get_session_maker

async def main():
    logger.info("Starting script...")
    session_maker = get_session_maker()
    async with session_maker() as session:
        # Your logic here
        pass

if __name__ == "__main__":
    asyncio.run(main())
```

2. **Именование**: `action_description.py` (например, `fix_missing_data.py`)

3. **Документация**: Добавить описание в этот README

4. **Безопасность**:
   - Всегда используй транзакции
   - Проверяй данные перед изменением
   - Логируй все операции
   - Делай скрипты идемпотентными (безопасно запускать повторно)

5. **Тестирование**:
   - Тестируй на dev окружении
   - Проверяй результаты в БД
   - Проверяй логи

---

## 📚 Связанные документы

- [REFERRAL_CODE_FIX_2025-12-04.md](../docs/REFERRAL_CODE_FIX_2025-12-04.md) - Исправление проблемы с referral codes
