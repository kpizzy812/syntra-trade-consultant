# coding: utf-8
"""
Volume Analyzer

Анализ объёмов для определения:
- Volume spikes (аномально высокий объём)
- Relative volume (vs average)
- Volume trend (растёт/падает)
- Buy vs Sell pressure (через OBV)

ВАЖНО для фьючерсов: высокий volume + price move = сильный сигнал!
"""
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

from loguru import logger


class VolumeAnalyzer:
    """
    Анализатор объёмов с определением аномалий и трендов

    Features:
    - Volume spike detection (> 2x average)
    - Relative volume calculation
    - Volume trend analysis
    - Integration with OBV indicator
    """

    def __init__(self):
        logger.info("VolumeAnalyzer initialized")

    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Анализ объёмов из OHLCV данных

        Args:
            df: DataFrame with 'volume' column

        Returns:
            {
                "current_volume": float,
                "avg_volume_20": float,
                "relative_volume": float,  # current / avg
                "volume_spike": bool,
                "volume_trend": "increasing" | "decreasing" | "stable",
                "volume_classification": "very_low" | "low" | "normal" | "high" | "very_high"
            }
        """
        try:
            if df is None or len(df) < 20:
                logger.warning("Insufficient data for volume analysis")
                return {}

            # Get volumes
            volumes = df["volume"].values
            current_volume = volumes[-1]

            # Calculate average volume (last 20 periods)
            avg_volume_20 = np.mean(volumes[-20:])

            # Relative volume
            if avg_volume_20 > 0:
                relative_volume = current_volume / avg_volume_20
            else:
                relative_volume = 1.0

            # Volume spike detection (> 2x average)
            is_spike = relative_volume > 2.0

            # Volume trend (compare recent vs older average)
            recent_avg = np.mean(volumes[-5:])   # Last 5 candles
            older_avg = np.mean(volumes[-20:-5]) # Previous 15 candles

            if recent_avg > older_avg * 1.2:
                volume_trend = "increasing"
            elif recent_avg < older_avg * 0.8:
                volume_trend = "decreasing"
            else:
                volume_trend = "stable"

            # Classification
            if relative_volume >= 3.0:
                volume_classification = "very_high"
            elif relative_volume >= 1.5:
                volume_classification = "high"
            elif relative_volume >= 0.5:
                volume_classification = "normal"
            elif relative_volume >= 0.25:
                volume_classification = "low"
            else:
                volume_classification = "very_low"

            result = {
                "current_volume": float(current_volume),
                "avg_volume_20": float(avg_volume_20),
                "relative_volume": round(relative_volume, 2),
                "volume_spike": is_spike,
                "volume_trend": volume_trend,
                "volume_classification": volume_classification
            }

            logger.debug(
                f"Volume analysis: current={current_volume:.0f}, "
                f"avg={avg_volume_20:.0f}, "
                f"relative={relative_volume:.2f}x, "
                f"spike={is_spike}"
            )

            return result

        except Exception as e:
            logger.exception(f"Error in volume analysis: {e}")
            return {}

    def detect_volume_climax(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Определить volume climax (кульминация объёмов)

        Volume climax = резкий всплеск объёма на экстремуме цены
        Обычно сигнализирует о развороте тренда

        Args:
            df: DataFrame with OHLCV

        Returns:
            {
                "is_climax": bool,
                "climax_type": "bullish" | "bearish" | None,
                "volume_multiplier": float,  # how many times > avg
                "price_extreme": bool  # is price at local high/low
            }
        """
        try:
            if df is None or len(df) < 20:
                return {"is_climax": False}

            # Get last candle
            last_volume = df["volume"].iloc[-1]
            last_close = df["close"].iloc[-1]
            last_open = df["open"].iloc[-1]

            # Calculate average volume
            avg_volume = df["volume"].iloc[-20:].mean()

            # Volume multiplier
            volume_mult = last_volume / avg_volume if avg_volume > 0 else 1.0

            # Check if volume is climactic (> 3x average)
            is_high_volume = volume_mult > 3.0

            # Check if price is at extreme
            recent_highs = df["high"].iloc[-10:].values
            recent_lows = df["low"].iloc[-10:].values

            is_at_high = last_close >= recent_highs.max() * 0.99
            is_at_low = last_close <= recent_lows.min() * 1.01

            # Determine climax type
            climax_type = None
            is_climax = False

            if is_high_volume:
                if is_at_high and last_close < last_open:
                    # High volume + price rejected from top = bearish climax
                    climax_type = "bearish"
                    is_climax = True
                elif is_at_low and last_close > last_open:
                    # High volume + price bounced from bottom = bullish climax
                    climax_type = "bullish"
                    is_climax = True

            result = {
                "is_climax": is_climax,
                "climax_type": climax_type,
                "volume_multiplier": round(volume_mult, 2),
                "price_extreme": is_at_high or is_at_low
            }

            if is_climax:
                logger.info(
                    f"Volume climax detected: {climax_type}, "
                    f"volume {volume_mult:.1f}x average"
                )

            return result

        except Exception as e:
            logger.exception(f"Error in climax detection: {e}")
            return {"is_climax": False}

    def get_volume_profile_summary(self, df: pd.DataFrame) -> str:
        """
        Получить краткое описание volume profile для AI prompt

        Args:
            df: DataFrame with volume

        Returns:
            Formatted string for AI
        """
        analysis = self.analyze(df)

        if not analysis:
            return "Данные по объёмам недоступны."

        rel_vol = analysis.get("relative_volume", 1.0)
        classification = analysis.get("volume_classification", "normal")
        trend = analysis.get("volume_trend", "stable")
        is_spike = analysis.get("volume_spike", False)

        # Format output
        if is_spike:
            return (
                f"🔥 VOLUME SPIKE: {rel_vol:.1f}x выше среднего! "
                f"Тренд объёмов: {trend}. "
                f"Сильный интерес к инструменту - возможен пробой или разворот."
            )
        elif classification == "very_high":
            return (
                f"📈 Высокий объём: {rel_vol:.1f}x от среднего. "
                f"Тренд: {trend}. "
                f"Хорошая ликвидность для входа."
            )
        elif classification == "very_low":
            return (
                f"📉 Низкий объём: {rel_vol:.1f}x от среднего. "
                f"Тренд: {trend}. "
                f"Осторожно - низкая ликвидность, возможны проскальзывания."
            )
        else:
            return (
                f"Объём в норме: {rel_vol:.1f}x от среднего. "
                f"Тренд: {trend}."
            )


# Singleton instance
volume_analyzer = VolumeAnalyzer()
