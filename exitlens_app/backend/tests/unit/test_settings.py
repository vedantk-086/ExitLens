"""Unit tests for ExitLens typed configuration settings."""

from pathlib import Path
import pytest
from app.core.config import Settings


def test_default_settings():
    """Verify default settings match the specification."""
    s = Settings()
    assert s.APP_ENV == "development"
    assert s.APP_HOST == "127.0.0.1"
    assert s.APP_PORT == 8000
    assert s.API_PREFIX == "/api/v1"
    assert "http://127.0.0.1:5173" in s.CORS_ORIGINS
    assert "http://localhost:5173" in s.CORS_ORIGINS
    assert s.GEMMA_PROVIDER == "google_ai_studio"
    assert s.GOOGLE_AI_MODEL == "gemma-4-26b-a4b-it"
    assert s.GEMMA_MODEL == "gemma4"
    assert s.ENABLE_PUBLIC_HTTPS_GIT_CLONE is True

    assert s.MAX_ANALYSIS_FILES == 5000
    assert s.MAX_SINGLE_FILE_BYTES == 500000
    assert s.MAX_TOTAL_SOURCE_BYTES == 20000000
    assert s.MAX_CAPTURED_OUTPUT_BYTES == 16000
    assert s.ALLOW_TEST_NETWORK is False


def test_cors_origins_comma_separated_parsing():
    """Verify comma-separated string in CORS_ORIGINS is parsed to list of strings."""
    s = Settings(CORS_ORIGINS="http://example.com, https://app.example.com")
    assert s.CORS_ORIGINS == ["http://example.com", "https://app.example.com"]


def test_allowed_roots_comma_separated_parsing():
    """Verify comma-separated string in ALLOWED_REPOSITORY_ROOTS is parsed."""
    s = Settings(ALLOWED_REPOSITORY_ROOTS="/path/one, /path/two")
    assert s.ALLOWED_REPOSITORY_ROOTS == ["/path/one", "/path/two"]


def test_canonical_path_resolution(temp_dir: Path):
    """Verify canonical resolution of allowed roots and data dir."""
    data_dir_rel = "reports/custom"
    s = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir / "repo1"), str(temp_dir / "repo2")],
        EXITLENS_DATA_DIR=data_dir_rel,
    )
    canonical_roots = s.get_canonical_allowed_roots(base_dir=temp_dir)
    assert len(canonical_roots) == 2
    assert canonical_roots[0].is_absolute()
    assert canonical_roots[0] == (temp_dir / "repo1").resolve()

    canonical_data_dir = s.get_canonical_data_dir(base_dir=temp_dir)
    assert canonical_data_dir.is_absolute()
    assert canonical_data_dir == (temp_dir / data_dir_rel).resolve()
