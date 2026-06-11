"""
redis_client.py — Singleton async Redis client for Fleet AI.

Provides a shared redis.asyncio.Redis instance configured from REDIS_URL.
All Fleet AI modules that need Redis import `get_redis()` from here.

Usage:
    from redis_client import get_redis, ping_redis

    r = await get_redis()
    await r.set("key", "value")
"""
from __future__ import annotations

import os
from typing import Optional

import structlog

log = structlog.get_logger(__name__)

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

_redis_instance: Optional[object] = None  # redis.asyncio.Redis, typed as object to avoid import at module level


async def get_redis():  # -> redis.asyncio.Redis
    """Return shared Redis instance, creating it on first call."""
    global _redis_instance
    if _redis_instance is None:
        import redis.asyncio as aioredis
        _redis_instance = aioredis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        log.info("redis_client_created", url=REDIS_URL)
    return _redis_instance


async def ping_redis() -> None:
    """
    Health check — raises RuntimeError if Redis is unreachable.
    Called during Fleet AI startup before accepting any orders.
    """
    try:
        r = await get_redis()
        await r.ping()
        log.info("redis_ping_ok", event="redis_ping_ok", service="fleet-ai", url=REDIS_URL)
    except Exception as exc:
        raise RuntimeError(f"Redis health check failed ({REDIS_URL}): {exc}") from exc


async def close_redis() -> None:
    """Close the Redis connection — call on shutdown."""
    global _redis_instance
    if _redis_instance is not None:
        try:
            await _redis_instance.aclose()
        except Exception as exc:
            log.warning("redis_close_error", event="redis_close_error", service="fleet-ai", error=str(exc))
        finally:
            _redis_instance = None
