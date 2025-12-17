# coding: utf-8
"""
Candlestick Pattern Recognition Service

Detects common candlestick patterns for technical analysis:
- Doji
- Hammer / Inverted Hammer
- Shooting Star
- Bullish/Bearish Engulfing
- Morning Star / Evening Star
- Three White Soldiers / Three Black Crows
- And more...

Note: This is a simplified implementation. For production use, consider TA-Lib.
"""
from typing import Optional, List, Dict, Any
import pandas as pd


from loguru import logger


class CandlestickPatterns:
    """
    Service for detecting candlestick patterns

    Uses OHLC data to identify common reversal and continuation patterns
    """

    def __init__(self):
        """Initialize Candlestick Patterns service"""
        pass

    def detect_all_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect all candlestick patterns in the data

        Args:
            df: DataFrame with columns: open, high, low, close

        Returns:
            Dict with detected patterns

        Example:
            {
                "patterns_found": ["doji", "hammer"],
                "doji": True,
                "hammer": True,
                "engulfing_bullish": False,
                "last_pattern": "hammer",
                "pattern_signal": "bullish"
            }
        """
        try:
            if df is None or len(df) < 3:
                logger.warning(
                    "Insufficient data for pattern detection (need at least 3 candles)"
                )
                return {}

            patterns = {}
            patterns_found = []

            # Get last candles for pattern detection
            last = df.iloc[-1]  # Most recent candle
            prev = df.iloc[-2] if len(df) >= 2 else None
            prev2 = df.iloc[-3] if len(df) >= 3 else None

            # === Single Candle Patterns ===

            # Doji
            if self._is_doji(last):
                patterns["doji"] = True
                patterns_found.append("doji")

            # Hammer
            if self._is_hammer(last):
                patterns["hammer"] = True
                patterns_found.append("hammer")

            # Inverted Hammer
            if self._is_inverted_hammer(last):
                patterns["inverted_hammer"] = True
                patterns_found.append("inverted_hammer")

            # Shooting Star
            if self._is_shooting_star(last):
                patterns["shooting_star"] = True
                patterns_found.append("shooting_star")

            # === Two Candle Patterns ===
            if prev is not None:
                # Bullish Engulfing
                if self._is_bullish_engulfing(prev, last):
                    patterns["engulfing_bullish"] = True
                    patterns_found.append("engulfing_bullish")

                # Bearish Engulfing
                if self._is_bearish_engulfing(prev, last):
                    patterns["engulfing_bearish"] = True
                    patterns_found.append("engulfing_bearish")

            # === Three Candle Patterns ===
            if prev is not None and prev2 is not None:
                # Morning Star
                if self._is_morning_star(prev2, prev, last):
                    patterns["morning_star"] = True
                    patterns_found.append("morning_star")

                # Evening Star
                if self._is_evening_star(prev2, prev, last):
                    patterns["evening_star"] = True
                    patterns_found.append("evening_star")

                # Three White Soldiers
                if self._is_three_white_soldiers(prev2, prev, last):
                    patterns["three_white_soldiers"] = True
                    patterns_found.append("three_white_soldiers")

                # Three Black Crows
                if self._is_three_black_crows(prev2, prev, last):
                    patterns["three_black_crows"] = True
                    patterns_found.append("three_black_crows")

            # Summary
            patterns["patterns_found"] = patterns_found
            patterns["last_pattern"] = patterns_found[-1] if patterns_found else None
            patterns["pattern_signal"] = self._classify_pattern_signal(patterns_found)

            if patterns_found:
                logger.info(f"Detected patterns: {patterns_found}")

            return patterns

        except Exception as e:
            logger.exception(f"Error in detect_all_patterns: {e}")
            return {}

    # === Pattern Detection Methods ===

    @staticmethod
    def _is_doji(candle: pd.Series) -> bool:
        """
        Doji: Open ≈ Close (small body, long shadows)
        Indicates indecision
        """
        body = abs(candle["close"] - candle["open"])
        range_size = candle["high"] - candle["low"]
        return body / range_size < 0.1 if range_size > 0 else False

    @staticmethod
    def _is_hammer(candle: pd.Series) -> bool:
        """
        Hammer: Small body at top, long lower shadow
        Bullish reversal signal
        """
        body = abs(candle["close"] - candle["open"])
        upper_shadow = candle["high"] - max(candle["open"], candle["close"])
        lower_shadow = min(candle["open"], candle["close"]) - candle["low"]
        range_size = candle["high"] - candle["low"]

        if range_size == 0:
            return False

        # Lower shadow should be at least 2x the body
        # Upper shadow should be very small
        return (
            lower_shadow > body * 2
            and upper_shadow < body * 0.1
            and body / range_size < 0.3
        )

    @staticmethod
    def _is_inverted_hammer(candle: pd.Series) -> bool:
        """
        Inverted Hammer: Small body at bottom, long upper shadow
        Bullish reversal signal
        """
        body = abs(candle["close"] - candle["open"])
        upper_shadow = candle["high"] - max(candle["open"], candle["close"])
        lower_shadow = min(candle["open"], candle["close"]) - candle["low"]
        range_size = candle["high"] - candle["low"]

        if range_size == 0:
            return False

        # Upper shadow should be at least 2x the body
        # Lower shadow should be very small
        return (
            upper_shadow > body * 2
            and lower_shadow < body * 0.1
            and body / range_size < 0.3
        )

    @staticmethod
    def _is_shooting_star(candle: pd.Series) -> bool:
        """
        Shooting Star: Small body at bottom, long upper shadow
        Bearish reversal signal (similar to inverted hammer but in uptrend)
        """
        body = abs(candle["close"] - candle["open"])
        upper_shadow = candle["high"] - max(candle["open"], candle["close"])
        lower_shadow = min(candle["open"], candle["close"]) - candle["low"]
        range_size = candle["high"] - candle["low"]

        if range_size == 0:
            return False

        return (
            upper_shadow > body * 2
            and lower_shadow < body * 0.1
            and candle["close"] < candle["open"]  # Bearish candle
        )

    @staticmethod
    def _is_bullish_engulfing(prev: pd.Series, current: pd.Series) -> bool:
        """
        Bullish Engulfing: Current bullish candle completely engulfs previous bearish candle
        """
        prev_bearish = prev["close"] < prev["open"]
        current_bullish = current["close"] > current["open"]

        engulfs = current["open"] <= prev["close"] and current["close"] >= prev["open"]

        return prev_bearish and current_bullish and engulfs

    @staticmethod
    def _is_bearish_engulfing(prev: pd.Series, current: pd.Series) -> bool:
        """
        Bearish Engulfing: Current bearish candle completely engulfs previous bullish candle
        """
        prev_bullish = prev["close"] > prev["open"]
        current_bearish = current["close"] < current["open"]

        engulfs = current["open"] >= prev["close"] and current["close"] <= prev["open"]

        return prev_bullish and current_bearish and engulfs

    @staticmethod
    def _is_morning_star(first: pd.Series, second: pd.Series, third: pd.Series) -> bool:
        """
        Morning Star: Bearish candle → Small candle (doji) → Bullish candle
        Bullish reversal signal
        """
        first_bearish = first["close"] < first["open"]
        second_small = (
            abs(second["close"] - second["open"])
            < abs(first["close"] - first["open"]) * 0.3
        )
        third_bullish = third["close"] > third["open"]

        # Third candle should close above midpoint of first
        third_closes_high = third["close"] > (first["open"] + first["close"]) / 2

        return first_bearish and second_small and third_bullish and third_closes_high

    @staticmethod
    def _is_evening_star(first: pd.Series, second: pd.Series, third: pd.Series) -> bool:
        """
        Evening Star: Bullish candle → Small candle (doji) → Bearish candle
        Bearish reversal signal
        """
        first_bullish = first["close"] > first["open"]
        second_small = (
            abs(second["close"] - second["open"])
            < abs(first["close"] - first["open"]) * 0.3
        )
        third_bearish = third["close"] < third["open"]

        # Third candle should close below midpoint of first
        third_closes_low = third["close"] < (first["open"] + first["close"]) / 2

        return first_bullish and second_small and third_bearish and third_closes_low

    @staticmethod
    def _is_three_white_soldiers(
        first: pd.Series, second: pd.Series, third: pd.Series
    ) -> bool:
        """
        Three White Soldiers: Three consecutive bullish candles with higher closes
        Strong bullish continuation signal
        """
        all_bullish = (
            first["close"] > first["open"]
            and second["close"] > second["open"]
            and third["close"] > third["open"]
        )

        consecutive_higher = (
            second["close"] > first["close"] and third["close"] > second["close"]
        )

        return all_bullish and consecutive_higher

    @staticmethod
    def _is_three_black_crows(
        first: pd.Series, second: pd.Series, third: pd.Series
    ) -> bool:
        """
        Three Black Crows: Three consecutive bearish candles with lower closes
        Strong bearish continuation signal
        """
        all_bearish = (
            first["close"] < first["open"]
            and second["close"] < second["open"]
            and third["close"] < third["open"]
        )

        consecutive_lower = (
            second["close"] < first["close"] and third["close"] < second["close"]
        )

        return all_bearish and consecutive_lower

    @staticmethod
    def _classify_pattern_signal(patterns: List[str]) -> str:
        """
        Classify overall pattern signal as bullish, bearish, or neutral
        """
        bullish_patterns = [
            "hammer",
            "inverted_hammer",
            "engulfing_bullish",
            "morning_star",
            "three_white_soldiers",
        ]
        bearish_patterns = [
            "shooting_star",
            "engulfing_bearish",
            "evening_star",
            "three_black_crows",
        ]

        bullish_count = sum(1 for p in patterns if p in bullish_patterns)
        bearish_count = sum(1 for p in patterns if p in bearish_patterns)

        if bullish_count > bearish_count:
            return "bullish"
        elif bearish_count > bullish_count:
            return "bearish"
        else:
            return "neutral"

    def format_patterns_for_prompt(self, patterns: Dict[str, Any]) -> str:
        """
        Format detected patterns into readable text for AI prompt

        Args:
            patterns: Dict from detect_all_patterns()

        Returns:
            Formatted string with detected patterns
        """
        if not patterns or not patterns.get("patterns_found"):
            return "Свечные паттерны не обнаружены."

        patterns_found = patterns.get("patterns_found", [])
        signal = patterns.get("pattern_signal", "neutral")

        # Pattern names in Russian
        pattern_names = {
            "doji": "Doji (нерешительность)",
            "hammer": "Hammer (бычий разворот)",
            "inverted_hammer": "Inverted Hammer (бычий разворот)",
            "shooting_star": "Shooting Star (медвежий разворот)",
            "engulfing_bullish": "Bullish Engulfing (бычье поглощение)",
            "engulfing_bearish": "Bearish Engulfing (медвежье поглощение)",
            "morning_star": "Morning Star (утренняя звезда)",
            "evening_star": "Evening Star (вечерняя звезда)",
            "three_white_soldiers": "Three White Soldiers (три белых солдата)",
            "three_black_crows": "Three Black Crows (три черных вороны)",
        }

        formatted_patterns = [pattern_names.get(p, p) for p in patterns_found]

        signal_emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "⚪"}

        return (
            f"{signal_emoji.get(signal, '⚪')} Обнаруженные паттерны: {', '.join(formatted_patterns)}\n"
            f"Общий сигнал: {signal}"
        )
