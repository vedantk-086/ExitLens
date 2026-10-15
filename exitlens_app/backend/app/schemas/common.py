"""Common schema models and enums for ExitLens API."""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProvenanceKind(str, Enum):
    """Provenance categories strictly defined by the ExitLens contract."""
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    AI_RECOMMENDATION = "AI_RECOMMENDATION"
    EXECUTION_RESULT = "EXECUTION_RESULT"
    NOT_VERIFIED = "NOT_VERIFIED"


class AnalysisStatus(str, Enum):
    """Canonical lifecycle states of an analysis run."""
    QUEUED = "queued"
    VALIDATING_REPOSITORY = "validating_repository"
    SCANNING = "scanning"
    MAPPING_USAGE = "mapping_usage"
    ASSESSING_RISK = "assessing_risk"
    GENERATING_RECOMMENDATIONS = "generating_recommendations"
    READY_FOR_VERIFICATION = "ready_for_verification"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"


class ErrorDetail(BaseModel):
    """Standardized error payload detail."""
    model_config = ConfigDict(extra="ignore")

    code: str = Field(..., description="Stable error code (e.g. NOT_FOUND, MODEL_UNAVAILABLE)")
    message: str = Field(..., description="Human-readable safe explanation")
    details: Dict[str, Any] = Field(default_factory=dict, description="Supplementary context")
    request_id: str = Field(..., description="Unique request tracing ID")


class ErrorResponse(BaseModel):
    """Standard top-level error response envelope."""
    model_config = ConfigDict(extra="ignore")

    error: ErrorDetail
