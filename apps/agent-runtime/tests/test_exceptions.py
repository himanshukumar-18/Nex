"""
NEX Agent Runtime — Exception Handling Unit Tests.
"""

from fastapi import APIRouter
import httpx
from pydantic import BaseModel
import pytest
import pytest_asyncio

from app.core.exceptions import DependencyUnavailableError, NexRuntimeError
from app.main import create_app


class SampleRequest(BaseModel):
    name: str
    count: int


@pytest.fixture
def error_test_app(test_settings):
    """Create an application with specific fault-injection test routes."""
    test_app = create_app(custom_settings=test_settings)
    router = APIRouter(prefix="/test-faults")

    @router.post("/validation")
    async def validation_endpoint(payload: SampleRequest):
        return {"received": payload.name}

    @router.get("/custom-runtime-error")
    async def custom_runtime_error_endpoint():
        raise NexRuntimeError(message="Custom operational failure", code="CUSTOM_FAULT", status_code=502)

    @router.get("/dependency-error")
    async def dependency_error_endpoint():
        raise DependencyUnavailableError(message="Postgres vector cluster down")

    @router.get("/unhandled-error")
    async def unhandled_error_endpoint():
        raise ZeroDivisionError("division by zero test")

    test_app.include_router(router)
    return test_app


@pytest_asyncio.fixture
async def fault_client(error_test_app) -> httpx.AsyncClient:
    from httpx import ASGITransport
    transport = ASGITransport(app=error_test_app, raise_app_exceptions=False)
    headers = {"X-Internal-Service-Key": error_test_app.state.settings.internal_service_secret}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", headers=headers) as ac:
        yield ac


@pytest.mark.asyncio
async def test_404_not_found_envelope(client: httpx.AsyncClient):
    """Verify that a 404 response uses the standardized error envelope."""
    res = await client.get("/api/v1/non-existent-endpoint")
    assert res.status_code == 404
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert data["error"]["message"] is not None


@pytest.mark.asyncio
async def test_405_method_not_allowed_envelope(client: httpx.AsyncClient):
    """Verify that a 405 response uses the standardized error envelope."""
    res = await client.post("/health")
    assert res.status_code == 405
    data = res.json()
    assert data["error"]["code"] == "METHOD_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_request_validation_error_envelope(fault_client: httpx.AsyncClient):
    """Verify that Pydantic validation errors return 422 with structured details."""
    res = await fault_client.post("/test-faults/validation", json={"name": "test", "count": "invalid-int"})
    assert res.status_code == 422
    data = res.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["message"] == "Request input validation failed"
    assert isinstance(data["error"]["detail"], list)
    assert any("count" in err["field"] for err in data["error"]["detail"])


@pytest.mark.asyncio
async def test_custom_runtime_error_envelope(fault_client: httpx.AsyncClient):
    """Verify that custom NexRuntimeError returns configured status and code."""
    res = await fault_client.get("/test-faults/custom-runtime-error")
    assert res.status_code == 502
    data = res.json()
    assert data["error"]["code"] == "CUSTOM_FAULT"
    assert data["error"]["message"] == "Custom operational failure"


@pytest.mark.asyncio
async def test_dependency_unavailable_envelope(fault_client: httpx.AsyncClient):
    """Verify that DependencyUnavailableError returns 503 SERVICE_UNAVAILABLE."""
    res = await fault_client.get("/test-faults/dependency-error")
    assert res.status_code == 503
    data = res.json()
    assert data["error"]["code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_unhandled_error_envelope_sanitized(fault_client: httpx.AsyncClient):
    """Verify that unhandled exceptions return 500 without leaking stack trace in non-debug mode."""
    res = await fault_client.get("/test-faults/unhandled-error")
    assert res.status_code == 500
    data = res.json()
    assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert data["error"]["message"] == "An unexpected internal error occurred"
    assert data["error"]["detail"] is None

