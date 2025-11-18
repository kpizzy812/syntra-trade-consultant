# coding: utf-8
"""
Binance API Service for cryptocurrency candlestick (OHLCV) data

Provides klines (candlestick) data for technical analysis indicators calculation.
Uses Binance public API (no authentication required).

Optional: With API keys, provides liquidation data and advanced features.
"""
import logging
import os
import hmac
import hashlib
import time
from typing import Optional, Dict, Any
from urllib.parse import urlencode
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
    FUTURES_URL_DATA = "https://fapi.binance.com/futures/data"

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
        "arbitrum": "ARBUSDT",
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
        # Optional API credentials for authenticated endpoints (liquidations, etc.)
        self.api_key = os.getenv("BINANCE_API_KEY", "")
        self.api_secret = os.getenv("BINANCE_API_SECRET", "")

        # Check if credentials are available
        self.has_credentials = bool(self.api_key and self.api_secret)
        if self.has_credentials:
            logger.info("Binance API credentials loaded (authenticated mode)")
        else:
            logger.info("Binance API running in public mode (no credentials)")

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

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Generate HMAC SHA256 signature for authenticated Binance API requests

        Args:
            params: Request parameters

        Returns:
            Hex signature string
        """
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

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
                        df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms")
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
                        logger.error(f"Binance Futures API error: {response.status}")
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
                        logger.error(f"Binance Futures API error: {response.status}")
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

    async def get_long_short_ratio(
        self, symbol: str, period: str = "5m", limit: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Get Long/Short Account Ratio from Binance Futures

        Shows the ratio of accounts with long vs short positions.
        Useful for understanding trader sentiment and potential liquidation zones.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            period: Time period ('5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d')
            limit: Number of data points (default 30, max 500)

        Returns:
            Dict with long/short ratio data or None

        Example:
        {
            "symbol": "BTCUSDT",
            "long_account": 0.76,
            "short_account": 0.24,
            "long_short_ratio": 3.17,
            "timestamp": "2024-01-01 12:00:00",
            "sentiment": "bullish"
        }
        """
        try:
            params = {"symbol": symbol, "period": period, "limit": limit}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.FUTURES_URL_DATA}/topLongShortAccountRatio", params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        if not data:
                            logger.warning(f"No long/short ratio data for {symbol}")
                            return None

                        # Get latest data point
                        latest = data[-1]
                        long_account = float(latest["longAccount"])
                        short_account = float(latest["shortAccount"])

                        # Calculate ratio
                        ratio = long_account / short_account if short_account > 0 else 0

                        # Determine sentiment
                        if ratio > 2.0:
                            sentiment = "very_bullish"
                        elif ratio > 1.2:
                            sentiment = "bullish"
                        elif ratio < 0.5:
                            sentiment = "very_bearish"
                        elif ratio < 0.8:
                            sentiment = "bearish"
                        else:
                            sentiment = "neutral"

                        return {
                            "symbol": symbol,
                            "long_account": round(long_account, 4),
                            "short_account": round(short_account, 4),
                            "long_short_ratio": round(ratio, 2),
                            "timestamp": pd.to_datetime(
                                latest["timestamp"], unit="ms"
                            ).strftime("%Y-%m-%d %H:%M:%S"),
                            "sentiment": sentiment,
                        }

                    else:
                        logger.error(f"Binance Futures API error: {response.status}")
                        return None

        except Exception as e:
            logger.exception(f"Error fetching long/short ratio for {symbol}: {e}")
            return None

    async def get_liquidation_history(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100,
    ) -> Optional[Dict[str, Any]]:
        """
        Get liquidation history from Binance Futures (REQUIRES API KEY)

        This endpoint returns forced liquidation orders for a symbol.
        Useful for analyzing liquidation events and volumes.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            start_time: Start timestamp in milliseconds (optional)
            end_time: End timestamp in milliseconds (optional)
            limit: Number of records (max 1000, default 100)

        Returns:
            Dict with liquidation data and aggregated statistics or None

        Example:
        {
            "symbol": "BTCUSDT",
            "liquidations": [
                {
                    "price": 95000.0,
                    "quantity": 1.5,
                    "value_usd": 142500.0,
                    "side": "SELL",  # SELL = long liquidation, BUY = short liquidation
                    "time": "2024-01-01 12:00:00"
                },
                ...
            ],
            "total_liquidations": 50,
            "total_volume_usd": 5000000.0,
            "long_liquidations_usd": 3000000.0,
            "short_liquidations_usd": 2000000.0,
            "period_start": "2024-01-01 10:00:00",
            "period_end": "2024-01-01 12:00:00"
        }

        Note:
        - Requires BINANCE_API_KEY and BINANCE_API_SECRET in .env
        - Only READ permission is needed
        - This is historical data (not real-time)
        """
        if not self.has_credentials:
            logger.warning(
                "Binance API credentials not configured. "
                "Cannot fetch liquidation history. "
                "Set BINANCE_API_KEY and BINANCE_API_SECRET in .env"
            )
            return None

        try:
            # Default time range: last 24 hours
            if not end_time:
                end_time = int(time.time() * 1000)
            if not start_time:
                start_time = end_time - (24 * 60 * 60 * 1000)  # 24 hours ago

            # Prepare request parameters
            params = {
                "symbol": symbol,
                "startTime": start_time,
                "endTime": end_time,
                "limit": min(limit, 1000),  # Max 1000
                "timestamp": int(time.time() * 1000),
            }

            # Generate signature
            params["signature"] = self._generate_signature(params)

            # Prepare headers
            headers = {"X-MBX-APIKEY": self.api_key}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.FUTURES_URL}/allForceOrders",
                    params=params,
                    headers=headers,
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        if not data:
                            logger.info(
                                f"No liquidations found for {symbol} in specified time range"
                            )
                            return {
                                "symbol": symbol,
                                "liquidations": [],
                                "total_liquidations": 0,
                                "total_volume_usd": 0.0,
                                "long_liquidations_usd": 0.0,
                                "short_liquidations_usd": 0.0,
                            }

                        # Process liquidation data
                        liquidations = []
                        total_volume = 0.0
                        long_liquidations = 0.0
                        short_liquidations = 0.0

                        for liq in data:
                            price = float(liq["price"])
                            qty = float(liq["origQty"])
                            value_usd = price * qty
                            side = liq["side"]

                            liquidations.append(
                                {
                                    "price": price,
                                    "quantity": qty,
                                    "value_usd": round(value_usd, 2),
                                    "side": side,
                                    "time": pd.to_datetime(
                                        liq["time"], unit="ms"
                                    ).strftime("%Y-%m-%d %H:%M:%S"),
                                }
                            )

                            total_volume += value_usd

                            # SELL side = long liquidation (forced sell)
                            # BUY side = short liquidation (forced buy)
                            if side == "SELL":
                                long_liquidations += value_usd
                            else:
                                short_liquidations += value_usd

                        return {
                            "symbol": symbol,
                            "liquidations": liquidations,
                            "total_liquidations": len(liquidations),
                            "total_volume_usd": round(total_volume, 2),
                            "long_liquidations_usd": round(long_liquidations, 2),
                            "short_liquidations_usd": round(short_liquidations, 2),
                            "period_start": pd.to_datetime(
                                start_time, unit="ms"
                            ).strftime("%Y-%m-%d %H:%M:%S"),
                            "period_end": pd.to_datetime(end_time, unit="ms").strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        }

                    elif response.status == 401:
                        logger.error(
                            "Binance API authentication failed. "
                            "Check your API keys in .env"
                        )
                        return None

                    elif response.status == 400:
                        error_data = await response.json()
                        error_msg = error_data.get("msg", "Unknown error")
                        logger.error(f"Binance API error for {symbol}: {error_msg}")
                        return None

                    else:
                        logger.error(f"Binance API error: {response.status}")
                        return None

        except Exception as e:
            logger.exception(f"Error fetching liquidation history for {symbol}: {e}")
            return None
