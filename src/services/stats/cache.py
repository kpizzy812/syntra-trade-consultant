"""
Stats Cache Layer - Redis caching с версионированием.

Использует версионированные ключи вместо wildcard delete:
- При инвалидации инкрементируем версию
- Старые ключи auto-expire по TTL

Следует паттерну из плана ancient-shimmying-pizza.md.
"""

import json
import hashlib
from typing import Optional, Any
from datetime import timedelta

from redis.asyncio import Redis


class StatsCacheLayer:
    """Redis caching для Stats API с версионированием."""

    # TTL по типу данных
    TTL_OVERVIEW = 60  # 1 min - часто обновляется
    TTL_OUTCOMES = 300  # 5 min
    TTL_ARCHETYPES = 600  # 10 min - реже меняется
    TTL_GATES = 60  # 1 min - критично для торговли
    TTL_FUNNEL = 1800  # 30 min - редко меняется
    TTL_SYMBOLS = 300  # 5 min

    # Version keys (инкрементируются при инвалидации)
    VERSION_KEYS = {
        "overview": "stats:v:overview",
        "outcomes": "stats:v:outcomes",
        "archetypes": "stats:v:archetypes",
        "gates": "stats:v:gates",
        "funnel": "stats:v:funnel",
        "symbols": "stats:v:symbols",
    }

    def __init__(self, redis: Optional[Redis] = None):
        self.redis = redis
        self._enabled = redis is not None

    @property
    def enabled(self) -> bool:
        return self._enabled and self.redis is not None

    async def get_version(self, cache_type: str) -> int:
        """Get current version for cache type."""
        if not self.enabled:
            return 0

        key = self.VERSION_KEYS.get(cache_type)
        if not key:
            return 0

        try:
            version = await self.redis.get(key)
            return int(version) if version else 0
        except Exception:
            return 0

    async def get_archetype_version(self, archetype: str) -> int:
        """Get version for specific archetype."""
        if not self.enabled:
            return 0

        key = f"stats:v:arch:{archetype}"
        try:
            version = await self.redis.get(key)
            return int(version) if version else 0
        except Exception:
            return 0

    async def cache_key(self, cache_type: str, **params) -> str:
        """Generate versioned cache key.

        Format: stats:{type}:v{version}:{hash}
        Example: stats:overview:v12:a1b2c3d4
        """
        version = await self.get_version(cache_type)
        param_str = json.dumps(params, sort_keys=True)
        hash_val = hashlib.md5(param_str.encode()).hexdigest()[:8]
        return f"stats:{cache_type}:v{version}:{hash_val}"

    async def cache_key_archetype_detail(self, archetype: str, **params) -> str:
        """Cache key для archetype detail с ОБЕИМИ версиями!

        Format: stats:archetype:{name}:v{arch_v}:v{global_v}:{hash}

        Используем и глобальную версию archetypes,
        и специфичную версию архетипа.
        """
        global_v = await self.get_version("archetypes")
        arch_v = await self.get_archetype_version(archetype)
        param_str = json.dumps(params, sort_keys=True)
        hash_val = hashlib.md5(param_str.encode()).hexdigest()[:8]
        return f"stats:archetype:{archetype}:v{arch_v}:v{global_v}:{hash_val}"

    async def get(self, cache_type: str, **params) -> Optional[dict]:
        """Get cached value."""
        if not self.enabled:
            return None

        try:
            key = await self.cache_key(cache_type, **params)
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    async def get_archetype_detail(self, archetype: str, **params) -> Optional[dict]:
        """Get cached archetype detail."""
        if not self.enabled:
            return None

        try:
            key = await self.cache_key_archetype_detail(archetype, **params)
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    async def set(
        self,
        cache_type: str,
        value: Any,
        **params
    ) -> bool:
        """Set cached value with appropriate TTL."""
        if not self.enabled:
            return False

        ttl_map = {
            "overview": self.TTL_OVERVIEW,
            "outcomes": self.TTL_OUTCOMES,
            "archetypes": self.TTL_ARCHETYPES,
            "gates": self.TTL_GATES,
            "funnel": self.TTL_FUNNEL,
            "symbols": self.TTL_SYMBOLS,
        }
        ttl = ttl_map.get(cache_type, 300)

        try:
            key = await self.cache_key(cache_type, **params)
            await self.redis.setex(
                key,
                timedelta(seconds=ttl),
                json.dumps(value, default=str)
            )
            return True
        except Exception:
            return False

    async def set_archetype_detail(
        self,
        archetype: str,
        value: Any,
        **params
    ) -> bool:
        """Set cached archetype detail."""
        if not self.enabled:
            return False

        try:
            key = await self.cache_key_archetype_detail(archetype, **params)
            await self.redis.setex(
                key,
                timedelta(seconds=self.TTL_ARCHETYPES),
                json.dumps(value, default=str)
            )
            return True
        except Exception:
            return False

    async def invalidate(self, cache_type: str) -> bool:
        """Invalidate cache by incrementing version.

        Old keys auto-expire by TTL. No SCAN, no DEL wildcard.
        """
        if not self.enabled:
            return False

        key = self.VERSION_KEYS.get(cache_type)
        if not key:
            return False

        try:
            await self.redis.incr(key)
            return True
        except Exception:
            return False

    async def invalidate_archetype(self, archetype: str) -> bool:
        """Invalidate specific archetype cache."""
        if not self.enabled:
            return False

        try:
            # Archetype-specific version
            key = f"stats:v:arch:{archetype}"
            await self.redis.incr(key)
            return True
        except Exception:
            return False

    async def invalidate_all_trading(self) -> bool:
        """Invalidate all trading-related caches."""
        if not self.enabled:
            return False

        try:
            await self.invalidate("overview")
            await self.invalidate("outcomes")
            await self.invalidate("symbols")
            return True
        except Exception:
            return False


async def on_trade_outcome_received(
    outcome,
    cache: StatsCacheLayer
) -> None:
    """Called when new TradeOutcome is received.

    Invalidates affected caches.
    """
    # Инкрементируем версии — старые ключи auto-expire по TTL
    await cache.invalidate("overview")
    await cache.invalidate("outcomes")

    # Archetype-specific invalidation
    archetype = getattr(outcome, 'primary_archetype', None)
    if archetype:
        await cache.invalidate_archetype(archetype)
        await cache.invalidate("archetypes")  # list тоже
