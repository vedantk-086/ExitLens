"""Unit tests for safe filesystem storage and run store."""

import json
from pathlib import Path
import pytest

from app.core.errors import PathTraversalDetectedError, ValidationError
from app.core.ids import generate_uuid
from app.schemas.analysis import AnalysisRecord, ProgressSummary
from app.schemas.capsule import (
    CapsuleDependencyRecord,
    CapsuleSummary,
    DependencyDetails,
    DependencyExitCapsule,
    RepositoryScope,
)
from app.schemas.common import AnalysisStatus, ProvenanceKind
from app.schemas.evidence import EvidenceRecord
from app.schemas.recommendation import AiProvenance, ProposedReplacement
from app.schemas.repository import AnalysisOptions, RepositoryInput, RepositoryKind
from app.schemas.verification import ExecutedTestResult, TestStatus, VerificationRecord
from app.storage.run_store import FileSystemRunStore, redact_sensitive_string, sanitize_dict_for_storage


def test_uuid_validation_enforced(temp_dir: Path):
    """Storage must accept valid UUID4 strings and reject arbitrary or traversal IDs."""
    store = FileSystemRunStore(base_data_dir=temp_dir)
    valid_uuid = generate_uuid()

    # Valid UUID4 accepted
    assert store.validate_analysis_id(valid_uuid) == valid_uuid

    # Non-UUID rejected
    with pytest.raises(ValidationError) as exc:
        store.validate_analysis_id("arbitrary-run-id-123")
    assert "must be valid UUID4 strings" in str(exc.value)

    # Traversal characters rejected
    with pytest.raises(PathTraversalDetectedError):
        store.validate_analysis_id("../../etc/passwd")

    with pytest.raises(PathTraversalDetectedError):
        store.validate_analysis_id(f"..\\..\\{valid_uuid}")


def test_atomic_writes_and_layout(temp_dir: Path):
    """Verify filesystem layout and atomic persistence for all 5 artifact types."""
    store = FileSystemRunStore(base_data_dir=temp_dir)
    analysis_id = generate_uuid()

    # 1. analysis.json
    analysis = AnalysisRecord(
        analysis_id=analysis_id,
        status=AnalysisStatus.SCANNING,
        stage=AnalysisStatus.SCANNING,
        created_at_utc="2026-10-15T12:00:00Z",
        updated_at_utc="2026-10-15T12:00:05Z",
        repository=RepositoryInput(kind=RepositoryKind.LOCAL_PATH, value="C:/test/repo"),
        options=AnalysisOptions(),
        progress=ProgressSummary(stage=AnalysisStatus.SCANNING, percent=25),
    )
    analysis_path = store.save_analysis(analysis)
    assert analysis_path.is_file()
    assert analysis_path.name == "analysis.json"
    reloaded_analysis = store.load_analysis(analysis_id)
    assert reloaded_analysis is not None
    assert reloaded_analysis.status == AnalysisStatus.SCANNING

    # 2. evidence.json
    evidence = [
        EvidenceRecord(
            evidence_id="ev-000001",
            kind="manifest_declaration",
            provenance=ProvenanceKind.OBSERVED,
            path="requirements.txt",
            line_start=1,
            line_end=1,
            excerpt="requests>=2.25.0",
            observed_at_utc="2026-10-15T12:00:00Z",
        )
    ]
    evidence_path = store.save_evidence(analysis_id, evidence)
    assert evidence_path.is_file()
    assert evidence_path.name == "evidence.json"
    reloaded_evidence = store.load_evidence(analysis_id)
    assert reloaded_evidence is not None
    assert len(reloaded_evidence) == 1
    assert reloaded_evidence[0].evidence_id == "ev-000001"

    # 3. capsule.json & capsule.md
    capsule = DependencyExitCapsule(
        capsule_id=generate_uuid(),
        analysis_id=analysis_id,
        generated_at_utc="2026-10-15T12:00:10Z",
        repository=RepositoryScope(source="C:/test/repo", python_version="3.13.7", analysis_scope="full"),
        summary=CapsuleSummary(dependencies_discovered=1, dependencies_flagged=1),
        dependencies=[
            CapsuleDependencyRecord(
                dependency_id="dep-1",
                dependency_details=DependencyDetails(
                    distribution_name="requests",
                    manifest_path="requirements.txt",
                    declared_specifier=">=2.25.0",
                ),
                proposed_replacement=ProposedReplacement(
                    status="proposed",
                    distribution_name="httpx",
                    rationale="Modern async alternative.",
                ),
            )
        ],
        ai_provenance=AiProvenance(model_id="gemma4:latest"),
    )
    json_path, md_path = store.save_capsule(capsule)
    assert json_path.is_file()
    assert json_path.name == "capsule.json"
    assert md_path.is_file()
    assert md_path.name == "capsule.md"

    reloaded_capsule = store.load_capsule(analysis_id)
    assert reloaded_capsule is not None
    assert reloaded_capsule.capsule_id == capsule.capsule_id

    md_content = store.load_capsule_md(analysis_id)
    assert md_content is not None
    assert "Dependency Exit Capsule" in md_content

    # 4. verification/<verification_id>.json
    v_id = "verif-test-01"
    verification = VerificationRecord(
        verification_id=v_id,
        analysis_id=analysis_id,
        dependency_ids=["dep-1"],
        baseline_profile_id="pytest-unit",
        results=[
            ExecutedTestResult(
                check_id="chk-01",
                run_kind="baseline",
                status=TestStatus.PASSED,
                profile_id="pytest-unit",
                argv=["pytest"],
                exit_code=0,
            )
        ],
        created_at_utc="2026-10-15T12:00:15Z",
    )
    v_path = store.save_verification(verification)
    assert v_path.is_file()
    assert v_path.name == f"{v_id}.json"
    assert v_path.parent.name == "verification"

    reloaded_v = store.load_verification(analysis_id, v_id)
    assert reloaded_v is not None
    assert reloaded_v.verification_id == v_id

    # Verify run layout on disk
    expected_run_dir = temp_dir / "runs" / analysis_id
    assert (expected_run_dir / "analysis.json").exists()
    assert (expected_run_dir / "evidence.json").exists()
    assert (expected_run_dir / "capsule.json").exists()
    assert (expected_run_dir / "capsule.md").exists()
    assert (expected_run_dir / "verification" / f"{v_id}.json").exists()


def test_secret_redaction_before_persistence(temp_dir: Path):
    """Storage must scrub passwords, tokens, and sensitive excerpts before writing."""
    raw_text = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secretpayload token: my_secret_token_12345678"
    redacted = redact_sensitive_string(raw_text)
    assert "my_secret_token_12345678" not in redacted
    assert "[REDACTED]" in redacted

    data_with_secret = {
        "user": "developer",
        "api_key": "super_secret_api_key_12345",
        "nested": {
            "password": "confidential_password",
            "message": "connect with token=token_val_123456789",
        },
    }
    sanitized = sanitize_dict_for_storage(data_with_secret)
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["password"] == "[REDACTED]"
    assert "token_val_123456789" not in sanitized["nested"]["message"]


def test_evidence_relative_path_enforcement(temp_dir: Path):
    """Evidence storage normalizes any absolute paths to relative paths."""
    store = FileSystemRunStore(base_data_dir=temp_dir)
    analysis_id = generate_uuid()

    evidence = [
        EvidenceRecord(
            evidence_id="ev-000002",
            kind="manifest_declaration",
            provenance=ProvenanceKind.OBSERVED,
            path="C:/Users/test/LinkWatch/requirements.txt",
            observed_at_utc="2026-10-15T12:00:00Z",
        )
    ]
    store.save_evidence(analysis_id, evidence)
    reloaded = store.load_evidence(analysis_id)
    assert reloaded is not None
    # Path is relativized, not absolute drive
    assert not reloaded[0].path.startswith("C:")
    assert not reloaded[0].path.startswith("/")
