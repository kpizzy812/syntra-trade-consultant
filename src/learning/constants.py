"""
Learning Module Constants

Константы для Scenario Class Backtesting System.
"""
from enum import Enum


# =============================================================================
# BUCKET CONSTANTS
# =============================================================================

# Sentinel value для L1 (coarse) уровня - заменяет NULL
ANY_BUCKET = "__any__"


class TrendBucket(str, Enum):
    """Bucket для тренда."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"


class VolBucket(str, Enum):
    """Bucket для волатильности."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class FundingBucket(str, Enum):
    """
    Bucket для funding rate (4 уровня).

    Thresholds:
    - strong_negative: < -0.02%
    - negative: -0.02% .. -0.005%
    - neutral: -0.005% .. 0.01%
    - positive: > 0.01%
    """
    STRONG_NEGATIVE = "strong_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"


class SentimentBucket(str, Enum):
    """
    Bucket для sentiment (Fear & Greed Index).

    Thresholds:
    - fear: < 30
    - neutral: 30 - 70
    - greed: > 70
    """
    FEAR = "fear"
    NEUTRAL = "neutral"
    GREED = "greed"


# =============================================================================
# BUCKET THRESHOLDS
# =============================================================================

# Funding rate thresholds (в процентах, 0.01 = 0.01%)
FUNDING_THRESHOLD_STRONG_NEG = -0.02
FUNDING_THRESHOLD_NEG = -0.005
FUNDING_THRESHOLD_POS = 0.01

# Sentiment (Fear & Greed) thresholds
SENTIMENT_THRESHOLD_FEAR = 30
SENTIMENT_THRESHOLD_GREED = 70

# Volatility thresholds (ATR / price ratio)
VOL_THRESHOLD_LOW = 0.015   # < 1.5% = low
VOL_THRESHOLD_HIGH = 0.035  # > 3.5% = high


# =============================================================================
# SAMPLE SIZE THRESHOLDS
# =============================================================================

# Minimum trades for different confidence levels
MIN_TRADES_INSUFFICIENT = 20   # < 20 = insufficient
MIN_TRADES_PRELIMINARY = 20    # 20-49 = preliminary
MIN_TRADES_RELIABLE = 50       # >= 50 = reliable

# Minimum для gates logic
MIN_TRADES_FOR_GATES = 50      # Kill switch / boost только при >= 50


# =============================================================================
# CONTEXT GATES THRESHOLDS
# =============================================================================

# Kill switch thresholds
KILL_SWITCH_EV_THRESHOLD = 0.0      # EV < 0 (с CI подтверждением)
KILL_SWITCH_PF_THRESHOLD = 0.8      # Profit factor < 0.8

# Excessive drawdown
MAX_DRAWDOWN_THRESHOLD = 5.0        # > 5R = excessive
MAX_DRAWDOWN_PRELIMINARY = 4.0      # Warning threshold для preliminary

# Boost thresholds
BOOST_EV_THRESHOLD = 0.5            # EV >= 0.5R
BOOST_WINRATE_THRESHOLD = 0.55      # >= 55%
BOOST_MAX_DD_THRESHOLD = 3.0        # < 3R

# Modifiers
BOOST_CONFIDENCE_MODIFIER = 0.05    # +5% к confidence
BOOST_EV_PRIOR = 0.1                # +0.1R к EV prior

PRELIMINARY_CONFIDENCE_PENALTY = -0.03  # -3% для preliminary samples


# =============================================================================
# COOLDOWN
# =============================================================================

# Cooldown после disable (в часах)
COOLDOWN_HOURS = 24


# =============================================================================
# ROLLING WINDOW
# =============================================================================

# Default rolling window для статистики (дней)
DEFAULT_WINDOW_DAYS = 90


# =============================================================================
# CONFIDENCE CLAMP
# =============================================================================

# Min/max для confidence после modifiers
CONFIDENCE_MIN = 0.05
CONFIDENCE_MAX = 0.95


# =============================================================================
# CONFIDENCE INTERVAL
# =============================================================================

# Z-score для 95% CI (для Wilson score и EV CI)
CI_Z_SCORE = 1.96
