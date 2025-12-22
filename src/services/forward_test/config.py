"""
Forward Test Configuration

Defaults для forward testing системы.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class SlippageConfig:
    """Конфигурация slippage и fees."""
    entry_bps: float = 3.0      # slippage на вход (basis points)
    exit_bps: float = 3.0       # slippage на выход
    fees_bps: float = 2.0       # комиссии (maker/taker avg)
    spread_buffer_bps: float = 5.0  # буфер для touch → fill


@dataclass
class UniverseConfig:
    """Universe для мониторинга."""
    symbols: List[str] = field(
        default_factory=lambda: ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    )
    timeframes: List[str] = field(default_factory=lambda: ["4h"])
    modes: List[str] = field(default_factory=lambda: ["standard"])


@dataclass
class RetentionConfig:
    """Настройки хранения данных (0 = хранить вечно)."""
    snapshots_days: int = 0     # хранить вечно (нужны для trade cards)
    events_days: int = 30       # 30 дней (debug trace, много данных)
    outcomes_days: int = 0      # хранить вечно (для all-time stats)


@dataclass
class MonitorConfig:
    """Настройки мониторинга."""
    interval_sec: int = 60          # интервал тика
    candle_lag_alert_sec: int = 180  # алерт если лаг свечей > N секунд
    lock_ttl_sec: int = 90          # TTL для distributed lock


@dataclass
class ScheduleConfig:
    """Расписание jobs (UTC)."""
    generation_hours: List[int] = field(
        default_factory=lambda: [0, 6, 12, 18]
    )
    aggregation_hour: int = 23
    aggregation_minute: int = 55
    telegram_report_hour: int = 23
    telegram_report_minute: int = 58
    cleanup_hour: int = 4
    cleanup_minute: int = 0


@dataclass
class LearningGatesConfig:
    """Gates для Learning integration."""
    paper_wr_gate: int = 30      # N для WR калибровки
    paper_ev_gate: int = 50      # N для EV калибровки
    paper_sl_opt_gate: int = 200  # N для SL/TP suggestions
    real_override_gate: int = 10  # N для override paper → real
    paper_weight: float = 0.3    # weight paper vs real
    paper_half_life_days: int = 30   # half-life для paper decay
    real_half_life_days: int = 90    # half-life для real decay


@dataclass
class PortfolioConfig:
    """
    Конфигурация Portfolio Mode.

    Реалистичная симуляция портфеля с лимитами позиций и риска.
    """
    enabled: bool = True

    # Position limits
    max_open_positions: int = 3
    max_total_risk_r: float = 1.0          # Максимальный суммарный риск в R

    # Risk mapping: 1R = r_to_pct % депозита
    r_to_pct: float = 0.01                 # 1R = 1% (НЕ /100, явно!)

    # Candidate pool
    max_active_candidates: int = 20
    candidate_ttl_hours: int = 24

    # Anti-duplication
    max_per_symbol: int = 1                # Макс позиций на символ (любой side)
    max_per_symbol_side: int = 1           # Макс позиций на (symbol, side)

    # Scoring weights (сумма = 1.0)
    ev_weight: float = 0.55
    confidence_weight: float = 0.30
    quality_weight: float = 0.15

    # Filters
    min_ev_r: float = 0.0                  # Минимальный EV для попадания в пул
    min_confidence: float = 0.4            # Минимальный confidence

    # Equity
    initial_capital: float = 10000.0

    # Fill attempt throttle (FIX #4)
    fill_attempt_throttle_sec: int = 300   # 5 минут между обновлениями attempt


@dataclass
class ForwardTestConfig:
    """Главная конфигурация Forward Test."""
    # Master switch - можно отключить через админку
    enabled: bool = True

    slippage: SlippageConfig = field(default_factory=SlippageConfig)
    universe: UniverseConfig = field(default_factory=UniverseConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    learning_gates: LearningGatesConfig = field(default_factory=LearningGatesConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)

    # Same-bar rule: sl_first означает SL проверяется до TP
    same_bar_rule: str = "sl_first"

    # BE логика по умолчанию
    be_after_tp1_default: bool = True

    # Partial close % при TP1 (по умолчанию)
    tp1_partial_close_pct: float = 30.0

    def get_generation_cron(self) -> str:
        """Cron expression для генерации."""
        hours = ",".join(str(h) for h in self.schedule.generation_hours)
        return f"0 {hours} * * *"


# Singleton instance
FORWARD_TEST_CONFIG = ForwardTestConfig()


def get_config() -> ForwardTestConfig:
    """Получить конфигурацию."""
    return FORWARD_TEST_CONFIG
