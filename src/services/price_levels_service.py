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

        Uses pivot points and local extremes to identify key levels

        Args:
            ohlc_data: List of OHLC candles with 'high', 'low', 'close', 'volume'
            current_price: Current price
            lookback_periods: Number of periods to analyze

        Returns:
            Dict with support/resistance levels
        """
        try:
            if not ohlc_data or len(ohlc_data) < 10:
                return {"success": False, "error": "Insufficient OHLC data"}

            # Take last N periods
            recent_data = ohlc_data[-lookback_periods:]

            # Find local highs and lows (pivot points)
            resistance_levels = []
            support_levels = []

            for i in range(2, len(recent_data) - 2):
                current = recent_data[i]

                # Check if this is a local high (resistance)
                is_local_high = (
                    current["high"] > recent_data[i-1]["high"] and
                    current["high"] > recent_data[i-2]["high"] and
                    current["high"] > recent_data[i+1]["high"] and
                    current["high"] > recent_data[i+2]["high"]
                )

                if is_local_high:
                    resistance_levels.append(current["high"])

                # Check if this is a local low (support)
                is_local_low = (
                    current["low"] < recent_data[i-1]["low"] and
                    current["low"] < recent_data[i-2]["low"] and
                    current["low"] < recent_data[i+1]["low"] and
                    current["low"] < recent_data[i+2]["low"]
                )

                if is_local_low:
                    support_levels.append(current["low"])

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

            return {
                "success": True,
                "resistance_levels": sorted(clustered_resistance, reverse=True)[:5],
                "support_levels": sorted(clustered_support, reverse=True)[:5],
                "nearest_resistance": nearest_resistance,
                "nearest_support": nearest_support,
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
        support_resistance_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate concrete price levels for trading scenarios

        Combines Fibonacci and S/R analysis to suggest:
        - Entry zones (with specific prices)
        - Stop-loss levels
        - Take-profit targets
        - Breakout/breakdown levels

        Args:
            current_price: Current token price
            ath_price: All-time high
            atl_price: All-time low (optional)
            fibonacci_data: Pre-calculated Fibonacci data
            support_resistance_data: Pre-calculated S/R data

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

            # Generate scenarios with concrete levels
            scenarios = {
                "bullish_scenario": {
                    "name": "Bullish Breakout",
                    "entry_zone": {
                        "conservative": current_price * 0.98,  # 2% below current
                        "aggressive": current_price * 1.02,   # 2% above current (after breakout)
                    },
                    "stop_loss": min(support_levels) if support_levels else current_price * 0.92,
                    "targets": {
                        "target_1": resistance_levels[0] if resistance_levels else current_price * 1.15,
                        "target_2": nearest_resistance_fib["price"] if nearest_resistance_fib else current_price * 1.30,
                        "target_3": fib_levels.get("78.6%", {}).get("price", current_price * 1.50),
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
                    "stop_loss": current_price * 1.08,
                    "targets": {
                        "target_1": fib_levels.get("23.6%", {}).get("price", current_price * 0.85),
                        "target_2": fib_levels.get("0.0%", {}).get("price", atl_price) if atl_price else current_price * 0.70,
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
                "key_levels": {
                    "immediate_support": min(support_levels) if support_levels else None,
                    "immediate_resistance": min(resistance_levels) if resistance_levels else None,
                    "major_support": nearest_support_fib["price"] if nearest_support_fib else None,
                    "major_resistance": nearest_resistance_fib["price"] if nearest_resistance_fib else None,
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
