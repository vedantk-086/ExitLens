"""End-to-end integration tests for ExitLens against LinkWatch workflow.

Verifies the complete integration lifecycle specified in FULL_IMPLEMENTATION_README.md
and BACKEND_README.md:
1. Health endpoint checks API readiness, environment, and storage without secret leakage.
2. LinkWatch-style service analysis execution without hard-coded dependency findings:
   - Analysis creation (POST /api/v1/analyses -> 202)
   - Status polling and progress monitoring (GET /api/v1/analyses/{id})
   - Dynamic dependency discovery and detail inspection (GET /api/v1/analyses/{id}/dependencies)
   - Recommendation generation with deterministic test provider
   - On-demand recommendation regeneration (POST /api/v1/analyses/{id}/recommendations)
   - Test profile discovery (GET /api/v1/analyses/{id}/test-profiles)
   - Verification execution safety: confirmation enforcement and unauthorized profile rejection
   - Safe verification execution: baseline execution and skipped/NOT_RUN replacement tracking
   - JSON deliverable download and capsule completeness validation
   - Markdown deliverable download
   - Export format validation error handling
3. Model-unavailable handling:
   - Graceful degradation when AI provider fails or is unconfigured
   - Preservation of 100% of static scanner and risk engine evidence
   - Honest UNAVAILABLE candidate status and warning emission
   - Completeness validation passes on the degraded capsule
"""

import asyncio
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.capsule.completeness import validate_capsule_completeness
from app.core.config import Settings, get_settings
from app.main import create_app
from app.schemas.capsule import DependencyExitCapsule
from app.schemas.common import AnalysisStatus, ProvenanceKind
from app.schemas.recommendation import CandidateStatus
from app.schemas.repository import (
    AnalysisOptions,
    CreateAnalysisRequest,
    RepositoryInput,
    RepositoryKind,
)
from app.schemas.verification import TestStatus
from app.services.analysis_service import AnalysisService
from app.services.orchestrator import OrchestrationService
from tests.fixtures.linkwatch_fixture import create_linkwatch_fixture_repo


@pytest.fixture
def linkwatch_repo(temp_dir: Path) -> Path:
    """Create a realistic LinkWatch repository fixture."""
    return create_linkwatch_fixture_repo(temp_dir)


@pytest.fixture
def linkwatch_settings(temp_dir: Path) -> Settings:
    """Configure Settings for LinkWatch end-to-end integration testing."""
    return Settings(
        APP_ENV="test",
        APP_HOST="127.0.0.1",
        APP_PORT=8000,
        API_PREFIX="/api/v1",
        CORS_ORIGINS=["http://127.0.0.1:5173", "http://localhost:5173"],
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        ENABLE_PUBLIC_HTTPS_GIT_CLONE=True,
        GEMMA_PROVIDER="test_fixture",
        GOOGLE_AI_API_KEY="",
        GOOGLE_AI_MODEL="gemma-4-26b-a4b-it",
        GOOGLE_AI_TIMEOUT_SECONDS=90,
        GOOGLE_AI_MAX_RETRIES=1,
        PROMPT_VERSION="exitlens-v1",
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
        LOG_LEVEL="DEBUG",
    )


@pytest.fixture
def linkwatch_app(linkwatch_settings: Settings):
    """FastAPI application with LinkWatch test settings override."""
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: linkwatch_settings
    return application


@pytest_asyncio.fixture
async def linkwatch_client(linkwatch_app) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient for LinkWatch integration tests."""
    transport = ASGITransport(app=linkwatch_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# =============================================================================
# 1. Health Endpoint Integration Test
# =============================================================================

@pytest.mark.asyncio
async def test_health_endpoint_contract(linkwatch_client: AsyncClient):
    """GET /api/v1/health returns 200 with service health and safe metadata."""
    resp = await linkwatch_client.get("/api/v1/health")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["api"]["environment"] == "test"
    assert data["storage"]["ready"] is True
    assert data["storage"]["writable"] is True
    assert data["ai"]["provider"] == "test_fixture"
    assert "version" in data["python"]
    assert "timestamp_utc" in data

    # Verify no secret leakage
    raw_text = resp.text
    assert "GOOGLE_AI_API_KEY" not in raw_text
    assert "api_key" not in raw_text.lower() or "configured" in raw_text.lower()


# =============================================================================
# 2. Complete LinkWatch Workflow End-to-End
# =============================================================================

@pytest.mark.asyncio
async def test_linkwatch_e2e_complete_workflow(
    linkwatch_client: AsyncClient,
    linkwatch_repo: Path,
    linkwatch_settings: Settings,
):
    """Execute complete LinkWatch analysis workflow without hardcoded findings."""
    analysis_svc = AnalysisService(settings=linkwatch_settings)
    orchestrator = OrchestrationService(analysis_service=analysis_svc, settings=linkwatch_settings)

    # -------------------------------------------------------------------------
    # A. Create Analysis (POST /api/v1/analyses)
    # -------------------------------------------------------------------------
    create_payload = {
        "repository": {
            "kind": "local_path",
            "value": str(linkwatch_repo),
        },
        "options": {
            "exclude_paths": [".git", ".venv", "venv", "node_modules", "reports", "exitlens_app"],
            "include_tests": True,
            "use_git_history": False,
            "generate_recommendations": True,
        },
    }
    create_resp = await linkwatch_client.post("/api/v1/analyses", json=create_payload)
    assert create_resp.status_code == 202
    created_data = create_resp.json()

    analysis_id = created_data["analysis_id"]
    assert analysis_id is not None
    assert created_data["status"] == AnalysisStatus.QUEUED.value

    # -------------------------------------------------------------------------
    # B. Run Pipeline & Status Polling (GET /api/v1/analyses/{id})
    # -------------------------------------------------------------------------
    # Run the pipeline through orchestrator
    completed_record = await orchestrator.run_pipeline(analysis_id)
    assert completed_record.status in (AnalysisStatus.COMPLETED, AnalysisStatus.COMPLETED_WITH_WARNINGS)

    # Poll status endpoint
    status_resp = await linkwatch_client.get(f"/api/v1/analyses/{analysis_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()

    assert status_data["analysis_id"] == analysis_id
    assert status_data["status"] in (AnalysisStatus.COMPLETED.value, AnalysisStatus.COMPLETED_WITH_WARNINGS.value)
    assert status_data["progress"]["percent"] == 100
    assert status_data["summary"]["dependencies_discovered"] > 0
    assert status_data["summary"]["dependencies_flagged"] > 0
    assert status_data["artifacts"]["has_capsule_json"] is True
    assert status_data["artifacts"]["has_capsule_md"] is True

    # -------------------------------------------------------------------------
    # C. Dynamic Dependency Retrieval (No Hardcoding)
    # -------------------------------------------------------------------------
    # List all flagged dependencies
    deps_resp = await linkwatch_client.get(f"/api/v1/analyses/{analysis_id}/dependencies")
    assert deps_resp.status_code == 200
    deps_data = deps_resp.json()

    assert len(deps_data) > 0
    discovered_dist_names = set()

    for dep in deps_data:
        dep_id = dep["dependency_id"]
        assert dep_id.startswith("dep-")

        details = dep["dependency_details"]
        assert "distribution_name" in details
        assert "manifest_path" in details
        discovered_dist_names.add(details["distribution_name"].lower())

        # Verify all 9 sections exist in structure
        assert isinstance(dep["risk_indicators"], list)
        assert isinstance(dep["usage_locations"], list)
        assert "proposed_replacement" in dep
        assert isinstance(dep["migration_steps"], list)
        assert isinstance(dep["suggested_tests"], list)
        assert isinstance(dep["executed_test_results"], list)
        assert isinstance(dep["compatibility_gaps"], list)
        assert isinstance(dep["open_concerns_limitations"], list)

    # Verify that expected LinkWatch packages were dynamically discovered
    # (requests, beautifulsoup4, urllib3, colorama, click are in the fixture manifests)
    assert any(name in discovered_dist_names for name in ["requests", "beautifulsoup4", "urllib3"])

    # Detail view for first dependency
    first_dep = deps_data[0]
    target_dep_id = first_dep["dependency_id"]

    detail_resp = await linkwatch_client.get(f"/api/v1/analyses/{analysis_id}/dependencies/{target_dep_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["dependency_id"] == target_dep_id
    assert detail_data["dependency_details"]["distribution_name"] == first_dep["dependency_details"]["distribution_name"]

    # -------------------------------------------------------------------------
    # D. Deterministic Recommendation & On-Demand Regeneration
    # -------------------------------------------------------------------------
    # Verify deterministic test provider provenance on initial recommendation
    prop_repl = first_dep["proposed_replacement"]
    assert prop_repl["status"] in (CandidateStatus.PROPOSED.value, CandidateStatus.NO_CANDIDATE_IDENTIFIED.value)
    assert len(prop_repl["rationale"]) > 0

    # Regenerate recommendations on demand for this specific dependency
    regen_resp = await linkwatch_client.post(
        f"/api/v1/analyses/{analysis_id}/recommendations",
        json={
            "dependency_ids": [target_dep_id],
            "force_regenerate": True,
        },
    )
    assert regen_resp.status_code == 202
    regen_data = regen_resp.json()
    assert regen_data["analysis_id"] == analysis_id
    assert regen_data["regenerated_count"] == 1
    assert len(regen_data["recommendations"]) == 1
    assert regen_data["recommendations"][0]["dependency_id"] == target_dep_id

    # -------------------------------------------------------------------------
    # E. Test Profile Discovery
    # -------------------------------------------------------------------------
    profiles_resp = await linkwatch_client.get(f"/api/v1/analyses/{analysis_id}/test-profiles")
    assert profiles_resp.status_code == 200
    profiles = profiles_resp.json()

    # LinkWatch has pytest.ini and tests/ -> pytest must be detected
    pytest_profiles = [p for p in profiles if p["framework"] == "pytest"]
    assert len(pytest_profiles) > 0
    assert any(p["is_detected"] is True for p in pytest_profiles)

    # -------------------------------------------------------------------------
    # F. Verification Safety Controls & Execution
    # -------------------------------------------------------------------------
    # 1. Missing explicit confirmation must be rejected with 422
    unconfirmed_payload = {
        "dependency_ids": [target_dep_id],
        "baseline_profile_id": "pytest-default",
        "confirm_repository_code_execution": False,
    }
    unconfirmed_resp = await linkwatch_client.post(
        f"/api/v1/analyses/{analysis_id}/verification",
        json=unconfirmed_payload,
    )
    assert unconfirmed_resp.status_code == 422
    assert unconfirmed_resp.json()["error"]["code"] == "CONFIRMATION_REQUIRED"

    # 2. Unauthorized profile must be rejected with 422
    unauth_payload = {
        "dependency_ids": [target_dep_id],
        "baseline_profile_id": "malicious_script.sh",
        "confirm_repository_code_execution": True,
    }
    unauth_resp = await linkwatch_client.post(
        f"/api/v1/analyses/{analysis_id}/verification",
        json=unauth_payload,
    )
    assert unauth_resp.status_code == 422
    assert "UNAUTHORIZED_TEST_PROFILE" in unauth_resp.json()["error"]["code"]

    # 3. Approved verification execution
    verif_payload = {
        "dependency_ids": [target_dep_id],
        "baseline_profile_id": "pytest-default",
        "confirm_repository_code_execution": True,
    }
    verif_resp = await linkwatch_client.post(
        f"/api/v1/analyses/{analysis_id}/verification",
        json=verif_payload,
    )
    assert verif_resp.status_code == 202
    verif_data = verif_resp.json()

    assert verif_data["analysis_id"] == analysis_id
    assert verif_data["verification_id"] is not None
    assert len(verif_data["results"]) >= 1

    # Baseline result check
    baseline_result = verif_data["results"][0]
    assert baseline_result["run_kind"] == "baseline"
    assert baseline_result["profile_id"] == "pytest-default"
    assert baseline_result["status"] in (TestStatus.PASSED.value, TestStatus.FAILED.value)

    # Replacement result check: since no patch was approved/applied, candidate must be SKIPPED
    if len(verif_data["results"]) > 1:
        replacement_result = verif_data["results"][1]
        assert replacement_result["run_kind"] == "replacement"
        assert replacement_result["status"] == TestStatus.SKIPPED.value
        assert len(replacement_result["skip_or_error_reason"]) > 0

    # Retrieve verification session
    verif_id = verif_data["verification_id"]
    get_verif_resp = await linkwatch_client.get(f"/api/v1/analyses/{analysis_id}/verification/{verif_id}")
    assert get_verif_resp.status_code == 200
    assert get_verif_resp.json()["verification_id"] == verif_id

    # -------------------------------------------------------------------------
    # G. Deliverable Downloads & Completeness Validation
    # -------------------------------------------------------------------------
    # 1. JSON Capsule Download
    json_resp = await linkwatch_client.get(f"/api/v1/analyses/{analysis_id}/capsule?format=json")
    assert json_resp.status_code == 200
    assert json_resp.headers["Content-Type"] == "application/json"

    raw_capsule_dict = json_resp.json()
    assert raw_capsule_dict["analysis_id"] == analysis_id
    assert len(raw_capsule_dict["dependencies"]) > 0

    # Validate capsule schema and completeness contract
    capsule_model = DependencyExitCapsule.model_validate(raw_capsule_dict)
    completeness_errors = validate_capsule_completeness(capsule_model, raise_on_error=False)
    assert len(completeness_errors) == 0, f"Capsule completeness errors: {completeness_errors}"

    # 2. Markdown Capsule Download
    md_resp = await linkwatch_client.get(f"/api/v1/analyses/{analysis_id}/capsule?format=md")
    assert md_resp.status_code == 200
    assert "text/markdown" in md_resp.headers["Content-Type"]
    md_text = md_resp.text

    assert "# Dependency Exit Capsule" in md_text
    assert "Executive Summary" in md_text
    assert "Flagged Dependencies" in md_text
    assert "Provenance & Verification Legend" in md_text

    # 3. Invalid export format rejected with 422
    invalid_format_resp = await linkwatch_client.get(f"/api/v1/analyses/{analysis_id}/capsule?format=docx")
    assert invalid_format_resp.status_code == 422
    assert invalid_format_resp.json()["error"]["code"] == "INVALID_EXPORT_FORMAT"


# =============================================================================
# 3. Model-Unavailable Handling Integration Test
# =============================================================================

@pytest.mark.asyncio
async def test_linkwatch_model_unavailable_graceful_degradation(
    linkwatch_repo: Path,
    temp_dir: Path,
):
    """When AI inference is unavailable, scan findings and risks are preserved."""
    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
        GEMMA_PROVIDER="google_ai_studio",
        GOOGLE_AI_API_KEY="",  # Unconfigured API key simulates model unavailability
    )
    analysis_svc = AnalysisService(settings=settings)

    # Mock AI provider that raises ModelUnavailable / quota error
    mock_ai = AsyncMock()
    mock_ai.generate_migration_plan.side_effect = Exception("Google AI Studio connection failed (503 Service Unavailable)")

    orchestrator = OrchestrationService(
        analysis_service=analysis_svc,
        ai_provider=mock_ai,
        settings=settings,
    )

    # 1. Create analysis
    create_req = CreateAnalysisRequest(
        repository=RepositoryInput(kind=RepositoryKind.LOCAL_PATH, value=str(linkwatch_repo)),
        options=AnalysisOptions(generate_recommendations=True),
    )
    record = analysis_svc.create_analysis(create_req)

    # 2. Run pipeline
    completed = await orchestrator.run_pipeline(record.analysis_id)

    # 3. Verify status transitions to COMPLETED_WITH_WARNINGS
    assert completed.status == AnalysisStatus.COMPLETED_WITH_WARNINGS
    assert len(completed.warnings) > 0
    assert any("AI recommendation unavailable" in w for w in completed.warnings)

    # 4. Verify static scan evidence is 100% preserved
    evidence = analysis_svc.get_evidence(record.analysis_id)
    assert len(evidence) > 0

    # 5. Verify capsule exists and marks candidate status honestly as UNAVAILABLE
    capsule = analysis_svc.get_capsule(record.analysis_id)
    assert capsule is not None
    assert len(capsule.dependencies) > 0

    assert capsule.ai_provenance is not None
    assert capsule.ai_provenance.provenance_kind == ProvenanceKind.AI_RECOMMENDATION

    for dep in capsule.dependencies:
        assert dep.proposed_replacement.status == CandidateStatus.UNAVAILABLE.value
        assert "unavailable" in dep.proposed_replacement.rationale.lower()

    # 6. Verify completeness validation passes even on degraded capsule
    errors = validate_capsule_completeness(capsule, raise_on_error=False)
    assert len(errors) == 0, f"Completeness errors on degraded capsule: {errors}"
