"""Analysis job lifecycle, status, and summary schemas."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.capsule import CapsuleSummary
from app.schemas.common import AnalysisStatus
from app.schemas.repository import AnalysisOptions, RepositoryInput


class ProgressSummary(BaseModel):
    """Real-time progress representation of an active analysis run."""
    model_config = ConfigDict(extra="ignore")

    stage: AnalysisStatus = Field(default=AnalysisStatus.QUEUED)
    percent: int = Field(default=0, ge=0, le=100)
    message: str = Field(default="Analysis queued.")


class ArtifactAvailability(BaseModel):
    """Presence flags for persisted run artifacts."""
    model_config = ConfigDict(extra="ignore")

    has_analysis_json: bool = False
    has_evidence_json: bool = False
    has_capsule_json: bool = False
    has_capsule_md: bool = False
    has_capsule_pdf: bool = False
    verification_count: int = 0


class AnalysisRecord(BaseModel):
    """Complete persistent state record of an analysis run stored in analysis.json."""
    model_config = ConfigDict(extra="ignore")

    analysis_id: str = Field(..., description="Stable analysis UUID")
    status: AnalysisStatus = Field(default=AnalysisStatus.QUEUED)
    stage: AnalysisStatus = Field(default=AnalysisStatus.VALIDATING_REPOSITORY)
    created_at_utc: str = Field(..., description="UTC ISO-8601 creation timestamp")
    updated_at_utc: str = Field(..., description="UTC ISO-8601 last update timestamp")
    completed_at_utc: Optional[str] = Field(default=None, description="UTC ISO-8601 completion timestamp")
    repository: RepositoryInput
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)
    progress: ProgressSummary = Field(default_factory=ProgressSummary)
    summary: CapsuleSummary = Field(default_factory=CapsuleSummary)
    warnings: List[str] = Field(default_factory=list, description="Logged coverage and non-fatal warnings")
    errors: List[str] = Field(default_factory=list, description="Fatal or critical process errors")
    artifacts: ArtifactAvailability = Field(default_factory=ArtifactAvailability)


class AnalysisStatusResponse(BaseModel):
    """Public status and progress view returned by GET /api/v1/analyses/{analysis_id}."""
    model_config = ConfigDict(extra="ignore")

    analysis_id: str
    status: AnalysisStatus
    stage: AnalysisStatus
    created_at_utc: str
    updated_at_utc: str
    completed_at_utc: Optional[str] = None
    progress: ProgressSummary
    summary: CapsuleSummary
    warnings: List[str] = Field(default_factory=list)
    artifacts: ArtifactAvailability
