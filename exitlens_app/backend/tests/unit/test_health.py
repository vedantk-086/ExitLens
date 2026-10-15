"""Unit tests for GET /api/v1/health and readiness reporting."""

from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """GET / returns service metadata and links to docs and health."""
    resp = await async_client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "ExitLens Backend"
    assert "health" in data


@pytest.mark.asyncio
async def test_health_endpoint_google_ai_studio_default(async_client: AsyncClient):
    """GET /api/v1/health returns Google AI Studio provider readiness safely."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()

    # Core structure
    assert "status" in data
    assert "timestamp_utc" in data
    assert "api" in data
    assert "python" in data
    assert "ai" in data
    assert "storage" in data

    # API details
    assert data["api"]["status"] == "ready"
    assert data["api"]["version"] == "0.1.0"

    # AI details for Google AI Studio
    assert data["ai"]["provider"] == "google_ai_studio"
    assert "gemma" in data["ai"]["configured_model"].lower()

    # Storage details
    assert data["storage"]["ready"] is True
    assert data["storage"]["writable"] is True

    # Critical security guarantee: NO secrets or private configuration exposed
    raw_text = response.text.lower()
    for secret_keyword in ["secret", "password", "token", "api_key", "bearer", "private"]:
        assert secret_keyword not in raw_text


@pytest.mark.asyncio
async def test_health_endpoint_with_configured_google_ai(async_client: AsyncClient):
    """GET /api/v1/health reports healthy when Google AI Studio has key configured."""
    with patch(
        "app.api.v1.routes.health.check_google_ai_readiness",
        return_value=(True, "Google AI Studio configured with model 'gemma-4-26b-a4b-it'"),
    ):
        response = await async_client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["ai"]["available"] is True
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_endpoint_with_ollama_provider(async_client: AsyncClient):
    """GET /api/v1/health returns Ollama status when configured for Ollama."""
    with patch(
        "app.api.v1.routes.health.check_ai_provider_readiness",
        new_callable=AsyncMock,
        return_value=("ollama", "gemma4", True, "Ollama is reachable and model 'gemma4' is installed"),
    ):
        response = await async_client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["ai"]["provider"] == "ollama"
        assert data["ai"]["configured_model"] == "gemma4"
        assert data["ai"]["available"] is True
        assert data["status"] == "healthy"



@pytest.mark.asyncio
async def test_health_endpoint_with_storage_failure(async_client: AsyncClient):
    """GET /api/v1/health returns degraded status if storage fails write check."""
    with patch(
        "app.api.v1.routes.health.check_storage_readiness",
        return_value=(True, False, "Storage write check failed"),
    ):
        response = await async_client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["storage"]["writable"] is False
        assert data["status"] == "degraded"


@pytest.mark.asyncio
async def test_request_id_in_health_response_header(async_client: AsyncClient):
    """Verify that every response includes an X-Request-ID header."""
    custom_id = "test-custom-req-12345"
    response = await async_client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id
