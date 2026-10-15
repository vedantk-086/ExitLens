"""Internal data models for scanner discovery and results."""

from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.capsule import DependencyDetails, UsageLocation
from app.schemas.evidence import EvidenceRecord


class DiscoveredFile(BaseModel):
    """Metadata for a scanned file within the repository."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    absolute_path: Path
    relative_path: str
    size_bytes: int
    is_manifest: bool = False
    is_python: bool = False
    is_test: bool = False


class WalkSummary(BaseModel):
    """Results from bounded repository filesystem traversal."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    manifest_files: List[DiscoveredFile] = Field(default_factory=list)
    python_files: List[DiscoveredFile] = Field(default_factory=list)
    scanned_file_count: int = 0
    scanned_byte_count: int = 0
    warnings: List[str] = Field(default_factory=list)


class ScanResult(BaseModel):
    """Aggregate output of manifest scanning and usage mapping."""
    model_config = ConfigDict(extra="ignore")

    dependencies: List[DependencyDetails] = Field(default_factory=list)
    usages: List[UsageLocation] = Field(default_factory=list)
    evidence: List[EvidenceRecord] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    file_count: int = 0
    total_bytes: int = 0
