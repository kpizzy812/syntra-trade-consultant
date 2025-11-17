# coding: utf-8
"""
Binance API Service for cryptocurrency candlestick (OHLCV) data

Provides klines (candlestick) data for technical analysis indicators calculation.
Uses Binance public API (no authentication required).
"""
import logging
from typing import Optional, List, Dict, Any
import aiohttp
import pandas as pd

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)


logger = logging.getLogger(__name__)


class BinanceService:
    """
    Service for fetching cryptocurrency data from Binance API

    Features:
    - Klines (candlestick) data in OHLCV format
    - Funding rates for perpetual futures (sentiment indicator)
    - Open Interest data
    - Multiple timeframe support (1m, 5m, 15m, 1h, 4h, 1d, etc.)
    - Symbol validation
    - Automatic retries on failures
    - pandas DataFrame output for technical analysis
    """

    BASE_URL = "https://api.binance.com/api/v3"
    FUTURES_URL = "https://fapi.binance.com/fapi/v1"

    # Common trading pairs on Binance
    COMMON_SYMBOLS = {
        "bitcoin": "BTCUSDT",
        "ethereum": "ETHUSDT",
        "binancecoin": "BNBUSDT",
        "cardano": "ADAUSDT",
        "solana": "SOLUSDT",
        "ripple": "XRPUSDT",
        "polkadot": "DOTUSDT",
        "dogecoin": "DOGEUSDT",
        "avalanche": "AVAXUSDT",
        "polygon": "MATICUSDT",
        "chainlink": "LINKUSDT",
        "litecoin": "LTCUSDT",
        "uniswap": "UNIUSDT",
        "stellar": "XLMUSDT",
        "algorand": "ALGOUSDT",
    }

    # Timeframe intervals
    INTERVALS = {
        "1m": "1m",
        "3m": "3m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "2h": "2h",
        "4h": "4h",
        "6h": "6h",
        "8h": "8h",
        "12h": "12h",
        "1d": "1d",
        "3d": "3d",
        "1w": "1w",
        "1M": "1M",
    }

    def __init__(self):
        """Initialize Binance service"""
        pass

    def get_symbol(self, coin_id: str) -> Optional[str]:
        """
        Convert CoinGecko coin ID to Binance symbol

        Args:
            coin_id: CoinGecko ID (e.g., 'bitcoin', 'ethereum')

        Returns:
            Binance symbol (e.g., 'BTCUSDT') or None
        """
        # Try direct mapping
        if coin_id.lower() in self.COMMON_SYMBOLS:
            return self.COMMON_SYMBOLS[coin_id.lower()]

        # Try uppercase + USDT
        symbol = f"{coin_id.upper()}USDT"
        return symbol

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def get_klines(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> Optional[pd.DataFrame]:
        """
        Get candlestick (klines) data from Binance with automatic retries

        Retries up to 3 times with exponential backoff for network errors.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            interval: Timeframe interval ('1m', '5m', '15m', '1h', '4h', '1d', etc.)
            limit: Number of candlesticks (max 1000)

        Returns:
            pandas DataFrame with OHLCV data or None

        DataFrame columns:
            - timestamp: Unix timestamp (milliseconds)
            - open: Opening price
            - high: Highest price
            - low: Lowest price
            - close: Closing price
            - volume: Trading volume
            - close_time: Close timestamp
            - quote_volume: Quote asset volume
            - trades: Number of trades
            - taker_buy_base: Taker buy base asset volume
            - taker_buy_quote: Taker buy quote asset volume
        """
        try:
            # Validate interval
            if interval not in self.INTERVALS:
                logger.error(
                    f"Invalid interval: {interval}. Use: {list(self.INTERVALS.keys())}"
                )
                return None

            # Limit max klines
            limit = min(max(1, limit), 1000)

            params = {"symbol": symbol, "interval": interval, "limit": limit}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/klines", params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        if not data:
                            logger.warning(f"No klines data for {symbol}")
                            return None

                        # Convert to DataFrame
                        df = pd.DataFrame(
                            data,
                            columns=[
                                "timestamp",
                                "open",
                                "high",
                                "low",
                                "close",
                                "volume",
                                "close_time",
                                "quote_volume",
                                "trades",
                                "taker_buy_base",
                                "taker_buy_quote",
                                "ignore",
                            ],
                        )

                        # Convert types
                        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

                        numeric_cols = [
                            "open",
                            "high",
                            "low",
                            "close",
                            "volume",
                            "quote_volume",
                            "taker_buy_base",
                            "taker_buy_quote",
                        ]
                        df[numeric_cols] = df[numeric_cols].astype(float)
                        df["trades"] = df["trades"].astype(int)

                        # Drop ignore column
                        df = df.drop("ignore", axis=1)

                        logger.info(
                            f"Fetched {len(df)} klines for {symbol} ({interval})"
                        )
                        return df

                    elif response.status == 400:
                        # Invalid symbol or parameters
                        error_data = await response.json()
                        logger.warning(f"Binance API error for {symbol}: {error_data}")
                        return None
                    else:
                        logger.error(f"Binance API error: {response.status}")
                        return None

        except Exception as e:
            logger.exception(f"Error fetching klines for {symbol}: {e}")
            return None

    async def get_klines_by_coin_id(
        self, coin_id: str, interval: str = "1h", limit: int = 100
    ) -> Optional[pd.DataFrame]:
        """
        Get klines data using CoinGecko coin ID

        Args:
            coin_id: CoinGecko ID (e.g., 'bitcoin', 'ethereum')
            interval: Timeframe interval
            limit: Number of candlesticks

        Returns:
            pandas DataFrame with OHLCV data or None
        """
        symbol = self.get_symbol(coin_id)
        if not symbol:
            logger.warning(f"Could not map coin_id '{coin_id}' to Binance symbol")
            return None

        return await self.get_klines(symbol, interval, limit)

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def check_symbol_exists(self, symbol: str) -> bool:
        """
        Check if trading symbol exists on Binance

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            True if symbol exists, False otherwise
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/ticker/price?symbol={symbol}"
                ) as response:
                    return response.status == 200

        except Exception as e:
            logger.warning(f"Error checking symbol {symbol}: {e}")
            return False

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a symbol

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            Current price or None
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/ticker/price?symbol={symbol}"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return float(data.get("price", 0))
                    return None

        except Exception as e:
            logger.error(f"Error fetching current price for {symbol}: {e}")
            return None

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def get_funding_rate(
        self, symbol: str, limit: int = 100
    ) -> Optional[pd.DataFrame]:
        """
        Get funding rate history for perpetual futures

        Funding rates indicate market sentiment:
        - Positive rate: Longs pay shorts (bullish sentiment, potential overheating)
        - Negative rate: Shorts pay longs (bearish sentiment)

        Rate limit: 500/5min/IP (shared with /fapi/v1/fundingInfo)

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            limit: Number of data points (max 1000, default 100)

        Returns:
            pandas DataFrame with funding rate history or None

        DataFrame columns:
            - symbol: Trading pair
            - funding_rate: Funding rate (e.g., 0.0001 = 0.01%)
            - funding_time: Funding interval timestamp
        """
        try:
            limit = min(max(1, limit), 1000)

            params = {"symbol": symbol, "limit": limit}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.FUTURES_URL}/fundingRate", params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        if not data:
                            logger.warning(f"No funding rate data for {symbol}")
                            return None

                        # Convert to DataFrame
                        df = pd.DataFrame(data)

                        # Convert types
                        df["fundingTime"] = pd.to_datetime(
                            df["fundingTime"], unit="ms"
                        )
                        df["fundingRate"] = df["fundingRate"].astype(float)

                        # Rename columns
                        df = df.rename(
                            columns={
                                "fundingTime": "funding_time",
                                "fundingRate": "funding_rate",
                            }
                        )

                        logger.info(
                            f"Fetched {len(df)} funding rate data points for {symbol}"
                        )
                        return df

                    elif response.status == 400:
                        error_data = await response.json()
                        logger.warning(
                            f"Binance Futures API error for {symbol}: {error_data}"
                        )
                        return None
                    else:
                        logger.error(
                            f"Binance Futures API error: {response.status}"
                        )
                        return None

        except Exception as e:
            logger.exception(f"Error fetching funding rate for {symbol}: {e}")
            return None

    async def get_latest_funding_rate(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest funding rate for a symbol

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            Dict with latest funding rate info or None

        Example:
        {
            "symbol": "BTCUSDT",
            "funding_rate": 0.0001,
            "funding_rate_pct": 0.01,
            "funding_time": datetime,
            "sentiment": "bullish"
        }
        """
        df = await self.get_funding_rate(symbol, limit=1)

        if df is not None and len(df) > 0:
            latest = df.iloc[-1]
            rate = latest["funding_rate"]

            # Determine sentiment
            if rate > 0.0005:  # > 0.05%
                sentiment = "very_bullish"
            elif rate > 0:
                sentiment = "bullish"
            elif rate < -0.0005:
                sentiment = "very_bearish"
            else:
                sentiment = "bearish"

            return {
                "symbol": latest["symbol"],
                "funding_rate": rate,
                "funding_rate_pct": rate * 100,  # Convert to percentage
                "funding_time": latest["funding_time"],
                "sentiment": sentiment,
            }

        return None

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def get_open_interest(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current open interest for perpetual futures

        Open Interest = total number of outstanding derivative contracts
        Rising OI + Rising Price = Bullish (new longs opening)
        Rising OI + Falling Price = Bearish (new shorts opening)
        Falling OI = Positions closing (profit-taking or stop-losses)

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            Dict with open interest data or None

        Example:
        {
            "symbol": "BTCUSDT",
            "open_interest": 123456.789,
            "timestamp": datetime
        }
        """
        try:
            params = {"symbol": symbol}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.FUTURES_URL}/openInterest", params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        return {
                            "symbol": data["symbol"],
                            "open_interest": float(data["openInterest"]),
                            "timestamp": pd.to_datetime(data["time"], unit="ms"),
                        }

                    else:
                        logger.error(
                            f"Binance Futures API error: {response.status}"
                        )
                        return None

        except Exception as e:
            logger.exception(f"Error fetching open interest for {symbol}: {e}")
            return None

    async def format_funding_rate(self, funding_data: Dict[str, Any]) -> str:
        """
        Format funding rate data for Telegram display

        Args:
            funding_data: Funding rate dict

        Returns:
            Formatted string for Telegram
        """
        if not funding_data:
            return "❌ Funding rate data not available"

        symbol = funding_data.get("symbol")
        rate = funding_data.get("funding_rate", 0)
        rate_pct = funding_data.get("funding_rate_pct", 0)
        sentiment = funding_data.get("sentiment", "neutral")

        # Emoji based on sentiment
        emoji_map = {
            "very_bullish": "🚀",
            "bullish": "📈",
            "bearish": "📉",
            "very_bearish": "🔻",
        }
        emoji = emoji_map.get(sentiment, "➡️")

        text = f"💰 **Funding Rate: {symbol}**\n\n"
        text += f"📊 Rate: {rate_pct:.4f}%\n"
        text += f"{emoji} Sentiment: {sentiment.replace('_', ' ').title()}\n\n"

        # Explanation
        if rate > 0:
            text += "📌 Longs are paying shorts → Bullish sentiment in market\n"
            if rate > 0.0005:
                text += "⚠️ High funding rate may indicate overheated longs\n"
        else:
            text += "📌 Shorts are paying longs → Bearish sentiment in market\n"
            if rate < -0.0005:
                text += "⚠️ High negative rate may indicate overheated shorts\n"

        return text
