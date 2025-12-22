"""
Epoch Manager для Forward Test.

Управляет текущей эпохой данных. При очистке эпоха увеличивается,
старые данные остаются в БД но не показываются в UI.
"""
import redis.asyncio as redis
from typing import Optional

REDIS_KEY = "forward_test:current_epoch"
_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get or create Redis connection."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url("redis://localhost:6379", decode_responses=True)
    return _redis_client


async def get_current_epoch() -> int:
    """Get current epoch number. Returns 1 if not set."""
    r = await get_redis()
    value = await r.get(REDIS_KEY)
    if value is None:
        await r.set(REDIS_KEY, "1")
        return 1
    return int(value)


async def increment_epoch() -> int:
    """Increment epoch and return new value."""
    r = await get_redis()
    new_epoch = await r.incr(REDIS_KEY)
    return new_epoch


async def set_epoch(epoch: int) -> None:
    """Set epoch to specific value."""
    r = await get_redis()
    await r.set(REDIS_KEY, str(epoch))
