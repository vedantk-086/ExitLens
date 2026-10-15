"""Unit tests for error formatting and exception handlers."""

import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.core.errors import (
    ModelUnavailableError,
    NotFoundError,
    PathForbiddenError,
    PathTraversalDetectedError,
    StateConflictError,
    ValidationError,
)
from app.core.paths import PathSafetyError, PathTraversalError
from app.main import create_app

# Router for testing error triggers (not prefixed with test_ to avoid pytest warning)
error_trigger_router = APIRouter(prefix="/error-triggers")


class SampleBody(BaseModel):
    name: str
    count: int


@error_trigger_router.post("/validate-body")
async def trigger_validation(body: SampleBody):
    return {"status": "ok", "name": body.name}


@error_trigger_router.get("/not-found")
async def trigger_not_found():
    raise NotFoundError("Analysis 'an-999' was not found.")


@error_trigger_router.get("/model-unavailable")
async def trigger_model_unavailable():
    raise ModelUnavailableError(details={"stage": "generating_recommendations"})


@error_trigger_router.get("/conflict")
async def trigger_conflict():
    raise StateConflictError("Cannot verify while scanning is in progress.")


@error_trigger_router.get("/path-safety")
async def trigger_path_safety():
    raise PathSafetyError("Target path escapes repository root.")


@error_trigger_router.get("/path-traversal")
async def trigger_path_traversal():
    raise PathTraversalError("Directory traversal '..' detected.")


@error_trigger_router.get("/unhandled")
async def trigger_unhandled():
    raise RuntimeError("Simulated unexpected crash that must not leak traceback")


@pytest.fixture
def app_with_test_errors():
    app = create_app()
    app.include_router(error_trigger_router)
    return app


@pytest.mark.asyncio
async def test_not_found_error_format(app_with_test_errors):
    transport = ASGITransport(app=app_with_test_errors, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/error-triggers/not-found")
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"
        assert "an-999" in data["error"]["message"]
        assert "request_id" in data["error"]
        assert resp.headers.get("X-Request-ID") == data["error"]["request_id"]


@pytest.mark.asyncio
async def test_unrouted_path_returns_standard_not_found_format(app_with_test_errors):
    transport = ASGITransport(app=app_with_test_errors, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/completely/nonexistent/path")
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"
        assert "request_id" in data["error"]
        assert resp.headers.get("X-Request-ID") == data["error"]["request_id"]


@pytest.mark.asyncio
async def test_model_unavailable_error_format(app_with_test_errors):
    transport = ASGITransport(app=app_with_test_errors, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/error-triggers/model-unavailable")
        assert resp.status_code == 503
        data = resp.json()
        assert data["error"]["code"] == "MODEL_UNAVAILABLE"
        assert "Gemma 4" in data["error"]["message"]
        assert data["error"]["details"] == {"stage": "generating_recommendations"}
        assert "request_id" in data["error"]


@pytest.mark.asyncio
async def test_state_conflict_error_format(app_with_test_errors):
    transport = ASGITransport(app=app_with_test_errors, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/error-triggers/conflict")
        assert resp.status_code == 409
        data = resp.json()
        assert data["error"]["code"] == "CONFLICT"
        assert "scanning is in progress" in data["error"]["message"]


@pytest.mark.asyncio
async def test_path_safety_and_traversal_errors(app_with_test_errors):
    transport = ASGITransport(app=app_with_test_errors, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Path safety (outside allowed root) -> 403
        resp1 = await client.get("/error-triggers/path-safety")
        assert resp1.status_code == 403
        assert resp1.json()["error"]["code"] == "PATH_NOT_ALLOWED"

        # Traversal -> 400
        resp2 = await client.get("/error-triggers/path-traversal")
        assert resp2.status_code == 400
        assert resp2.json()["error"]["code"] == "PATH_TRAVERSAL_DETECTED"


@pytest.mark.asyncio
async def test_validation_error_format_422(app_with_test_errors):
    transport = ASGITransport(app=app_with_test_errors, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Send invalid body (missing required fields, wrong type)
        resp = await client.post("/error-triggers/validate-body", json={"count": "not-an-int"})
        assert resp.status_code == 422
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "details" in data["error"]
        assert "errors" in data["error"]["details"]
        assert "request_id" in data["error"]


@pytest.mark.asyncio
async def test_unhandled_500_does_not_leak_traceback(app_with_test_errors):
    transport = ASGITransport(app=app_with_test_errors, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/error-triggers/unhandled")
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"]["code"] == "INTERNAL_ERROR"
        assert "unexpected server error" in data["error"]["message"]
        # Ensure stack trace or exception internals are not leaked in body
        assert "Traceback" not in resp.text
        assert "Simulated unexpected crash" not in resp.text
