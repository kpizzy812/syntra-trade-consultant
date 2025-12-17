# coding: utf-8
"""
Binance API Service for cryptocurrency candlestick (OHLCV) data

Provides klines (candlestick) data for technical analysis indicators calculation.
Uses Binance public API (no authentication required).

Optional: With API keys, provides liquidation data and advanced features.
"""
import hmac
import hashlib
import time
import logging  # Needed for tenacity before_sleep_log level constants
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

from loguru import logger
from config.config import BINANCE_API_KEY, BINANCE_API_SECRET
from config.cache_config import CacheTTL
from src.cache import get_redis_manager, CacheKeyBuilder


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
        """Initialize Binance service with Redis caching"""
        # Optional API credentials for authenticated endpoints (liquidations, etc.)
        self.api_key = BINANCE_API_KEY
        self.api_secret = BINANCE_API_SECRET

        # Redis cache manager
        self.redis = get_redis_manager()

        # Check if credentials are available
        self.has_credentials = bool(self.api_key and self.api_secret)
        if self.has_credentials:
            logger.info(
                f"Binance API credentials loaded (authenticated mode), "
                f"Redis cache: {'enabled' if self.redis.is_available() else 'disabled'}"
            )
        else:
            logger.info(
                f"Binance API running in public mode (no credentials), "
                f"Redis cache: {'enabled' if self.redis.is_available() else 'disabled'}"
            )

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

    def _get_klines_ttl(self, interval: str) -> int:
        """Get appropriate TTL for klines based on interval"""
        interval_ttl_map = {
            "1m": CacheTTL.BINANCE_KLINES_1M,
            "5m": CacheTTL.BINANCE_KLINES_5M,
            "15m": CacheTTL.BINANCE_KLINES_15M,
            "1h": CacheTTL.BINANCE_KLINES_1H,
            "4h": CacheTTL.BINANCE_KLINES_4H,
            "1d": CacheTTL.BINANCE_KLINES_1D,
        }
        return interval_ttl_map.get(interval, CacheTTL.BINANCE_KLINES_1H)

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
        Get candlestick (klines) data from Binance with Redis caching and automatic retries

        Кэширует исторические данные с разумным TTL (свечи не меняются ретроспективно)

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            interval: Timeframe interval ('1m', '5m', '15m', '1h', '4h', '1d', etc.)
            limit: Number of candlesticks (max 1000)

        Returns:
            pandas DataFrame with OHLCV data or None

        DataFrame columns:
            - timestamp: Unix timestamp (milliseconds)
            - open, high, low, close, volume, close_time, quote_volume, trades
            - taker_buy_base, taker_buy_quote
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

            # Check cache first
            cache_key = CacheKeyBuilder.build("binance", "klines", {
                "symbol": symbol,
                "interval": interval,
                "limit": str(limit)
            })
            cached = await self.redis.get(cache_key)

            if cached is not None:
                # Redis manager returns already deserialized JSON (list)
                # Check if it's already a list or still a JSON string
                if isinstance(cached, str):
                    df = pd.read_json(cached, orient='records')
                else:
                    # Already deserialized as list of dicts
                    df = pd.DataFrame(cached)

                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df["close_time"] = pd.to_datetime(df["close_time"])
                logger.debug(f"Redis cache HIT: {cache_key} ({len(df)} klines)")
                return df

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

                        # Cache the DataFrame (serialize to JSON)
                        ttl = self._get_klines_ttl(interval)
                        df_json = df.to_json(orient='records', date_format='iso')
                        await self.redis.set(cache_key, df_json, ttl=ttl)
                        logger.debug(f"Redis cache SET: {cache_key} (TTL={ttl}s, {len(df)} klines)")

                        logger.info(
                            f"Fetched {len(df)} klines for {symbol} ({interval})"
                        )
                        return df

                    elif response.status == 400:
                        # Invalid symbol or parameters
                        try:
                            error_data = await response.json()
                            error_msg = error_data.get("msg", str(error_data))
                        except Exception:
                            error_msg = await response.text()
                        logger.warning(f"Binance API error for {symbol}: {error_msg}")
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
                        try:
                            error_data = await response.json()
                            error_msg = error_data.get("msg", str(error_data))
                        except Exception:
                            error_msg = await response.text()
                        logger.warning(
                            f"Binance Futures API error for {symbol}: {error_msg}"
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
            limit: Number of records (max 100, default 100)

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
        - Time range must be within the last 7 days (API limitation)
        - Max limit is 100 records per request
        - Uses /fapi/v1/forceOrders endpoint
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

            # Binance API limitation: max 7 days time range
            max_range = 7 * 24 * 60 * 60 * 1000  # 7 days in milliseconds
            if end_time - start_time > max_range:
                logger.warning(
                    f"Time range too large for {symbol}. "
                    "Binance API allows max 7 days. Adjusting start_time."
                )
                start_time = end_time - max_range

            # Prepare request parameters
            params = {
                "symbol": symbol,
                # 🔧 TEMP: Remove autoCloseType to test if it's blocking results
                # "autoCloseType": "LIQUIDATION",  # This param may be deprecated/wrong
                "startTime": start_time,
                "endTime": end_time,
                "limit": min(limit, 100),  # Max 100 for new endpoint
                "timestamp": int(time.time() * 1000),
            }

            # Generate signature
            params["signature"] = self._generate_signature(params)

            # Prepare headers
            headers = {"X-MBX-APIKEY": self.api_key}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.FUTURES_URL}/forceOrders",  # Updated endpoint
                    params=params,
                    headers=headers,
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        # 🔧 DEBUG: Log what API returns
                        logger.debug(f"Liquidation API response: {len(data) if data else 0} records")
                        if data and len(data) > 0:
                            logger.debug(f"First liquidation: {data[0]}")

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
                        try:
                            error_data = await response.json()
                            error_msg = error_data.get("msg", "Unknown error")
                        except Exception:
                            error_msg = await response.text()
                        logger.error(f"Binance API error for {symbol}: {error_msg}")
                        return None

                    else:
                        logger.error(f"Binance API error: {response.status}")
                        return None

        except Exception as e:
            logger.exception(f"Error fetching liquidation history for {symbol}: {e}")
            return None

    async def get_instrument_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get instrument info from Binance Futures for position sizing

        Returns:
            {
                "symbol": "BTCUSDT",
                "qty_step": "0.001",
                "tick_size": "0.1",
                "min_order_qty": "0.001",
                "max_order_qty": "1000",
                "min_notional": "5",
                "max_leverage": 125
            }
        """
        try:
            url = f"https://fapi.binance.com/fapi/v1/exchangeInfo"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()

                        # Find symbol in list
                        symbols = data.get("symbols", [])
                        symbol_info = next(
                            (s for s in symbols if s["symbol"] == symbol),
                            None
                        )

                        if not symbol_info:
                            logger.warning(f"Symbol {symbol} not found in Binance Futures")
                            return None

                        # Extract filters
                        filters = {f["filterType"]: f for f in symbol_info.get("filters", [])}

                        lot_size = filters.get("LOT_SIZE", {})
                        price_filter = filters.get("PRICE_FILTER", {})
                        min_notional_filter = filters.get("MIN_NOTIONAL", {})

                        result = {
                            "symbol": symbol,
                            "qty_step": lot_size.get("stepSize", "0.001"),
                            "tick_size": price_filter.get("tickSize", "0.1"),
                            "min_order_qty": lot_size.get("minQty", "0.001"),
                            "max_order_qty": lot_size.get("maxQty", "1000"),
                            "min_notional": min_notional_filter.get("notional", "5"),
                            "max_leverage": 125  # Default, can be different per symbol
                        }

                        logger.info(
                            f"Instrument info for {symbol}: "
                            f"qtyStep={result['qty_step']}, "
                            f"tickSize={result['tick_size']}"
                        )

                        return result

                    else:
                        logger.error(f"Failed to fetch instrument info: {response.status}")
                        return None

        except Exception as e:
            logger.exception(f"Error fetching instrument info for {symbol}: {e}")
            return None


# Singleton instance
binance_service = BinanceService()
