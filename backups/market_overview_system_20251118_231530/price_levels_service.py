# coding: utf-8
"""
Price Levels Service

Calculates key price levels for crypto analysis:
- Fibonacci retracement levels (from ATH to current/ATL)
- Support and resistance levels from historical data
- Volume-weighted price zones

Used for scenario generation with concrete entry/exit points.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PriceLevelsService:
    """
    Service for calculating technical price levels

    Provides actionable price levels for trading scenarios:
    - Fibonacci retracement (23.6%, 38.2%, 50%, 61.8%, 78.6%)
    - Historical support/resistance from OHLC data
    - Volume profile zones (high-volume price areas)
    """

    # Fibonacci retracement levels
    FIBONACCI_LEVELS = {
        0: "Current Low / ATL",
        0.236: "23.6% Retracement",
        0.382: "38.2% Retracement",
        0.5: "50% Retracement",
        0.618: "61.8% Golden Ratio",
        0.786: "78.6% Retracement",
        1.0: "ATH / High"
    }

    def calculate_fibonacci_retracement(
        self,
        current_price: float,
        ath_price: float,
        atl_price: Optional[float] = None,
        use_recent_swing: bool = False
    ) -> Dict[str, Any]:
        """
        Calculate Fibonacci retracement levels

        Two modes:
        1. ATH to current (default) - for downtrends from ATH
        2. ATL to ATH - for full cycle analysis

        Args:
            current_price: Current token price
            ath_price: All-time high price
            atl_price: All-time low price (optional)
            use_recent_swing: Use recent swing high/low instead of ATH/ATL

        Returns:
            Dict with Fibonacci levels and interpretation

        Example:
            {
                "levels": {
                    "0.236": 45000.0,
                    "0.382": 42000.0,
                    ...
                },
                "current_zone": "38.2%-50% retracement",
                "interpretation": "Price in accumulation zone",
                "support_level": 42000.0,
                "resistance_level": 48000.0
            }
        """
        try:
            # Determine swing range
            if use_recent_swing:
                # For recent swing, use smaller range (last major move)
                # This requires OHLC data - fallback to ATH for now
                swing_high = ath_price
                swing_low = atl_price if atl_price else current_price
            else:
                # Use ATH to current/ATL
                swing_high = ath_price
                swing_low = atl_price if atl_price else current_price

            # Calculate price difference
            price_range = swing_high - swing_low

            if price_range <= 0:
                logger.warning(f"Invalid price range: high={swing_high}, low={swing_low}")
                return {"error": "Invalid price range for Fibonacci calculation"}

            # Calculate Fibonacci levels
            fib_levels = {}
            for ratio, description in self.FIBONACCI_LEVELS.items():
                level_price = swing_low + (price_range * ratio)
                fib_levels[f"{ratio:.1%}"] = {
                    "price": round(level_price, 6),
                    "description": description
                }

            # Determine current zone
            current_zone = self._identify_fib_zone(current_price, swing_high, swing_low)

            # Find nearest support and resistance
            support = self._find_nearest_support(current_price, fib_levels)
            resistance = self._find_nearest_resistance(current_price, fib_levels)

            # Interpretation based on zone
            interpretation = self._interpret_fib_position(current_zone, current_price, ath_price)

            return {
                "success": True,
                "levels": fib_levels,
                "swing_high": swing_high,
                "swing_low": swing_low,
                "current_price": current_price,
                "current_zone": current_zone,
                "nearest_support": support,
                "nearest_resistance": resistance,
                "interpretation": interpretation,
                "distance_from_ath_pct": ((ath_price - current_price) / ath_price) * 100,
            }

        except Exception as e:
            logger.error(f"Error calculating Fibonacci retracement: {e}")
            return {"success": False, "error": str(e)}

    def _identify_fib_zone(self, current_price: float, high: float, low: float) -> str:
        """Identify which Fibonacci zone the current price is in"""
        price_range = high - low
        position = (current_price - low) / price_range

        if position >= 0.786:
            return "78.6%-100% (Near ATH - overbought zone)"
        elif position >= 0.618:
            return "61.8%-78.6% (Strong resistance zone)"
        elif position >= 0.5:
            return "50%-61.8% (Neutral-bullish zone)"
        elif position >= 0.382:
            return "38.2%-50% (Accumulation zone)"
        elif position >= 0.236:
            return "23.6%-38.2% (Strong support zone)"
        else:
            return "0%-23.6% (Near ATL - oversold zone)"

    def _find_nearest_support(self, current_price: float, fib_levels: Dict) -> Optional[Dict]:
        """Find the nearest Fibonacci level below current price (support)"""
        support_levels = []
        for level_name, level_data in fib_levels.items():
            if level_data["price"] < current_price:
                support_levels.append({
                    "level": level_name,
                    "price": level_data["price"],
                    "distance_pct": ((current_price - level_data["price"]) / current_price) * 100
                })

        if support_levels:
            # Return the closest support level
            return min(support_levels, key=lambda x: x["distance_pct"])
        return None

    def _find_nearest_resistance(self, current_price: float, fib_levels: Dict) -> Optional[Dict]:
        """Find the nearest Fibonacci level above current price (resistance)"""
        resistance_levels = []
        for level_name, level_data in fib_levels.items():
            if level_data["price"] > current_price:
                resistance_levels.append({
                    "level": level_name,
                    "price": level_data["price"],
                    "distance_pct": ((level_data["price"] - current_price) / current_price) * 100
                })

        if resistance_levels:
            # Return the closest resistance level
            return min(resistance_levels, key=lambda x: x["distance_pct"])
        return None

    def _interpret_fib_position(self, zone: str, current_price: float, ath_price: float) -> str:
        """Interpret the significance of current Fibonacci position"""
        distance_from_ath = ((ath_price - current_price) / ath_price) * 100

        if "Near ATH" in zone:
            return (
                f"Price is near all-time high ({distance_from_ath:.1f}% below ATH). "
                "This is typically a distribution zone with high sell pressure. "
                "Consider taking profits or waiting for pullback to lower Fibonacci levels."
            )
        elif "resistance" in zone.lower():
            return (
                f"Price is in resistance zone ({distance_from_ath:.1f}% below ATH). "
                "Strong overhead resistance expected. Look for confirmation before entering."
            )
        elif "Accumulation" in zone:
            return (
                f"Price is in accumulation zone ({distance_from_ath:.1f}% below ATH). "
                "This is a potential buy zone. Consider entries on pullbacks to lower levels."
            )
        elif "support" in zone.lower():
            return (
                f"Price is in strong support zone ({distance_from_ath:.1f}% below ATH). "
                "High probability reversal area. Good risk/reward for entries."
            )
        elif "Near ATL" in zone:
            return (
                f"Price is near all-time low ({distance_from_ath:.1f}% below ATH). "
                "Extreme oversold condition. High risk but potentially high reward. "
                "Wait for reversal confirmation."
            )
        else:
            return (
                f"Price is in neutral zone ({distance_from_ath:.1f}% below ATH). "
                "No clear technical bias. Wait for breakout in either direction."
            )

    def calculate_support_resistance_from_ohlc(
        self,
        ohlc_data: List[Dict[str, Any]],
        current_price: float,
        lookback_periods: int = 90
    ) -> Dict[str, Any]:
        """
        Calculate support and resistance levels from historical OHLC data

        Uses:
        - Pivot points (swing high/low)
        - Volume-based liquidity zones (high volume + large body candles)
        - Local extremes

        Args:
            ohlc_data: List of OHLC candles with 'high', 'low', 'close', 'volume'
            current_price: Current price
            lookback_periods: Number of periods to analyze

        Returns:
            Dict with support/resistance levels and liquidity zones
        """
        try:
            if not ohlc_data or len(ohlc_data) < 10:
                return {"success": False, "error": "Insufficient OHLC data"}

            # Take last N periods
            recent_data = ohlc_data[-lookback_periods:]

            # Calculate average volume for liquidity zone detection
            volumes = [candle.get("volume", 0) for candle in recent_data]
            avg_volume = sum(volumes) / len(volumes) if volumes else 0

            # Find local highs and lows (pivot points) + liquidity zones
            resistance_levels = []
            support_levels = []
            liquidity_zones = []

            for i in range(2, len(recent_data) - 2):
                current = recent_data[i]

                # Extract OHLC data
                open_price = current.get("open", current.get("close", 0))
                close_price = current.get("close", 0)
                high_price = current.get("high", 0)
                low_price = current.get("low", 0)
                volume = current.get("volume", 0)

                # Skip if invalid data
                if not close_price or not high_price or not low_price:
                    continue

                # Check if this is a local high (resistance)
                is_local_high = (
                    high_price > recent_data[i-1].get("high", 0) and
                    high_price > recent_data[i-2].get("high", 0) and
                    high_price > recent_data[i+1].get("high", 0) and
                    high_price > recent_data[i+2].get("high", 0)
                )

                if is_local_high:
                    resistance_levels.append(high_price)

                # Check if this is a local low (support)
                is_local_low = (
                    low_price < recent_data[i-1].get("low", float('inf')) and
                    low_price < recent_data[i-2].get("low", float('inf')) and
                    low_price < recent_data[i+1].get("low", float('inf')) and
                    low_price < recent_data[i+2].get("low", float('inf'))
                )

                if is_local_low:
                    support_levels.append(low_price)

                # Check for liquidity zones (high volume + large body)
                if avg_volume > 0 and close_price > 0:
                    body_size_pct = abs(close_price - open_price) / close_price * 100
                    volume_ratio = volume / avg_volume

                    # Liquidity zone criteria: >3% body AND >1.8x average volume
                    if body_size_pct > 3.0 and volume_ratio > 1.8:
                        # Price level = mid of the large candle
                        liquidity_level = (high_price + low_price) / 2
                        liquidity_zones.append({
                            "price": liquidity_level,
                            "volume_ratio": volume_ratio,
                            "body_size_pct": body_size_pct,
                            "type": "high_liquidity"
                        })

                        # Also add to S/R levels based on candle direction
                        if close_price > open_price:  # Bullish candle
                            resistance_levels.append(liquidity_level)
                        else:  # Bearish candle
                            support_levels.append(liquidity_level)

            # Cluster nearby levels (within 2% of each other)
            clustered_resistance = self._cluster_price_levels(resistance_levels, tolerance=0.02)
            clustered_support = self._cluster_price_levels(support_levels, tolerance=0.02)

            # Find nearest levels to current price
            nearest_resistance = min(
                [r for r in clustered_resistance if r > current_price],
                default=None
            )
            nearest_support = max(
                [s for s in clustered_support if s < current_price],
                default=None
            )

            # Find nearest liquidity zone
            nearest_liquidity_zone = None
            if liquidity_zones:
                nearest_liquidity_zone = min(
                    liquidity_zones,
                    key=lambda z: abs(z["price"] - current_price)
                )

            return {
                "success": True,
                "resistance_levels": sorted(clustered_resistance, reverse=True)[:5],
                "support_levels": sorted(clustered_support, reverse=True)[:5],
                "nearest_resistance": nearest_resistance,
                "nearest_support": nearest_support,
                "liquidity_zones": liquidity_zones[:10],  # Top 10 liquidity zones
                "nearest_liquidity_zone": nearest_liquidity_zone,
                "current_price": current_price,
            }

        except Exception as e:
            logger.error(f"Error calculating S/R from OHLC: {e}")
            return {"success": False, "error": str(e)}

    def _cluster_price_levels(self, levels: List[float], tolerance: float = 0.02) -> List[float]:
        """
        Cluster nearby price levels into single levels

        Args:
            levels: List of price levels
            tolerance: Percentage tolerance for clustering (0.02 = 2%)

        Returns:
            List of clustered price levels
        """
        if not levels:
            return []

        sorted_levels = sorted(levels)
        clustered = []
        current_cluster = [sorted_levels[0]]

        for level in sorted_levels[1:]:
            # Check if this level is within tolerance of current cluster average
            cluster_avg = sum(current_cluster) / len(current_cluster)
            if abs(level - cluster_avg) / cluster_avg <= tolerance:
                current_cluster.append(level)
            else:
                # Start new cluster
                clustered.append(sum(current_cluster) / len(current_cluster))
                current_cluster = [level]

        # Add last cluster
        if current_cluster:
            clustered.append(sum(current_cluster) / len(current_cluster))

        return clustered

    def generate_scenario_levels(
        self,
        current_price: float,
        ath_price: float,
        atl_price: Optional[float] = None,
        fibonacci_data: Optional[Dict] = None,
        support_resistance_data: Optional[Dict] = None,
        ema_data: Optional[Dict] = None,
        atr: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Generate concrete price levels for trading scenarios

        Combines Fibonacci, S/R, EMA, and ATR analysis to suggest:
        - Entry zones (with specific prices)
        - Stop-loss levels (ATR-based if available)
        - Take-profit targets (ATR-based if available)
        - Breakout/breakdown levels
        - Dynamic EMA levels

        Args:
            current_price: Current token price
            ath_price: All-time high
            atl_price: All-time low (optional)
            fibonacci_data: Pre-calculated Fibonacci data
            support_resistance_data: Pre-calculated S/R data
            ema_data: Dict with EMA values (ema_20, ema_50, ema_200)
            atr: Average True Range for volatility-based SL/TP

        Returns:
            Dict with scenario-specific price levels
        """
        try:
            # Calculate Fibonacci if not provided
            if not fibonacci_data:
                fibonacci_data = self.calculate_fibonacci_retracement(
                    current_price, ath_price, atl_price
                )

            if not fibonacci_data.get("success"):
                return fibonacci_data

            # Extract key levels
            fib_levels = fibonacci_data["levels"]
            nearest_support_fib = fibonacci_data.get("nearest_support")
            nearest_resistance_fib = fibonacci_data.get("nearest_resistance")

            # Combine with S/R if available
            support_levels = []
            resistance_levels = []

            if nearest_support_fib:
                support_levels.append(nearest_support_fib["price"])
            if nearest_resistance_fib:
                resistance_levels.append(nearest_resistance_fib["price"])

            if support_resistance_data and support_resistance_data.get("success"):
                if support_resistance_data.get("nearest_support"):
                    support_levels.append(support_resistance_data["nearest_support"])
                if support_resistance_data.get("nearest_resistance"):
                    resistance_levels.append(support_resistance_data["nearest_resistance"])

            # Add EMA levels as dynamic support/resistance
            ema_levels = {}
            if ema_data:
                ema_20 = ema_data.get("ema_20")
                ema_50 = ema_data.get("ema_50")
                ema_200 = ema_data.get("ema_200")

                if ema_20:
                    distance_pct = ((current_price - ema_20) / current_price) * 100
                    ema_levels["ema_20"] = {
                        "price": ema_20,
                        "distance_pct": round(distance_pct, 2),
                        "position": "below" if ema_20 < current_price else "above"
                    }
                    # EMA20 acts as dynamic S/R based on position
                    if ema_20 < current_price:
                        support_levels.append(ema_20)
                    else:
                        resistance_levels.append(ema_20)

                if ema_50:
                    distance_pct = ((current_price - ema_50) / current_price) * 100
                    ema_levels["ema_50"] = {
                        "price": ema_50,
                        "distance_pct": round(distance_pct, 2),
                        "position": "below" if ema_50 < current_price else "above"
                    }
                    if ema_50 < current_price:
                        support_levels.append(ema_50)
                    else:
                        resistance_levels.append(ema_50)

                if ema_200:
                    distance_pct = ((current_price - ema_200) / current_price) * 100
                    ema_levels["ema_200"] = {
                        "price": ema_200,
                        "distance_pct": round(distance_pct, 2),
                        "position": "below" if ema_200 < current_price else "above"
                    }
                    if ema_200 < current_price:
                        support_levels.append(ema_200)
                    else:
                        resistance_levels.append(ema_200)

            # Calculate ATR-based SL/TP or fallback to percentage
            leverage_recommendation = None
            if atr and atr > 0:
                # ATR-based calculations (professional approach)
                conservative_sl_distance = 1.0 * atr  # 1x ATR for conservative
                aggressive_sl_distance = 0.5 * atr    # 0.5x ATR for aggressive
                tp1_distance = 0.5 * atr              # 0.5x ATR scalp target
                tp2_distance = 1.0 * atr              # 1x ATR swing target
                tp3_distance = 2.0 * atr              # 2x ATR extended target

                # Calculate leverage recommendation based on ATR volatility
                atr_percentage = (atr / current_price) * 100

                if atr_percentage < 2.0:
                    # Low volatility - higher leverage safe
                    leverage_recommendation = {
                        "conservative": "3x-5x",
                        "moderate": "5x-8x",
                        "aggressive": "8x-10x",
                        "volatility_level": "low",
                        "atr_pct": round(atr_percentage, 2),
                        "reasoning": "Низкая волатильность — можно использовать умеренное плечо"
                    }
                elif atr_percentage < 4.0:
                    # Medium volatility - moderate leverage
                    leverage_recommendation = {
                        "conservative": "2x-3x",
                        "moderate": "3x-5x",
                        "aggressive": "5x-7x",
                        "volatility_level": "medium",
                        "atr_pct": round(atr_percentage, 2),
                        "reasoning": "Средняя волатильность — осторожно с плечом"
                    }
                else:
                    # High volatility - low leverage only
                    leverage_recommendation = {
                        "conservative": "1x-2x",
                        "moderate": "2x-3x",
                        "aggressive": "3x-5x",
                        "volatility_level": "high",
                        "atr_pct": round(atr_percentage, 2),
                        "reasoning": "Высокая волатильность — минимальное плечо или spot"
                    }
            else:
                # Fallback to percentage-based (if no ATR available)
                conservative_sl_distance = current_price * 0.08  # 8%
                aggressive_sl_distance = current_price * 0.05    # 5%
                tp1_distance = current_price * 0.15              # 15%
                tp2_distance = current_price * 0.30              # 30%
                tp3_distance = current_price * 0.50              # 50%

            # Generate scenarios with concrete levels
            scenarios = {
                "bullish_scenario": {
                    "name": "Bullish Breakout",
                    "entry_zone": {
                        "conservative": current_price * 0.98,  # 2% below current
                        "aggressive": current_price * 1.02,   # 2% above current (after breakout)
                    },
                    "stop_loss": {
                        "conservative": current_price - conservative_sl_distance,
                        "aggressive": current_price - aggressive_sl_distance,
                        "nearest_support": min(support_levels) if support_levels else None,
                    },
                    "targets": {
                        "target_1": current_price + tp1_distance,  # ATR-based or % scalp
                        "target_2": current_price + tp2_distance,  # ATR-based or % swing
                        "target_3": min(resistance_levels) if resistance_levels else current_price + tp3_distance,  # Nearest resistance or extended
                        "fib_resistance": fib_levels.get("78.6%", {}).get("price"),
                    },
                    "conditions": [
                        f"Price holds above ${nearest_support_fib['price']:.4f} support" if nearest_support_fib else "Price holds current support",
                        "Volume increases on upward moves",
                        "Market sentiment improves (Fear & Greed rises)",
                    ]
                },
                "bearish_scenario": {
                    "name": "Bearish Breakdown",
                    "entry_zone": {
                        "conservative": min(support_levels) if support_levels else current_price * 0.90,
                        "aggressive": nearest_support_fib["price"] * 0.95 if nearest_support_fib else current_price * 0.85,
                    },
                    "stop_loss": {
                        "conservative": current_price + conservative_sl_distance,  # Above for shorts
                        "aggressive": current_price + aggressive_sl_distance,
                        "nearest_resistance": min(resistance_levels) if resistance_levels else None,
                    },
                    "targets": {
                        "target_1": current_price - tp1_distance,  # ATR-based scalp
                        "target_2": current_price - tp2_distance,  # ATR-based swing
                        "fib_support": fib_levels.get("23.6%", {}).get("price"),
                        "atl": atl_price if atl_price else None,
                    },
                    "conditions": [
                        f"Price breaks below ${nearest_support_fib['price']:.4f}" if nearest_support_fib else "Price breaks key support",
                        "Volume increases on downward moves",
                        "Market sentiment deteriorates",
                    ]
                },
                "range_bound_scenario": {
                    "name": "Range Trading",
                    "range": {
                        "upper": nearest_resistance_fib["price"] if nearest_resistance_fib else current_price * 1.10,
                        "lower": nearest_support_fib["price"] if nearest_support_fib else current_price * 0.90,
                    },
                    "strategy": "Buy near support, sell near resistance",
                    "conditions": [
                        "Price respects range boundaries",
                        "No major news catalysts",
                        "Low volatility environment",
                    ]
                }
            }

            return {
                "success": True,
                "current_price": current_price,
                "atr": atr,
                "atr_based_calculations": atr is not None and atr > 0,
                "leverage_recommendation": leverage_recommendation,  # Leverage based on ATR volatility
                "key_levels": {
                    "immediate_support": min(support_levels) if support_levels else None,
                    "immediate_resistance": min(resistance_levels) if resistance_levels else None,
                    "major_support": nearest_support_fib["price"] if nearest_support_fib else None,
                    "major_resistance": nearest_resistance_fib["price"] if nearest_resistance_fib else None,
                    "ema_levels": ema_levels,  # Dynamic EMA levels
                    "all_support_levels": sorted(support_levels) if support_levels else [],
                    "all_resistance_levels": sorted(resistance_levels) if resistance_levels else [],
                },
                "scenarios": scenarios,
                "fibonacci_zone": fibonacci_data.get("current_zone"),
                "distance_from_ath": fibonacci_data.get("distance_from_ath_pct"),
            }

        except Exception as e:
            logger.error(f"Error generating scenario levels: {e}")
            return {"success": False, "error": str(e)}


# Singleton instance
price_levels_service = PriceLevelsService()
