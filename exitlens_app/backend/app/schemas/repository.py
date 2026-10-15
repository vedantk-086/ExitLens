"""Repository input and analysis options schemas."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import AnalysisStatus


class RepositoryKind(str, Enum):
    """Permitted source kinds for repository analysis."""
    LOCAL_PATH = "local_path"
    GIT_URL = "git_url"


class RepositoryInput(BaseModel):
    """Specification of the target repository."""
    model_config = ConfigDict(extra="ignore")

    kind: RepositoryKind = Field(
        default=RepositoryKind.LOCAL_PATH,
        description="Whether target is a local folder or public HTTPS Git URL",
    )
    value: str = Field(
        ...,
        description="Local directory path or public Git repository URL",
        examples=["C:/work/LinkWatch", "https://github.com/rishrek/LinkWatch"],
    )
    git_ref: Optional[str] = Field(
        default=None,
        description="Optional Git branch, tag, or commit hash to check out",
    )


class AnalysisOptions(BaseModel):
    """Configurable options bounding and tuning the analysis run."""
    model_config = ConfigDict(extra="ignore")

    exclude_paths: List[str] = Field(
        default_factory=lambda: [".git", ".venv", "venv", "node_modules", "reports", "exitlens_app"],
        description="Paths or patterns to ignore during file discovery",
    )
    include_tests: bool = Field(
        default=True,
        description="Whether to scan test files for dependency usages",
    )
    use_git_history: bool = Field(
        default=True,
        description="Whether to inspect Git commit log for revision metadata",
    )
    generate_recommendations: bool = Field(
        default=True,
        description="Whether to invoke local Gemma 4 for flagged dependency recommendations",
    )


class CreateAnalysisRequest(BaseModel):
    """Payload to initiate a new repository analysis run."""
    model_config = ConfigDict(extra="ignore")

    repository: RepositoryInput
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)


class CreateAnalysisResponse(BaseModel):
    """Immediate response confirming analysis creation."""
    model_config = ConfigDict(extra="ignore")

    analysis_id: str = Field(..., description="Stable UUID of the created analysis run")
    status: AnalysisStatus = Field(default=AnalysisStatus.QUEUED)
    stage: AnalysisStatus = Field(default=AnalysisStatus.VALIDATING_REPOSITORY)
    created_at: str = Field(..., description="UTC ISO-8601 timestamp of creation")
