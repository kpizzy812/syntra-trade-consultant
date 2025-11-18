# coding: utf-8
"""
DexScreener API Service for DEX cryptocurrency data

Provides access to DEX (Decentralized Exchange) data across multiple blockchains:
- Solana (Raydium, Orca, etc.)
- BSC (PancakeSwap)
- Ethereum (Uniswap, SushiSwap)
- Polygon, Avalanche, Arbitrum, and more

Free API, no authentication required.
Rate limit: 300 requests/minute
"""
import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import aiohttp
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from config.config import CACHE_TTL_COINGECKO  # Reuse same TTL for consistency


# Create standard logger for tenacity
std_logger = logging.getLogger(__name__)


class DexScreenerService:
    """
    Service for fetching cryptocurrency data from DexScreener API

    Features:
    - Search tokens across all DEX platforms
    - Get token pair data (price, liquidity, volume)
    - Multi-chain support (Solana, BSC, ETH, etc.)
    - OHLCV data for technical analysis
    - Simple in-memory caching with TTL
    - No API key required (free tier)

    Rate limits:
    - 300 requests/minute for DEX queries
    - Automatic retry with exponential backoff
    """

    BASE_URL = "https://api.dexscreener.com"

    # Chain IDs supported by DexScreener
    CHAIN_IDS = {
        "solana": "solana",
        "bsc": "bsc",
        "ethereum": "ethereum",
        "polygon": "polygon",
        "avalanche": "avalanche",
        "arbitrum": "arbitrum",
        "optimism": "optimism",
        "base": "base",
        "sui": "sui",
        "aptos": "aptos",
    }

    def __init__(self):
        """Initialize DexScreener service with caching"""
        self.cache: Dict[str, tuple[Any, float]] = {}
        self.cache_ttl = CACHE_TTL_COINGECKO  # Reuse same TTL (5 minutes)

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
        reraise=True,
    )
    async def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make request to DexScreener API with caching and automatic retries

        Retries up to 3 times with exponential backoff (2-10s) for:
        - ClientError (network/HTTP errors)
        - TimeoutError (request timeout)

        Args:
            endpoint: API endpoint (e.g., '/latest/dex/search')
            params: Query parameters

        Returns:
            JSON response or None on error
        """
        params = params or {}

        # Check cache
        cache_key = self._get_cache_key(endpoint, params)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Make request
        url = f"{self.BASE_URL}{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._set_cache(cache_key, data)
                        return data
                    elif response.status == 429:
                        logger.warning("DexScreener rate limit exceeded. Retry after delay.")
                        return None
                    else:
                        logger.error(
                            f"DexScreener API error: {response.status} - "
                            f"{await response.text()}"
                        )
                        return None

        except Exception as e:
            logger.exception(f"Error making DexScreener request: {e}")
            return None

    async def search_token(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """
        Search for tokens/pairs by name, symbol, or address

        Args:
            query: Search query (token name, symbol, or address)

        Returns:
            List of matching pairs or None

        Example:
            [
                {
                    "chainId": "solana",
                    "dexId": "raydium",
                    "pairAddress": "...",
                    "baseToken": {"symbol": "MORI", "name": "Memori", ...},
                    "quoteToken": {"symbol": "SOL", ...},
                    "priceUsd": "0.0123",
                    "volume": {"h24": 123456},
                    "liquidity": {"usd": 50000},
                    "priceChange": {"h24": 15.5}
                },
                ...
            ]
        """
        try:
            response = await self._make_request(
                "/latest/dex/search",
                params={"q": query}
            )

            if not response or "pairs" not in response:
                logger.warning(f"No pairs found for query: {query}")
                return None

            pairs = response.get("pairs", [])
            logger.info(f"Found {len(pairs)} pairs for '{query}'")
            return pairs

        except Exception as e:
            logger.error(f"Error searching token '{query}': {e}")
            return None

    async def get_token_pairs(
        self, chain_id: str, token_address: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get all trading pairs for a specific token on a chain

        Args:
            chain_id: Blockchain ID ('solana', 'bsc', 'ethereum', etc.)
            token_address: Token contract address

        Returns:
            List of pairs for this token or None
        """
        try:
            response = await self._make_request(
                f"/token-pairs/v1/{chain_id}/{token_address}"
            )

            if not response or "pairs" not in response:
                logger.warning(f"No pairs found for {token_address} on {chain_id}")
                return None

            pairs = response.get("pairs", [])
            logger.info(f"Found {len(pairs)} pairs for {token_address} on {chain_id}")
            return pairs

        except Exception as e:
            logger.error(f"Error getting pairs for {token_address} on {chain_id}: {e}")
            return None

    async def get_best_pair(
        self, query: str, min_liquidity_usd: float = 1000.0
    ) -> Optional[Dict[str, Any]]:
        """
        Get the best (most active) trading pair for a token

        Selects based on trading activity (volume 24h), not just liquidity.
        This prevents selecting locked liquidity pools with low activity.

        Args:
            query: Token name, symbol, or address
            min_liquidity_usd: Minimum liquidity in USD (default: $1000)

        Returns:
            Best pair data or None
        """
        try:
            pairs = await self.search_token(query)

            if not pairs:
                return None

            # Filter by minimum liquidity
            valid_pairs = [
                pair for pair in pairs
                if pair.get("liquidity", {}).get("usd", 0) >= min_liquidity_usd
            ]

            if not valid_pairs:
                logger.warning(
                    f"No pairs found with liquidity >= ${min_liquidity_usd} for '{query}'"
                )
                # Return best pair anyway, even if below threshold
                valid_pairs = pairs

            # Sort by VOLUME 24h (activity), not just liquidity
            # This prevents selecting locked liquidity pools (high liquidity, low volume)
            best_pair = max(
                valid_pairs,
                key=lambda p: p.get("volume", {}).get("h24", 0)
            )

            volume_24h = best_pair.get("volume", {}).get("h24", 0)
            liquidity = best_pair.get("liquidity", {}).get("usd", 0)

            logger.info(
                f"Best pair for '{query}': {best_pair.get('dexId')} on "
                f"{best_pair.get('chainId')} "
                f"(volume: ${volume_24h:,.0f}, liquidity: ${liquidity:,.0f})"
            )

            return best_pair

        except Exception as e:
            logger.error(f"Error getting best pair for '{query}': {e}")
            return None

    async def get_all_token_variants(
        self, query: str, min_liquidity_usd: float = 1000.0, min_volume_24h_usd: float = 1000.0, top_n: int = 5
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get multiple token variants (useful when there are many tokens with same name)

        Args:
            query: Token name, symbol, or address
            min_liquidity_usd: Minimum liquidity in USD (default: $1000)
            min_volume_24h_usd: Minimum 24h volume in USD (default: $1000)
            top_n: Number of top variants to return (default: 5)

        Returns:
            List of top token variants sorted by liquidity, or None
        """
        try:
            pairs = await self.search_token(query)

            if not pairs:
                return None

            # Filter by minimum liquidity AND volume (both must pass)
            valid_pairs = [
                pair for pair in pairs
                if (pair.get("liquidity", {}).get("usd", 0) >= min_liquidity_usd
                    and pair.get("volume", {}).get("h24", 0) >= min_volume_24h_usd)
            ]

            # If no pairs meet BOTH thresholds, try with just liquidity
            if not valid_pairs:
                valid_pairs = [
                    pair for pair in pairs
                    if pair.get("liquidity", {}).get("usd", 0) >= min_liquidity_usd
                ]

            # If still no pairs, take all
            if not valid_pairs:
                valid_pairs = pairs

            # Sort by liquidity (descending) and take top N
            sorted_pairs = sorted(
                valid_pairs,
                key=lambda p: p.get("liquidity", {}).get("usd", 0),
                reverse=True
            )[:top_n]

            # Format each variant
            variants = []
            for pair in sorted_pairs:
                base_token = pair.get("baseToken", {})
                variants.append({
                    "symbol": base_token.get("symbol", "").upper(),
                    "name": base_token.get("name", "Unknown"),
                    "price_usd": float(pair.get("priceUsd", 0)),
                    "price_change_24h": pair.get("priceChange", {}).get("h24", 0),
                    "volume_24h_usd": pair.get("volume", {}).get("h24", 0),
                    "liquidity_usd": pair.get("liquidity", {}).get("usd", 0),
                    "market_cap_usd": pair.get("marketCap") or pair.get("fdv"),
                    "fdv": pair.get("fdv"),
                    "chain": pair.get("chainId", ""),
                    "dex": pair.get("dexId", ""),
                    "pair_address": pair.get("pairAddress", ""),
                    "token_address": base_token.get("address", ""),
                })

            logger.info(f"Found {len(variants)} variants for '{query}'")
            return variants

        except Exception as e:
            logger.error(f"Error getting token variants for '{query}': {e}")
            return None

    async def get_token_price(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Get price and market data for a token (convenience method)

        Args:
            query: Token name, symbol, or address

        Returns:
            Price data dict or None

        Example:
            {
                "symbol": "MORI",
                "name": "Memori",
                "price_usd": 0.0123,
                "price_change_24h": 15.5,
                "volume_24h_usd": 123456,
                "liquidity_usd": 50000,
                "market_cap_usd": 1230000,
                "chain": "solana",
                "dex": "raydium",
                "pair_address": "...",
                "token_address": "..."
            }
        """
        try:
            best_pair = await self.get_best_pair(query)

            if not best_pair:
                return None

            # Extract price data
            base_token = best_pair.get("baseToken", {})
            price_usd = float(best_pair.get("priceUsd", 0))
            volume_24h = best_pair.get("volume", {}).get("h24", 0)
            liquidity_usd = best_pair.get("liquidity", {}).get("usd", 0)
            price_change_24h = best_pair.get("priceChange", {}).get("h24", 0)
            fdv = best_pair.get("fdv")  # Fully diluted valuation
            market_cap = best_pair.get("marketCap")

            return {
                "symbol": base_token.get("symbol", "").upper(),
                "name": base_token.get("name", "Unknown"),
                "price_usd": price_usd,
                "price_change_24h": price_change_24h,
                "volume_24h_usd": volume_24h,
                "liquidity_usd": liquidity_usd,
                "market_cap_usd": market_cap or fdv,  # Use market cap or FDV
                "fdv": fdv,
                "chain": best_pair.get("chainId", ""),
                "dex": best_pair.get("dexId", ""),
                "pair_address": best_pair.get("pairAddress", ""),
                "token_address": base_token.get("address", ""),
            }

        except Exception as e:
            logger.error(f"Error getting token price for '{query}': {e}")
            return None
