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
    before_sleep_log
)


logger = logging.getLogger(__name__)


class BinanceService:
    """
    Service for fetching cryptocurrency candlestick data from Binance API

    Features:
    - Klines (candlestick) data in OHLCV format
    - Multiple timeframe support (1m, 5m, 15m, 1h, 4h, 1d, etc.)
    - Symbol validation
    - Automatic retries on failures
    - pandas DataFrame output for technical analysis
    """

    BASE_URL = "https://api.binance.com/api/v3"

    # Common trading pairs on Binance
    COMMON_SYMBOLS = {
        'bitcoin': 'BTCUSDT',
        'ethereum': 'ETHUSDT',
        'binancecoin': 'BNBUSDT',
        'cardano': 'ADAUSDT',
        'solana': 'SOLUSDT',
        'ripple': 'XRPUSDT',
        'polkadot': 'DOTUSDT',
        'dogecoin': 'DOGEUSDT',
        'avalanche': 'AVAXUSDT',
        'polygon': 'MATICUSDT',
        'chainlink': 'LINKUSDT',
        'litecoin': 'LTCUSDT',
        'uniswap': 'UNIUSDT',
        'stellar': 'XLMUSDT',
        'algorand': 'ALGOUSDT',
    }

    # Timeframe intervals
    INTERVALS = {
        '1m': '1m',
        '3m': '3m',
        '5m': '5m',
        '15m': '15m',
        '30m': '30m',
        '1h': '1h',
        '2h': '2h',
        '4h': '4h',
        '6h': '6h',
        '8h': '8h',
        '12h': '12h',
        '1d': '1d',
        '3d': '3d',
        '1w': '1w',
        '1M': '1M',
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
        reraise=True
    )
    async def get_klines(
        self,
        symbol: str,
        interval: str = '1h',
        limit: int = 100
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
                logger.error(f"Invalid interval: {interval}. Use: {list(self.INTERVALS.keys())}")
                return None

            # Limit max klines
            limit = min(max(1, limit), 1000)

            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}/klines", params=params) as response:
                    if response.status == 200:
                        data = await response.json()

                        if not data:
                            logger.warning(f"No klines data for {symbol}")
                            return None

                        # Convert to DataFrame
                        df = pd.DataFrame(data, columns=[
                            'timestamp', 'open', 'high', 'low', 'close', 'volume',
                            'close_time', 'quote_volume', 'trades',
                            'taker_buy_base', 'taker_buy_quote', 'ignore'
                        ])

                        # Convert types
                        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                        df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')

                        numeric_cols = ['open', 'high', 'low', 'close', 'volume',
                                        'quote_volume', 'taker_buy_base', 'taker_buy_quote']
                        df[numeric_cols] = df[numeric_cols].astype(float)
                        df['trades'] = df['trades'].astype(int)

                        # Drop ignore column
                        df = df.drop('ignore', axis=1)

                        logger.info(f"Fetched {len(df)} klines for {symbol} ({interval})")
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
        self,
        coin_id: str,
        interval: str = '1h',
        limit: int = 100
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
        reraise=True
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
                async with session.get(f"{self.BASE_URL}/ticker/price?symbol={symbol}") as response:
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
                async with session.get(f"{self.BASE_URL}/ticker/price?symbol={symbol}") as response:
                    if response.status == 200:
                        data = await response.json()
                        return float(data.get('price', 0))
                    return None

        except Exception as e:
            logger.error(f"Error fetching current price for {symbol}: {e}")
            return None
