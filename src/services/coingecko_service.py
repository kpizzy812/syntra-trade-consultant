# coding: utf-8
"""
CoinGecko API Service for cryptocurrency data
"""
import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

import aiohttp
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from config.config import COINGECKO_API_KEY, CACHE_TTL_COINGECKO


# Create standard logger for tenacity
std_logger = logging.getLogger(__name__)


class CoinGeckoService:
    """
    Service for fetching cryptocurrency data from CoinGecko API

    Features:
    - Price data for any cryptocurrency
    - Market data (volume, market cap, etc.)
    - Historical data
    - Top cryptocurrencies by market cap
    - Simple in-memory caching with TTL
    """

    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self):
        """Initialize CoinGecko service with caching"""
        self.api_key = COINGECKO_API_KEY
        self.cache: Dict[str, tuple[Any, float]] = {}
        self.cache_ttl = CACHE_TTL_COINGECKO

    def _get_cache_key(self, endpoint: str, params: Dict) -> str:
        """Generate cache key from endpoint and params"""
        param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{endpoint}?{param_str}"

    def _get_cached(self, cache_key: str) -> Optional[Any]:
        """Get cached data if not expired"""
        if cache_key in self.cache:
            data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                logger.debug(f"Cache hit for {cache_key}")
                return data
            else:
                # Remove expired cache
                del self.cache[cache_key]
        return None

    def _set_cache(self, cache_key: str, data: Any) -> None:
        """Set cache with current timestamp"""
        self.cache[cache_key] = (data, time.time())
        logger.debug(f"Cached {cache_key}")

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(std_logger, logging.WARNING),
        reraise=True
    )
    async def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make request to CoinGecko API with caching and automatic retries

        Retries up to 3 times with exponential backoff (2-10s) for:
        - ClientError (network/HTTP errors)
        - TimeoutError (request timeout)

        Args:
            endpoint: API endpoint (e.g., '/simple/price')
            params: Query parameters

        Returns:
            JSON response or None on error
        """
        params = params or {}

        # Add API key if available (for Pro tier)
        if self.api_key:
            params['x_cg_pro_api_key'] = self.api_key

        # Check cache
        cache_key = self._get_cache_key(endpoint, params)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Make request
        url = f"{self.BASE_URL}{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._set_cache(cache_key, data)
                        return data
                    else:
                        logger.error(
                            f"CoinGecko API error: {response.status} - "
                            f"{await response.text()}"
                        )
                        return None

        except Exception as e:
            logger.exception(f"Error making CoinGecko request: {e}")
            return None

    async def get_price(
        self,
        coin_id: str,
        vs_currency: str = "usd",
        include_24h_change: bool = True,
        include_market_cap: bool = False,
        include_24h_volume: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get current price for a cryptocurrency

        Args:
            coin_id: Coin ID (e.g., 'bitcoin', 'ethereum')
            vs_currency: Currency to compare against (default: 'usd')
            include_24h_change: Include 24h price change percentage
            include_market_cap: Include market cap
            include_24h_volume: Include 24h volume

        Returns:
            Price data dict or None

        Example:
            {
                "bitcoin": {
                    "usd": 45000,
                    "usd_24h_change": 2.5,
                    "usd_market_cap": 850000000000,
                    "usd_24h_vol": 35000000000
                }
            }
        """
        params = {
            "ids": coin_id,
            "vs_currencies": vs_currency,
        }

        if include_24h_change:
            params["include_24hr_change"] = "true"

        if include_market_cap:
            params["include_market_cap"] = "true"

        if include_24h_volume:
            params["include_24hr_vol"] = "true"

        return await self._make_request("/simple/price", params)

    async def get_coin_data(self, coin_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed data for a cryptocurrency

        Args:
            coin_id: Coin ID (e.g., 'bitcoin')

        Returns:
            Detailed coin data including market data, description, etc.
        """
        params = {
            "localization": "false",
            "tickers": "false",
            "community_data": "false",
            "developer_data": "false"
        }

        return await self._make_request(f"/coins/{coin_id}", params)

    async def get_extended_market_data(self, coin_id: str) -> Optional[Dict[str, Any]]:
        """
        Get extended market data for cryptocurrency analysis

        Extracts:
        - ATH (All-Time High) and ATL (All-Time Low)
        - Price changes (7d, 30d, 90d, 1y)
        - Supply metrics (total, circulating, max)
        - Market dominance
        - Volume/Market Cap ratio

        Args:
            coin_id: Coin ID (e.g., 'bitcoin')

        Returns:
            Extended market data dict with all metrics or None

        Example:
            {
                "ath": 69000,
                "ath_date": "2021-11-10",
                "ath_change_percentage": -35.5,
                "atl": 67.81,
                "atl_date": "2013-07-06",
                "atl_change_percentage": 65000.2,
                "price_change_7d": 2.5,
                "price_change_30d": -5.2,
                "price_change_90d": 15.8,
                "price_change_1y": 45.3,
                "total_supply": 21000000,
                "circulating_supply": 19500000,
                "max_supply": 21000000,
                "market_dominance": 45.2,
                "volume_to_market_cap": 0.05
            }
        """
        try:
            # Get detailed coin data
            coin_data = await self.get_coin_data(coin_id)
            if not coin_data:
                return None

            market_data = coin_data.get('market_data', {})
            if not market_data:
                return None

            # Extract current price for calculations
            current_price = market_data.get('current_price', {}).get('usd', 0)

            # Extract ATH/ATL data
            ath = market_data.get('ath', {}).get('usd')
            ath_date = market_data.get('ath_date', {}).get('usd')
            ath_change_percentage = market_data.get('ath_change_percentage', {}).get('usd')

            atl = market_data.get('atl', {}).get('usd')
            atl_date = market_data.get('atl_date', {}).get('usd')
            atl_change_percentage = market_data.get('atl_change_percentage', {}).get('usd')

            # Extract price changes for different timeframes
            price_change_7d = market_data.get('price_change_percentage_7d')
            price_change_30d = market_data.get('price_change_percentage_30d')
            price_change_60d = market_data.get('price_change_percentage_60d')
            price_change_1y = market_data.get('price_change_percentage_1y')

            # Extract supply metrics
            total_supply = market_data.get('total_supply')
            circulating_supply = market_data.get('circulating_supply')
            max_supply = market_data.get('max_supply')

            # Extract market cap and volume
            market_cap = market_data.get('market_cap', {}).get('usd', 0)
            total_volume = market_data.get('total_volume', {}).get('usd', 0)

            # Calculate Volume/Market Cap ratio (liquidity indicator)
            volume_to_market_cap = (total_volume / market_cap) if market_cap > 0 else 0

            # Get market cap rank (for dominance estimation)
            market_cap_rank = coin_data.get('market_cap_rank')

            # Build extended data dict
            extended_data = {
                # ATH/ATL data
                "ath": ath,
                "ath_date": ath_date,
                "ath_change_percentage": ath_change_percentage,
                "atl": atl,
                "atl_date": atl_date,
                "atl_change_percentage": atl_change_percentage,

                # Price changes
                "price_change_7d": price_change_7d,
                "price_change_30d": price_change_30d,
                "price_change_60d": price_change_60d,
                "price_change_1y": price_change_1y,

                # Supply metrics
                "total_supply": total_supply,
                "circulating_supply": circulating_supply,
                "max_supply": max_supply,

                # Market metrics
                "market_cap": market_cap,
                "total_volume": total_volume,
                "volume_to_market_cap": volume_to_market_cap,
                "market_cap_rank": market_cap_rank,

                # Current price (for reference)
                "current_price": current_price
            }

            logger.debug(f"Extended market data for {coin_id}: {extended_data}")
            return extended_data

        except Exception as e:
            logger.error(f"Error getting extended market data for {coin_id}: {e}")
            return None

    async def get_market_chart(
        self,
        coin_id: str,
        vs_currency: str = "usd",
        days: int = 7
    ) -> Optional[Dict[str, Any]]:
        """
        Get historical market data (price, volume, market cap)

        Args:
            coin_id: Coin ID
            vs_currency: Currency to compare against
            days: Number of days of historical data (1, 7, 14, 30, 90, 180, 365, max)

        Returns:
            Market chart data with prices, volumes, market_caps arrays
        """
        params = {
            "vs_currency": vs_currency,
            "days": days
        }

        return await self._make_request(f"/coins/{coin_id}/market_chart", params)

    async def get_trending(self) -> Optional[Dict[str, Any]]:
        """
        Get trending cryptocurrencies

        Returns:
            List of trending coins
        """
        return await self._make_request("/search/trending")

    async def get_top_coins(
        self,
        vs_currency: str = "usd",
        limit: int = 10
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get top cryptocurrencies by market cap

        Args:
            vs_currency: Currency to compare against
            limit: Number of coins to return

        Returns:
            List of top coins with market data
        """
        params = {
            "vs_currency": vs_currency,
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "sparkline": "false"
        }

        return await self._make_request("/coins/markets", params)

    async def search_coin(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Search for a cryptocurrency by name or symbol

        Args:
            query: Search query (name or symbol)

        Returns:
            Search results with coins, exchanges, categories
        """
        params = {"query": query}
        return await self._make_request("/search", params)

    async def get_trending_coins(
        self,
        vs_currency: str = "usd",
        limit: int = 10
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get trending cryptocurrencies by market cap (alias for get_top_coins)

        Args:
            vs_currency: Currency to compare against
            limit: Number of coins to return

        Returns:
            List of trending coins with market data
        """
        return await self.get_top_coins(vs_currency, limit)

    def format_price_message(self, coin_data: Dict[str, Any], coin_id: str) -> str:
        """
        Format price data into a readable message

        Args:
            coin_data: Data from get_price()
            coin_id: Coin ID

        Returns:
            Formatted message string
        """
        if not coin_data or coin_id not in coin_data:
            return f"5 C40;>AL ?>;CG8BL 40==K5 4;O {coin_id}"

        data = coin_data[coin_id]
        price = data.get('usd', 0)
        change_24h = data.get('usd_24h_change', 0)

        # Format price with appropriate precision
        if price >= 1:
            price_str = f"${price:,.2f}"
        else:
            price_str = f"${price:.6f}"

        # Change emoji and formatting
        if change_24h > 0:
            change_emoji = "=�"
            change_str = f"+{change_24h:.2f}%"
        else:
            change_emoji = "=�"
            change_str = f"{change_24h:.2f}%"

        return (
            f"=� <b>{coin_id.upper()}</b>\n"
            f"&5=0: <b>{price_str}</b>\n"
            f"24G: {change_emoji} {change_str}"
        )
