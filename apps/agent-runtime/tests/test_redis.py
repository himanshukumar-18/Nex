"""
NEX Agent Runtime — Redis Lifecycle & Health Unit Tests.
"""

from unittest.mock import AsyncMock, patch
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.redis import check_redis_health, close_redis_pool, init_redis_pool


@pytest.mark.asyncio
async def test_redis_init_and_close():
    """Verify that Redis connection pool initializes and tears down cleanly."""
    with patch("redis.asyncio.ConnectionPool.from_url") as mock_pool, \
         patch("redis.asyncio.Redis.ping", new_callable=AsyncMock) as mock_ping, \
         patch("redis.asyncio.Redis.aclose", new_callable=AsyncMock) as mock_aclose:
        mock_pool.return_value.disconnect = AsyncMock()
        mock_ping.return_value = True

        client = await init_redis_pool()
        assert client is not None

        await close_redis_pool()
        mock_aclose.assert_awaited_once()
        mock_pool.return_value.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_redis_health_success():
    """Verify check_redis_health returns True when ping succeeds."""
    with patch("app.core.redis._redis_client") as mock_client:
        mock_client.ping = AsyncMock(return_value=True)
        assert await check_redis_health() is True


@pytest.mark.asyncio
async def test_check_redis_health_failure():
    """Verify check_redis_health returns False when ping throws an exception."""
    with patch("app.core.redis._redis_client") as mock_client:
        mock_client.ping = AsyncMock(side_effect=RedisConnectionError("Connection refused"))
        assert await check_redis_health() is False

