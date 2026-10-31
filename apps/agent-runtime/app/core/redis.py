"""
NEX Agent Runtime — Redis Connection Lifecycle & Health.

Manages the async Redis connection pool using redis.asyncio.
Provides dependency injection for route handlers and readiness probes.
Never exposes credentials in logs.
"""

import logging
from typing import AsyncIterator, Optional
import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger("agent_runtime.redis")

# Module-level connection pool and client reference
_redis_pool: Optional[aioredis.ConnectionPool] = None
_redis_client: Optional[aioredis.Redis] = None


async def init_redis_pool() -> aioredis.Redis:
    """
    Initialize the async Redis connection pool and test connectivity.
    Called during application lifespan startup.
    """
    global _redis_pool, _redis_client

    if _redis_client is not None:
        return _redis_client

    logger.info("Initializing async Redis connection pool")
    _redis_pool = aioredis.ConnectionPool.from_url(
        settings.redis_url,
        max_connections=settings.redis_max_connections,
        socket_connect_timeout=settings.redis_connect_timeout_seconds,
        socket_timeout=settings.redis_socket_timeout_seconds,
        decode_responses=True,
    )
    _redis_client = aioredis.Redis(connection_pool=_redis_pool)

    # Perform initial connectivity ping
    try:
        await _redis_client.ping()
        logger.info("Async Redis connection successfully verified")
    except (RedisError, OSError) as exc:
        logger.warning("Redis initial ping failed (service will run, but readiness probe will report degraded): %s", exc)

    return _redis_client


async def close_redis_pool() -> None:
    """
    Gracefully close Redis connections and release socket resources.
    Called during application lifespan shutdown.
    """
    global _redis_pool, _redis_client

    if _redis_client is not None:
        logger.info("Closing Redis client")
        await _redis_client.aclose()
        _redis_client = None

    if _redis_pool is not None:
        logger.info("Disconnecting Redis connection pool")
        await _redis_pool.disconnect()
        _redis_pool = None


async def check_redis_health() -> bool:
    """
    Check if Redis is responsive via PING with a bounded timeout.
    Returns True if healthy, False if unreachable or timed out.
    """
    if _redis_client is None:
        return False
    try:
        response = await _redis_client.ping()
        return bool(response)
    except Exception as exc:
        logger.warning("Redis health check failed: %s", exc)
        return False


async def get_redis() -> AsyncIterator[aioredis.Redis]:
    """
    FastAPI dependency for accessing the Redis client.
    Raises RuntimeError if Redis client has not been initialized.
    """
    if _redis_client is None:
        raise RuntimeError("Redis client is not initialized in application lifespan")
    yield _redis_client

