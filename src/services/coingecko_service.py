# coding: utf-8
"""
CoinGecko API Service for cryptocurrency data
"""
import time
import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from collections import deque

import aiohttp
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from config.config import COINGECKO_API_KEY, CACHE_TTL_COINGECKO


# Create standard logger for tenacity
std_logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter using sliding window algorithm
    Tracks request timestamps to enforce rate limits
    """

    def __init__(self, max_calls: int, time_window: int = 60):
        """
        Initialize rate limiter

        Args:
            max_calls: Maximum number of calls allowed in time window
            time_window: Time window in seconds (default: 60s)
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: deque = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Wait until a request slot is available
        Removes old timestamps outside the time window
        """
        async with self._lock:
            now = time.time()

            # Remove timestamps outside time window
            while self.calls and self.calls[0] < now - self.time_window:
                self.calls.popleft()

            # If at limit, wait until oldest call expires
            if len(self.calls) >= self.max_calls:
                sleep_time = self.calls[0] + self.time_window - now
                if sleep_time > 0:
                    logger.warning(
                        f"Rate limit reached ({len(self.calls)}/{self.max_calls}), "
                        f"waiting {sleep_time:.1f}s"
                    )
                    await asyncio.sleep(sleep_time)
                    # Recursively try again
                    return await self.acquire()

            # Record this call
            self.calls.append(now)

    def get_stats(self) -> Dict[str, Any]:
        """Get current rate limiter statistics"""
        now = time.time()
        recent_calls = sum(1 for t in self.calls if t > now - self.time_window)
        return {
            "recent_calls": recent_calls,
            "max_calls": self.max_calls,
            "time_window": self.time_window,
            "usage_percent": (recent_calls / self.max_calls * 100) if self.max_calls > 0 else 0
        }


class CoinGeckoService:
    """
    Service for fetching cryptocurrency data from CoinGecko API

    Features:
    - Price data for any cryptocurrency
    - Market data (volume, market cap, etc.)
    - Historical data
    - Top cryptocurrencies by market cap
    - Advanced caching with differentiated TTL
    - Rate limiting to prevent 429 errors
    - Automatic retry with exponential backoff
    """

    # Demo API (бесплатный) и Public API используют один URL
    BASE_URL = "https://api.coingecko.com/api/v3"

    # Pro API использует другой URL (если когда-нибудь понадобится)
    # BASE_URL_PRO = "https://pro-api.coingecko.com/api/v3"

    # Differentiated cache TTL for different data types (in seconds)
    CACHE_TTL = {
        "price": 90,           # Price data: 90s (changes frequently)
        "coin_data": 300,      # Detailed coin data: 5min (relatively stable)
        "market_chart": 600,   # Historical data: 10min (doesn't change)
        "trending": 300,       # Trending coins: 5min
        "global": 300,         # Global market data: 5min
        "search": 600,         # Search results: 10min (rarely changes)
        "default": 180,        # Default: 3min
    }

    def __init__(self, rate_limit: int = 25):
        """
        Initialize CoinGecko service with caching and rate limiting

        Args:
            rate_limit: Max API calls per minute (default: 25 for Demo API with free key)
                       Set to 10 for Public API without key
        """
        self.api_key = COINGECKO_API_KEY
        self.cache: Dict[str, tuple[Any, float, str]] = {}  # (data, timestamp, cache_type)

        # Initialize rate limiter
        # Default 25/min for Demo API (30 calls/min limit, буфер 5 запросов)
        # Для Public API без ключа установите 10/min
        self.rate_limiter = RateLimiter(max_calls=rate_limit, time_window=60)

        logger.info(f"CoinGecko service initialized with {rate_limit} calls/min rate limit")

    def _get_cache_key(self, endpoint: str, params: Dict) -> str:
        """Generate cache key from endpoint and params"""
        param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{endpoint}?{param_str}"

    def _get_cache_type(self, endpoint: str) -> str:
        """Determine cache type based on endpoint"""
        if "/simple/price" in endpoint:
            return "price"
        elif "/coins/" in endpoint and "/market_chart" in endpoint:
            return "market_chart"
        elif "/coins/" in endpoint:
            return "coin_data"
        elif "/search/trending" in endpoint:
            return "trending"
        elif "/global" in endpoint:
            return "global"
        elif "/search" in endpoint:
            return "search"
        else:
            return "default"

    def _get_cached(self, cache_key: str, endpoint: str) -> Optional[Any]:
        """Get cached data if not expired"""
        if cache_key in self.cache:
            data, timestamp, cache_type = self.cache[cache_key]
            ttl = self.CACHE_TTL.get(cache_type, self.CACHE_TTL["default"])

            if time.time() - timestamp < ttl:
                logger.debug(f"Cache hit for {cache_key} (TTL: {ttl}s, type: {cache_type})")
                return data
            else:
                # Remove expired cache
                del self.cache[cache_key]
                logger.debug(f"Cache expired for {cache_key} (type: {cache_type})")
        return None

    def _set_cache(self, cache_key: str, data: Any, endpoint: str) -> None:
        """Set cache with current timestamp and type"""
        cache_type = self._get_cache_type(endpoint)
        self.cache[cache_key] = (data, time.time(), cache_type)
        ttl = self.CACHE_TTL.get(cache_type, self.CACHE_TTL["default"])
        logger.debug(f"Cached {cache_key} (TTL: {ttl}s, type: {cache_type})")

    async def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Make request to CoinGecko API with caching, rate limiting, and automatic retries

        Features:
        - Checks cache before making request
        - Rate limiting to prevent 429 errors
        - Retries with exponential backoff for network errors and 429
        - Handles 429 (Rate Limit) with longer backoff

        Args:
            endpoint: API endpoint (e.g., '/simple/price')
            params: Query parameters
            max_retries: Maximum number of retry attempts (default: 3)

        Returns:
            JSON response or None on error
        """
        params = params or {}

        # Add Demo API key to params if available
        if self.api_key:
            params["x_cg_demo_api_key"] = self.api_key

        # Check cache first
        cache_key = self._get_cache_key(endpoint, params)
        cached = self._get_cached(cache_key, endpoint)
        if cached is not None:
            return cached

        # Make request with retries
        url = f"{self.BASE_URL}{endpoint}"
        last_error = None

        for attempt in range(max_retries):
            try:
                # Wait for rate limiter before making request
                await self.rate_limiter.acquire()

                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            self._set_cache(cache_key, data, endpoint)
                            return data

                        elif response.status == 429:
                            # Rate limit exceeded - wait longer before retry
                            retry_after = int(response.headers.get("Retry-After", 60))
                            wait_time = min(retry_after, 60)  # Cap at 60s

                            logger.warning(
                                f"Rate limit (429) on attempt {attempt + 1}/{max_retries}. "
                                f"Waiting {wait_time}s before retry"
                            )

                            if attempt < max_retries - 1:
                                await asyncio.sleep(wait_time)
                                continue
                            else:
                                logger.error(
                                    f"Rate limit exceeded after {max_retries} attempts: "
                                    f"{await response.text()}"
                                )
                                return None

                        else:
                            # Other HTTP errors
                            error_text = await response.text()
                            logger.error(
                                f"CoinGecko API error {response.status}: {error_text}"
                            )
                            return None

            except (aiohttp.ClientError, TimeoutError, asyncio.TimeoutError) as e:
                last_error = e
                wait_time = min(2 ** attempt, 10)  # Exponential backoff: 1s, 2s, 4s (max 10s)

                logger.warning(
                    f"Request error on attempt {attempt + 1}/{max_retries}: {e}. "
                    f"Retrying in {wait_time}s"
                )

                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Request failed after {max_retries} attempts: {last_error}")
                    return None

            except Exception as e:
                logger.exception(f"Unexpected error making CoinGecko request: {e}")
                return None

        return None

    async def get_price(
        self,
        coin_id: str,
        vs_currency: str = "usd",
        include_24h_change: bool = True,
        include_market_cap: bool = False,
        include_24h_volume: bool = False,
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
            "developer_data": "false",
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

            market_data = coin_data.get("market_data", {})
            if not market_data:
                return None

            # Extract current price for calculations
            current_price = market_data.get("current_price", {}).get("usd", 0)

            # Extract ATH/ATL data
            ath = market_data.get("ath", {}).get("usd")
            ath_date = market_data.get("ath_date", {}).get("usd")
            ath_change_percentage = market_data.get("ath_change_percentage", {}).get(
                "usd"
            )

            atl = market_data.get("atl", {}).get("usd")
            atl_date = market_data.get("atl_date", {}).get("usd")
            atl_change_percentage = market_data.get("atl_change_percentage", {}).get(
                "usd"
            )

            # Extract price changes for different timeframes
            price_change_7d = market_data.get("price_change_percentage_7d")
            price_change_30d = market_data.get("price_change_percentage_30d")
            price_change_60d = market_data.get("price_change_percentage_60d")
            price_change_1y = market_data.get("price_change_percentage_1y")

            # Extract supply metrics
            total_supply = market_data.get("total_supply")
            circulating_supply = market_data.get("circulating_supply")
            max_supply = market_data.get("max_supply")

            # Extract market cap and volume
            market_cap = market_data.get("market_cap", {}).get("usd", 0)
            total_volume = market_data.get("total_volume", {}).get("usd", 0)

            # Calculate Volume/Market Cap ratio (liquidity indicator)
            volume_to_market_cap = (total_volume / market_cap) if market_cap > 0 else 0

            # Get market cap rank (for dominance estimation)
            market_cap_rank = coin_data.get("market_cap_rank")

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
                "current_price": current_price,
            }

            logger.debug(f"Extended market data for {coin_id}: {extended_data}")
            return extended_data

        except Exception as e:
            logger.error(f"Error getting extended market data for {coin_id}: {e}")
            return None

    async def get_market_chart(
        self, coin_id: str, vs_currency: str = "usd", days: int = 7
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
        params = {"vs_currency": vs_currency, "days": days}

        return await self._make_request(f"/coins/{coin_id}/market_chart", params)

    async def get_trending(self) -> Optional[Dict[str, Any]]:
        """
        Get trending cryptocurrencies

        Returns:
            List of trending coins
        """
        return await self._make_request("/search/trending")

    async def get_top_coins(
        self, vs_currency: str = "usd", limit: int = 10
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
            "sparkline": "false",
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
        self, vs_currency: str = "usd", limit: int = 10
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

    async def get_global_market_data(self) -> Optional[Dict[str, Any]]:
        """
        Get global cryptocurrency market data

        Returns market dominance, total market cap, volume, and other global metrics.
        Useful for understanding market phases (Bitcoin season vs Alt season).

        Returns:
            Dict with global market data or None

        Example:
        {
            "total_market_cap_usd": 3330090432842,
            "total_volume_24h_usd": 176924238498,
            "btc_dominance": 57.13,
            "eth_dominance": 11.57,
            "altcoin_dominance": 31.30,  # Calculated: 100 - BTC - ETH
            "market_cap_change_24h": -2.5,
            "active_cryptocurrencies": 19425,
            "markets": 1415,
            "defi_market_cap": 123456789,
            "defi_volume_24h": 12345678,
            "defi_dominance": 3.71
        }
        """
        data = await self._make_request("/global")

        if not data or "data" not in data:
            return None

        market_data = data["data"]

        # Extract and format key metrics
        total_market_cap = market_data.get("total_market_cap", {}).get("usd", 0)
        total_volume = market_data.get("total_volume", {}).get("usd", 0)
        btc_dominance = market_data.get("market_cap_percentage", {}).get("btc", 0)
        eth_dominance = market_data.get("market_cap_percentage", {}).get("eth", 0)

        # Calculate altcoin dominance (everything except BTC and ETH)
        altcoin_dominance = 100 - btc_dominance - eth_dominance

        # Get DeFi data if available
        defi_market_cap = market_data.get("defi_market_cap", 0)
        defi_volume = market_data.get("defi_24h_vol", 0)
        defi_dominance = market_data.get("defi_dominance", 0)

        return {
            "total_market_cap_usd": total_market_cap,
            "total_volume_24h_usd": total_volume,
            "btc_dominance": round(btc_dominance, 2),
            "eth_dominance": round(eth_dominance, 2),
            "altcoin_dominance": round(altcoin_dominance, 2),
            "market_cap_change_24h": market_data.get(
                "market_cap_change_percentage_24h_usd", 0
            ),
            "active_cryptocurrencies": market_data.get("active_cryptocurrencies", 0),
            "markets": market_data.get("markets", 0),
            "defi_market_cap": defi_market_cap,
            "defi_volume_24h": defi_volume,
            "defi_dominance": defi_dominance,
            "updated_at": market_data.get("updated_at", 0),
        }

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
        price = data.get("usd", 0)
        change_24h = data.get("usd_24h_change", 0)

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

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get current API usage statistics

        Returns:
            Dict with cache and rate limiter stats

        Example:
            {
                "rate_limiter": {
                    "recent_calls": 15,
                    "max_calls": 25,
                    "time_window": 60,
                    "usage_percent": 60.0
                },
                "cache": {
                    "total_entries": 42,
                    "by_type": {
                        "price": 10,
                        "coin_data": 15,
                        "global": 1
                    }
                }
            }
        """
        # Get rate limiter stats
        rate_stats = self.rate_limiter.get_stats()

        # Count cache entries by type
        cache_by_type = {}
        for _, _, cache_type in self.cache.values():
            cache_by_type[cache_type] = cache_by_type.get(cache_type, 0) + 1

        return {
            "rate_limiter": rate_stats,
            "cache": {
                "total_entries": len(self.cache),
                "by_type": cache_by_type,
            }
        }
