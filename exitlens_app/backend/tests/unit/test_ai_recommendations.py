"""Unit tests for ExitLens AI recommendation engine and Google AI Studio integration."""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest

from app.ai.fake_provider import FakeAiProvider
from app.ai.google_studio import GoogleAiStudioProvider
from app.ai.prompts import PROMPT_VERSION, build_migration_prompt, build_schema_repair_prompt
from app.ai.validator import validate_and_parse_ai_response, validate_patch_security
from app.core.config import Settings
from app.schemas.capsule import DependencyDetails, UsageLocation
from app.schemas.common import ProvenanceKind
from app.schemas.evidence import EvidenceRecord
from app.schemas.recommendation import CandidateStatus, ProposedReplacement, RecommendationRecord
from app.schemas.risk import RiskIndicator, RiskSeverity


def create_test_dep(name: str = "requests") -> DependencyDetails:
    return DependencyDetails(
        distribution_name=name,
        manifest_path="requirements.txt",
        declared_specifier=">=2.25.0",
        package_manager="pip",
    )


def create_test_ev(ev_id: str = "ev-req-1", path: str = "requirements.txt") -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=ev_id,
        kind="manifest_declaration",
        provenance=ProvenanceKind.OBSERVED,
        path=path,
        line_start=1,
        line_end=1,
        excerpt="requests>=2.25.0",
        sha256="abc123hash",
        observed_at_utc="2026-10-15T12:00:00Z",
    )


@pytest.mark.asyncio
async def test_successful_validated_recommendation():
    """Verify fake provider generates a validated structured recommendation with evidence refs."""
    provider = FakeAiProvider(scenario="valid")
    dep = create_test_dep()
    ev = create_test_ev()

    rec = await provider.generate_migration_plan(
        evidence_bundle=[ev],
        dependency_record=dep,
    )

    assert rec.dependency_id == "dep-requests"
    assert rec.proposed_replacement.status == CandidateStatus.PROPOSED.value
    assert rec.proposed_replacement.distribution_name == "httpx"
    assert rec.proposed_replacement.specifier == ">=0.27.0"
    assert len(rec.migration_steps) >= 1
    assert len(rec.suggested_tests) >= 1
    assert rec.patch_proposal is not None

    # Provenance verification
    prov = rec.provenance
    assert prov is not None
    assert prov.provider == "test_fixture"
    assert prov.provenance_kind == ProvenanceKind.AI_RECOMMENDATION
    assert prov.recommendation_status == CandidateStatus.PROPOSED.value
    assert "ev-req-1" in prov.evidence_references


@pytest.mark.asyncio
async def test_malformed_response_triggers_schema_repair_and_handles_gracefully():
    """Verify malformed JSON responses are caught and handled without crashing."""
    provider = FakeAiProvider(scenario="malformed_json")
    dep = create_test_dep()
    ev = create_test_ev()

    rec = await provider.generate_migration_plan(
        evidence_bundle=[ev],
        dependency_record=dep,
    )

    assert rec.proposed_replacement.status == CandidateStatus.INVALID_RESPONSE.value
    assert "could not be validated" in rec.proposed_replacement.rationale.lower()
    assert rec.provenance.recommendation_status == CandidateStatus.INVALID_RESPONSE.value
    assert rec.provenance.failure_category == "schema_validation_failed"


@pytest.mark.asyncio
async def test_unknown_evidence_ids_rejected():
    """Verify that hallucinated evidence IDs not present in valid_evidence_ids are rejected."""
    provider = FakeAiProvider(scenario="unknown_evidence_ids")
    dep = create_test_dep()
    ev = create_test_ev("ev-known-1")

    rec = await provider.generate_migration_plan(
        evidence_bundle=[ev],
        dependency_record=dep,
    )

    # Unknown evidence references should cause rejection / invalid_response
    assert rec.proposed_replacement.status == CandidateStatus.INVALID_RESPONSE.value
    assert "unknown/invented evidence ids" in rec.proposed_replacement.rationale.lower()


@pytest.mark.asyncio
async def test_unsupported_recommendation_status_rejected():
    """Verify statuses outside CandidateStatus enumeration are rejected."""
    provider = FakeAiProvider(scenario="unsupported_status")
    dep = create_test_dep()
    ev = create_test_ev()

    rec = await provider.generate_migration_plan(
        evidence_bundle=[ev],
        dependency_record=dep,
    )

    assert rec.proposed_replacement.status == CandidateStatus.INVALID_RESPONSE.value
    assert "unsupported candidate_status" in rec.proposed_replacement.rationale.lower()


@pytest.mark.asyncio
async def test_unsafe_patch_path_rejected():
    """Verify patches targeting directory traversal or absolute paths are rejected."""
    # 1. Traversal patch via fake provider
    provider = FakeAiProvider(scenario="unsafe_patch")
    dep = create_test_dep()
    ev = create_test_ev()

    rec = await provider.generate_migration_plan(
        evidence_bundle=[ev],
        dependency_record=dep,
    )

    assert rec.proposed_replacement.status == CandidateStatus.INVALID_RESPONSE.value
    assert "traversal" in rec.proposed_replacement.rationale.lower()

    # 2. Direct patch validator checks
    safe_patch = "--- a/src/app.py\n+++ b/src/app.py\n@@ -1,1 +1,1 @@\n-import requests\n+import httpx\n"
    is_safe, err = validate_patch_security(safe_patch)
    assert is_safe is True
    assert err is None

    abs_patch_unix = "--- /etc/shadow\n+++ /etc/shadow\n"
    is_safe_abs, err_abs = validate_patch_security(abs_patch_unix)
    assert is_safe_abs is False
    assert "absolute path" in err_abs.lower()

    abs_patch_win = "--- C:\\Windows\\System32\\calc.exe\n+++ C:\\Windows\\System32\\calc.exe\n"
    is_safe_win, err_win = validate_patch_security(abs_patch_win)
    assert is_safe_win is False
    assert "windows drive" in err_win.lower() or "absolute" in err_win.lower()


@pytest.mark.asyncio
async def test_timeout_handled_gracefully():
    """Verify timeout produces unavailable status and records timeout failure category."""
    provider = FakeAiProvider(scenario="timeout")
    dep = create_test_dep()
    ev = create_test_ev()

    rec = await provider.generate_migration_plan(
        evidence_bundle=[ev],
        dependency_record=dep,
    )

    assert rec.proposed_replacement.status == CandidateStatus.UNAVAILABLE.value
    assert "timed out" in rec.proposed_replacement.rationale.lower()
    assert rec.provenance.failure_category == "timeout"


@pytest.mark.asyncio
async def test_unavailable_provider_handled_gracefully():
    """Verify unavailable provider preserves findings and marks recommendation unavailable."""
    provider = FakeAiProvider(scenario="unavailable")
    dep = create_test_dep()
    ev = create_test_ev()

    rec = await provider.generate_migration_plan(
        evidence_bundle=[ev],
        dependency_record=dep,
    )

    assert rec.proposed_replacement.status == CandidateStatus.UNAVAILABLE.value
    assert rec.provenance.failure_category == "test_unavailable"


@pytest.mark.asyncio
async def test_one_schema_repair_retry_succeeding():
    """Verify that a first malformed response can be successfully repaired on the 1 retry."""
    provider = FakeAiProvider(scenario="repair_succeeds")
    dep = create_test_dep()
    ev = create_test_ev()

    rec = await provider.generate_migration_plan(
        evidence_bundle=[ev],
        dependency_record=dep,
    )

    assert provider.call_count == 2
    assert rec.proposed_replacement.status == CandidateStatus.PROPOSED.value
    assert "repaired valid response" in rec.proposed_replacement.rationale.lower()


@pytest.mark.asyncio
async def test_one_schema_repair_retry_failing_stores_invalid_response():
    """Verify that if the single repair retry also fails, invalid_response is stored."""
    provider = FakeAiProvider(scenario="repair_fails")
    dep = create_test_dep()
    ev = create_test_ev()

    rec = await provider.generate_migration_plan(
        evidence_bundle=[ev],
        dependency_record=dep,
    )

    assert provider.call_count == 2
    assert rec.proposed_replacement.status == CandidateStatus.INVALID_RESPONSE.value
    assert rec.provenance.failure_category == "schema_validation_failed"


@pytest.mark.asyncio
async def test_google_ai_studio_unconfigured_key_safe_handling():
    """Verify GoogleAiStudioProvider with missing API key safely degrades without leaking."""
    settings = Settings(
        GEMMA_PROVIDER="google_ai_studio",
        GOOGLE_AI_API_KEY="",
        GOOGLE_AI_MODEL="gemma-4-26b-a4b-it",
    )
    provider = GoogleAiStudioProvider(settings=settings)
    dep = create_test_dep()
    ev = create_test_ev()

    rec = await provider.generate_migration_plan(
        evidence_bundle=[ev],
        dependency_record=dep,
    )

    assert rec.proposed_replacement.status == CandidateStatus.UNAVAILABLE.value
    assert "api key is not configured" in rec.proposed_replacement.rationale.lower()
    assert rec.provenance.failure_category == "unconfigured_api_key"
    assert rec.provenance.provider == "google_ai_studio"
    assert rec.provenance.model_id == "gemma-4-26b-a4b-it"


@pytest.mark.asyncio
async def test_no_api_key_leakage_in_serialization_or_logs():
    """Critical security guarantee: API key must NEVER appear in outputs, logs, or exports."""
    secret_key = "AIzaSySecretApiKeyDoNotLeak12345"
    settings = Settings(
        GEMMA_PROVIDER="google_ai_studio",
        GOOGLE_AI_API_KEY=secret_key,
        GOOGLE_AI_MODEL="gemma-4-26b-a4b-it",
    )
    provider = GoogleAiStudioProvider(settings=settings)
    dep = create_test_dep()
    ev = create_test_ev()

    # Mock client generate call returning valid recommendation
    mock_resp = AsyncMock()
    mock_resp.text = (
        '{"candidate_status": "proposed", "replacement_distribution": "httpx", '
        '"rationale": "test rationale", "evidence_references": ["ev-req-1"]}'
    )

    with patch.object(provider, "_call_model", return_value=mock_resp.text):
        rec = await provider.generate_migration_plan(
            evidence_bundle=[ev],
            dependency_record=dep,
        )

        serialized_json = rec.model_dump_json()

        # Strict assertion: Secret key MUST NOT exist anywhere in the serialized payload
        assert secret_key not in serialized_json
        assert "aizasy" not in serialized_json.lower()
        assert rec.provenance.provider == "google_ai_studio"
        assert rec.provenance.model_id == "gemma-4-26b-a4b-it"
