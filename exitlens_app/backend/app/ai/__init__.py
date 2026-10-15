"""AI and recommendation engine module for ExitLens."""

from app.ai.base import BaseAiProvider
from app.ai.fake_provider import FakeAiProvider
from app.ai.google_studio import GoogleAiStudioProvider
from app.ai.prompts import PROMPT_VERSION, build_migration_prompt, build_schema_repair_prompt
from app.ai.validator import validate_and_parse_ai_response, validate_patch_security

from typing import Optional
from app.core.config import Settings, get_settings

def get_ai_provider(settings: Optional[Settings] = None) -> BaseAiProvider:
    """Factory creating the configured AI provider based on GEMMA_PROVIDER setting."""
    s = settings or get_settings()
    provider_name = s.GEMMA_PROVIDER.lower().strip()
    if provider_name == "test_fixture":
        return FakeAiProvider(settings=s)
    elif provider_name == "google_ai_studio":
        return GoogleAiStudioProvider(settings=s)
    elif provider_name == "ollama":
        return FakeAiProvider(settings=s)
    else:
        return GoogleAiStudioProvider(settings=s)


__all__ = [
    "BaseAiProvider",
    "GoogleAiStudioProvider",
    "FakeAiProvider",
    "get_ai_provider",
    "PROMPT_VERSION",
    "build_migration_prompt",
    "build_schema_repair_prompt",
    "validate_and_parse_ai_response",
    "validate_patch_security",
]

