"""
NEX Agent Runtime — Test Configuration and Fixtures.
"""

from typing import AsyncIterator
import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    """Return test settings with debug enabled and test environment."""
    return Settings(
        app_name="NEX Agent Runtime (Test)",
        app_env="test",
        app_debug=False,
        redis_url="redis://localhost:6379/15",
        backend_url="http://localhost:8000",
        max_request_body_size_bytes=1024 * 1024,  # 1 MB for testing
        internal_service_secret="test-internal-secret-12345678901234567890",
        internal_service_secret_fallback="test-fallback-secret-12345678901234567890",
    )


@pytest.fixture
def app(test_settings: Settings):
    """Create and return a FastAPI test application instance."""
    return create_app(custom_settings=test_settings)


@pytest_asyncio.fixture
async def client(app, test_settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    """Provide an authenticated async HTTP test client communicating via ASGITransport."""
    transport = ASGITransport(app=app)
    headers = {"X-Internal-Service-Key": test_settings.internal_service_secret}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", headers=headers) as ac:
        yield ac


@pytest_asyncio.fixture
async def unauth_client(app) -> AsyncIterator[httpx.AsyncClient]:
    """Provide an unauthenticated async HTTP test client communicating via ASGITransport."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
