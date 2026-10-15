"""Verification run and executed test result models."""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TestStatus(str, Enum):
    """Explicit verification test outcome statuses."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    ERROR = "ERROR"
    TIMED_OUT = "TIMED_OUT"
    SKIPPED = "SKIPPED"
    NOT_RUN = "NOT_RUN"


# Prevent pytest from attempting to collect the enum as a test case class
TestStatus.__test__ = False


class ExecutedTestResult(BaseModel):
    """Execution record of an allow-listed test check in an isolated workspace."""
    model_config = ConfigDict(extra="ignore")

    check_id: str = Field(..., description="Unique check execution identifier")
    run_kind: str = Field(..., description="'baseline' or 'replacement'")
    status: TestStatus = Field(..., description="Observed outcome status")
    profile_id: str = Field(..., description="Approved profile ID (e.g. pytest-detected)")
    argv: List[str] = Field(..., description="Exact command line argv executed")
    started_at_utc: Optional[str] = Field(default=None, description="Start timestamp UTC ISO-8601")
    completed_at_utc: Optional[str] = Field(default=None, description="End timestamp UTC ISO-8601")
    duration_seconds: Optional[float] = Field(default=None, description="Execution duration")
    exit_code: Optional[int] = Field(default=None, description="Process exit code")
    runtime_environment: Dict[str, str] = Field(
        default_factory=dict,
        description="Safe runtime information (Python version, OS; no private envs)",
    )
    stdout_excerpt: Optional[str] = Field(default=None, description="Bounded stdout snippet")
    stderr_excerpt: Optional[str] = Field(default=None, description="Bounded stderr snippet")
    output_truncated: bool = Field(default=False, description="True if output exceeded limit")
    patch_id: Optional[str] = Field(default=None, description="Applied patch identifier if replacement run")
    skip_or_error_reason: Optional[str] = Field(
        default=None,
        description="Explicit explanation when test is SKIPPED, ERROR, or NOT_RUN",
    )
    evidence_id: Optional[str] = Field(
        default=None,
        description="Evidence ID linking this execution to the run ledger",
    )


class VerificationRequest(BaseModel):
    """Request payload to trigger human-approved verification."""
    model_config = ConfigDict(extra="ignore")

    dependency_ids: List[str] = Field(..., min_length=1)
    baseline_profile_id: str = Field(..., description="Detected allow-listed baseline test profile")
    replacement_profile_id: Optional[str] = Field(
        default=None,
        description="Profile to execute in disposable copy with candidate patch",
    )
    confirm_repository_code_execution: bool = Field(
        default=True,
        description="Explicit user acknowledgement permitting test execution in isolated copy",
    )
    allow_network: bool = Field(default=False, description="Whether network access is permitted")
    timeout_seconds: int = Field(default=90, ge=1, le=180, description="Process timeout limit")


class VerificationRecord(BaseModel):
    """Persisted record of a verification session."""
    model_config = ConfigDict(extra="ignore")

    verification_id: str = Field(..., description="Unique verification identifier")
    analysis_id: str = Field(..., description="Parent analysis UUID")
    dependency_ids: List[str] = Field(..., description="Dependencies under test")
    baseline_profile_id: str
    replacement_profile_id: Optional[str] = None
    results: List[ExecutedTestResult] = Field(default_factory=list)
    created_at_utc: str
