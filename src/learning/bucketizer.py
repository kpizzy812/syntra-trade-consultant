"""
Bucketizer

Преобразование market context в bucket values для class key.
Никогда не возвращает None - всегда реальное значение или fallback.
"""
from typing import Dict, Any, Optional

from src.learning.constants import (
    TrendBucket,
    VolBucket,
    FundingBucket,
    SentimentBucket,
    FUNDING_THRESHOLD_STRONG_NEG,
    FUNDING_THRESHOLD_NEG,
    FUNDING_THRESHOLD_POS,
    SENTIMENT_THRESHOLD_FEAR,
    SENTIMENT_THRESHOLD_GREED,
    VOL_THRESHOLD_LOW,
    VOL_THRESHOLD_HIGH,
)


def get_trend_bucket(factors: Dict[str, Any]) -> str:
    """
    Определить trend bucket из market factors.

    Args:
        factors: Dict с ключами trend, trend_strength, etc.

    Returns:
        TrendBucket value (никогда не None!)
    """
    trend = factors.get("trend", "").lower()

    if trend in ("bullish", "uptrend", "up"):
        return TrendBucket.BULLISH.value
    elif trend in ("bearish", "downtrend", "down"):
        return TrendBucket.BEARISH.value

    # Попробуем определить по trend_strength
    trend_strength = factors.get("trend_strength", 0)
    if isinstance(trend_strength, (int, float)):
        if trend_strength > 0.3:
            return TrendBucket.BULLISH.value
        elif trend_strength < -0.3:
            return TrendBucket.BEARISH.value

    # Default fallback
    return TrendBucket.SIDEWAYS.value


def get_vol_bucket(factors: Dict[str, Any]) -> str:
    """
    Определить volatility bucket из market factors.

    Args:
        factors: Dict с ключами volatility_regime, atr_ratio, etc.

    Returns:
        VolBucket value (никогда не None!)
    """
    # Сначала проверяем готовый volatility_regime
    vol_regime = factors.get("volatility_regime", "").lower()
    if vol_regime in ("low", "calm"):
        return VolBucket.LOW.value
    elif vol_regime in ("high", "volatile", "extreme"):
        return VolBucket.HIGH.value
    elif vol_regime in ("normal", "medium", "moderate"):
        return VolBucket.NORMAL.value

    # Пробуем по ATR ratio
    atr_ratio = factors.get("atr_ratio") or factors.get("atr_pct")
    if atr_ratio is not None:
        try:
            ratio = float(atr_ratio)
            if ratio < VOL_THRESHOLD_LOW:
                return VolBucket.LOW.value
            elif ratio > VOL_THRESHOLD_HIGH:
                return VolBucket.HIGH.value
            return VolBucket.NORMAL.value
        except (ValueError, TypeError):
            pass

    # Default fallback
    return VolBucket.NORMAL.value


def get_funding_bucket(factors: Dict[str, Any]) -> str:
    """
    Определить funding bucket из market factors.

    Thresholds:
    - strong_negative: < -0.02%
    - negative: -0.02% .. -0.005%
    - neutral: -0.005% .. 0.01%
    - positive: > 0.01%

    Args:
        factors: Dict с ключами funding_rate, funding, etc.

    Returns:
        FundingBucket value (никогда не None!)
    """
    funding = factors.get("funding_rate") or factors.get("funding")

    if funding is not None:
        try:
            rate = float(funding)
            # Нормализуем: если передано как 0.0001 вместо 0.01%
            if abs(rate) < 0.001:
                rate *= 100  # Конвертируем в проценты

            if rate < FUNDING_THRESHOLD_STRONG_NEG:
                return FundingBucket.STRONG_NEGATIVE.value
            elif rate < FUNDING_THRESHOLD_NEG:
                return FundingBucket.NEGATIVE.value
            elif rate > FUNDING_THRESHOLD_POS:
                return FundingBucket.POSITIVE.value
            return FundingBucket.NEUTRAL.value
        except (ValueError, TypeError):
            pass

    # Default fallback
    return FundingBucket.NEUTRAL.value


def get_sentiment_bucket(factors: Dict[str, Any]) -> str:
    """
    Определить sentiment bucket из market factors.

    Thresholds (Fear & Greed Index):
    - fear: < 30
    - neutral: 30 - 70
    - greed: > 70

    Args:
        factors: Dict с ключами sentiment, fear_greed, etc.

    Returns:
        SentimentBucket value (никогда не None!)
    """
    # Пробуем разные ключи
    sentiment = (
        factors.get("sentiment") or
        factors.get("fear_greed") or
        factors.get("fear_greed_index") or
        factors.get("market_sentiment")
    )

    if sentiment is not None:
        # Если строка
        if isinstance(sentiment, str):
            sent_lower = sentiment.lower()
            if sent_lower in ("fear", "extreme_fear", "fearful"):
                return SentimentBucket.FEAR.value
            elif sent_lower in ("greed", "extreme_greed", "greedy"):
                return SentimentBucket.GREED.value
            return SentimentBucket.NEUTRAL.value

        # Если число (F&G index 0-100)
        try:
            value = float(sentiment)
            if value < SENTIMENT_THRESHOLD_FEAR:
                return SentimentBucket.FEAR.value
            elif value > SENTIMENT_THRESHOLD_GREED:
                return SentimentBucket.GREED.value
            return SentimentBucket.NEUTRAL.value
        except (ValueError, TypeError):
            pass

    # Default fallback
    return SentimentBucket.NEUTRAL.value


def get_all_buckets(factors: Dict[str, Any]) -> Dict[str, str]:
    """
    Получить все bucket values из market factors.

    Args:
        factors: Market context factors

    Returns:
        Dict с ключами trend_bucket, vol_bucket, funding_bucket, sentiment_bucket
    """
    return {
        "trend_bucket": get_trend_bucket(factors),
        "vol_bucket": get_vol_bucket(factors),
        "funding_bucket": get_funding_bucket(factors),
        "sentiment_bucket": get_sentiment_bucket(factors),
    }
