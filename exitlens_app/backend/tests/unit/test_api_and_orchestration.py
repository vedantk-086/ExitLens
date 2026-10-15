"""Integration and unit tests for ExitLens FastAPI API and orchestration layer.

Verifies:
1. Successful end-to-end orchestration pipeline (validate → scan → map → risk → recommendations → capsule).
2. Invalid repository path fails gracefully with proper error reporting.
3. Unknown analysis ID returns HTTP 404 with standard error envelope.
4. Invalid dependency ID returns HTTP 404.
5. Unavailable AI model preserves scan/risk findings and marks run completed_with_warnings.
6. Invalid verification request rejected (confirmation required, unauthorized profile).
7. Capsule download endpoints serve canonical JSON and Markdown deliverables.
8. Recommendations regeneration updates selected dependencies without re-scanning.
"""

from pathlib import Path
import sys
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.schemas.analysis import AnalysisRecord
from app.schemas.capsule import DependencyExitCapsule
from app.schemas.common import AnalysisStatus
from app.schemas.recommendation import CandidateStatus
from app.schemas.repository import (
    AnalysisOptions,
    CreateAnalysisRequest,
    RepositoryInput,
    RepositoryKind,
)
from app.services.analysis_service import AnalysisService
from app.services.orchestrator import OrchestrationService


@pytest.fixture
def test_repo(temp_dir: Path) -> Path:
    """Create a realistic repository for orchestration testing."""
    repo = temp_dir / "sample_service"
    repo.mkdir(parents=True, exist_ok=True)

    # Manifest with wide/unpinned dependency
    (repo / "requirements.txt").write_text(
        "requests>=2.0.0\nurllib3==1.26.15\n",
        encoding="utf-8",
    )
    # Pytest configuration
    (repo / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n", encoding="utf-8")

    # Source file with usage
    (repo / "client.py").write_text(
        "import requests\n\ndef fetch():\n    return requests.get('https://example.com')\n",
        encoding="utf-8",
    )

    # Test file
    tests_dir = repo / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test_client.py").write_text(
        "from client import fetch\n\ndef test_fetch():\n    assert callable(fetch)\n",
        encoding="utf-8",
    )
    return repo


# -----------------------------------------------------------------------------
# Test 1: Successful End-to-End Orchestration Flow
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_successful_end_to_end_orchestration_flow(test_repo: Path, temp_dir: Path):
    """Pipeline executes all 6 stages and produces canonical capsule and evidence."""
    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
        GEMMA_PROVIDER="test_fixture",
    )
    analysis_svc = AnalysisService(settings=settings)
    orchestrator = OrchestrationService(analysis_service=analysis_svc, settings=settings)

    # 1. Create analysis
    req = CreateAnalysisRequest(
        repository=RepositoryInput(kind=RepositoryKind.LOCAL_PATH, value=str(test_repo)),
        options=AnalysisOptions(generate_recommendations=True),
    )
    created = analysis_svc.create_analysis(req)
    assert created.status == AnalysisStatus.QUEUED

    # 2. Run pipeline
    completed = await orchestrator.run_pipeline(created.analysis_id)
    assert completed.status in (AnalysisStatus.COMPLETED, AnalysisStatus.COMPLETED_WITH_WARNINGS)
    assert completed.progress.percent == 100

    # 3. Verify artifacts exist and are non-empty
    evidence = analysis_svc.get_evidence(created.analysis_id)
    assert len(evidence) > 0

    capsule = analysis_svc.get_capsule(created.analysis_id)
    assert isinstance(capsule, DependencyExitCapsule)
    assert capsule.analysis_id == created.analysis_id
    assert capsule.summary.dependencies_discovered >= 2
    assert capsule.summary.dependencies_flagged >= 1

    # Verify Markdown export exists and has content
    md_content = analysis_svc.get_capsule_markdown(created.analysis_id)
    assert "# Dependency Exit Capsule" in md_content
    assert "Executive Summary" in md_content


# -----------------------------------------------------------------------------
# Test 2: Invalid Repository Path Fails Gracefully
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_repository_path_fails_gracefully(temp_dir: Path):
    """Pipeline rejects repository path outside allowed roots without crashing."""
    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir / "only_here")],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
    )
    analysis_svc = AnalysisService(settings=settings)
    orchestrator = OrchestrationService(analysis_service=analysis_svc, settings=settings)

    # Repository path outside allowed roots
    forbidden_repo = temp_dir / "forbidden_outside"
    forbidden_repo.mkdir(parents=True, exist_ok=True)

    with pytest.raises(Exception):
        req = CreateAnalysisRequest(
            repository=RepositoryInput(kind=RepositoryKind.LOCAL_PATH, value=str(forbidden_repo))
        )
        analysis_svc.create_analysis(req)


# -----------------------------------------------------------------------------
# Test 3: Unknown Analysis ID Returns 404
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_analysis_id_returns_404(async_client: AsyncClient):
    """All analysis endpoints return standard 404 when analysis ID is unknown."""
    unknown_id = "a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c8d"

    # GET /analyses/{id}
    resp = await async_client.get(f"/api/v1/analyses/{unknown_id}")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "NOT_FOUND"

    # GET /analyses/{id}/dependencies
    resp2 = await async_client.get(f"/api/v1/analyses/{unknown_id}/dependencies")
    assert resp2.status_code == 404

    # GET /analyses/{id}/capsule
    resp3 = await async_client.get(f"/api/v1/analyses/{unknown_id}/capsule?format=json")
    assert resp3.status_code == 404


# -----------------------------------------------------------------------------
# Test 4: Invalid Dependency ID Returns 404
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_dependency_id_returns_404(async_client: AsyncClient, test_repo: Path, temp_dir: Path):
    """GET /analyses/{id}/dependencies/{dep_id} returns 404 for non-existent dependency."""
    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
        GEMMA_PROVIDER="test_fixture",
    )
    analysis_svc = AnalysisService(settings=settings)
    orchestrator = OrchestrationService(analysis_service=analysis_svc, settings=settings)

    req = CreateAnalysisRequest(
        repository=RepositoryInput(kind=RepositoryKind.LOCAL_PATH, value=str(test_repo))
    )
    record = analysis_svc.create_analysis(req)
    await orchestrator.run_pipeline(record.analysis_id)

    # Request non-existent dependency ID
    resp = await async_client.get(f"/api/v1/analyses/{record.analysis_id}/dependencies/dep-nonexistent-999")
    assert resp.status_code == 404
    err_data = resp.json()
    assert err_data["error"]["code"] == "DEPENDENCY_NOT_FOUND"


# -----------------------------------------------------------------------------
# Test 5: Unavailable AI Model Preserves Scan & Completes With Warnings
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unavailable_model_preserves_scan_and_completes_with_warnings(test_repo: Path, temp_dir: Path):
    """When AI provider fails, scan and risk findings are preserved and run completes with warnings."""
    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
    )
    analysis_svc = AnalysisService(settings=settings)

    # Mock provider that fails with network or rate limit error
    mock_ai = AsyncMock()
    mock_ai.generate_migration_plan.side_effect = Exception("Google AI Studio quota exceeded / 429 Too Many Requests")

    orchestrator = OrchestrationService(
        analysis_service=analysis_svc,
        ai_provider=mock_ai,
        settings=settings,
    )

    req = CreateAnalysisRequest(
        repository=RepositoryInput(kind=RepositoryKind.LOCAL_PATH, value=str(test_repo)),
        options=AnalysisOptions(generate_recommendations=True),
    )
    record = analysis_svc.create_analysis(req)
    completed = await orchestrator.run_pipeline(record.analysis_id)

    # 1. State must transition to COMPLETED_WITH_WARNINGS
    assert completed.status == AnalysisStatus.COMPLETED_WITH_WARNINGS
    assert len(completed.warnings) > 0
    assert any("AI recommendation unavailable" in w for w in completed.warnings)

    # 2. Scanner evidence and capsule must still be fully generated and preserved
    capsule = analysis_svc.get_capsule(record.analysis_id)
    assert capsule is not None
    assert len(capsule.dependencies) >= 1

    # Flagged dependency must have honest unavailable status
    flagged = capsule.dependencies[0]
    assert flagged.proposed_replacement.status == CandidateStatus.UNAVAILABLE


# -----------------------------------------------------------------------------
# Test 6: Invalid Verification Requests Rejected
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_verification_request_rejected(async_client: AsyncClient, test_repo: Path, temp_dir: Path):
    """Verification rejects missing confirmation and unauthorized test profiles."""
    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
    )
    analysis_svc = AnalysisService(settings=settings)
    req = CreateAnalysisRequest(
        repository=RepositoryInput(kind=RepositoryKind.LOCAL_PATH, value=str(test_repo))
    )
    record = analysis_svc.create_analysis(req)

    # 1. Unconfirmed request rejected with 422
    unconfirmed = {
        "dependency_ids": ["dep-requests"],
        "baseline_profile_id": "pytest-default",
        "confirm_repository_code_execution": False,
    }
    resp = await async_client.post(
        f"/api/v1/analyses/{record.analysis_id}/verification",
        json=unconfirmed,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "CONFIRMATION_REQUIRED"

    # 2. Unauthorized profile rejected with 422
    malicious_profile = {
        "dependency_ids": ["dep-requests"],
        "baseline_profile_id": "rm -rf /; pytest",
        "confirm_repository_code_execution": True,
    }
    resp2 = await async_client.post(
        f"/api/v1/analyses/{record.analysis_id}/verification",
        json=malicious_profile,
    )
    assert resp2.status_code == 422
    assert "UNAUTHORIZED_TEST_PROFILE" in resp2.json()["error"]["code"]


# -----------------------------------------------------------------------------
# Test 7: Capsule Downloads in JSON and Markdown
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_capsule_downloads_json_and_markdown(async_client: AsyncClient, test_repo: Path, temp_dir: Path):
    """GET /analyses/{id}/capsule serves application/json and text/markdown deliverables."""
    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
        GEMMA_PROVIDER="test_fixture",
    )
    analysis_svc = AnalysisService(settings=settings)
    orchestrator = OrchestrationService(analysis_service=analysis_svc, settings=settings)

    req = CreateAnalysisRequest(
        repository=RepositoryInput(kind=RepositoryKind.LOCAL_PATH, value=str(test_repo))
    )
    record = analysis_svc.create_analysis(req)
    await orchestrator.run_pipeline(record.analysis_id)

    # 1. format=json
    resp_json = await async_client.get(f"/api/v1/analyses/{record.analysis_id}/capsule?format=json")
    assert resp_json.status_code == 200
    assert resp_json.headers["Content-Type"] == "application/json"
    capsule_dict = resp_json.json()
    assert capsule_dict["analysis_id"] == record.analysis_id
    assert "dependencies" in capsule_dict

    # 2. format=md
    resp_md = await async_client.get(f"/api/v1/analyses/{record.analysis_id}/capsule?format=md")
    assert resp_md.status_code == 200
    assert "text/markdown" in resp_md.headers["Content-Type"]
    assert "# Dependency Exit Capsule" in resp_md.text

    # 3. format=pdf
    resp_pdf = await async_client.get(f"/api/v1/analyses/{record.analysis_id}/capsule?format=pdf")
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["Content-Type"] == "application/pdf"
    assert len(resp_pdf.content) > 1000

    # 4. Invalid format query parameter rejected with 422
    resp_invalid = await async_client.get(f"/api/v1/analyses/{record.analysis_id}/capsule?format=invalid_fmt")
    assert resp_invalid.status_code == 422
    assert resp_invalid.json()["error"]["code"] == "INVALID_EXPORT_FORMAT"


# -----------------------------------------------------------------------------
# Test 8: Recommendations Regeneration Without Re-scan
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recommendations_regeneration_without_rescan(async_client: AsyncClient, test_repo: Path, temp_dir: Path):
    """POST /analyses/{id}/recommendations updates only selected dependency IDs."""
    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
        GEMMA_PROVIDER="test_fixture",
    )
    analysis_svc = AnalysisService(settings=settings)
    orchestrator = OrchestrationService(analysis_service=analysis_svc, settings=settings)

    req = CreateAnalysisRequest(
        repository=RepositoryInput(kind=RepositoryKind.LOCAL_PATH, value=str(test_repo))
    )
    record = analysis_svc.create_analysis(req)
    await orchestrator.run_pipeline(record.analysis_id)

    capsule = analysis_svc.get_capsule(record.analysis_id)
    assert len(capsule.dependencies) >= 1
    target_dep_id = capsule.dependencies[0].dependency_id

    # Trigger regeneration for this dependency
    regen_payload = {
        "dependency_ids": [target_dep_id],
        "force_regenerate": True,
    }
    resp = await async_client.post(
        f"/api/v1/analyses/{record.analysis_id}/recommendations",
        json=regen_payload,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["analysis_id"] == record.analysis_id
    assert data["regenerated_count"] == 1
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["dependency_id"] == target_dep_id
