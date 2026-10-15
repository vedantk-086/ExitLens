"""Pytest shared configuration and fixtures for ExitLens tests."""

from pathlib import Path
import tempfile
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.main import create_app


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test storage or repositories."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td).resolve()


@pytest.fixture
def test_settings(temp_dir: Path) -> Settings:
    """Return Settings configured specifically for unit tests."""
    return Settings(
        APP_ENV="test",
        APP_HOST="127.0.0.1",
        APP_PORT=8000,
        API_PREFIX="/api/v1",
        CORS_ORIGINS=["http://127.0.0.1:5173", "http://localhost:5173"],
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        ENABLE_PUBLIC_HTTPS_GIT_CLONE=True,
        GEMMA_PROVIDER="google_ai_studio",
        GOOGLE_AI_API_KEY="",
        GOOGLE_AI_MODEL="gemma-4-26b-a4b-it",
        GOOGLE_AI_TIMEOUT_SECONDS=90,
        GOOGLE_AI_MAX_RETRIES=1,
        PROMPT_VERSION="exitlens-v1",
        OLLAMA_BASE_URL="http://127.0.0.1:11434",
        GEMMA_MODEL="gemma4",
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
        LOG_LEVEL="DEBUG",
    )


@pytest.fixture
def app(test_settings: Settings):
    """FastAPI application fixture with test settings dependency override."""
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: test_settings
    return application


@pytest_asyncio.fixture
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Asynchronous HTTP test client."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
