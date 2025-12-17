# coding: utf-8
"""
Cycle Analysis Service

Provides cryptocurrency market cycle analysis:
- Bitcoin Rainbow Chart (logarithmic regression)
- Pi Cycle Top indicator
- Market cycle phase detection
- Historical cycle comparisons

Based on:
- Rainbow Chart: log10(price) = 2.6521 * ln(days) - 18.163
- Pi Cycle: MA 111 / MA 350*2 crossover
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, UTC
import numpy as np
import pandas as pd


from loguru import logger


class CycleAnalysisService:
    """
    Service for cryptocurrency market cycle analysis

    Features:
    - Bitcoin Rainbow Chart calculations
    - Pi Cycle Top indicator
    - Market cycle phase detection
    - Bull/bear market identification
    """

    # Bitcoin genesis block date (UTC timezone-aware)
    BITCOIN_GENESIS = datetime(2009, 1, 9, tzinfo=UTC)

    # Rainbow Chart parameters (Bitbo formula 2025)
    RAINBOW_A = 2.6521
    RAINBOW_B = 18.163

    # Rainbow bands multipliers
    RAINBOW_BANDS = {
        "maximum_bubble": 10.0,
        "sell": 4.0,
        "fomo_intensifies": 2.5,
        "is_this_a_bubble": 2.0,
        "still_cheap": 1.5,
        "hodl": 1.0,  # Center line
        "accumulate": 0.7,
        "buy": 0.5,
        "basically_a_fire_sale": 0.3,
    }

    def __init__(self):
        pass

    def calculate_days_since_genesis(self, target_date: Optional[datetime] = None) -> int:
        """
        Calculate days since Bitcoin genesis block

        Args:
            target_date: Target date (default: now)

        Returns:
            Number of days since genesis
        """
        if not target_date:
            target_date = datetime.now(UTC)

        delta = target_date - self.BITCOIN_GENESIS
        return delta.days

    def calculate_rainbow_price(
        self, days_since_genesis: int, band: str = "hodl"
    ) -> float:
        """
        Calculate Bitcoin price for Rainbow Chart band

        Formula: price = 10^(a * ln(days) - b) * multiplier

        Args:
            days_since_genesis: Days since genesis block
            band: Band name (see RAINBOW_BANDS)

        Returns:
            Predicted price for that band
        """
        if days_since_genesis <= 0:
            return 0.0

        # Base regression line (center line / hodl)
        log_price = self.RAINBOW_A * np.log(days_since_genesis) - self.RAINBOW_B
        base_price = 10 ** log_price

        # Apply band multiplier
        multiplier = self.RAINBOW_BANDS.get(band, 1.0)
        return base_price * multiplier

    def get_rainbow_chart_data(
        self, current_price: float, target_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get complete Rainbow Chart analysis

        Args:
            current_price: Current Bitcoin price
            target_date: Analysis date (default: now)

        Returns:
            Dict with Rainbow Chart data

        Example:
        {
            "days_since_genesis": 5800,
            "current_price": 45000,
            "bands": {
                "maximum_bubble": 100000,
                "sell": 60000,
                ...
            },
            "current_band": "hodl",
            "sentiment": "fair_value"
        }
        """
        if not target_date:
            target_date = datetime.now(UTC)

        days = self.calculate_days_since_genesis(target_date)

        # Calculate all band prices
        bands = {}
        for band_name in self.RAINBOW_BANDS.keys():
            bands[band_name] = self.calculate_rainbow_price(days, band_name)

        # Determine current band
        current_band = self.determine_current_band(current_price, bands)

        # Determine sentiment
        sentiment = self.get_sentiment_from_band(current_band)

        return {
            "days_since_genesis": days,
            "current_price": current_price,
            "bands": bands,
            "current_band": current_band,
            "sentiment": sentiment,
            "date": target_date.strftime("%Y-%m-%d"),
        }

    def determine_current_band(
        self, current_price: float, bands: Dict[str, float]
    ) -> str:
        """
        Determine which Rainbow Chart band current price is in

        Args:
            current_price: Current price
            bands: Dict of band prices

        Returns:
            Band name
        """
        # Sort bands by price (descending)
        sorted_bands = sorted(
            bands.items(), key=lambda x: x[1], reverse=True
        )

        # Find the band current price falls into
        for i, (band_name, band_price) in enumerate(sorted_bands):
            if current_price >= band_price:
                return band_name

        # If price is below all bands, return lowest band
        return sorted_bands[-1][0]

    def get_sentiment_from_band(self, band: str) -> str:
        """
        Get market sentiment from Rainbow Chart band

        Args:
            band: Band name

        Returns:
            Sentiment description
        """
        sentiment_map = {
            "maximum_bubble": "extreme_greed",
            "sell": "sell_zone",
            "fomo_intensifies": "overheated",
            "is_this_a_bubble": "getting_expensive",
            "still_cheap": "fair_value",
            "hodl": "fair_value",
            "accumulate": "undervalued",
            "buy": "buy_zone",
            "basically_a_fire_sale": "fire_sale",
        }

        return sentiment_map.get(band, "neutral")

    def calculate_pi_cycle_top(self, prices_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate Pi Cycle Top indicator

        The Pi Cycle Top indicator uses two moving averages:
        - 111 Day Moving Average (111DMA)
        - 350 Day Moving Average x 2 (350DMA x 2)

        When 111DMA crosses above 350DMA x 2, it signals a market top.

        Args:
            prices_df: DataFrame with 'close' column and datetime index

        Returns:
            Dict with Pi Cycle indicator data

        Example:
        {
            "ma_111": 45000,
            "ma_350_x2": 42000,
            "signal": "bullish",  # or "top_signal", "bearish"
            "distance_to_top": 0.15  # percentage distance
        }
        """
        if len(prices_df) < 350:
            logger.warning("Not enough data for Pi Cycle (need 350+ days)")
            return {
                "error": "insufficient_data",
                "required_days": 350,
                "available_days": len(prices_df),
            }

        # Calculate moving averages
        ma_111 = prices_df["close"].rolling(window=111).mean()
        ma_350 = prices_df["close"].rolling(window=350).mean()
        ma_350_x2 = ma_350 * 2

        # Get latest values
        latest_ma_111 = ma_111.iloc[-1]
        latest_ma_350_x2 = ma_350_x2.iloc[-1]

        # Determine signal
        if latest_ma_111 > latest_ma_350_x2:
            # Check if recent crossover (within last 5 days)
            recent_cross = False
            if len(ma_111) >= 5:
                for i in range(1, 6):
                    if ma_111.iloc[-i] <= ma_350_x2.iloc[-i]:
                        recent_cross = True
                        break

            signal = "top_signal" if recent_cross else "overheated"
        elif latest_ma_111 < latest_ma_350_x2:
            signal = "bullish"
        else:
            signal = "neutral"

        # Calculate distance to top signal
        distance_to_top = ((latest_ma_350_x2 - latest_ma_111) / latest_ma_111) * 100

        return {
            "ma_111": float(latest_ma_111),
            "ma_350_x2": float(latest_ma_350_x2),
            "signal": signal,
            "distance_to_top_pct": float(distance_to_top),
        }

    def calculate_200_week_ma(self, prices_df: pd.DataFrame) -> Optional[float]:
        """
        Calculate 200 Week Moving Average

        The 200 Week MA has historically acted as Bitcoin's long-term floor.
        Price rarely goes below this level.

        Args:
            prices_df: DataFrame with 'close' column and datetime index

        Returns:
            200 Week MA value or None
        """
        if len(prices_df) < 1400:  # ~200 weeks
            logger.warning("Not enough data for 200 Week MA (need 1400+ days)")
            return None

        # Resample to weekly data
        weekly_prices = prices_df["close"].resample("W").last()

        if len(weekly_prices) < 200:
            return None

        # Calculate 200 Week MA
        ma_200w = weekly_prices.rolling(window=200).mean()

        return float(ma_200w.iloc[-1])

    def detect_market_cycle_phase(
        self,
        current_price: float,
        rainbow_data: Dict[str, Any],
        pi_cycle_data: Dict[str, Any],
        ma_200w: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Detect current market cycle phase using multiple indicators

        Args:
            current_price: Current price
            rainbow_data: Rainbow Chart data
            pi_cycle_data: Pi Cycle data
            ma_200w: 200 Week MA value

        Returns:
            Dict with cycle phase analysis

        Phases:
        - accumulation: Below fair value, good buying opportunity
        - markup: Rising from accumulation, bull market starts
        - distribution: Near/at top, high risk
        - markdown: Bear market, falling prices
        """
        signals = []
        phase_scores = {
            "accumulation": 0,
            "markup": 0,
            "distribution": 0,
            "markdown": 0,
        }

        # Rainbow Chart analysis
        rainbow_band = rainbow_data.get("current_band", "")
        if rainbow_band in ["buy", "basically_a_fire_sale", "accumulate"]:
            phase_scores["accumulation"] += 3
            signals.append("Rainbow: Buy/Accumulate zone")
        elif rainbow_band in ["hodl", "still_cheap"]:
            phase_scores["markup"] += 2
            signals.append("Rainbow: Fair value zone")
        elif rainbow_band in ["is_this_a_bubble", "fomo_intensifies"]:
            phase_scores["distribution"] += 2
            signals.append("Rainbow: Overheated zone")
        elif rainbow_band in ["sell", "maximum_bubble"]:
            phase_scores["distribution"] += 3
            signals.append("Rainbow: Sell zone")

        # Pi Cycle analysis
        pi_signal = pi_cycle_data.get("signal", "")
        if pi_signal == "top_signal":
            phase_scores["distribution"] += 3
            signals.append("Pi Cycle: TOP SIGNAL")
        elif pi_signal == "overheated":
            phase_scores["distribution"] += 1
            signals.append("Pi Cycle: Overheated")
        elif pi_signal == "bullish":
            phase_scores["markup"] += 2
            signals.append("Pi Cycle: Bullish")

        # 200 Week MA analysis
        if ma_200w:
            distance_from_ma = ((current_price - ma_200w) / ma_200w) * 100

            if distance_from_ma < 10:  # Within 10% of 200W MA
                phase_scores["accumulation"] += 2
                signals.append(f"200W MA: Near floor ({distance_from_ma:.1f}% above)")
            elif distance_from_ma > 100:  # More than 2x above MA
                phase_scores["distribution"] += 1
                signals.append(f"200W MA: Far above floor ({distance_from_ma:.0f}% above)")

        # Determine dominant phase
        dominant_phase = max(phase_scores, key=phase_scores.get)

        return {
            "phase": dominant_phase,
            "confidence": phase_scores[dominant_phase],
            "signals": signals,
            "phase_scores": phase_scores,
        }

    def format_rainbow_chart(self, rainbow_data: Dict[str, Any]) -> str:
        """
        Format Rainbow Chart analysis for Telegram

        Args:
            rainbow_data: Rainbow Chart data dict

        Returns:
            Formatted string
        """
        if not rainbow_data:
            return "❌ Rainbow Chart data not available"

        current_price = rainbow_data.get("current_price")
        current_band = rainbow_data.get("current_band", "").replace("_", " ").title()
        sentiment = rainbow_data.get("sentiment", "").replace("_", " ").title()
        bands = rainbow_data.get("bands", {})

        # Emoji based on band
        emoji_map = {
            "Maximum Bubble": "🔴",
            "Sell": "🟠",
            "Fomo Intensifies": "🟡",
            "Is This A Bubble": "🟡",
            "Still Cheap": "🟢",
            "Hodl": "🔵",
            "Accumulate": "🟢",
            "Buy": "🟢",
            "Basically A Fire Sale": "🟢",
        }
        emoji = emoji_map.get(current_band, "⚪")

        text = f"🌈 **Bitcoin Rainbow Chart**\n\n"
        text += f"{emoji} Current Band: **{current_band}**\n"
        text += f"💭 Sentiment: {sentiment}\n"
        text += f"💰 Current Price: ${current_price:,.0f}\n\n"

        # Show nearest bands
        text += "📊 **Key Levels:**\n"
        if "hodl" in bands:
            text += f"🔵 HODL (Fair Value): ${bands['hodl']:,.0f}\n"
        if "buy" in bands:
            text += f"🟢 Buy Zone: ${bands['buy']:,.0f}\n"
        if "sell" in bands:
            text += f"🟠 Sell Zone: ${bands['sell']:,.0f}\n"

        return text

    def format_cycle_analysis(
        self, cycle_data: Dict[str, Any], current_price: float
    ) -> str:
        """
        Format complete cycle analysis for Telegram

        Args:
            cycle_data: Cycle phase data
            current_price: Current price

        Returns:
            Formatted string
        """
        phase = cycle_data.get("phase", "").title()
        confidence = cycle_data.get("confidence", 0)
        signals = cycle_data.get("signals", [])

        # Emoji based on phase
        phase_emoji = {
            "Accumulation": "🟢",
            "Markup": "🔵",
            "Distribution": "🟡",
            "Markdown": "🔴",
        }
        emoji = phase_emoji.get(phase, "⚪")

        text = f"📊 **Market Cycle Analysis**\n\n"
        text += f"{emoji} Current Phase: **{phase}**\n"
        text += f"🎯 Confidence: {'⭐' * min(confidence, 5)}\n"
        text += f"💰 Price: ${current_price:,.0f}\n\n"

        text += "🔍 **Signals:**\n"
        for signal in signals:
            text += f"• {signal}\n"

        return text
