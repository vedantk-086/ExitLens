"""Health check route reporting safe readiness information for ExitLens."""

import os
import sys
from pathlib import Path
from typing import Tuple

from fastapi import APIRouter, Depends
import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.time import utc_now_iso
from app.schemas.health import (
    AiStatus,
    ApiStatus,
    HealthResponse,
    PythonStatus,
    StorageStatus,
)

logger = get_logger("exitlens.health")
router = APIRouter(tags=["Health"])


def check_google_ai_readiness(settings: Settings) -> Tuple[bool, str]:
    """Report safe Google AI Studio configuration readiness without leaking secrets.
    
    Reports configuration readiness separately from live connectivity to avoid
    consuming quota during routine health checks.
    """
    if not settings.GOOGLE_AI_API_KEY or not settings.GOOGLE_AI_API_KEY.strip():
        return False, "Google AI Studio API credentials are not configured"
    return True, f"Google AI Studio configured with model '{settings.GOOGLE_AI_MODEL}'"


async def check_ollama_readiness(settings: Settings) -> Tuple[bool, str]:
    """Asynchronously check if Ollama service is reachable and has the model available.
    
    Safe probe: does not block event loop, handles errors cleanly, never leaks secrets.
    """
    if settings.GEMMA_PROVIDER.lower() != "ollama":
        return False, f"Provider '{settings.GEMMA_PROVIDER}' is not configured for local Ollama"

    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
                model_found = any(settings.GEMMA_MODEL in m for m in models if m)
                if model_found:
                    return True, f"Ollama is reachable and model '{settings.GEMMA_MODEL}' is installed"
                return True, (
                    f"Ollama is reachable, but model '{settings.GEMMA_MODEL}' was not found in local models list. "
                    f"Run: ollama pull {settings.GEMMA_MODEL}"
                )
            return False, f"Ollama returned unexpected status code: {resp.status_code}"
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return False, f"Cannot connect to Ollama at {settings.OLLAMA_BASE_URL} (service may not be running)"
    except httpx.TimeoutException:
        return False, "Timed out waiting for response from Ollama endpoint"
    except Exception as exc:
        logger.debug("Error during Ollama health check: %s", exc)
        return False, "Error querying Ollama endpoint"


async def check_ai_provider_readiness(settings: Settings) -> Tuple[str, str, bool, str]:
    """Check AI provider status safely without leaking secrets or consuming unexpected quota."""
    provider = settings.GEMMA_PROVIDER.lower()
    if provider == "google_ai_studio":
        available, details = check_google_ai_readiness(settings)
        return "google_ai_studio", settings.GOOGLE_AI_MODEL, available, details
    elif provider == "ollama":
        available, details = await check_ollama_readiness(settings)
        return "ollama", settings.GEMMA_MODEL, available, details
    elif provider == "test_fixture":
        return "test_fixture", "test-fixture-model", True, "Test fixture provider active"
    else:
        return provider, "unknown", False, f"Unknown AI provider '{provider}'"


def check_storage_readiness(settings: Settings) -> Tuple[bool, bool, str]:
    """Verify that the analysis data directory can be created and is writable."""
    try:
        data_dir = settings.get_canonical_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        probe_file = data_dir / ".storage_write_test"
        try:
            probe_file.write_text("probe", encoding="utf-8")
            if probe_file.exists():
                probe_file.unlink()
            return True, True, "Storage directory is ready and writable"
        except Exception as write_err:
            return True, False, f"Storage directory exists but write check failed: {write_err}"
    except Exception as exc:
        return False, False, f"Failed to initialize storage directory: {exc}"


def check_python_compatibility() -> Tuple[str, bool, str]:
    """Check if active Python interpreter is Python 3.12 or 3.13."""
    version_str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    is_compatible = (sys.version_info.major == 3 and sys.version_info.minor in (12, 13))
    if is_compatible:
        details = f"Python {version_str} meets target specification (3.12 or 3.13)"
    else:
        details = (
            f"Python {version_str} is running, but target specification recommends Python 3.12 or 3.13. "
            f"Python 3.14 is incompatible with LinkWatch target."
        )
    return version_str, is_compatible, details


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Get safe service health and readiness status",
    description=(
        "Returns readiness information for API, Python runtime, configured AI inference provider, "
        "and filesystem storage. Never leaks configuration secrets or sensitive tokens."
    ),
)
async def get_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Return safe readiness info for API, Python runtime, AI provider, and storage."""
    # 1. Python status
    py_ver, py_compat, py_details = check_python_compatibility()
    py_status = PythonStatus(
        version=py_ver,
        is_compatible=py_compat,
        details=py_details,
    )

    # 2. AI provider readiness
    ai_provider, ai_model, ai_available, ai_details = await check_ai_provider_readiness(settings)
    ai_status = AiStatus(
        provider=ai_provider,
        configured_model=ai_model,
        available=ai_available,
        details=ai_details,
    )


    # 3. Storage readiness
    storage_ready, storage_writable, storage_details = check_storage_readiness(settings)
    storage_status = StorageStatus(
        ready=storage_ready,
        writable=storage_writable,
        details=storage_details,
    )

    # 4. API status
    api_status = ApiStatus(
        status="ready",
        version="0.1.0",
        environment=settings.APP_ENV,
    )

    # 5. Overall status: healthy if core components are ready; degraded if optional local AI is offline
    is_healthy = storage_ready and storage_writable and ai_available
    overall_status = "healthy" if is_healthy else "degraded"

    return HealthResponse(
        status=overall_status,
        timestamp_utc=utc_now_iso(),
        api=api_status,
        python=py_status,
        ai=ai_status,
        storage=storage_status,
    )
