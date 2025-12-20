"""
Core Enums - единые типы для всего стека Stats System.

Определяет:
- OutcomeType: терминальные типы закрытия сделок
- TradeOrigin: источник сделки (AI vs Manual)
- FunnelStage: стадии воронки конверсии
- SuppressionReason: причины НЕ показа сценария
- ViewedReason: результат показа сценария
"""

from enum import Enum


class OutcomeType(str, Enum):
    """Terminal outcome types - ЕДИНСТВЕННЫЙ источник истины.

    Описывает КАК именно закрылась сделка.

    Логика классификации:
    - SL до TP1 → SL_EARLY (полный лосс -1R)
    - BE после TP1 → BE_AFTER_TP1
    - Trail/lock profit после TP1 → STOP_IN_PROFIT
    - Финал на TP1/TP2/TP3 → TP1_FINAL/TP2_FINAL/TP3_FINAL
    - Ручное закрытие → MANUAL_CLOSE
    - Ликвидация → LIQUIDATION
    - Всё остальное → OTHER
    """

    SL_EARLY = "sl_early"  # SL до TP1
    BE_AFTER_TP1 = "be_after_tp1"  # BE после TP1
    STOP_IN_PROFIT = "stop_in_profit"  # Трейлинг стоп в профите
    TP1_FINAL = "tp1_final"  # Закрытие на TP1
    TP2_FINAL = "tp2_final"  # Закрытие на TP2
    TP3_FINAL = "tp3_final"  # Закрытие на TP3
    MANUAL_CLOSE = "manual_close"  # Ручное закрытие
    LIQUIDATION = "liquidation"  # Ликвидация
    OTHER = "other"  # Прочее (timeout, cancel, etc.)

    @classmethod
    def is_loss(cls, outcome: "OutcomeType") -> bool:
        """Проверить является ли outcome лоссом."""
        return outcome in (cls.SL_EARLY, cls.LIQUIDATION)

    @classmethod
    def is_win(cls, outcome: "OutcomeType") -> bool:
        """Проверить является ли outcome выигрышем."""
        return outcome in (
            cls.STOP_IN_PROFIT,
            cls.TP1_FINAL,
            cls.TP2_FINAL,
            cls.TP3_FINAL,
        )

    @classmethod
    def is_breakeven(cls, outcome: "OutcomeType") -> bool:
        """Проверить является ли outcome breakeven."""
        return outcome == cls.BE_AFTER_TP1


class TradeOrigin(str, Enum):
    """Источник сделки - откуда взялся трейд.

    Критично для:
    - Разделения AI vs Manual статистики
    - Фильтрации в Stats API
    - Оценки эффективности AI vs человека
    """

    AI_SCENARIO = "ai_scenario"  # Из AI сценария (автоматический)
    MANUAL = "manual"  # Ручной вход (пользователь сам)
    COPY_TRADE = "copy_trade"  # Копитрейдинг
    FORWARD_TEST = "forward_test"  # Paper trading / forward test


class FunnelStage(str, Enum):
    """Стадии воронки конверсии сценариев.

    ВАЖНО: VIEWED = реально показали пользователю!
    Если НЕ показали — это SUPPRESSED, не VIEWED.

    Правильная семантика:
    GENERATED:  1500  ─────────────────── 100%
        │
        ├─► SUPPRESSED: 700 (47%)  ← НЕ показали (gate, filter, limit)
        │
        └─► VIEWED: 800 (53%)      ← Реально показали
                │
                ├─► SELECTED: 250 (31% от viewed)
                │       │
                │       └─► PLACED: 150 (60% от selected)
                │               │
                │               └─► CLOSED: 145 (97% от placed)
                │
                └─► Skipped: 550 (69% от viewed) ← не логируем, вычисляем
    """

    GENERATED = "generated"  # Сценарий сгенерирован
    SUPPRESSED = "suppressed"  # НЕ показан (filtered/blocked)
    VIEWED = "viewed"  # Реально показан пользователю
    SELECTED = "selected"  # Пользователь выбрал для входа
    PLACED = "placed"  # Ордер размещён на бирже
    CLOSED = "closed"  # Сделка закрыта


class SuppressionReason(str, Enum):
    """Причина почему сценарий НЕ был показан пользователю.

    Логируется в stage=SUPPRESSED, НЕ в VIEWED!
    Это важно для корректной метрики VIEWED = % реально показанных.
    """

    BLOCKED_BY_GATE = "blocked_by_gate"  # EV gate заблокировал
    RATE_LIMITED = "rate_limited"  # Лимит запросов
    USER_INACTIVE = "user_inactive"  # Пользователь не активен
    FILTERED_QUALITY = "filtered_quality"  # Не прошёл quality filter
    DUPLICATE = "duplicate"  # Уже показывали похожий


class ViewedReason(str, Enum):
    """Результат показа сценария пользователю (для VIEWED stage).

    Отличаем успешную доставку от failed delivery.
    """

    DELIVERED = "delivered"  # Успешно доставлено
    DELIVERY_FAILED = "delivery_failed"  # Telegram вернул ошибку
