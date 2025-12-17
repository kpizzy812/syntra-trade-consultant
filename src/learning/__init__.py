"""
Learning Module

Модуль машинного обучения для Syntra:
- Калибровка confidence
- Статистика архетипов
- Оптимизация SL/TP
- Expected Value (EV) расчёт
- Scenario Class Backtesting (context gates)
"""

from src.learning.confidence_calibrator import confidence_calibrator
from src.learning.archetype_analyzer import archetype_analyzer
from src.learning.sltp_optimizer import sltp_optimizer
from src.learning.scheduler import learning_scheduler
from src.learning.ev_calculator import ev_calculator, EVCalculator, OutcomeProbs, EVMetrics

# Scenario Class Backtesting System
from src.learning.constants import (
    ANY_BUCKET,
    TrendBucket,
    VolBucket,
    FundingBucket,
    SentimentBucket,
    CONFIDENCE_MIN,
    CONFIDENCE_MAX,
)
from src.learning.bucketizer import (
    get_trend_bucket,
    get_vol_bucket,
    get_funding_bucket,
    get_sentiment_bucket,
    get_all_buckets,
)
from src.learning.class_key import ClassKey, build_class_key, build_class_key_from_trade
from src.learning.drawdown_calculator import (
    calculate_max_drawdown,
    DrawdownResult,
)
from src.learning.confidence_intervals import (
    wilson_score_interval,
    wilson_score_lower,
    ev_confidence_interval,
    ev_lower_ci,
    WilsonResult,
    EVConfidenceResult,
)
from src.learning.class_stats_analyzer import class_stats_analyzer, ClassStatsLookupResult

__all__ = [
    # Original exports
    "confidence_calibrator",
    "archetype_analyzer",
    "sltp_optimizer",
    "learning_scheduler",
    "ev_calculator",
    "EVCalculator",
    "OutcomeProbs",
    "EVMetrics",
    # Scenario Class Backtesting
    "ANY_BUCKET",
    "TrendBucket",
    "VolBucket",
    "FundingBucket",
    "SentimentBucket",
    "get_trend_bucket",
    "get_vol_bucket",
    "get_funding_bucket",
    "get_sentiment_bucket",
    "get_all_buckets",
    "ClassKey",
    "build_class_key",
    "build_class_key_from_trade",
    "calculate_max_drawdown",
    "DrawdownResult",
    "wilson_score_interval",
    "wilson_score_lower",
    "ev_confidence_interval",
    "ev_lower_ci",
    "WilsonResult",
    "EVConfidenceResult",
    "class_stats_analyzer",
    "ClassStatsLookupResult",
    "CONFIDENCE_MIN",
    "CONFIDENCE_MAX",
]
