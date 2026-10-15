"""Unit tests validating core domain Pydantic schemas."""

import json
import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.capsule import (
    CapsuleDependencyRecord,
    CapsuleSummary,
    CompatibilityGap,
    DependencyDetails,
    DependencyExitCapsule,
    RepositoryScope,
    ToolInfo,
    UsageLocation,
)
from app.schemas.common import AnalysisStatus, ProvenanceKind
from app.schemas.evidence import EvidenceRecord
from app.schemas.recommendation import (
    AiProvenance,
    MigrationStep,
    ProposedReplacement,
    SuggestedTest,
)
from app.schemas.repository import (
    AnalysisOptions,
    CreateAnalysisRequest,
    CreateAnalysisResponse,
    RepositoryInput,
    RepositoryKind,
)
from app.schemas.risk import RiskIndicator, RiskSeverity
from app.schemas.verification import ExecutedTestResult, TestStatus, VerificationRecord


def test_repository_input_and_options():
    """Verify repository input and options schemas."""
    repo = RepositoryInput(
        kind=RepositoryKind.LOCAL_PATH,
        value="C:/work/LinkWatch",
    )
    assert repo.kind == RepositoryKind.LOCAL_PATH
    assert repo.value == "C:/work/LinkWatch"

    opts = AnalysisOptions(
        include_tests=True,
        use_git_history=False,
    )
    assert ".venv" in opts.exclude_paths
    assert opts.include_tests is True
    assert opts.use_git_history is False

    req = CreateAnalysisRequest(repository=repo, options=opts)
    assert req.repository.value == "C:/work/LinkWatch"

    resp = CreateAnalysisResponse(
        analysis_id="123e4567-e89b-12d3-a456-426614174000",
        created_at="2026-10-15T12:00:00Z",
    )
    assert resp.status == AnalysisStatus.QUEUED
    assert resp.stage == AnalysisStatus.VALIDATING_REPOSITORY


def test_evidence_record_validation():
    """Verify EvidenceRecord enforces repository-relative paths and provenance."""
    ev = EvidenceRecord(
        evidence_id="ev-000101",
        kind="manifest_declaration",
        provenance=ProvenanceKind.OBSERVED,
        path="requirements.txt",
        line_start=15,
        line_end=15,
        excerpt="urllib3==1.26.5",
        sha256="abc123def456",
        observed_at_utc="2026-10-15T12:00:00Z",
    )
    assert ev.provenance == ProvenanceKind.OBSERVED
    assert ev.line_start == 15

    # Verify JSON serialization round-trip
    dumped = ev.model_dump_json()
    reloaded = EvidenceRecord.model_validate_json(dumped)
    assert reloaded.evidence_id == ev.evidence_id


def test_risk_indicator_validation():
    """Verify RiskIndicator severity tiers and evidence references."""
    risk = RiskIndicator(
        rule_id="UNPINNED_OR_WIDE_CONSTRAINT",
        severity=RiskSeverity.HIGH,
        title="Unpinned dependency constraint",
        explanation="requests>=2.0.0 allows potentially breaking major/minor drift.",
        signal_source="manifest",
        evidence_refs=["ev-000101"],
        confidence="high",
        limitations="Does not inspect remote index.",
    )
    assert risk.severity == RiskSeverity.HIGH
    assert risk.provenance == ProvenanceKind.INFERRED
    assert len(risk.evidence_refs) == 1



def test_verification_result_statuses():
    """Verify test statuses: PASSED, FAILED, ERROR, TIMED_OUT, SKIPPED, NOT_RUN."""
    res = ExecutedTestResult(
        check_id="chk-001",
        run_kind="baseline",
        status=TestStatus.PASSED,
        profile_id="pytest-default",
        argv=["pytest", "tests/"],
        exit_code=0,
        duration_seconds=1.23,
    )
    assert res.status == TestStatus.PASSED

    res_skipped = ExecutedTestResult(
        check_id="chk-002",
        run_kind="replacement",
        status=TestStatus.SKIPPED,
        profile_id="pytest-default",
        argv=["pytest", "tests/"],
        skip_or_error_reason="Replacement package not cached locally and network disabled.",
    )
    assert res_skipped.status == TestStatus.SKIPPED
    assert res_skipped.skip_or_error_reason is not None


def test_complete_dependency_exit_capsule_schema():
    """Verify the 9 mandatory sections on every flagged dependency record."""
    dep = CapsuleDependencyRecord(
        dependency_id="dep-001",
        dependency_details=DependencyDetails(
            distribution_name="urllib3",
            manifest_path="requirements.txt",
            declared_specifier="==1.26.5",
            package_manager="pip",
            dependency_type="direct",
        ),
        risk_indicators=[
            RiskIndicator(
                rule_id="DEPRECATED_OR_STALE_METADATA",
                severity=RiskSeverity.MEDIUM,
                title="Stale major version",
                explanation="urllib3 v1 branch has limited ongoing maintenance.",
                signal_source="metadata",
            )
        ],
        usage_locations=[
            UsageLocation(
                usage_id="usg-001",
                path="src/client.py",
                line_start=5,
                line_end=5,
                import_statement="import urllib3",
                evidence_id="ev-000101",
            )
        ],
        proposed_replacement=ProposedReplacement(
            status="proposed",
            distribution_name="urllib3",
            specifier=">=2.2.0",
            rationale="Upgrade to maintained v2 branch.",
            candidate_validation_status="NOT_VERIFIED",
        ),
        migration_steps=[
            MigrationStep(
                step_number=1,
                action="Update requirements",
                description="Bump constraint in requirements.txt",
                target_file="requirements.txt",
            )
        ],
        suggested_tests=[
            SuggestedTest(
                test_id="tst-001",
                objective="Verify HTTP connection pool behavior",
                relation_to_usage="client.py connection creation",
                suggested_profile="pytest-unit",
                expected_signal="All test suite passes",
            )
        ],
        executed_test_results=[
            ExecutedTestResult(
                check_id="chk-001",
                run_kind="baseline",
                status=TestStatus.PASSED,
                profile_id="pytest-unit",
                argv=["pytest", "tests/unit/test_client.py"],
                exit_code=0,
            )
        ],
        compatibility_gaps=[
            CompatibilityGap(
                gap_id="gap-001",
                title="OpenSSL 1.1.1+ requirement",
                description="urllib3 v2 requires OpenSSL 1.1.1 or later.",
                verified=False,
            )
        ],
        open_concerns_limitations=[
            "Replacement tests in disposable copy were not executed.",
        ],
        evidence_refs=["ev-000101"],
    )

    capsule = DependencyExitCapsule(
        capsule_id="999e4567-e89b-12d3-a456-426614174999",
        analysis_id="123e4567-e89b-12d3-a456-426614174000",
        generated_at_utc="2026-10-15T12:00:00Z",
        tool=ToolInfo(),
        repository=RepositoryScope(
            source="C:/work/LinkWatch",
            python_version="3.13.7",
            analysis_scope="full",
        ),
        summary=CapsuleSummary(
            dependencies_discovered=10,
            dependencies_flagged=1,
            recommendations_available=1,
            baseline_checks=1,
            checks_passed=1,
        ),
        dependencies=[dep],
        ai_provenance=AiProvenance(
            model_id="gemma4:latest",
        ),
        evidence=[],
        known_limitations=["Local test environment only"],
    )

    # Validate all 9 sections exist on the dependency record
    assert dep.dependency_details.distribution_name == "urllib3"
    assert len(dep.risk_indicators) == 1
    assert len(dep.usage_locations) == 1
    assert dep.proposed_replacement.status == "proposed"
    assert len(dep.migration_steps) == 1
    assert len(dep.suggested_tests) == 1
    assert len(dep.executed_test_results) == 1
    assert len(dep.compatibility_gaps) == 1
    assert len(dep.open_concerns_limitations) == 1

    # Round trip JSON serialization
    capsule_json = capsule.model_dump_json()
    reloaded_capsule = DependencyExitCapsule.model_validate_json(capsule_json)
    assert reloaded_capsule.capsule_id == capsule.capsule_id
    assert len(reloaded_capsule.dependencies) == 1
    assert reloaded_capsule.dependencies[0].dependency_id == "dep-001"
