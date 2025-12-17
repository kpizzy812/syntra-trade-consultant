# coding: utf-8
"""
Cache decorators for easy integration with Redis

Provides decorators to automatically cache async function results.
"""
import functools
from typing import Any, Callable, Optional

from loguru import logger

from src.cache.redis_manager import get_redis_manager
from src.cache.cache_keys import CacheKeyBuilder
from config.cache_config import CacheTTL


def cached(
    service: str,
    method: str,
    ttl: Optional[int] = None,
    key_builder: Optional[Callable] = None,
):
    """
    Decorator to cache async function results in Redis

    Args:
        service: Service name (e.g., 'coingecko', 'binance')
        method: Method name (e.g., 'price', 'klines')
        ttl: Cache TTL in seconds (default: CacheTTL.DEFAULT)
        key_builder: Optional custom key builder function

    Usage:
        @cached('coingecko', 'price', ttl=CacheTTL.COINGECKO_PRICE)
        async def get_price(coin_id: str, vs_currency: str):
            # Function implementation
            return price_data

    The decorator will:
    1. Build a cache key from service, method, and function args
    2. Try to get cached value from Redis
    3. If cache miss, call the original function
    4. Store the result in Redis with TTL
    5. Return the result
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            redis_mgr = get_redis_manager()

            # Build cache key
            if key_builder:
                # Custom key builder
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default key builder using args/kwargs
                params = _extract_params(func, args, kwargs)
                cache_key = CacheKeyBuilder.build(service, method, params)

            # Try to get from cache
            cached_value = await redis_mgr.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return cached_value

            # Cache miss - call original function
            logger.debug(f"Cache MISS: {cache_key} - calling original function")
            result = await func(*args, **kwargs)

            # Cache the result
            cache_ttl = ttl if ttl is not None else CacheTTL.DEFAULT
            await redis_mgr.set(cache_key, result, ttl=cache_ttl)

            return result

        return wrapper

    return decorator


def _extract_params(func: Callable, args: tuple, kwargs: dict) -> dict:
    """
    Extract function parameters from args and kwargs

    Args:
        func: Function being called
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Dict of parameter names and values

    Examples:
        >>> def get_price(coin_id: str, vs_currency: str = 'usd'):
        ...     pass
        >>> _extract_params(get_price, ('bitcoin',), {'vs_currency': 'usd'})
        {'coin_id': 'bitcoin', 'vs_currency': 'usd'}
    """
    import inspect

    # Get function signature
    sig = inspect.signature(func)
    param_names = list(sig.parameters.keys())

    # Remove 'self' or 'cls' from parameters (for class methods)
    if param_names and param_names[0] in ('self', 'cls'):
        param_names = param_names[1:]
        args = args[1:]  # Skip self/cls in args too

    # Build params dict
    params = {}

    # Add positional args
    for i, arg in enumerate(args):
        if i < len(param_names):
            params[param_names[i]] = arg

    # Add keyword args
    params.update(kwargs)

    return params


def invalidate_cache(service: str, method: Optional[str] = None):
    """
    Decorator to invalidate cache after function execution

    Useful for functions that modify data and should clear related caches.

    Args:
        service: Service name
        method: Optional method name (if None, clears all service cache)

    Usage:
        @invalidate_cache('coingecko', 'price')
        async def update_price(coin_id: str):
            # Update price in database
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Call original function
            result = await func(*args, **kwargs)

            # Invalidate cache
            redis_mgr = get_redis_manager()
            pattern = CacheKeyBuilder.pattern(service, method)
            deleted = await redis_mgr.delete_pattern(pattern)
            logger.info(f"Cache invalidated: {deleted} keys deleted for pattern '{pattern}'")

            return result

        return wrapper

    return decorator


# Convenience decorators for specific services


def cached_coingecko(method: str, ttl: Optional[int] = None):
    """Decorator for CoinGecko API calls"""
    return cached('coingecko', method, ttl=ttl)


def cached_binance(method: str, ttl: Optional[int] = None):
    """Decorator for Binance API calls"""
    return cached('binance', method, ttl=ttl)


def cached_dexscreener(method: str, ttl: Optional[int] = None):
    """Decorator for DexScreener API calls"""
    return cached('dexscreener', method, ttl=ttl)


def cached_coinmarketcap(method: str, ttl: Optional[int] = None):
    """Decorator for CoinMarketCap API calls"""
    return cached('coinmarketcap', method, ttl=ttl)


def cached_cryptopanic(method: str, ttl: Optional[int] = None):
    """Decorator for CryptoPanic API calls"""
    return cached('cryptopanic', method, ttl=ttl)


def cached_feargreed(ttl: Optional[int] = CacheTTL.FEAR_GREED_INDEX):
    """Decorator for Fear & Greed API calls"""
    return cached('feargreed', 'current', ttl=ttl)


if __name__ == "__main__":
    import asyncio

    # Example usage
    @cached_coingecko('price', ttl=CacheTTL.COINGECKO_PRICE)
    async def get_price(coin_id: str, vs_currency: str = 'usd'):
        """Mock function to demonstrate caching"""
        print(f"Fetching price for {coin_id} in {vs_currency}...")
        await asyncio.sleep(1)  # Simulate API call
        return {"price": 45000}

    async def test():
        """Test caching"""
        redis_mgr = get_redis_manager()
        await redis_mgr.initialize()

        # First call - cache miss
        result1 = await get_price("bitcoin")
        print(f"Result 1: {result1}")

        # Second call - cache hit
        result2 = await get_price("bitcoin")
        print(f"Result 2: {result2}")

        # Stats
        print(f"Stats: {redis_mgr.get_stats()}")

        await redis_mgr.close()

    asyncio.run(test())
