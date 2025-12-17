# coding: utf-8
"""
Technical Indicators Service

Calculates technical analysis indicators using the 'ta' library:
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- EMA/SMA (Exponential/Simple Moving Averages)
- Bollinger Bands
- Stochastic Oscillator
- ADX (Average Directional Index)
- And more...

Requires candlestick (OHLCV) data from Binance or other sources.
"""
from typing import Optional, Dict, Any
import pandas as pd

# Technical Analysis library
import ta


from loguru import logger


class TechnicalIndicators:
    """
    Service for calculating technical analysis indicators

    Uses 'ta' library (https://github.com/bukosabino/ta)
    """

    def __init__(self):
        """Initialize Technical Indicators service"""
        pass

    def calculate_all_indicators(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Calculate all major technical indicators from OHLCV data

        Args:
            df: DataFrame with columns: open, high, low, close, volume

        Returns:
            Dict with all calculated indicators or None

        Example:
            {
                "rsi": 65.5,
                "rsi_signal": "neutral",
                "macd": 150.2,
                "macd_signal": -50.1,
                "macd_histogram": 200.3,
                "macd_crossover": "bullish",
                "ema_20": 45000,
                "ema_50": 44500,
                "sma_200": 43000,
                "bb_upper": 46000,
                "bb_middle": 45000,
                "bb_lower": 44000,
                "bb_width": 4.5,
                "stoch": 75.2,
                "stoch_signal": "overbought",
                "adx": 25.5,
                "trend_strength": "moderate",
                ...
            }
        """
        try:
            if df is None or len(df) < 20:
                logger.warning(
                    "Insufficient data for indicator calculation (need at least 20 candles)"
                )
                return None

            # Ensure required columns exist
            required_cols = ["open", "high", "low", "close", "volume"]
            if not all(col in df.columns for col in required_cols):
                logger.error(f"Missing required columns. Need: {required_cols}")
                return None

            # Get latest values (most recent candle)
            close = df["close"].iloc[-1]
            high = df["high"]
            low = df["low"]
            close_series = df["close"]
            volume = df["volume"]

            # Initialize result dict
            indicators = {}

            # === RSI (Relative Strength Index) ===
            try:
                rsi = ta.momentum.RSIIndicator(close=close_series, window=14)
                rsi_value = rsi.rsi().iloc[-1]
                indicators["rsi"] = round(rsi_value, 2)
                indicators["rsi_signal"] = self._classify_rsi(rsi_value)
            except Exception as e:
                logger.warning(f"Error calculating RSI: {e}")
                indicators["rsi"] = None

            # === MACD (Moving Average Convergence Divergence) ===
            try:
                macd = ta.trend.MACD(
                    close=close_series, window_slow=26, window_fast=12, window_sign=9
                )
                macd_value = macd.macd().iloc[-1]
                macd_signal = macd.macd_signal().iloc[-1]
                macd_histogram = macd.macd_diff().iloc[-1]

                indicators["macd"] = round(macd_value, 2)
                indicators["macd_signal"] = round(macd_signal, 2)
                indicators["macd_histogram"] = round(macd_histogram, 2)
                indicators["macd_crossover"] = self._classify_macd(
                    macd_value, macd_signal
                )
            except Exception as e:
                logger.warning(f"Error calculating MACD: {e}")
                indicators["macd"] = None

            # === EMA (Exponential Moving Averages) ===
            try:
                ema_20 = (
                    ta.trend.EMAIndicator(close=close_series, window=20)
                    .ema_indicator()
                    .iloc[-1]
                )
                ema_50 = (
                    ta.trend.EMAIndicator(close=close_series, window=50)
                    .ema_indicator()
                    .iloc[-1]
                )

                indicators["ema_20"] = round(ema_20, 2)
                indicators["ema_50"] = round(ema_50, 2)
                indicators["ema_trend"] = self._classify_ema_trend(
                    close, ema_20, ema_50
                )
            except Exception as e:
                logger.warning(f"Error calculating EMA: {e}")
                indicators["ema_20"] = None

            # === SMA 200 (Long-term trend) ===
            try:
                if len(df) >= 200:
                    sma_200 = (
                        ta.trend.SMAIndicator(close=close_series, window=200)
                        .sma_indicator()
                        .iloc[-1]
                    )
                    indicators["sma_200"] = round(sma_200, 2)
                    indicators["sma_200_position"] = (
                        "above" if close > sma_200 else "below"
                    )
                else:
                    indicators["sma_200"] = None
            except Exception as e:
                logger.warning(f"Error calculating SMA 200: {e}")
                indicators["sma_200"] = None

            # === Bollinger Bands ===
            try:
                bb = ta.volatility.BollingerBands(
                    close=close_series, window=20, window_dev=2
                )
                bb_upper = bb.bollinger_hband().iloc[-1]
                bb_middle = bb.bollinger_mavg().iloc[-1]
                bb_lower = bb.bollinger_lband().iloc[-1]
                bb_width = ((bb_upper - bb_lower) / bb_middle) * 100

                indicators["bb_upper"] = round(bb_upper, 2)
                indicators["bb_middle"] = round(bb_middle, 2)
                indicators["bb_lower"] = round(bb_lower, 2)
                indicators["bb_width"] = round(bb_width, 2)
                indicators["bb_position"] = self._classify_bb_position(
                    close, bb_upper, bb_middle, bb_lower
                )
            except Exception as e:
                logger.warning(f"Error calculating Bollinger Bands: {e}")
                indicators["bb_upper"] = None

            # === Stochastic Oscillator ===
            try:
                stoch = ta.momentum.StochasticOscillator(
                    high=high, low=low, close=close_series, window=14, smooth_window=3
                )
                stoch_value = stoch.stoch().iloc[-1]
                stoch_signal = stoch.stoch_signal().iloc[-1]

                indicators["stoch"] = round(stoch_value, 2)
                indicators["stoch_signal_line"] = round(stoch_signal, 2)
                indicators["stoch_signal"] = self._classify_stochastic(stoch_value)
            except Exception as e:
                logger.warning(f"Error calculating Stochastic: {e}")
                indicators["stoch"] = None

            # === ADX (Average Directional Index) - Trend Strength ===
            try:
                adx = ta.trend.ADXIndicator(
                    high=high, low=low, close=close_series, window=14
                )
                adx_value = adx.adx().iloc[-1]

                indicators["adx"] = round(adx_value, 2)
                indicators["trend_strength"] = self._classify_adx(adx_value)
            except Exception as e:
                logger.warning(f"Error calculating ADX: {e}")
                indicators["adx"] = None

            # === ATR (Average True Range) - Volatility ===
            try:
                atr = ta.volatility.AverageTrueRange(
                    high=high, low=low, close=close_series, window=14
                )
                atr_value = atr.average_true_range().iloc[-1]
                indicators["atr"] = round(atr_value, 2)

                # ATR as % of price (normalized volatility)
                atr_percent = (atr_value / close) * 100
                indicators["atr_percent"] = round(atr_percent, 2)
                indicators["volatility"] = self._classify_atr(atr_percent)
            except Exception as e:
                logger.warning(f"Error calculating ATR: {e}")
                indicators["atr"] = None

            # === Volume indicators ===
            try:
                # On-Balance Volume (OBV)
                obv = ta.volume.OnBalanceVolumeIndicator(
                    close=close_series, volume=volume
                )
                obv_value = obv.on_balance_volume().iloc[-1]
                indicators["obv"] = round(obv_value, 2)

                # VWAP (Volume Weighted Average Price)
                vwap = ta.volume.VolumeWeightedAveragePrice(
                    high=high, low=low, close=close_series, volume=volume
                )
                vwap_value = vwap.volume_weighted_average_price().iloc[-1]
                indicators["vwap"] = round(vwap_value, 2)

                # VWAP signal
                if close > vwap_value:
                    indicators["vwap_signal"] = "above_vwap_bullish"
                else:
                    indicators["vwap_signal"] = "below_vwap_bearish"

                # Volume trend (comparing last 10 candles avg)
                recent_volume = volume.iloc[-10:].mean()
                previous_volume = volume.iloc[-20:-10].mean()
                indicators["volume_trend"] = (
                    "increasing" if recent_volume > previous_volume else "decreasing"
                )

                # Average volume
                indicators["avg_volume_10"] = round(recent_volume, 2)
                indicators["avg_volume_20"] = round(previous_volume, 2)
            except Exception as e:
                logger.warning(f"Error calculating Volume indicators: {e}")
                indicators["obv"] = None
                indicators["vwap"] = None

            logger.info(
                f"Calculated {len([v for v in indicators.values() if v is not None])} indicators successfully"
            )
            return indicators

        except Exception as e:
            logger.exception(f"Error in calculate_all_indicators: {e}")
            return None

    # === Classification helpers ===

    @staticmethod
    def _classify_rsi(rsi: float) -> str:
        """Classify RSI signal"""
        if rsi >= 70:
            return "overbought"
        elif rsi <= 30:
            return "oversold"
        else:
            return "neutral"

    @staticmethod
    def _classify_macd(macd: float, signal: float) -> str:
        """Classify MACD crossover"""
        if macd > signal:
            return "bullish"
        else:
            return "bearish"

    @staticmethod
    def _classify_ema_trend(price: float, ema_20: float, ema_50: float) -> str:
        """Classify EMA trend"""
        if price > ema_20 > ema_50:
            return "strong_uptrend"
        elif price > ema_20 and ema_20 < ema_50:
            return "uptrend"
        elif price < ema_20 < ema_50:
            return "strong_downtrend"
        elif price < ema_20 and ema_20 > ema_50:
            return "downtrend"
        else:
            return "sideways"

    @staticmethod
    def _classify_bb_position(
        price: float, upper: float, middle: float, lower: float
    ) -> str:
        """Classify price position relative to Bollinger Bands"""
        if price >= upper:
            return "above_upper"
        elif price <= lower:
            return "below_lower"
        elif price > middle:
            return "upper_half"
        else:
            return "lower_half"

    @staticmethod
    def _classify_stochastic(stoch: float) -> str:
        """Classify Stochastic Oscillator"""
        if stoch >= 80:
            return "overbought"
        elif stoch <= 20:
            return "oversold"
        else:
            return "neutral"

    @staticmethod
    def _classify_adx(adx: float) -> str:
        """Classify ADX trend strength"""
        if adx < 20:
            return "weak"
        elif adx < 40:
            return "moderate"
        else:
            return "strong"

    @staticmethod
    def _classify_atr(atr_percent: float) -> str:
        """Classify ATR (volatility) as percentage of price"""
        if atr_percent < 1:
            return "very_low"
        elif atr_percent < 2:
            return "low"
        elif atr_percent < 4:
            return "moderate"
        elif atr_percent < 6:
            return "high"
        else:
            return "very_high"

    def format_indicators_for_prompt(self, indicators: Dict[str, Any]) -> str:
        """
        Format indicators into readable text for AI prompt

        Args:
            indicators: Dict from calculate_all_indicators()

        Returns:
            Formatted string with all indicators
        """
        if not indicators:
            return "Технические индикаторы недоступны."

        lines = []

        # RSI
        if indicators.get("rsi"):
            lines.append(
                f"RSI (14): {indicators['rsi']} ({indicators.get('rsi_signal', 'N/A')})"
            )

        # MACD
        if indicators.get("macd"):
            lines.append(
                f"MACD: {indicators['macd']}, Signal: {indicators['macd_signal']}, "
                f"Histogram: {indicators['macd_histogram']} ({indicators.get('macd_crossover', 'N/A')})"
            )

        # EMAs
        if indicators.get("ema_20"):
            lines.append(
                f"EMA 20: {indicators['ema_20']}, EMA 50: {indicators['ema_50']} "
                f"(Trend: {indicators.get('ema_trend', 'N/A')})"
            )

        # SMA 200
        if indicators.get("sma_200"):
            lines.append(
                f"SMA 200: {indicators['sma_200']} (Price {indicators.get('sma_200_position', 'N/A')})"
            )

        # Bollinger Bands
        if indicators.get("bb_upper"):
            lines.append(
                f"Bollinger Bands: Upper {indicators['bb_upper']}, Middle {indicators['bb_middle']}, "
                f"Lower {indicators['bb_lower']} (Width: {indicators['bb_width']}%, "
                f"Position: {indicators.get('bb_position', 'N/A')})"
            )

        # Stochastic
        if indicators.get("stoch"):
            lines.append(
                f"Stochastic: {indicators['stoch']} ({indicators.get('stoch_signal', 'N/A')})"
            )

        # ADX
        if indicators.get("adx"):
            lines.append(
                f"ADX: {indicators['adx']} (Trend: {indicators.get('trend_strength', 'N/A')})"
            )

        # Volume
        if indicators.get("volume_trend"):
            lines.append(f"Volume Trend: {indicators['volume_trend']}")

        return "\n".join(lines)
