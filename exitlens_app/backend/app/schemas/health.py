"""Health and readiness response schemas for ExitLens."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ApiStatus(BaseModel):
    """API service state."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field(default="ready", description="API operational readiness state")
    version: str = Field(default="0.1.0", description="ExitLens backend release version")
    environment: str = Field(default="development", description="Configured application environment")


class PythonStatus(BaseModel):
    """Python interpreter runtime status."""
    model_config = ConfigDict(extra="ignore")

    version: str = Field(..., description="Active runtime Python version")
    is_compatible: bool = Field(..., description="True if running on supported Python 3.12 or 3.13")
    details: Optional[str] = Field(default=None, description="Compatibility commentary")


class AiStatus(BaseModel):
    """Local Gemma 4 / Ollama inference readiness."""
    model_config = ConfigDict(extra="ignore")

    provider: str = Field(..., description="Configured inference provider")
    configured_model: str = Field(..., description="Configured Gemma model name or tag")
    available: bool = Field(..., description="True if local provider is reachable and responsive")
    details: Optional[str] = Field(default=None, description="Safe summary of provider readiness")


class StorageStatus(BaseModel):
    """Analysis reports storage readiness."""
    model_config = ConfigDict(extra="ignore")

    ready: bool = Field(..., description="True if storage directory exists and is accessible")
    writable: bool = Field(..., description="True if storage directory permits writing run artifacts")
    details: Optional[str] = Field(default=None, description="Safe storage status notes")


class HealthResponse(BaseModel):
    """Safe readiness payload returned by GET /api/v1/health."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="Overall status ('healthy' or 'degraded')")
    timestamp_utc: str = Field(..., description="Observation timestamp in UTC ISO-8601")
    api: ApiStatus
    python: PythonStatus
    ai: AiStatus
    storage: StorageStatus
