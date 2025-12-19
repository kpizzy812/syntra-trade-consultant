"""
Forward Test Enums

Нормализованные состояния для state machine и результатов.
Используются как PostgreSQL ENUM types.
"""
from enum import Enum


class ScenarioState(str, Enum):
    """
    State machine состояния сценария.

    Lifecycle:
    - ARMED: сценарий создан, ждёт activation condition
    - TRIGGERED: activation выполнено, ждём entry fill
    - ENTERED: вошли в позицию
    - TP1: milestone (partial close), продолжаем мониторинг
    - TP2/TP3/SL/BE/EXPIRED: terminal states
    - INVALID: сценарий невалидный (ошибка генерации)
    """
    ARMED = "armed"
    TRIGGERED = "triggered"
    ENTERED = "entered"
    TP1 = "tp1"       # milestone, НЕ terminal!
    TP2 = "tp2"       # terminal
    TP3 = "tp3"       # terminal
    SL = "sl"         # terminal
    BE = "be"         # terminal (breakeven after TP1 = profit!)
    EXPIRED = "expired"  # terminal
    INVALID = "invalid"  # terminal

    @classmethod
    def active_states(cls) -> list["ScenarioState"]:
        """Состояния требующие мониторинга."""
        return [cls.ARMED, cls.TRIGGERED, cls.ENTERED, cls.TP1]

    @classmethod
    def terminal_states(cls) -> list["ScenarioState"]:
        """Финальные состояния (outcome создан)."""
        return [cls.TP2, cls.TP3, cls.SL, cls.BE, cls.EXPIRED, cls.INVALID]

    def is_terminal(self) -> bool:
        """Проверка на финальное состояние."""
        return self in self.terminal_states()

    def is_active(self) -> bool:
        """Проверка на активное состояние."""
        return self in self.active_states()


class TerminalState(str, Enum):
    """
    Финальные состояния для outcome.

    Важно: TP1 НЕ входит - это milestone!
    BE после TP1 = profit (realized_r_from_tp1 > 0).
    """
    TP2 = "tp2"
    TP3 = "tp3"
    SL = "sl"
    BE = "be"         # BE после TP1 = profit!
    EXPIRED = "expired"

    def is_profitable_exit(self) -> bool:
        """TP2/TP3 всегда профит, BE может быть профитом после TP1."""
        return self in (self.TP2, self.TP3)


class OutcomeResult(str, Enum):
    """
    Результат для отчётности.

    BREAKEVEN используется только для SL → BE без TP1.
    BE после TP1 = WIN!
    """
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"  # редкий случай: BE без TP1
    EXPIRED = "expired"


class PnLClass(str, Enum):
    """
    Классификация PnL по total_r.

    Используется для простой фильтрации в отчётах.
    """
    WIN = "win"       # total_r > 0.05
    LOSS = "loss"     # total_r < -0.05
    FLAT = "flat"     # -0.05 <= total_r <= 0.05

    @classmethod
    def from_r(cls, total_r: float) -> "PnLClass":
        """Определить класс по R-multiple."""
        if total_r > 0.05:
            return cls.WIN
        elif total_r < -0.05:
            return cls.LOSS
        else:
            return cls.FLAT


class Bias(str, Enum):
    """Направление сценария."""
    LONG = "long"
    SHORT = "short"

    def direction_sign(self) -> int:
        """Знак для расчёта R: +1 для long, -1 для short."""
        return 1 if self == self.LONG else -1

    def opposite(self) -> "Bias":
        """Обратное направление."""
        return self.SHORT if self == self.LONG else self.LONG


class FillModel(str, Enum):
    """
    Модель fills для симуляции.

    MVP: touch_fill (цена коснулась = fill)
    Future: prob_fill_by_vol (вероятность по объёму)
    """
    TOUCH_FILL = "touch_fill"
    PROB_FILL_BY_VOL = "prob_fill_by_vol"


class EventType(str, Enum):
    """Типы событий для scenario_events."""
    TRIGGER_HIT = "trigger_hit"
    ENTRY_FILL = "entry_fill"
    TP1_HIT = "tp1_hit"
    TP2_HIT = "tp2_hit"
    TP3_HIT = "tp3_hit"
    SL_HIT = "sl_hit"
    BE_HIT = "be_hit"
    EXPIRED = "expired"
    BE_MOVED = "be_moved"  # SL сдвинут в BE после TP1
