"""Unit tests for analysis lifecycle states, transitions, and service operations."""

from pathlib import Path
import pytest

from app.core.config import Settings
from app.core.errors import NotFoundError, PathSafetyError, ValidationError
from app.core.ids import generate_uuid
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
from app.schemas.repository import (
    AnalysisOptions,
    CreateAnalysisRequest,
    RepositoryInput,
    RepositoryKind,
)
from app.schemas.verification import ExecutedTestResult, TestStatus, VerificationRecord
from app.services.analysis_service import AnalysisService
from app.storage.run_store import FileSystemRunStore


ALL_11_STAGES = [
    AnalysisStatus.QUEUED,
    AnalysisStatus.VALIDATING_REPOSITORY,
    AnalysisStatus.SCANNING,
    AnalysisStatus.MAPPING_USAGE,
    AnalysisStatus.ASSESSING_RISK,
    AnalysisStatus.GENERATING_RECOMMENDATIONS,
    AnalysisStatus.READY_FOR_VERIFICATION,
    AnalysisStatus.VERIFYING,
    AnalysisStatus.COMPLETED,
    AnalysisStatus.COMPLETED_WITH_WARNINGS,
    AnalysisStatus.FAILED,
]


def test_all_11_lifecycle_stages_supported(temp_dir: Path):
    """Verify all 11 lifecycle stages can be transitioned through and persisted."""
    repo_dir = temp_dir / "target_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
    )
    service = AnalysisService(settings=settings)

    # Initial creation
    record = service.create_analysis(
        CreateAnalysisRequest(
            repository=RepositoryInput(kind=RepositoryKind.LOCAL_PATH, value=str(repo_dir)),
        )
    )
    analysis_id = record.analysis_id
    assert record.status == AnalysisStatus.QUEUED
    assert record.stage == AnalysisStatus.VALIDATING_REPOSITORY

    # Cycle through all stages
    percent = 10
    for stage in ALL_11_STAGES:
        updated = service.update_stage(
            analysis_id=analysis_id,
            stage=stage,
            progress_percent=percent,
            message=f"Testing stage {stage.value}",
        )
        assert updated.stage == stage
        assert updated.progress.percent == percent
        assert updated.progress.message == f"Testing stage {stage.value}"
        percent = min(100, percent + 8)

        # Reload directly from disk to confirm stage transition persistence
        reloaded = service.get_analysis(analysis_id)
        assert reloaded.stage == stage


def test_repository_input_safety_checks(temp_dir: Path):
    """Verify repository path safety and Git URL constraints."""
    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir / "allowed")],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
    )
    service = AnalysisService(settings=settings)

    # 1. Reject path outside allowed roots
    outside_repo = temp_dir / "outside"
    outside_repo.mkdir(parents=True, exist_ok=True)
    with pytest.raises(PathSafetyError):
        service.create_analysis(
            CreateAnalysisRequest(
                repository=RepositoryInput(kind=RepositoryKind.LOCAL_PATH, value=str(outside_repo))
            )
        )

    # 2. Reject non-https Git URL
    with pytest.raises((ValidationError, PathSafetyError)) as exc:
        service.create_analysis(
            CreateAnalysisRequest(
                repository=RepositoryInput(kind=RepositoryKind.GIT_URL, value="http://insecure.git/repo")
            )
        )
    assert "Only public HTTPS" in str(exc.value)

    # 3. Reject embedded credentials in Git URL
    with pytest.raises((ValidationError, PathSafetyError)) as exc:
        service.create_analysis(
            CreateAnalysisRequest(
                repository=RepositoryInput(kind=RepositoryKind.GIT_URL, value="https://token:pass@github.com/repo.git")
            )
        )
    assert "Embedded credentials" in str(exc.value)


def test_warning_and_error_handling(temp_dir: Path):
    """Verify warnings accumulate without duplication and errors transition to failed."""
    repo_dir = temp_dir / "target_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
    )
    service = AnalysisService(settings=settings)

    record = service.create_analysis(
        CreateAnalysisRequest(
            repository=RepositoryInput(kind=RepositoryKind.LOCAL_PATH, value=str(repo_dir)),
        )
    )
    a_id = record.analysis_id

    # Add warning
    service.record_warning(a_id, "Unsupported directive in requirements: -c constraints.txt")
    # Duplicate warning is ignored
    service.record_warning(a_id, "Unsupported directive in requirements: -c constraints.txt")

    reloaded = service.get_analysis(a_id)
    assert len(reloaded.warnings) == 1
    assert "Unsupported directive" in reloaded.warnings[0]

    # Record error transitions to FAILED
    failed_record = service.record_error(a_id, "Local Ollama service died during generation.")
    assert failed_record.status == AnalysisStatus.FAILED
    assert failed_record.stage == AnalysisStatus.FAILED
    assert len(failed_record.errors) == 1
    assert failed_record.completed_at_utc is not None


def test_full_persistence_and_reload_roundtrip(temp_dir: Path):
    """Test creating run, adding evidence, capsule, verification, and reloading with fresh service."""
    repo_dir = temp_dir / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
    )

    # 1. Instance 1 writes all records
    service1 = AnalysisService(settings=settings)
    analysis = service1.create_analysis(
        CreateAnalysisRequest(
            repository=RepositoryInput(kind=RepositoryKind.LOCAL_PATH, value=str(repo_dir)),
        )
    )
    a_id = analysis.analysis_id

    # Advance stage
    service1.update_stage(a_id, AnalysisStatus.SCANNING, 30, "Scanning manifests")

    # Add Evidence
    ev_list = [
        EvidenceRecord(
            evidence_id="ev-0001",
            kind="manifest_declaration",
            provenance=ProvenanceKind.OBSERVED,
            path="requirements.txt",
            observed_at_utc="2026-10-15T12:00:00Z",
        )
    ]
    service1.save_evidence(a_id, ev_list)

    # Add Capsule
    capsule = DependencyExitCapsule(
        capsule_id=generate_uuid(),
        analysis_id=a_id,
        generated_at_utc="2026-10-15T12:05:00Z",
        repository=RepositoryScope(source=str(repo_dir), python_version="3.13.7", analysis_scope="full"),
        summary=CapsuleSummary(dependencies_discovered=5, dependencies_flagged=1),
        dependencies=[
            CapsuleDependencyRecord(
                dependency_id="dep-1",
                dependency_details=DependencyDetails(
                    distribution_name="urllib3",
                    manifest_path="requirements.txt",
                    declared_specifier="<2.0.0",
                ),
                proposed_replacement=ProposedReplacement(
                    status="proposed",
                    distribution_name="urllib3",
                    specifier=">=2.0.0",
                    rationale="Bump to supported version.",
                ),
            )
        ],
        ai_provenance=AiProvenance(model_id="gemma4"),
    )
    service1.save_capsule(capsule)

    # Add Verification
    verif = VerificationRecord(
        verification_id="verif-roundtrip-01",
        analysis_id=a_id,
        dependency_ids=["dep-1"],
        baseline_profile_id="pytest-default",
        results=[
            ExecutedTestResult(
                check_id="chk-1",
                run_kind="baseline",
                status=TestStatus.PASSED,
                profile_id="pytest-default",
                argv=["pytest"],
                exit_code=0,
            )
        ],
        created_at_utc="2026-10-15T12:10:00Z",
    )
    service1.save_verification(verif)

    # 2. Instance 2 created completely independently reading the same directory
    service2 = AnalysisService(settings=settings)

    # Verify analysis state
    reloaded_analysis = service2.get_analysis(a_id)
    assert reloaded_analysis.analysis_id == a_id
    assert reloaded_analysis.stage == AnalysisStatus.SCANNING
    assert reloaded_analysis.artifacts.has_analysis_json is True
    assert reloaded_analysis.artifacts.has_evidence_json is True
    assert reloaded_analysis.artifacts.has_capsule_json is True
    assert reloaded_analysis.artifacts.has_capsule_md is True
    assert reloaded_analysis.artifacts.verification_count == 1

    # Verify evidence
    reloaded_ev = service2.get_evidence(a_id)
    assert len(reloaded_ev) == 1
    assert reloaded_ev[0].evidence_id == "ev-0001"

    # Verify capsule JSON and Markdown
    reloaded_capsule = service2.get_capsule(a_id)
    assert reloaded_capsule.capsule_id == capsule.capsule_id
    assert len(reloaded_capsule.dependencies) == 1

    capsule_md = service2.get_capsule_markdown(a_id)
    assert "Dependency Exit Capsule" in capsule_md
    assert "urllib3" in capsule_md

    # Verify verification record
    reloaded_v = service2.get_verification(a_id, "verif-roundtrip-01")
    assert reloaded_v.verification_id == "verif-roundtrip-01"
    assert len(reloaded_v.results) == 1
    assert reloaded_v.results[0].status == TestStatus.PASSED

    # Verify listing
    all_runs = service2.list_analyses()
    assert len(all_runs) >= 1
    assert any(r.analysis_id == a_id for r in all_runs)
