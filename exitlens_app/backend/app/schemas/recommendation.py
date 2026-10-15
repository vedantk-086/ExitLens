from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ProvenanceKind


class CandidateStatus(str, Enum):
    """Enumeration of permitted recommendation states."""
    PROPOSED = "proposed"
    NO_CANDIDATE_IDENTIFIED = "no_candidate_identified"
    UNAVAILABLE = "unavailable"
    INVALID_RESPONSE = "invalid_response"


class MigrationStep(BaseModel):
    """An ordered, concrete migration step proposed for a dependency exit."""
    model_config = ConfigDict(extra="ignore")

    step_number: int = Field(..., description="1-indexed sequence number")
    action: str = Field(..., description="Short action summary (e.g. 'Replace import', 'Update requirements')")
    description: str = Field(..., description="Detailed instructions for the developer")
    target_file: Optional[str] = Field(default=None, description="Repository-relative target file path")
    code_example: Optional[str] = Field(default=None, description="Code example or snippet for the step")
    human_review_required: bool = Field(default=True, description="True if step requires human validation")


class SuggestedTest(BaseModel):
    """A test suggestion formulated based on discovered usages."""
    model_config = ConfigDict(extra="ignore")

    test_id: str = Field(..., description="Unique suggestion identifier")
    objective: str = Field(..., description="Goal of the test check")
    description: Optional[str] = Field(default=None, description="Short summary of the test check")
    relation_to_usage: str = Field(..., description="How this check links to discovered repository usages")
    suggested_profile: str = Field(..., description="Test profile identifier (e.g. pytest-unit)")
    test_type: Optional[str] = Field(default=None, description="Test framework or profile type")
    preconditions: List[str] = Field(default_factory=list, description="Requirements prior to execution")
    expected_signal: str = Field(..., description="Expected outcome indicating compatibility")
    code_example: Optional[str] = Field(default=None, description="Expected signal or test code snippet")


class ProposedReplacement(BaseModel):
    """Structured candidate proposed by AI or explicit empty state."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field(
        ...,
        description="Candidate status: 'proposed', 'no_candidate_identified', 'unavailable', 'invalid_response'",
    )
    distribution_name: Optional[str] = Field(
        default=None,
        description="Suggested replacement PyPI package name, or None if none identified",
    )
    candidate_distribution: Optional[str] = Field(
        default=None,
        description="Alias for distribution_name",
    )
    specifier: Optional[str] = Field(
        default=None,
        description="Recommended version constraint/specifier (e.g. '>=2.31.0')",
    )
    candidate_specifier: Optional[str] = Field(
        default=None,
        description="Alias for specifier",
    )
    rationale: str = Field(..., description="Evidence-backed rationale for the recommendation")
    limitations: Optional[str] = Field(default=None, description="Candidate limitations or architectural notes")
    candidate_validation_status: str = Field(
        default="NOT_VERIFIED",
        description="Validation outcome: 'NOT_VERIFIED', 'VERIFIED_PASSING', 'VERIFIED_FAILING', etc.",
    )


class AiProvenance(BaseModel):
    """Verifiable execution metadata for hosted or local AI inference."""
    model_config = ConfigDict(extra="ignore")

    provider: str = Field(default="google_ai_studio", description="Provider identifier (e.g. 'google_ai_studio')")
    model_family: str = Field(default="Gemma", description="Model family name")
    model_id: str = Field(..., description="Actual configured model identifier, e.g. gemma-4-26b-a4b-it")
    inference_method: str = Field(default="hosted_google_ai_studio", description="Inference modality")
    prompt_version: str = Field(default="exitlens-v1", description="Prompt template version")
    generated_at_utc: str = Field(default="", description="Observation timestamp in UTC ISO-8601")
    evidence_references: List[str] = Field(default_factory=list, description="Validated evidence IDs referenced")
    recommendation_status: str = Field(default="proposed", description="Recommendation status code")
    request_id: Optional[str] = Field(default=None, description="Safe request or correlation ID")
    failure_category: Optional[str] = Field(default=None, description="Safe failure category if unsuccessful")
    terms_url: str = Field(default="https://ai.google.dev/terms", description="Applicable model terms URL")
    provenance_kind: ProvenanceKind = Field(
        default=ProvenanceKind.AI_RECOMMENDATION,
        description="Must always be AI_RECOMMENDATION",
    )



class RecommendationRecord(BaseModel):
    """Complete recommendation package for one dependency."""
    model_config = ConfigDict(extra="ignore")

    dependency_id: str
    proposed_replacement: ProposedReplacement
    migration_steps: List[MigrationStep] = Field(default_factory=list)
    api_differences: List[str] = Field(default_factory=list)
    suggested_tests: List[SuggestedTest] = Field(default_factory=list)
    compatibility_concerns: List[str] = Field(default_factory=list)
    open_concerns_limitations: List[str] = Field(default_factory=list)
    patch_proposal: Optional[str] = Field(default=None, description="Optional unified diff patch")
    provenance: Optional[AiProvenance] = None


class RegenerateRecommendationsRequest(BaseModel):
    """Request payload to regenerate recommendations for selected dependencies."""
    model_config = ConfigDict(extra="ignore")

    dependency_ids: List[str] = Field(..., min_length=1, description="Selected dependency IDs")
    force_regenerate: bool = Field(default=False, description="Whether to overwrite existing recommendations")


class RegenerateRecommendationsResponse(BaseModel):
    """Response payload acknowledging recommendation regeneration."""
    model_config = ConfigDict(extra="ignore")

    analysis_id: str
    status: str = "queued"
    stage: str = "generating_recommendations"
    regenerated_count: int
    recommendations: List[RecommendationRecord] = Field(default_factory=list)
