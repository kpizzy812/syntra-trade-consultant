# coding: utf-8
"""
Price Structure Analyzer - анализ структуры цены для LLM.

Swing points, range, trend state, volatility regime.
"""
from typing import Any, Dict

import numpy as np
import pandas as pd
from loguru import logger


class PriceStructureAnalyzer:
    """
    Рассчитывает сжатую структуру цены для LLM.
    """

    def calculate(
        self,
        klines: pd.DataFrame,
        current_price: float,
        indicators: Dict,
        timeframe: str
    ) -> Dict[str, Any]:
        """
        Рассчитать сжатую структуру цены для LLM.

        Вместо того чтобы давать LLM 200 свечей, даём ему:
        - Swing points (последние 5 highs/lows)
        - Range (high/low за N свечей)
        - Trend state по таймфреймам
        - Volatility regime
        - Distance to key levels

        Returns:
            {
                "swing_highs": [{price: 96500, distance_pct: 1.2}],
                "swing_lows": [{price: 93800, distance_pct: -1.5}],
                "range_high": 96500,
                "range_low": 93800,
                "range_size_pct": 2.8,
                "current_position_in_range": 0.65,
                "trend_state": {"1h": "bullish_strong"},
                "volatility_regime": "expansion"
            }
        """
        structure = {}

        # 1. Swing points detection с ATR threshold
        swing_highs, swing_lows = self._detect_swing_points(
            klines, current_price, indicators
        )

        structure["swing_highs"] = swing_highs
        structure["swing_lows"] = swing_lows

        # 2. Range high/low (последние N свечей)
        lookback = 50 if timeframe in ["1h", "4h"] else 30
        recent_data = klines.tail(lookback)

        range_high = recent_data['high'].max()
        range_low = recent_data['low'].min()
        range_size_pct = ((range_high - range_low) / range_low) * 100 if range_low > 0 else 0

        structure["range_high"] = round(range_high, 2)
        structure["range_low"] = round(range_low, 2)
        structure["range_size_pct"] = round(range_size_pct, 2)

        # Position in range
        if range_high > range_low:
            position_in_range = (current_price - range_low) / (range_high - range_low)
            structure["current_position_in_range"] = round(position_in_range, 2)
        else:
            structure["current_position_in_range"] = 0.5

        # 3. Trend state (используя EMA cross + ADX)
        structure["trend_state"] = self._calculate_trend_state(
            current_price, indicators, timeframe
        )

        # 4. Volatility regime
        structure["volatility_regime"] = self._calculate_volatility_regime(indicators)

        # 5. Distance to nearest support/resistance
        self._add_nearest_levels(structure, current_price)

        # Convert numpy types to native Python types for JSON serialization
        structure = self._convert_numpy_types(structure)

        logger.debug(f"Price structure calculated: {structure}")
        return structure

    def _detect_swing_points(
        self,
        klines: pd.DataFrame,
        current_price: float,
        indicators: Dict
    ) -> tuple[list, list]:
        """
        Обнаружить swing highs/lows с ATR threshold.
        """
        window = 5  # Смотрим на 5 свечей влево и вправо

        highs = klines['high'].values
        lows = klines['low'].values

        # ATR threshold для значимости swing point
        atr = indicators.get("atr", 0)
        # Минимальный порог: 0.3*ATR или 0.3% от цены (что больше)
        min_threshold_pct = 0.003  # 0.3%
        min_threshold = max(atr * 0.3, current_price * min_threshold_pct) if atr else current_price * min_threshold_pct

        swing_highs = []
        swing_lows = []

        # Проходим по свечам (исключая края)
        for i in range(window, len(highs) - window):
            # Swing high: если high[i] выше всех соседей НА threshold
            left_highs = highs[i-window:i]
            right_highs = highs[i+1:i+window+1]

            left_max = max(left_highs) if len(left_highs) > 0 else 0
            right_max = max(right_highs) if len(right_highs) > 0 else 0
            prominence_high = highs[i] - max(left_max, right_max)

            if (all(highs[i] > h for h in left_highs) and
                all(highs[i] > h for h in right_highs) and
                prominence_high >= min_threshold):
                price = highs[i]
                distance_pct = ((price - current_price) / current_price) * 100
                swing_highs.append({
                    "price": round(price, 2),
                    "distance_pct": round(distance_pct, 2),
                    "prominence": round(prominence_high, 2),
                    "idx": i
                })

            # Swing low: если low[i] ниже всех соседей НА threshold
            left_lows = lows[i-window:i]
            right_lows = lows[i+1:i+window+1]

            left_min = min(left_lows) if len(left_lows) > 0 else float('inf')
            right_min = min(right_lows) if len(right_lows) > 0 else float('inf')
            prominence_low = min(left_min, right_min) - lows[i]

            if (all(lows[i] < low for low in left_lows) and
                all(lows[i] < low for low in right_lows) and
                prominence_low >= min_threshold):
                price = lows[i]
                # Use abs() for support distance - always positive (how far below current)
                distance_pct = abs((price - current_price) / current_price) * 100
                swing_lows.append({
                    "price": round(price, 2),
                    "distance_pct": round(distance_pct, 2),
                    "prominence": round(prominence_low, 2),
                    "idx": i
                })

        # Берём ПОСЛЕДНИЕ 5 swing points (по времени), сортируя по prominence как вторичный критерий
        swing_highs = sorted(
            swing_highs,
            key=lambda x: (x["idx"], x.get("prominence", 0)),
            reverse=True
        )[:5]
        swing_lows = sorted(
            swing_lows,
            key=lambda x: (x["idx"], x.get("prominence", 0)),
            reverse=True
        )[:5]

        # Log swing detection stats
        logger.debug(
            f"Swing detection: {len(swing_highs)} highs, {len(swing_lows)} lows "
            f"(threshold={min_threshold:.2f}, ATR={(atr or 0):.2f})"
        )

        return swing_highs, swing_lows

    def _calculate_trend_state(
        self,
        current_price: float,
        indicators: Dict,
        timeframe: str
    ) -> Dict[str, str]:
        """Определить состояние тренда."""
        ema_20 = indicators.get("ema_20")
        ema_50 = indicators.get("ema_50")
        adx = indicators.get("adx", 20)

        trend_state = {}

        if ema_20 and ema_50:
            if current_price > ema_20 > ema_50:
                trend = "bullish"
                strength = "strong" if adx > 30 else "weak"
            elif current_price < ema_20 < ema_50:
                trend = "bearish"
                strength = "strong" if adx > 30 else "weak"
            else:
                trend = "sideways"
                strength = "weak"

            trend_state[timeframe] = f"{trend}_{strength}"

        return trend_state

    def _calculate_volatility_regime(self, indicators: Dict) -> str:
        """Определить режим волатильности."""
        atr_pct = indicators.get("atr_percent", 2.0)

        # Правильный порядок условий (от меньшего к большему для <)
        if atr_pct > 3.0:
            return "very_high"
        elif atr_pct > 2.5:
            return "expansion"
        elif atr_pct < 1.0:  # Сначала очень низкий
            return "very_low"
        elif atr_pct < 1.5:  # Потом просто низкий
            return "compression"
        else:
            return "normal"

    def _add_nearest_levels(self, structure: Dict, current_price: float) -> None:
        """Добавить расстояние до ближайших уровней."""
        if structure.get("swing_highs"):
            nearest_resistance = min(
                [sh for sh in structure["swing_highs"] if sh["price"] > current_price],
                key=lambda x: abs(x["distance_pct"]),
                default=None
            )
            if nearest_resistance:
                structure["distance_to_resistance_pct"] = nearest_resistance["distance_pct"]

        if structure.get("swing_lows"):
            nearest_support = min(
                [sl for sl in structure["swing_lows"] if sl["price"] < current_price],
                key=lambda x: abs(x["distance_pct"]),
                default=None
            )
            if nearest_support:
                structure["distance_to_support_pct"] = nearest_support["distance_pct"]

    def _convert_numpy_types(self, obj: Any) -> Any:
        """Recursively convert numpy types to native Python types."""
        if isinstance(obj, dict):
            return {k: self._convert_numpy_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj
