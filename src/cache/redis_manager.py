# coding: utf-8
"""
Redis Manager for centralized cache management

Provides async Redis client with connection pooling, graceful degradation,
and comprehensive error handling.
"""
import json
from typing import Any, Optional, Union
from contextlib import asynccontextmanager

from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from loguru import logger

from config.cache_config import CacheConfig, CacheTTL


class RedisManager:
    """
    Centralized Redis cache manager with connection pooling

    Features:
    - Async Redis operations
    - Connection pooling for efficiency
    - Graceful degradation (works without Redis)
    - JSON serialization
    - TTL management
    - Error handling and logging

    Usage:
        >>> redis_mgr = RedisManager()
        >>> await redis_mgr.initialize()
        >>> await redis_mgr.set("key", {"data": "value"}, ttl=300)
        >>> data = await redis_mgr.get("key")
        >>> await redis_mgr.close()
    """

    def __init__(self):
        """Initialize Redis manager"""
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[Redis] = None
        self._is_available = False
        self._stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "sets": 0,
            "deletes": 0,
        }

    async def initialize(self) -> bool:
        """
        Initialize Redis connection pool

        Returns:
            True if Redis is available, False otherwise

        Note:
            Failures are gracefully handled - the bot will work without Redis
        """
        if not CacheConfig.CACHE_ENABLED:
            logger.info("Redis caching is disabled in configuration")
            return False

        try:
            # Parse Redis URL
            url = CacheConfig.REDIS_URL

            # Create connection pool
            self._pool = ConnectionPool.from_url(
                url,
                max_connections=CacheConfig.REDIS_MAX_CONNECTIONS,
                decode_responses=True,  # Auto-decode bytes to strings
                socket_connect_timeout=CacheConfig.REDIS_SOCKET_CONNECT_TIMEOUT,
                socket_timeout=CacheConfig.REDIS_SOCKET_TIMEOUT,
            )

            # Create Redis client
            self._client = Redis(connection_pool=self._pool)

            # Test connection
            await self._client.ping()

            self._is_available = True
            logger.info(
                f"Redis initialized successfully (url={url}, max_connections={CacheConfig.REDIS_MAX_CONNECTIONS})"
            )
            return True

        except RedisConnectionError as e:
            logger.warning(f"Redis connection failed: {e}. Bot will work without cache.")
            self._is_available = False
            return False

        except Exception as e:
            logger.error(f"Unexpected error initializing Redis: {e}")
            self._is_available = False
            return False

    async def close(self):
        """Close Redis connections gracefully"""
        if self._client:
            try:
                await self._client.aclose()  # type: ignore
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")

        if self._pool:
            try:
                await self._pool.aclose()  # type: ignore
                logger.debug("Redis connection pool closed")
            except Exception as e:
                logger.error(f"Error closing Redis pool: {e}")

        self._is_available = False

    @asynccontextmanager
    async def lifespan(self):
        """
        Context manager for Redis lifespan

        Usage:
            async with redis_manager.lifespan():
                # Use Redis here
                await redis_manager.set("key", "value")
        """
        await self.initialize()
        try:
            yield self
        finally:
            await self.close()

    async def get(
        self, key: str, default: Any = None
    ) -> Optional[Union[str, dict, list]]:
        """
        Get value from cache

        Args:
            key: Cache key
            default: Default value if key not found

        Returns:
            Cached value (deserialized from JSON) or default

        Examples:
            >>> await redis_mgr.get("syntra:coingecko:price:bitcoin")
            {"bitcoin": {"usd": 45000}}

            >>> await redis_mgr.get("nonexistent_key", default={})
            {}
        """
        if not self._is_available:
            return default

        try:
            value = await self._client.get(key)  # type: ignore

            if value is None:
                self._stats["misses"] += 1
                if CacheConfig.CACHE_LOG_MISSES:
                    logger.debug(f"Cache MISS: {key}")
                return default

            # Deserialize JSON
            try:
                deserialized = json.loads(value)
                self._stats["hits"] += 1
                if CacheConfig.CACHE_LOG_HITS:
                    logger.debug(f"Cache HIT: {key}")
                return deserialized
            except json.JSONDecodeError:
                # Value is not JSON, return as-is
                self._stats["hits"] += 1
                if CacheConfig.CACHE_LOG_HITS:
                    logger.debug(f"Cache HIT (string): {key}")
                return value

        except RedisError as e:
            self._stats["errors"] += 1
            logger.warning(f"Redis GET error for key '{key}': {e}")
            if CacheConfig.CACHE_RAISE_ON_ERROR:
                raise
            return default

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Unexpected error in Redis GET for key '{key}': {e}")
            return default

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set value in cache with TTL

        Args:
            key: Cache key
            value: Value to cache (will be JSON-serialized)
            ttl: Time-to-live in seconds (default: CacheTTL.DEFAULT)

        Returns:
            True if successful, False otherwise

        Examples:
            >>> await redis_mgr.set("key", {"data": "value"}, ttl=300)
            True

            >>> await redis_mgr.set("key", "simple string", ttl=60)
            True
        """
        if not self._is_available:
            return False

        if ttl is None:
            ttl = CacheTTL.DEFAULT

        try:
            # Serialize to JSON
            if isinstance(value, (dict, list, tuple)):
                serialized = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, str):
                serialized = value
            else:
                serialized = json.dumps(value)

            # Set with TTL
            await self._client.setex(key, ttl, serialized)  # type: ignore
            self._stats["sets"] += 1
            logger.debug(f"Cache SET: {key} (TTL={ttl}s)")
            return True

        except RedisError as e:
            self._stats["errors"] += 1
            logger.warning(f"Redis SET error for key '{key}': {e}")
            if CacheConfig.CACHE_RAISE_ON_ERROR:
                raise
            return False

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Unexpected error in Redis SET for key '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache

        Args:
            key: Cache key to delete

        Returns:
            True if key was deleted, False otherwise
        """
        if not self._is_available:
            return False

        try:
            result = await self._client.delete(key)  # type: ignore
            self._stats["deletes"] += 1
            if result > 0:
                logger.debug(f"Cache DELETE: {key}")
                return True
            else:
                logger.debug(f"Cache DELETE (key not found): {key}")
                return False

        except RedisError as e:
            self._stats["errors"] += 1
            logger.warning(f"Redis DELETE error for key '{key}': {e}")
            if CacheConfig.CACHE_RAISE_ON_ERROR:
                raise
            return False

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Unexpected error in Redis DELETE for key '{key}': {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern

        Args:
            pattern: Key pattern (e.g., 'syntra:coingecko:*')

        Returns:
            Number of keys deleted

        Examples:
            >>> await redis_mgr.delete_pattern("syntra:coingecko:*")
            42
        """
        if not self._is_available:
            return 0

        try:
            # Find keys matching pattern
            keys = []
            async for key in self._client.scan_iter(match=pattern):  # type: ignore
                keys.append(key)

            if not keys:
                logger.debug(f"Cache DELETE_PATTERN: no keys match '{pattern}'")
                return 0

            # Delete all matching keys
            deleted = await self._client.delete(*keys)  # type: ignore
            self._stats["deletes"] += deleted
            logger.info(f"Cache DELETE_PATTERN: deleted {deleted} keys matching '{pattern}'")
            return deleted

        except RedisError as e:
            self._stats["errors"] += 1
            logger.warning(f"Redis DELETE_PATTERN error for pattern '{pattern}': {e}")
            if CacheConfig.CACHE_RAISE_ON_ERROR:
                raise
            return 0

        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Unexpected error in Redis DELETE_PATTERN for pattern '{pattern}': {e}")
            return 0

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise
        """
        if not self._is_available:
            return False

        try:
            exists = await self._client.exists(key)  # type: ignore
            return exists > 0

        except Exception as e:
            logger.warning(f"Redis EXISTS error for key '{key}': {e}")
            return False

    async def get_ttl(self, key: str) -> Optional[int]:
        """
        Get remaining TTL for a key

        Args:
            key: Cache key

        Returns:
            Remaining TTL in seconds, or None if key doesn't exist or has no TTL
        """
        if not self._is_available:
            return None

        try:
            ttl = await self._client.ttl(key)  # type: ignore
            if ttl > 0:
                return ttl
            return None

        except Exception as e:
            logger.warning(f"Redis TTL error for key '{key}': {e}")
            return None

    def get_stats(self) -> dict:
        """
        Get cache statistics

        Returns:
            Dict with cache hits, misses, errors, etc.

        Examples:
            >>> redis_mgr.get_stats()
            {"hits": 100, "misses": 20, "errors": 1, "hit_rate": 0.83}
        """
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0

        return {
            **self._stats,
            "total_requests": total,
            "hit_rate": round(hit_rate, 2),
            "is_available": self._is_available,
        }

    def is_available(self) -> bool:
        """Check if Redis is available"""
        return self._is_available


# Global Redis manager instance
_redis_manager: Optional[RedisManager] = None


def get_redis_manager() -> RedisManager:
    """
    Get global Redis manager instance (singleton)

    Returns:
        RedisManager instance

    Examples:
        >>> redis_mgr = get_redis_manager()
        >>> await redis_mgr.initialize()
    """
    global _redis_manager
    if _redis_manager is None:
        _redis_manager = RedisManager()
    return _redis_manager


# Convenience async context manager
@asynccontextmanager
async def redis_lifespan():
    """
    Convenience context manager for Redis lifespan

    Usage:
        async with redis_lifespan() as redis_mgr:
            await redis_mgr.set("key", "value")
            value = await redis_mgr.get("key")
    """
    redis_mgr = get_redis_manager()
    await redis_mgr.initialize()
    try:
        yield redis_mgr
    finally:
        await redis_mgr.close()


if __name__ == "__main__":
    import asyncio

    async def test():
        """Test Redis manager"""
        async with redis_lifespan() as redis_mgr:
            # Test set/get
            await redis_mgr.set("test_key", {"data": "value"}, ttl=60)
            value = await redis_mgr.get("test_key")
            print(f"Retrieved: {value}")

            # Test stats
            stats = redis_mgr.get_stats()
            print(f"Stats: {stats}")

    asyncio.run(test())
