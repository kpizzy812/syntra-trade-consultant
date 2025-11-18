# coding: utf-8
"""
CoinMarketCap API Service for cryptocurrency data

Provides access to comprehensive cryptocurrency data from CoinMarketCap,
including tokens from smaller exchanges not covered by CoinGecko.

Free tier includes:
- 10,000 API calls per month (~333/day)
- Latest cryptocurrency quotes
- Market data and rankings
- Cryptocurrency metadata

Requires API key (free registration at coinmarketcap.com/api)
"""
import time
import logging
from typing import Optional, Dict, Any, List

import aiohttp
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from config.config import CACHE_TTL_COINGECKO  # Reuse same TTL


# Create standard logger for tenacity
std_logger = logging.getLogger(__name__)


class CoinMarketCapService:
    """
    Service for fetching cryptocurrency data from CoinMarketCap API

    Features:
    - Latest price quotes and market data
    - Support for tokens from smaller exchanges
    - Cryptocurrency search and mapping
    - Global market metrics
    - Simple in-memory caching with TTL

    Authentication:
    - Requires CMC_API_KEY in environment variables
    - Free tier: 10,000 calls/month

    Rate limits:
    - Free tier: ~333 calls/day
    - Automatic retry with exponential backoff
    """

    BASE_URL = "https://pro-api.coinmarketcap.com/v1"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize CoinMarketCap service

        Args:
            api_key: CoinMarketCap API key (optional, loaded from config if not provided)
        """
        self.api_key = api_key
        self.cache: Dict[str, tuple[Any, float]] = {}
        self.cache_ttl = CACHE_TTL_COINGECKO  # 5 minutes

        if not self.api_key:
            logger.warning(
                "CoinMarketCap API key not configured. "
                "Service will not be available. "
                "Set CMC_API_KEY in .env to enable."
            )

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
        reraise=True,
    )
    async def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make request to CoinMarketCap API with caching and retries

        Args:
            endpoint: API endpoint (e.g., '/cryptocurrency/quotes/latest')
            params: Query parameters

        Returns:
            JSON response or None on error
        """
        if not self.api_key:
            logger.error("CoinMarketCap API key not configured")
            return None

        params = params or {}

        # Check cache
        cache_key = self._get_cache_key(endpoint, params)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Make request
        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "X-CMC_PRO_API_KEY": self.api_key,
            "Accept": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._set_cache(cache_key, data)
                        return data
                    elif response.status == 401:
                        logger.error("CoinMarketCap API authentication failed. Check your API key.")
                        return None
                    elif response.status == 429:
                        logger.warning("CoinMarketCap rate limit exceeded.")
                        return None
                    else:
                        logger.error(
                            f"CoinMarketCap API error: {response.status} - "
                            f"{await response.text()}"
                        )
                        return None

        except Exception as e:
            logger.exception(f"Error making CoinMarketCap request: {e}")
            return None

    async def get_quote_by_symbol(
        self, symbol: str, convert: str = "USD"
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest price quote for a cryptocurrency by symbol

        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC', 'ETH', 'MORI')
            convert: Fiat currency to convert to (default: 'USD')

        Returns:
            Quote data dict or None

        Example response:
            {
                "symbol": "BTC",
                "name": "Bitcoin",
                "price": 45000.0,
                "volume_24h": 35000000000,
                "market_cap": 850000000000,
                "percent_change_24h": 2.5,
                "circulating_supply": 19500000,
                "total_supply": 21000000,
                "max_supply": 21000000
            }
        """
        try:
            response = await self._make_request(
                "/cryptocurrency/quotes/latest",
                params={"symbol": symbol.upper(), "convert": convert}
            )

            if not response or "data" not in response:
                logger.warning(f"No data found for symbol: {symbol}")
                return None

            # Extract data for this symbol
            data = response["data"].get(symbol.upper())
            if not data:
                logger.warning(f"Symbol {symbol} not found in response")
                return None

            # Extract quote data
            quote = data.get("quote", {}).get(convert, {})

            return {
                "symbol": data.get("symbol", "").upper(),
                "name": data.get("name", "Unknown"),
                "price": quote.get("price", 0),
                "volume_24h": quote.get("volume_24h", 0),
                "market_cap": quote.get("market_cap", 0),
                "percent_change_24h": quote.get("percent_change_24h", 0),
                "circulating_supply": data.get("circulating_supply"),
                "total_supply": data.get("total_supply"),
                "max_supply": data.get("max_supply"),
                "cmc_rank": data.get("cmc_rank"),
                "last_updated": quote.get("last_updated"),
            }

        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            return None

    async def search_cryptocurrency(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """
        Search for cryptocurrencies by name or symbol

        Note: CoinMarketCap doesn't have a dedicated search endpoint in free tier,
        so we use the map endpoint and filter locally.

        Args:
            query: Search query (name or symbol)

        Returns:
            List of matching cryptocurrencies or None
        """
        try:
            # Get cryptocurrency map (all cryptos)
            response = await self._make_request("/cryptocurrency/map")

            if not response or "data" not in response:
                logger.warning("Failed to get cryptocurrency map")
                return None

            cryptos = response["data"]
            query_lower = query.lower()

            # Filter by symbol or name
            matches = [
                crypto for crypto in cryptos
                if query_lower in crypto.get("symbol", "").lower()
                or query_lower in crypto.get("name", "").lower()
            ]

            logger.info(f"Found {len(matches)} matches for '{query}'")
            return matches[:10]  # Return top 10 matches

        except Exception as e:
            logger.error(f"Error searching for '{query}': {e}")
            return None

    async def get_global_metrics(self) -> Optional[Dict[str, Any]]:
        """
        Get global cryptocurrency market metrics

        Returns:
            Global metrics dict or None

        Example:
            {
                "total_market_cap": 3330090432842,
                "total_volume_24h": 176924238498,
                "btc_dominance": 57.13,
                "eth_dominance": 11.57,
                "active_cryptocurrencies": 19425
            }
        """
        try:
            response = await self._make_request("/global-metrics/quotes/latest")

            if not response or "data" not in response:
                logger.warning("Failed to get global metrics")
                return None

            data = response["data"]
            quote = data.get("quote", {}).get("USD", {})

            return {
                "total_market_cap": quote.get("total_market_cap", 0),
                "total_volume_24h": quote.get("total_volume_24h", 0),
                "btc_dominance": data.get("btc_dominance", 0),
                "eth_dominance": data.get("eth_dominance", 0),
                "active_cryptocurrencies": data.get("active_cryptocurrencies", 0),
                "active_exchanges": data.get("active_exchanges", 0),
                "last_updated": quote.get("last_updated"),
            }

        except Exception as e:
            logger.error(f"Error getting global metrics: {e}")
            return None
