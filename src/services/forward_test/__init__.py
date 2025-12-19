"""
Forward Test Service

Автоматический forward testing AI-сценариев.
- Генерация snapshots каждые 6 часов
- Мониторинг по 1m OHLC
- Расчёт метрик: WR/EV/DD/конверсия
- Интеграция с Learning layer

NOTE: Сервисы импортируются напрямую из своих модулей чтобы избежать circular imports:
    from src.services.forward_test.snapshot_service import SnapshotService
    from src.services.forward_test.monitor_service import MonitorService
    from src.services.forward_test.scheduler import ForwardTestScheduler
"""
from src.services.forward_test.enums import (
    ScenarioState,
    TerminalState,
    OutcomeResult,
    PnLClass,
    Bias,
    FillModel,
    EventType,
)
from src.services.forward_test.config import (
    ForwardTestConfig,
    SlippageConfig,
    UniverseConfig,
    RetentionConfig,
    MonitorConfig,
    ScheduleConfig,
    LearningGatesConfig,
    get_config,
    FORWARD_TEST_CONFIG,
)
from src.services.forward_test.models import (
    ForwardTestSnapshot,
    ForwardTestMonitorState,
    ForwardTestEvent,
    ForwardTestOutcome,
)

__all__ = [
    # Enums
    "ScenarioState",
    "TerminalState",
    "OutcomeResult",
    "PnLClass",
    "Bias",
    "FillModel",
    "EventType",
    # Config
    "ForwardTestConfig",
    "SlippageConfig",
    "UniverseConfig",
    "RetentionConfig",
    "MonitorConfig",
    "ScheduleConfig",
    "LearningGatesConfig",
    "get_config",
    "FORWARD_TEST_CONFIG",
    # Models
    "ForwardTestSnapshot",
    "ForwardTestMonitorState",
    "ForwardTestEvent",
    "ForwardTestOutcome",
]
