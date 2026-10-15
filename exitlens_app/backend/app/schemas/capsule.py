"""Canonical Dependency Exit Capsule schema.

Defines the single source of truth for 9-section Dependency Exit Capsule records,
used identically for JSON export and Markdown rendering.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evidence import EvidenceRecord
from app.schemas.recommendation import (
    AiProvenance,
    MigrationStep,
    ProposedReplacement,
    SuggestedTest,
)
from app.schemas.risk import RiskIndicator
from app.schemas.verification import ExecutedTestResult


class UsageLocation(BaseModel):
    """Specific line/symbol usage reference of a dependency in source code."""
    model_config = ConfigDict(extra="ignore")

    usage_id: str = Field(..., description="Stable usage reference identifier")
    path: str = Field(..., description="Repository-relative file path")
    line_start: Optional[int] = Field(default=None, description="Starting line reference")
    line_end: Optional[int] = Field(default=None, description="Ending line reference")
    import_statement: Optional[str] = Field(default=None, description="Discovered import snippet")
    symbol: Optional[str] = Field(default=None, description="Specific imported symbol or class")
    pattern: Optional[str] = Field(default=None, description="Usage pattern or call expression")
    evidence_id: str = Field(..., description="Linked evidence ID")
    note: Optional[str] = Field(default=None, description="Uncertainty or scoping explanation")


class CompatibilityGap(BaseModel):
    """An observed or inferred behavioral incompatibility or API discrepancy."""
    model_config = ConfigDict(extra="ignore")

    gap_id: str = Field(..., description="Stable gap identifier")
    title: str = Field(..., description="Short gap summary")
    description: str = Field(..., description="Detailed explanation of the discrepancy")
    evidence_refs: List[str] = Field(default_factory=list, description="Supporting evidence IDs")
    verified: bool = Field(default=False, description="True if proven via execution result")


class DependencyDetails(BaseModel):
    """Section 1: Detailed metadata and declaration context for a dependency."""
    model_config = ConfigDict(extra="ignore")

    distribution_name: str = Field(..., description="PyPI package distribution name")
    manifest_path: str = Field(..., description="Repository-relative manifest path")
    declared_specifier: str = Field(..., description="Declared version constraint")
    resolved_version: Optional[str] = Field(default=None, description="Locked/resolved version if available")
    package_manager: str = Field(default="pip", description="Manifest format: pip, poetry, uv, pipfile")
    dependency_type: str = Field(default="direct", description="'direct', 'transitive', or 'unknown'")
    runtime_markers: Optional[str] = Field(default=None, description="PEP 508 environment markers")
    metadata_availability: str = Field(default="available", description="Metadata retrieval status")


class CapsuleDependencyRecord(BaseModel):
    """A flagged dependency record containing all nine required capsule sections."""
    model_config = ConfigDict(extra="ignore")

    dependency_id: str = Field(..., description="Unique dependency identifier, e.g. dep-001")

    # The 9 mandatory sections:
    dependency_details: DependencyDetails
    risk_indicators: List[RiskIndicator] = Field(default_factory=list)
    usage_locations: List[UsageLocation] = Field(default_factory=list)
    proposed_replacement: ProposedReplacement
    migration_steps: List[MigrationStep] = Field(default_factory=list)
    suggested_tests: List[SuggestedTest] = Field(default_factory=list)
    executed_test_results: List[ExecutedTestResult] = Field(default_factory=list)
    compatibility_gaps: List[CompatibilityGap] = Field(default_factory=list)
    open_concerns_limitations: List[str] = Field(default_factory=list)

    evidence_refs: List[str] = Field(default_factory=list)


class ToolInfo(BaseModel):
    """Analysis engine identity."""
    model_config = ConfigDict(extra="ignore")

    name: str = Field(default="ExitLens")
    version: str = Field(default="0.1.0")


class RepositoryScope(BaseModel):
    """Target repository scope and environment metadata."""
    model_config = ConfigDict(extra="ignore")

    source: str = Field(..., description="Original repository input path or URL")
    revision: Optional[str] = Field(default=None, description="Git commit hash if available")
    python_version: str = Field(..., description="Target runtime Python version")
    analysis_scope: str = Field(default="all_discovered", description="Scanned paths and exclusions")


class CapsuleSummary(BaseModel):
    """High-level metrics summarizing the analysis and verification run."""
    model_config = ConfigDict(extra="ignore")

    dependencies_discovered: int = 0
    dependencies_flagged: int = 0
    recommendations_available: int = 0
    baseline_checks: int = 0
    replacement_checks: int = 0
    checks_passed: int = 0
    checks_failed: int = 0
    checks_skipped_or_unverified: int = 0


DEFAULT_PROVENANCE_LEGEND: Dict[str, str] = {
    "OBSERVED": "Read from repository manifests, source files, or local metadata",
    "INFERRED": "Deterministic rule-based deduction backed by evidence references",
    "AI_RECOMMENDATION": "Proposed by local Gemma 4; not execution proof",
    "EXECUTION_RESULT": "Recorded outcome from an actual allow-listed command run",
    "NOT_VERIFIED": "Available evidence cannot confirm the claim",
}


class DependencyExitCapsule(BaseModel):
    """The canonical, exportable Dependency Exit Capsule deliverable."""
    model_config = ConfigDict(extra="ignore")

    schema_version: str = Field(default="1.0.0")
    capsule_id: str = Field(..., description="Stable capsule UUID")
    analysis_id: str = Field(..., description="Parent analysis UUID")
    generated_at_utc: str = Field(..., description="UTC ISO-8601 generation timestamp")
    tool: ToolInfo = Field(default_factory=ToolInfo)
    repository: RepositoryScope
    summary: CapsuleSummary = Field(default_factory=CapsuleSummary)
    dependencies: List[CapsuleDependencyRecord] = Field(
        default_factory=list,
        description="Records for every flagged dependency containing all 9 sections",
    )
    ai_provenance: AiProvenance
    provenance_legend: Dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_PROVENANCE_LEGEND))
    evidence: List[EvidenceRecord] = Field(default_factory=list)
    known_limitations: List[str] = Field(default_factory=list)
