"""Evidence record models for ExitLens."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ProvenanceKind


class EvidenceRecord(BaseModel):
    """An atomic, immutable piece of observed repository or run evidence."""
    model_config = ConfigDict(extra="ignore")

    evidence_id: str = Field(..., description="Stable per-run evidence identifier, e.g. ev-000123")
    kind: str = Field(
        ...,
        description="Type of evidence: manifest_declaration, ast_import, lockfile_entry, test_usage, etc.",
    )
    provenance: ProvenanceKind = Field(
        default=ProvenanceKind.OBSERVED,
        description="Source classification: OBSERVED, INFERRED, AI_RECOMMENDATION, etc.",
    )
    path: str = Field(..., description="Repository-relative file path with forward slashes")
    line_start: Optional[int] = Field(default=None, description="Starting line reference (1-indexed)")
    line_end: Optional[int] = Field(default=None, description="Ending line reference (1-indexed)")
    excerpt: Optional[str] = Field(default=None, description="Sanitized, bounded content snippet")
    sha256: Optional[str] = Field(default=None, description="SHA-256 hash of the source file or excerpt")
    observed_at_utc: str = Field(..., description="UTC ISO-8601 observation timestamp")


class EvidencePackage(BaseModel):
    """Collection of all evidence observed during an analysis run."""
    model_config = ConfigDict(extra="ignore")

    analysis_id: str = Field(..., description="Parent analysis UUID")
    items: List[EvidenceRecord] = Field(default_factory=list, description="All indexed evidence records")
