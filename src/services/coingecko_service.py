# coding: utf-8
"""
CoinGecko API Service for cryptocurrency data
"""
import time
import asyncio
from typing import Optional, Dict, Any, List
from collections import deque

import aiohttp
from loguru import logger

from config.config import COINGECKO_API_KEY
from src.cache import get_redis_manager, CacheKeyBuilder


# ============================================================================
# STATIC FALLBACK DATA (Last resort when all caches fail)
# ============================================================================
# Эти данные используются ТОЛЬКО когда:
# 1. CoinGecko API недоступен (503, 500, network errors)
# 2. Redis cache недоступен или пуст
# 3. In-memory cache пуст
#
# Данные примерные, но реалистичные для основных монет
# ============================================================================

STATIC_FALLBACK_PRICES = {
    "bitcoin": {
        "usd": 43000,
        "usd_24h_change": 2.5,
        "usd_market_cap": 840000000000,
        "usd_24h_vol": 28000000000
    },
    "ethereum": {
        "usd": 2300,
        "usd_24h_change": 1.8,
        "usd_market_cap": 275000000000,
        "usd_24h_vol": 15000000000
    },
    "toncoin": {
        "usd": 2.3,
        "usd_24h_change": 3.2,
        "usd_market_cap": 8000000000,
        "usd_24h_vol": 120000000
    },
    "binancecoin": {
        "usd": 310,
        "usd_24h_change": 1.5,
        "usd_market_cap": 47000000000,
        "usd_24h_vol": 1200000000
    },
    "solana": {
        "usd": 105,
        "usd_24h_change": 4.2,
        "usd_market_cap": 45000000000,
        "usd_24h_vol": 2500000000
    },
    "ripple": {
        "usd": 0.52,
        "usd_24h_change": -0.8,
        "usd_market_cap": 28000000000,
        "usd_24h_vol": 1100000000
    },
    "cardano": {
        "usd": 0.48,
        "usd_24h_change": 1.2,
        "usd_market_cap": 17000000000,
        "usd_24h_vol": 450000000
    },
    "dogecoin": {
        "usd": 0.085,
        "usd_24h_change": -1.5,
        "usd_market_cap": 12000000000,
        "usd_24h_vol": 600000000
    },
    "polkadot": {
        "usd": 7.2,
        "usd_24h_change": 2.1,
        "usd_market_cap": 9000000000,
        "usd_24h_vol": 280000000
    },
    "chainlink": {
        "usd": 15.5,
        "usd_24h_change": 3.5,
        "usd_market_cap": 8500000000,
        "usd_24h_vol": 450000000
    }
}


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded and waiting would take too long"""
    pass


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

    async def acquire(self, max_wait: float = 10.0) -> bool:
        """
        Wait until a request slot is available

        Args:
            max_wait: Maximum time to wait in seconds (default: 10s)

        Returns:
            True if slot acquired, False if max_wait exceeded

        Raises:
            RateLimitError: If max_wait time exceeded
        """
        async with self._lock:
            now = time.time()

            # Remove timestamps outside time window
            while self.calls and self.calls[0] < now - self.time_window:
                self.calls.popleft()

            # If at limit, check if we should wait
            if len(self.calls) >= self.max_calls:
                sleep_time = self.calls[0] + self.time_window - now

                if sleep_time > 0:
                    # If wait time exceeds max_wait, raise error instead of waiting
                    if sleep_time > max_wait:
                        logger.error(
                            f"Rate limit reached ({len(self.calls)}/{self.max_calls}). "
                            f"Would need to wait {sleep_time:.1f}s, but max_wait is {max_wait:.1f}s. "
                            f"Consider using cached data or reducing API calls."
                        )
                        raise RateLimitExceeded(
                            f"Rate limit exceeded. Need to wait {sleep_time:.1f}s (max: {max_wait:.1f}s)"
                        )

                    logger.warning(
                        f"Rate limit reached ({len(self.calls)}/{self.max_calls}), "
                        f"waiting {sleep_time:.1f}s (max allowed: {max_wait:.1f}s)"
                    )
                    await asyncio.sleep(sleep_time)
                    # Recursively try again
                    return await self.acquire(max_wait)

            # Record this call
            self.calls.append(now)
            return True

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
        "categories": 3600,    # Categories with market data: 1 hour (changes slowly)
        "categories_list": 86400,  # Category list: 24 hours (almost static)
        "markets": 180,        # Coins markets endpoint: 3min
        "default": 180,        # Default: 3min
    }

    def __init__(self, rate_limit: int = 25):
        """
        Initialize CoinGecko service with Redis caching and rate limiting

        Args:
            rate_limit: Max API calls per minute (default: 25 for Demo API with free key)
                       Set to 10 for Public API without key
        """
        self.api_key = COINGECKO_API_KEY

        # Redis cache manager (graceful degradation if unavailable)
        self.redis = get_redis_manager()

        # Fallback in-memory cache (if Redis unavailable)
        self._fallback_cache: Dict[str, tuple[Any, float, str]] = {}

        # Initialize rate limiter (CRITICAL - must respect API limits!)
        # Default 25/min for Demo API (30 calls/min limit, буфер 5 запросов)
        # Для Public API без ключа установите 10/min
        self.rate_limiter = RateLimiter(max_calls=rate_limit, time_window=60)

        logger.info(
            f"CoinGecko service initialized with {rate_limit} calls/min rate limit "
            f"(Redis cache: {'enabled' if self.redis.is_available() else 'disabled'})"
        )

    def _build_cache_key(self, endpoint: str, params: Dict) -> str:
        """
        Build Redis cache key from endpoint and params

        Format: syntra:coingecko:{method}:{params}
        """
        # Extract method from endpoint (e.g., "/simple/price" -> "price")
        method = endpoint.strip("/").replace("/", "_")

        # Build params string
        params_dict = {k: str(v) for k, v in sorted(params.items()) if k != "x_cg_demo_api_key"}

        return CacheKeyBuilder.build("coingecko", method, params_dict)

    def _get_cache_type(self, endpoint: str) -> str:
        """Determine cache type based on endpoint"""
        if "/simple/price" in endpoint:
            return "price"
        elif "/coins/" in endpoint and "/market_chart" in endpoint:
            return "market_chart"
        elif "/coins/categories/list" in endpoint:
            return "categories_list"
        elif "/coins/categories" in endpoint:
            return "categories"
        elif "/coins/markets" in endpoint:
            return "markets"
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

    async def _get_cached(self, cache_key: str, endpoint: str) -> Optional[Any]:
        """
        Get cached data from Redis (with fallback to in-memory)

        Uses differentiated TTL based on endpoint type
        """
        # Try Redis first
        cached = await self.redis.get(cache_key)
        if cached is not None:
            cache_type = self._get_cache_type(endpoint)
            ttl = self.CACHE_TTL.get(cache_type, self.CACHE_TTL["default"])
            logger.debug(f"Redis cache HIT: {cache_key} (type: {cache_type}, TTL: {ttl}s)")
            return cached

        # Fallback to in-memory cache if Redis unavailable
        if not self.redis.is_available() and cache_key in self._fallback_cache:
            data, timestamp, cache_type = self._fallback_cache[cache_key]
            ttl = self.CACHE_TTL.get(cache_type, self.CACHE_TTL["default"])

            if time.time() - timestamp < ttl:
                logger.debug(f"Fallback cache HIT: {cache_key} (TTL: {ttl}s)")
                return data
            else:
                # Don't delete expired cache - keep it for emergency fallback
                logger.debug(f"Fallback cache EXPIRED: {cache_key} (kept for emergency fallback)")

        return None

    def _get_static_fallback(self, params: Dict[str, Any], endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Get static fallback data as LAST RESORT when all other options fail

        This returns hardcoded approximate prices for major coins when:
        1. CoinGecko API is down
        2. All caches (Redis + in-memory) are empty/unavailable
        3. User still needs SOME data to display

        Args:
            params: Original request parameters
            endpoint: API endpoint being requested

        Returns:
            Static fallback data or None
        """
        # Only provide static fallback for price endpoints
        if "/simple/price" not in endpoint:
            return None

        # Extract coin IDs from params
        coin_ids_str = params.get("ids", "")
        if not coin_ids_str:
            return None

        coin_ids = coin_ids_str.split(",")

        # Build response from static fallback data
        result = {}
        found_any = False

        for coin_id in coin_ids:
            coin_id = coin_id.strip()
            if coin_id in STATIC_FALLBACK_PRICES:
                result[coin_id] = STATIC_FALLBACK_PRICES[coin_id].copy()
                found_any = True

        if found_any:
            logger.warning(
                f"⚠️ Using STATIC FALLBACK data for {len(result)} coins. "
                f"This is APPROXIMATE data - actual prices may differ!"
            )
            return result

        return None

    async def _get_stale_cache(self, cache_key: str, endpoint: str, params: Dict[str, Any]) -> Optional[Any]:
        """
        Get stale cached data (ignoring TTL) as emergency fallback when API is down

        Priority:
        1. Stale Redis cache (ignoring TTL)
        2. Stale in-memory cache (ignoring TTL)
        3. Static fallback data (hardcoded approximate values)

        Args:
            cache_key: Cache key to retrieve
            endpoint: API endpoint (for logging)
            params: Request parameters (for static fallback)

        Returns:
            Cached data or None
        """
        # Try Redis first (with extended TTL tolerance)
        cached = await self.redis.get(cache_key)
        if cached is not None:
            logger.warning(f"Using STALE Redis cache as fallback: {cache_key}")
            return cached

        # Try in-memory cache (even if expired)
        if cache_key in self._fallback_cache:
            data, timestamp, cache_type = self._fallback_cache[cache_key]
            age_hours = (time.time() - timestamp) / 3600
            logger.warning(
                f"Using STALE fallback cache (age: {age_hours:.1f}h): {cache_key}"
            )
            return data

        # Last resort: static fallback data
        static_data = self._get_static_fallback(params, endpoint)
        if static_data is not None:
            return static_data

        logger.error(f"No stale cache or static fallback available for {cache_key}")
        return None

    async def _set_cache(self, cache_key: str, data: Any, endpoint: str) -> None:
        """
        Set cache in Redis (with fallback to in-memory)

        Uses differentiated TTL based on endpoint type
        """
        cache_type = self._get_cache_type(endpoint)
        ttl = self.CACHE_TTL.get(cache_type, self.CACHE_TTL["default"])

        # Try Redis first
        success = await self.redis.set(cache_key, data, ttl=ttl)

        if success:
            logger.debug(f"Redis cache SET: {cache_key} (TTL: {ttl}s, type: {cache_type})")
        else:
            # Fallback to in-memory cache
            self._fallback_cache[cache_key] = (data, time.time(), cache_type)
            logger.debug(f"Fallback cache SET: {cache_key} (TTL: {ttl}s, type: {cache_type})")

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
        cache_key = self._build_cache_key(endpoint, params)
        cached = await self._get_cached(cache_key, endpoint)
        if cached is not None:
            return cached

        # Make request with retries
        url = f"{self.BASE_URL}{endpoint}"
        last_error = None

        for attempt in range(max_retries):
            try:
                # Wait for rate limiter before making request (max 10s wait)
                try:
                    await self.rate_limiter.acquire(max_wait=10.0)
                except RateLimitExceeded as e:
                    logger.error(f"Rate limit exceeded: {e}")
                    # Return cached data if available, otherwise None
                    return self._get_cached(cache_key, endpoint)

                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            await self._set_cache(cache_key, data, endpoint)
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
                            # Other HTTP errors (500, 503, etc.)
                            error_text = await response.text()
                            logger.error(
                                f"CoinGecko API error {response.status}: {error_text}"
                            )

                            # Return stale cache as fallback
                            stale_cache = await self._get_stale_cache(cache_key, endpoint, params)
                            if stale_cache is not None:
                                return stale_cache

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

                    # Return stale cache as emergency fallback
                    stale_cache = await self._get_stale_cache(cache_key, endpoint, params)
                    if stale_cache is not None:
                        return stale_cache

                    return None

            except Exception as e:
                logger.exception(f"Unexpected error making CoinGecko request: {e}")

                # Return stale cache as emergency fallback
                stale_cache = await self._get_stale_cache(cache_key, endpoint, params)
                if stale_cache is not None:
                    return stale_cache

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

    async def get_batch_prices(
        self,
        coin_ids: List[str],
        vs_currency: str = "usd",
        include_24h_change: bool = True,
        include_market_cap: bool = True,
        include_24h_volume: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Get current prices for multiple cryptocurrencies in one request

        This is more efficient than calling get_price() multiple times as it uses
        only 1 API call instead of N calls for N coins.

        Args:
            coin_ids: List of coin IDs (e.g., ['bitcoin', 'ethereum', 'solana'])
            vs_currency: Currency to compare against (default: 'usd')
            include_24h_change: Include 24h price change percentage
            include_market_cap: Include market cap
            include_24h_volume: Include 24h volume

        Returns:
            Dict with price data for all coins or None

        Example:
            {
                "bitcoin": {
                    "usd": 45000,
                    "usd_24h_change": 2.5,
                    "usd_market_cap": 850000000000,
                    "usd_24h_vol": 35000000000
                },
                "ethereum": {
                    "usd": 3000,
                    "usd_24h_change": 1.8,
                    ...
                }
            }
        """
        if not coin_ids:
            return {}

        # Join coin IDs with comma for batch request
        params = {
            "ids": ",".join(coin_ids),
            "vs_currencies": vs_currency,
        }

        if include_24h_change:
            params["include_24hr_change"] = "true"

        if include_market_cap:
            params["include_market_cap"] = "true"

        if include_24h_volume:
            params["include_24hr_vol"] = "true"

        return await self._make_request("/simple/price", params)

    async def get_batch_coins_data(
        self,
        coin_ids: List[str],
        vs_currency: str = "usd",
        include_sparkline: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get detailed market data for multiple coins using /coins/markets endpoint

        This endpoint returns comprehensive data including ATH, ATL, price changes,
        supply metrics, etc. - all in ONE API call.

        Args:
            coin_ids: List of coin IDs
            vs_currency: Currency to compare against
            include_sparkline: Include 7-day price sparkline

        Returns:
            List of coin market data dicts

        Example:
            [
                {
                    "id": "bitcoin",
                    "symbol": "btc",
                    "name": "Bitcoin",
                    "current_price": 45000,
                    "market_cap": 850000000000,
                    "price_change_percentage_24h": 2.5,
                    "ath": 69000,
                    "ath_change_percentage": -34.78,
                    "atl": 67.81,
                    "atl_change_percentage": 66239.42,
                    "circulating_supply": 19500000,
                    "total_supply": 21000000,
                    ...
                },
                ...
            ]
        """
        if not coin_ids:
            return []

        params = {
            "vs_currency": vs_currency,
            "ids": ",".join(coin_ids),
            "order": "market_cap_desc",
            "sparkline": str(include_sparkline).lower(),
            "price_change_percentage": "7d,30d,60d,1y",
        }

        return await self._make_request("/coins/markets", params)

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
        self, vs_currency: str = "usd", limit: int = 10, include_1h_7d_change: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get top cryptocurrencies by market cap

        Args:
            vs_currency: Currency to compare against
            limit: Number of coins to return
            include_1h_7d_change: Include 1h and 7d price change percentages

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

        # Add price change percentages for 1h and 7d timeframes
        if include_1h_7d_change:
            params["price_change_percentage"] = "1h,24h,7d"

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

    async def get_stablecoins_market_cap(self) -> Optional[Dict[str, Any]]:
        """
        Get total market cap of all stablecoins

        Uses /coins/categories endpoint to get accurate stablecoin market cap.
        This is more accurate than summing individual stablecoins from top-10.

        Returns:
            Dict with stablecoin metrics or None

        Example:
            {
                "market_cap_usd": 309957268056,
                "volume_24h_usd": 12345678900,
                "dominance_pct": 9.55,  # Based on total crypto market cap
                "category_name": "Stablecoins"
            }
        """
        try:
            # Get all categories with market data
            categories = await self.get_categories_with_data()
            if not categories:
                logger.warning("Failed to get categories data for stablecoins")
                return None

            # Find stablecoins category (case-insensitive search)
            stablecoin_category = None
            for cat in categories:
                cat_name = cat.get("name", "").lower()
                if cat_name == "stablecoins":
                    stablecoin_category = cat
                    break

            if not stablecoin_category:
                logger.warning("Stablecoins category not found in categories list")
                return None

            # Extract stablecoin data
            stable_mcap = stablecoin_category.get("market_cap", 0)
            stable_volume = stablecoin_category.get("volume_24h", 0)

            # Get total market cap for dominance calculation
            global_data = await self._make_request("/global")
            if global_data and "data" in global_data:
                total_mcap = global_data["data"]["total_market_cap"].get("usd", 0)
                dominance_pct = (stable_mcap / total_mcap * 100) if total_mcap > 0 else 0
            else:
                dominance_pct = 0
                logger.warning("Could not calculate stablecoin dominance - missing global data")

            return {
                "market_cap_usd": stable_mcap,
                "volume_24h_usd": stable_volume,
                "dominance_pct": round(dominance_pct, 2),
                "category_name": stablecoin_category.get("name"),
            }

        except Exception as e:
            logger.error(f"Error getting stablecoins market cap: {e}")
            return None

    async def get_global_market_data(self) -> Optional[Dict[str, Any]]:
        """
        Get global cryptocurrency market data with accurate dominance metrics

        Returns market dominance, total market cap, volume, and other global metrics.
        Includes TOTAL2, TOTAL3, and Real Alts (Others) metrics for altseason analysis.

        Returns:
            Dict with global market data or None

        Example:
        {
            "total_market_cap_usd": 3330090432842,
            "total_volume_24h_usd": 176924238498,
            "btc_dominance": 57.13,
            "eth_dominance": 11.57,
            "stablecoin_dominance": 9.55,  # NEW: Accurate stablecoin dominance
            "altcoin_dominance": 23.75,    # NEW: Real alts only (excludes stablecoins)
            "total2_dominance": 42.87,     # NEW: Everything except BTC
            "total3_dominance": 31.30,     # NEW: Everything except BTC and ETH
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

        # Get accurate stablecoin dominance from categories
        stablecoin_data = await self.get_stablecoins_market_cap()
        stablecoin_dominance = 0
        if stablecoin_data:
            stablecoin_dominance = stablecoin_data.get("dominance_pct", 0)
            logger.debug(f"Stablecoin dominance: {stablecoin_dominance:.2f}%")
        else:
            # Fallback: estimate from top-10 (USDT + USDC)
            usdt_dom = market_data.get("market_cap_percentage", {}).get("usdt", 0)
            usdc_dom = market_data.get("market_cap_percentage", {}).get("usdc", 0)
            stablecoin_dominance = usdt_dom + usdc_dom
            logger.warning(
                f"Using fallback stablecoin dominance from top-10: {stablecoin_dominance:.2f}% "
                f"(actual is likely ~1-2% higher)"
            )

        # Calculate new dominance metrics
        # TOTAL2 = All market except BTC (includes ETH, alts, stablecoins)
        total2_dominance = 100 - btc_dominance

        # TOTAL3 = All market except BTC and ETH (includes alts and stablecoins)
        total3_dominance = 100 - btc_dominance - eth_dominance

        # Real Alts (Others) = All market except BTC, ETH, and Stablecoins
        # This is the TRUE altcoin dominance for altseason analysis
        altcoin_dominance = total3_dominance - stablecoin_dominance

        # Get DeFi data if available
        defi_market_cap = market_data.get("defi_market_cap", 0)
        defi_volume = market_data.get("defi_24h_vol", 0)
        defi_dominance = market_data.get("defi_dominance", 0)

        logger.info(
            f"Market dominance: BTC {btc_dominance:.2f}%, ETH {eth_dominance:.2f}%, "
            f"Stables {stablecoin_dominance:.2f}%, Real Alts {altcoin_dominance:.2f}% | "
            f"TOTAL2 {total2_dominance:.2f}%, TOTAL3 {total3_dominance:.2f}%"
        )

        return {
            "total_market_cap_usd": total_market_cap,
            "total_volume_24h_usd": total_volume,
            # Core dominance metrics
            "btc_dominance": round(btc_dominance, 2),
            "eth_dominance": round(eth_dominance, 2),
            "stablecoin_dominance": round(stablecoin_dominance, 2),
            "altcoin_dominance": round(altcoin_dominance, 2),  # Real alts (excl. stablecoins)
            # TradingView-style metrics for altseason analysis
            "total2_dominance": round(total2_dominance, 2),  # All except BTC
            "total3_dominance": round(total3_dominance, 2),  # All except BTC & ETH
            # Other metrics
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

    async def get_categories_list(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get list of all available coin categories

        Returns:
            List of categories with category_id and name

        Example:
            [
                {"category_id": "layer-1", "name": "Layer 1 (L1)"},
                {"category_id": "decentralized-finance-defi", "name": "DeFi"},
                ...
            ]
        """
        return await self._make_request("/coins/categories/list")

    async def get_categories_with_data(
        self, order: str = "market_cap_desc"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get categories with market data (market cap, volume, top coins)

        Args:
            order: Sorting order
                   - market_cap_desc/asc
                   - name_desc/asc
                   - market_cap_change_24h_desc/asc

        Returns:
            List of categories with market metrics

        Example:
            [
                {
                    "id": "layer-1",
                    "name": "Layer 1 (L1)",
                    "market_cap": 2060000000000,
                    "market_cap_change_24h": -0.66,
                    "volume_24h": 61100000000,
                    "top_3_coins": ["bitcoin", "ethereum", "binancecoin"]
                },
                ...
            ]
        """
        params = {"order": order}
        return await self._make_request("/coins/categories", params)

    async def get_coins_by_category(
        self,
        category: str,
        vs_currency: str = "usd",
        per_page: int = 100,
        page: int = 1,
        exclude_btc_eth: bool = True,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get coins by category with optional BTC/ETH filtering

        Args:
            category: Category ID (e.g., 'layer-1', 'decentralized-finance-defi')
            vs_currency: Currency to compare against
            per_page: Results per page (1-250)
            page: Page number
            exclude_btc_eth: Exclude Bitcoin and Ethereum from results

        Returns:
            List of coins with full market data sorted by market cap

        Example:
            [
                {
                    "id": "solana",
                    "symbol": "sol",
                    "name": "Solana",
                    "current_price": 150.25,
                    "market_cap": 65000000000,
                    "price_change_percentage_24h": 5.2,
                    "ath": 260.06,
                    "ath_change_percentage": -42.2,
                    ...
                },
                ...
            ]
        """
        params = {
            "vs_currency": vs_currency,
            "category": category,
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": page,
            "sparkline": "false",
            "price_change_percentage": "1h,24h,7d,30d,200d,1y",
        }

        data = await self._make_request("/coins/markets", params)

        if data and exclude_btc_eth:
            return [coin for coin in data if coin["id"] not in ["bitcoin", "ethereum"]]

        return data

    async def get_top_altcoins(
        self,
        vs_currency: str = "usd",
        limit: int = 50,
        exclude_stablecoins: bool = True,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get top altcoins excluding BTC, ETH and optionally stablecoins

        This method fetches top cryptocurrencies by market cap and filters out
        Bitcoin, Ethereum and stablecoins to return only altcoins.

        Args:
            vs_currency: Currency to compare against
            limit: Number of altcoins to return
            exclude_stablecoins: Exclude stablecoins (USDT, USDC, etc.)

        Returns:
            List of altcoins sorted by market cap

        Example:
            [
                {
                    "id": "solana",
                    "symbol": "sol",
                    "current_price": 150.25,
                    "market_cap": 65000000000,
                    "ath": 260.06,
                    "ath_change_percentage": -42.2,
                    ...
                },
                ...
            ]
        """
        # Request with buffer for filtering
        params = {
            "vs_currency": vs_currency,
            "order": "market_cap_desc",
            "per_page": 250,  # Max allowed, to ensure we get enough after filtering
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "1h,24h,7d,30d,200d,1y",
        }

        data = await self._make_request("/coins/markets", params)

        if not data:
            return None

        # Build exclusion list
        excluded = ["bitcoin", "ethereum"]

        if exclude_stablecoins:
            stablecoins = [
                "tether",
                "usd-coin",
                "binance-usd",
                "dai",
                "true-usd",
                "frax",
                "paxos-standard",
                "gemini-dollar",
                "first-digital-usd",
                "paypal-usd",
            ]
            excluded.extend(stablecoins)

        # Filter and limit
        altcoins = [coin for coin in data if coin["id"] not in excluded]

        logger.debug(
            f"Filtered {len(data)} coins to {len(altcoins)} altcoins "
            f"(excluded {len(excluded)} coins)"
        )

        return altcoins[:limit]

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
        for _, _, cache_type in self._fallback_cache.values():
            cache_by_type[cache_type] = cache_by_type.get(cache_type, 0) + 1

        return {
            "rate_limiter": rate_stats,
            "cache": {
                "total_entries": len(self._fallback_cache),
                "by_type": cache_by_type,
            }
        }
