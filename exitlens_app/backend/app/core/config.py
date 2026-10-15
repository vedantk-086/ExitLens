"""Application configuration module for ExitLens backend.

All configuration is loaded via pydantic-settings from environment variables
and an optional .env file.
"""

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, List, Optional, Union


from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings for ExitLens."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: Union[List[str], str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    # Permitted local repository roots. Paths will be resolved canonically.
    ALLOWED_REPOSITORY_ROOTS: Union[List[str], str] = ["../.."]
    ENABLE_PUBLIC_HTTPS_GIT_CLONE: bool = True

    # AI Provider configuration (Google AI Studio as primary default)
    GEMMA_PROVIDER: str = "google_ai_studio"
    GOOGLE_AI_API_KEY: Optional[str] = None
    GOOGLE_AI_MODEL: str = "gemma-4-26b-a4b-it"
    GOOGLE_AI_TIMEOUT_SECONDS: int = 90
    GOOGLE_AI_MAX_RETRIES: int = 1
    PROMPT_VERSION: str = "exitlens-v1"

    # Ollama settings (retained for fallback / offline compatibility)
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    GEMMA_MODEL: str = "gemma4"
    GEMMA_TIMEOUT_SECONDS: int = 90
    GEMMA_MAX_RETRIES: int = 1


    # Filesystem storage paths & limits
    EXITLENS_DATA_DIR: str = "../../reports/exitlens"
    MAX_ANALYSIS_FILES: int = 5000
    MAX_SINGLE_FILE_BYTES: int = 500000
    MAX_TOTAL_SOURCE_BYTES: int = 20000000
    MAX_CAPTURED_OUTPUT_BYTES: int = 16000
    DEFAULT_TEST_TIMEOUT_SECONDS: int = 90
    MAX_TEST_TIMEOUT_SECONDS: int = 180
    COMMAND_TIMEOUT_SECONDS: int = 120
    ALLOW_TEST_NETWORK: bool = False
    LOG_LEVEL: str = "INFO"

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> List[str]:
        """Parse comma-separated strings or list of origins."""
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("[") and value.endswith("]"):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, (list, tuple)):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        return []

    @field_validator("ALLOWED_REPOSITORY_ROOTS", mode="after")
    @classmethod
    def parse_allowed_roots(cls, value: Any) -> List[str]:
        """Parse comma-separated strings or list of repository root paths."""
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("[") and value.endswith("]"):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [root.strip() for root in value.split(",") if root.strip()]
        if isinstance(value, (list, tuple)):
            return [str(root).strip() for root in value if str(root).strip()]
        return []

    def get_canonical_allowed_roots(self, base_dir: Union[Path, None] = None) -> List[Path]:
        """Resolve all allowed repository roots canonically to absolute paths."""
        base = (base_dir or Path.cwd()).resolve()
        canonical_roots: List[Path] = []
        roots = self.ALLOWED_REPOSITORY_ROOTS if isinstance(self.ALLOWED_REPOSITORY_ROOTS, list) else [self.ALLOWED_REPOSITORY_ROOTS]
        for root in roots:
            path = Path(root)
            if not path.is_absolute():
                path = (base / path).resolve()
            else:
                path = path.resolve()
            canonical_roots.append(path)
        return canonical_roots

    def get_canonical_data_dir(self, base_dir: Union[Path, None] = None) -> Path:
        """Resolve the ExitLens data directory canonically to an absolute path."""
        base = (base_dir or Path.cwd()).resolve()
        path = Path(self.EXITLENS_DATA_DIR)
        if not path.is_absolute():
            return (base / path).resolve()
        return path.resolve()

    def is_production(self) -> bool:
        """Return True if application is running in production mode."""
        return self.APP_ENV.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
