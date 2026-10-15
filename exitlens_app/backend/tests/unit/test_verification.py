"""Unit tests for ExitLens verification engine.

Verifies:
1. Approval enforcement (explicit user confirmation requirement).
2. Timeout handling with subprocess termination.
3. Non-zero exit code capture and status=FAILED preservation.
4. Output truncation and credential redaction.
5. No-network environment isolation and secret scrubbing.
6. Unsafe patch rejection (absolute paths, ../ traversal).
7. Baseline failure preservation (never attributed to replacement).
8. Skipped replacement behavior for missing candidates or patches.
9. Disposable workspace isolation (original repo is never modified).
10. Test profile discovery and allow-listed server-defined argv enforcement.
"""

import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.core.errors import ConfirmationRequiredError, ValidationError
from app.schemas.analysis import AnalysisRecord
from app.schemas.capsule import DependencyDetails
from app.schemas.common import AnalysisStatus
from app.schemas.recommendation import (
    CandidateStatus,
    ProposedReplacement,
    RecommendationRecord,
)
from app.schemas.repository import (
    AnalysisOptions,
    CreateAnalysisRequest,
    RepositoryInput,
    RepositoryKind,
)
from app.schemas.verification import (
    ExecutedTestResult,
    TestStatus,
    VerificationRecord,
    VerificationRequest,
)
from app.services.analysis_service import AnalysisService
from app.verification.environment import (
    build_restricted_environment,
    redact_and_truncate_output,
)
from app.verification.patch_applier import (
    PatchApplicationError,
    apply_patch_to_workspace,
)
from app.verification.profiles import (
    ALLOWLISTED_PROFILES,
    discover_test_profiles,
    get_allowlisted_profile,
)
from app.verification.runner import VerificationRunner
from app.verification.service import VerificationService
from app.verification.workspace import disposable_workspace


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def sample_repo(temp_dir: Path) -> Path:
    """Create a minimal sample repository for verification testing."""
    repo = temp_dir / "target_repo"
    repo.mkdir(parents=True, exist_ok=True)
    
    (repo / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n", encoding="utf-8")
    
    tests_dir = repo / "tests"
    tests_dir.mkdir(exist_ok=True)
    
    (tests_dir / "test_sample.py").write_text(
        "def test_pass():\n    assert True\n",
        encoding="utf-8",
    )
    (repo / "app.py").write_text("def run():\n    return 'hello'\n", encoding="utf-8")
    return repo


@pytest.fixture
def mock_analysis(temp_dir: Path, sample_repo: Path) -> AnalysisRecord:
    """Create a persisted mock analysis run."""
    service = AnalysisService(
        settings=Settings(
            ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
            EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
        )
    )
    req = CreateAnalysisRequest(
        repository=RepositoryInput(kind=RepositoryKind.LOCAL_PATH, value=str(sample_repo))
    )
    record = service.create_analysis(req)
    service.update_stage(record.analysis_id, AnalysisStatus.READY_FOR_VERIFICATION)
    return record


# -----------------------------------------------------------------------------
# Test 1: Approval Enforcement
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approval_enforcement_prevents_execution(sample_repo: Path, mock_analysis: AnalysisRecord, temp_dir: Path):
    """Execution must not proceed without explicit confirm_repository_code_execution=True."""
    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
    )
    service = VerificationService(settings=settings)

    request = VerificationRequest(
        dependency_ids=["dep-1"],
        baseline_profile_id="pytest-default",
        confirm_repository_code_execution=False,  # Unconfirmed!
    )

    record = await service.execute_verification_session(
        analysis_id=mock_analysis.analysis_id,
        request=request,
        repository_path=sample_repo,
    )

    # Verification record should be persisted with NOT_RUN status
    assert len(record.results) == 1
    result = record.results[0]
    assert result.status == TestStatus.NOT_RUN
    assert "Explicit confirmation required" in result.skip_or_error_reason
    assert result.argv == []


# -----------------------------------------------------------------------------
# Test 2: Timeout Handling
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_timeout_enforcement(sample_repo: Path, temp_dir: Path):
    """Runner terminates and kills subprocess when execution exceeds timeout limit."""
    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
        MAX_TEST_TIMEOUT_SECONDS=180,
    )
    runner = VerificationRunner(settings=settings)

    # Mock subprocess to simulate a hanging process
    async def mock_communicate():
        import asyncio
        await asyncio.sleep(5)
        return b"", b""

    mock_proc = AsyncMock()
    mock_proc.communicate = mock_communicate
    mock_proc.kill = MagicMock()
    mock_proc.wait = AsyncMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await runner.execute_profile(
            workspace_path=sample_repo,
            profile_id="pytest-default",
            run_kind="baseline",
            timeout_seconds=1,  # Short 1-second timeout
        )

    assert result.status == TestStatus.TIMED_OUT
    assert "timed out after 1" in result.skip_or_error_reason
    mock_proc.kill.assert_called_once()


# -----------------------------------------------------------------------------
# Test 3: Non-zero Exit Code Capture
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_zero_exit_captures_failure(sample_repo: Path, temp_dir: Path):
    """Runner records FAILED status and captures non-zero exit code faithfully."""
    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
    )
    runner = VerificationRunner(settings=settings)

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"pytest run", b"AssertionError: 1 != 2"))
    mock_proc.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await runner.execute_profile(
            workspace_path=sample_repo,
            profile_id="pytest-default",
            run_kind="baseline",
        )

    assert result.status == TestStatus.FAILED
    assert result.exit_code == 1
    assert "AssertionError" in result.stderr_excerpt


# -----------------------------------------------------------------------------
# Test 4: Output Truncation & Credential Redaction
# -----------------------------------------------------------------------------

def test_output_truncation_and_credential_redaction():
    """Output exceeding MAX_CAPTURED_OUTPUT_BYTES is truncated and API keys are redacted."""
    # 1. Redaction of Google AI Studio and OpenAI secret formats
    raw_output = (
        "Traceback with api_key='AIzaSyAbc12345678901234567890123456789' "
        "and secret=sk-123456789012345678901234567890 "
        "and Bearer 123456789abcdef"
    )
    redacted, is_trunc = redact_and_truncate_output(raw_output, max_bytes=5000)
    assert "AIzaSy" not in redacted
    assert "[REDACTED_GOOGLE_API_KEY]" in redacted
    assert "[REDACTED_API_SECRET]" in redacted
    assert "[REDACTED_TOKEN]" in redacted
    assert is_trunc is False

    # 2. Bounded truncation
    massive_output = "Line of output: " + ("X" * 20000)
    truncated, was_trunc = redact_and_truncate_output(massive_output, max_bytes=1000)
    assert was_trunc is True
    assert "OUTPUT TRUNCATED" in truncated
    assert len(truncated.encode("utf-8")) < 2000


# -----------------------------------------------------------------------------
# Test 5: No-network Environment & Secret Scrubbing
# -----------------------------------------------------------------------------

def test_no_network_behavior_and_secret_scrubbing(monkeypatch):
    """Subprocess environment blocks network and strips inherited secrets."""
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "sensitive_ai_key_12345")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "super_secret_aws")
    monkeypatch.setenv("DATABASE_PASSWORD", "db_pass_123")
    monkeypatch.setenv("SAFE_ALLOWED_VAR", "visible")

    env = build_restricted_environment(allow_network=False)

    # Secrets MUST be scrubbed
    assert "GOOGLE_AI_API_KEY" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "DATABASE_PASSWORD" not in env

    # Network must be explicitly disabled
    assert env["PIP_NO_INDEX"] == "1"
    assert env["PIP_OFFLINE"] == "1"
    assert env["HTTP_PROXY"] == "http://127.0.0.1:0"
    assert env["HTTPS_PROXY"] == "http://127.0.0.1:0"


# -----------------------------------------------------------------------------
# Test 6: Unsafe Patch Rejection
# -----------------------------------------------------------------------------

def test_unsafe_patch_rejection(temp_dir: Path):
    """Patches with absolute paths or directory traversal (../) are rejected."""
    workspace = temp_dir / "ws"
    workspace.mkdir()
    (workspace / "valid.py").write_text("x = 1\n", encoding="utf-8")

    # 1. Directory traversal patch
    traversal_patch = (
        "--- a/../../outside.py\n"
        "+++ b/../../outside.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-x = 1\n"
        "+x = 2\n"
    )
    with pytest.raises(PatchApplicationError) as exc_info:
        apply_patch_to_workspace(workspace, traversal_patch)
    assert "traversal" in str(exc_info.value).lower() or "rejected" in str(exc_info.value).lower()

    # 2. Absolute path patch
    abs_patch = (
        "--- /etc/passwd\n"
        "+++ /etc/passwd\n"
        "@@ -1,1 +1,1 @@\n"
        "-root:x\n"
        "+root:pwned\n"
    )
    with pytest.raises(PatchApplicationError):
        apply_patch_to_workspace(workspace, abs_patch)


# -----------------------------------------------------------------------------
# Test 7: Baseline Failure Preservation
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_baseline_failure_preservation(sample_repo: Path, mock_analysis: AnalysisRecord, temp_dir: Path):
    """When baseline tests fail, failure is preserved and not attributed to replacement."""
    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
    )

    # Mock runner where baseline fails (exit code 2)
    mock_runner = AsyncMock()
    mock_runner.execute_profile.return_value = ExecutedTestResult(
        check_id="chk-baseline-1",
        run_kind="baseline",
        status=TestStatus.FAILED,
        profile_id="pytest-default",
        argv=["pytest"],
        exit_code=2,
        stderr_excerpt="Pre-existing test failure in test_auth.py",
    )

    service = VerificationService(runner=mock_runner, settings=settings)

    request = VerificationRequest(
        dependency_ids=["dep-1"],
        baseline_profile_id="pytest-default",
        confirm_repository_code_execution=True,
    )

    record = await service.execute_verification_session(
        analysis_id=mock_analysis.analysis_id,
        request=request,
        repository_path=sample_repo,
    )

    assert len(record.results) >= 1
    baseline = record.results[0]
    assert baseline.status == TestStatus.FAILED
    assert baseline.exit_code == 2
    assert "Pre-existing test failure" in baseline.stderr_excerpt


# -----------------------------------------------------------------------------
# Test 8: Skipped Replacement Behavior
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skipped_replacement_behavior(sample_repo: Path, mock_analysis: AnalysisRecord, temp_dir: Path):
    """Replacement verification is SKIPPED honestly when candidate or patch is missing."""
    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        EXITLENS_DATA_DIR=str(temp_dir / "reports" / "exitlens"),
    )

    mock_runner = AsyncMock()
    mock_runner.execute_profile.return_value = ExecutedTestResult(
        check_id="chk-b",
        run_kind="baseline",
        status=TestStatus.PASSED,
        profile_id="pytest-default",
        argv=["pytest"],
        exit_code=0,
    )

    service = VerificationService(runner=mock_runner, settings=settings)

    # 1. Dependency with no candidate recommendation
    request = VerificationRequest(
        dependency_ids=["dep-missing-candidate"],
        baseline_profile_id="pytest-default",
        confirm_repository_code_execution=True,
    )

    record = await service.execute_verification_session(
        analysis_id=mock_analysis.analysis_id,
        request=request,
        repository_path=sample_repo,
        recommendations=[],  # No recommendations
    )

    assert len(record.results) == 2  # Baseline + skipped replacement
    repl_result = record.results[1]
    assert repl_result.status == TestStatus.SKIPPED
    assert "No proposed replacement candidate identified" in repl_result.skip_or_error_reason

    # 2. Dependency with candidate but no patch proposal
    rec_no_patch = RecommendationRecord(
        recommendation_id="rec-1",
        analysis_id=mock_analysis.analysis_id,
        dependency_id="dep-with-candidate",
        proposed_replacement=ProposedReplacement(
            status=CandidateStatus.PROPOSED,
            distribution_name="httpx",
            specifier=">=0.27.0",
            rationale="Modern HTTP client with sync and async APIs",
        ),
        patch_proposal=None,  # No patch proposal
    )

    request2 = VerificationRequest(
        dependency_ids=["dep-with-candidate"],
        baseline_profile_id="pytest-default",
        confirm_repository_code_execution=True,
    )

    record2 = await service.execute_verification_session(
        analysis_id=mock_analysis.analysis_id,
        request=request2,
        repository_path=sample_repo,
        recommendations=[rec_no_patch],
    )

    repl_result2 = record2.results[1]
    assert repl_result2.status == TestStatus.SKIPPED
    assert "No validated migration patch proposal available" in repl_result2.skip_or_error_reason


# -----------------------------------------------------------------------------
# Test 9: Disposable Workspace Isolation
# -----------------------------------------------------------------------------

def test_disposable_workspace_isolation(sample_repo: Path):
    """Modifying files in a disposable workspace NEVER modifies the original repository."""
    orig_content = (sample_repo / "app.py").read_text(encoding="utf-8")

    with disposable_workspace(sample_repo) as ws:
        ws_file = ws / "app.py"
        assert ws_file.is_file()
        ws_file.write_text("def run():\n    return 'COMPLETELY_MODIFIED'\n", encoding="utf-8")
        assert "COMPLETELY_MODIFIED" in ws_file.read_text(encoding="utf-8")

    # Original file MUST remain unchanged
    after_content = (sample_repo / "app.py").read_text(encoding="utf-8")
    assert after_content == orig_content
    assert "COMPLETELY_MODIFIED" not in after_content


# -----------------------------------------------------------------------------
# Test 10: Test Profile Discovery and Allow-list
# -----------------------------------------------------------------------------

def test_test_profile_discovery_and_allowlist(sample_repo: Path):
    """Profiles are discovered from repo files without executing code, and unknown IDs are rejected."""
    profiles = discover_test_profiles(sample_repo)
    assert len(profiles) >= 2
    
    # pytest-default should be detected because pytest.ini is present
    pytest_prof = next(p for p in profiles if p.profile_id == "pytest-default")
    assert pytest_prof.is_detected is True
    assert "pytest.ini" in pytest_prof.detection_reason
    assert pytest_prof.server_argv == [sys.executable, "-m", "pytest", "-q", "--tb=short"]

    # Allow-list validation
    valid = get_allowlisted_profile("pytest-default")
    assert valid.profile_id == "pytest-default"

    with pytest.raises(ValidationError) as exc_info:
        get_allowlisted_profile("malicious-rm-rf; pytest")
    assert "UNAUTHORIZED_TEST_PROFILE" in str(exc_info.value.code)


# -----------------------------------------------------------------------------
# Test 11: Verification API Endpoints
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verification_api_endpoints(async_client: AsyncClient, mock_analysis: AnalysisRecord):
    """Test profiles discovery and verification execution via HTTP API."""
    # 1. GET /api/v1/analyses/{id}/test-profiles
    resp = await async_client.get(f"/api/v1/analyses/{mock_analysis.analysis_id}/test-profiles")
    assert resp.status_code == 200
    profiles = resp.json()
    assert isinstance(profiles, list)
    assert any(p["profile_id"] == "pytest-default" for p in profiles)

    # 2. POST /api/v1/analyses/{id}/verification without confirmation returns 422
    unconfirmed_payload = {
        "dependency_ids": ["dep-1"],
        "baseline_profile_id": "pytest-default",
        "confirm_repository_code_execution": False,
    }
    resp = await async_client.post(
        f"/api/v1/analyses/{mock_analysis.analysis_id}/verification",
        json=unconfirmed_payload,
    )
    assert resp.status_code == 422
    err_data = resp.json()
    assert err_data["error"]["code"] == "CONFIRMATION_REQUIRED"
