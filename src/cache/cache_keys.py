# coding: utf-8
"""
Cache key generation utilities

Provides consistent, namespaced key generation for Redis cache.
"""
import hashlib
import json
from typing import Any, Dict, List, Optional, Union

from config.cache_config import CacheConfig


class CacheKeyBuilder:
    """
    Utility class for building consistent cache keys

    Key format: {namespace}:{service}:{method}:{params_hash}

    Examples:
        syntra:coingecko:price:bitcoin_usd
        syntra:binance:klines:BTCUSDT_1h_100
        syntra:dexscreener:search:bitcoin
    """

    SEPARATOR = CacheConfig.CACHE_KEY_SEPARATOR
    NAMESPACE = CacheConfig.CACHE_NAMESPACE

    @classmethod
    def build(
        cls,
        service: str,
        method: str,
        params: Optional[Union[Dict[str, Any], List[Any], str]] = None,
    ) -> str:
        """
        Build a cache key from components

        Args:
            service: Service name (e.g., 'coingecko', 'binance')
            method: Method name (e.g., 'price', 'klines')
            params: Parameters (dict, list, or string)

        Returns:
            Cache key string

        Examples:
            >>> CacheKeyBuilder.build('coingecko', 'price', {'coin_id': 'bitcoin', 'vs_currency': 'usd'})
            'syntra:coingecko:price:bitcoin_usd'

            >>> CacheKeyBuilder.build('binance', 'klines', {'symbol': 'BTCUSDT', 'interval': '1h', 'limit': 100})
            'syntra:binance:klines:BTCUSDT_1h_100'
        """
        key_parts = [cls.NAMESPACE, service, method]

        if params:
            params_str = cls._serialize_params(params)
            key_parts.append(params_str)

        return cls.SEPARATOR.join(key_parts)

    @classmethod
    def _serialize_params(cls, params: Union[Dict[str, Any], List[Any], str]) -> str:
        """
        Serialize parameters into a consistent string representation

        Args:
            params: Parameters to serialize

        Returns:
            Serialized parameter string

        Examples:
            >>> CacheKeyBuilder._serialize_params({'coin_id': 'bitcoin', 'vs_currency': 'usd'})
            'bitcoin_usd'

            >>> CacheKeyBuilder._serialize_params(['bitcoin', 'usd'])
            'bitcoin_usd'
        """
        if isinstance(params, str):
            # Already a string, use as-is
            return params

        if isinstance(params, dict):
            # Sort keys for consistency
            sorted_items = sorted(params.items())
            # Create readable string from key-value pairs
            param_values = [str(v) for k, v in sorted_items]
            return "_".join(param_values)

        if isinstance(params, (list, tuple)):
            # Join list items
            return "_".join(str(item) for item in params)

        # Fallback: convert to string
        return str(params)

    @classmethod
    def build_hashed(
        cls,
        service: str,
        method: str,
        params: Optional[Union[Dict[str, Any], List[Any], str]] = None,
    ) -> str:
        """
        Build a cache key with hashed parameters (for very long params)

        Uses SHA256 hash for parameters to keep keys short.

        Args:
            service: Service name
            method: Method name
            params: Parameters to hash

        Returns:
            Cache key with hashed params

        Examples:
            >>> CacheKeyBuilder.build_hashed('coingecko', 'batch_prices', {'ids': ['bitcoin', 'ethereum', ...]})
            'syntra:coingecko:batch_prices:a3f2d9...'
        """
        key_parts = [cls.NAMESPACE, service, method]

        if params:
            # Create deterministic hash of params
            params_json = json.dumps(params, sort_keys=True, ensure_ascii=False)
            params_hash = hashlib.sha256(params_json.encode()).hexdigest()[:12]
            key_parts.append(params_hash)

        return cls.SEPARATOR.join(key_parts)

    @classmethod
    def pattern(cls, service: str, method: Optional[str] = None) -> str:
        """
        Build a pattern for key deletion/searching

        Args:
            service: Service name
            method: Optional method name

        Returns:
            Redis key pattern (with wildcards)

        Examples:
            >>> CacheKeyBuilder.pattern('coingecko')
            'syntra:coingecko:*'

            >>> CacheKeyBuilder.pattern('coingecko', 'price')
            'syntra:coingecko:price:*'
        """
        if method:
            return f"{cls.NAMESPACE}{cls.SEPARATOR}{service}{cls.SEPARATOR}{method}{cls.SEPARATOR}*"
        return f"{cls.NAMESPACE}{cls.SEPARATOR}{service}{cls.SEPARATOR}*"


# Convenience functions for specific services


def coingecko_key(method: str, params: Any = None) -> str:
    """Build CoinGecko cache key"""
    return CacheKeyBuilder.build("coingecko", method, params)


def binance_key(method: str, params: Any = None) -> str:
    """Build Binance cache key"""
    return CacheKeyBuilder.build("binance", method, params)


def dexscreener_key(method: str, params: Any = None) -> str:
    """Build DexScreener cache key"""
    return CacheKeyBuilder.build("dexscreener", method, params)


def coinmarketcap_key(method: str, params: Any = None) -> str:
    """Build CoinMarketCap cache key"""
    return CacheKeyBuilder.build("coinmarketcap", method, params)


def cryptopanic_key(method: str, params: Any = None) -> str:
    """Build CryptoPanic cache key"""
    return CacheKeyBuilder.build("cryptopanic", method, params)


def feargreed_key(method: str = "current") -> str:
    """Build Fear & Greed cache key"""
    return CacheKeyBuilder.build("feargreed", method)


if __name__ == "__main__":
    # Test key generation
    print("Cache Key Examples:")
    print(coingecko_key("price", {"coin_id": "bitcoin", "vs_currency": "usd"}))
    print(binance_key("klines", {"symbol": "BTCUSDT", "interval": "1h", "limit": 100}))
    print(dexscreener_key("search", "bitcoin"))
    print(feargreed_key())
    print("\nPatterns:")
    print(CacheKeyBuilder.pattern("coingecko"))
    print(CacheKeyBuilder.pattern("binance", "klines"))
