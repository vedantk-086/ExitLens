"""Deterministic fake AI provider for unit testing.

Explicitly tagged provider=test_fixture. Never contacts remote endpoints.
Returns controlled fixtures to verify validation, error recovery, and provenance.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Set

from app.ai.base import BaseAiProvider
from app.ai.prompts import PROMPT_VERSION, build_migration_prompt, build_schema_repair_prompt
from app.ai.validator import validate_and_parse_ai_response
from app.core.time import utc_now_iso
from app.schemas.capsule import DependencyDetails, UsageLocation
from app.schemas.common import ProvenanceKind
from app.schemas.evidence import EvidenceRecord
from app.schemas.recommendation import (
    AiProvenance,
    CandidateStatus,
    ProposedReplacement,
    RecommendationRecord,
)
from app.schemas.risk import RiskIndicator


class FakeAiProvider(BaseAiProvider):
    """Deterministic, test-only AI provider generating controlled fixtures."""

    def __init__(
        self,
        scenario: str = "valid",
        model_name: str = "test-fixture-gemma",
        settings: Optional[Any] = None,
    ) -> None:
        self.scenario = scenario
        self.model_name = model_name
        self.settings = settings
        self.call_count = 0

    @property
    def provider_id(self) -> str:
        return "test_fixture"

    @property
    def configured_model(self) -> str:
        return self.model_name

    def _generate_raw_fixture(self, valid_evidence_ids: Set[str]) -> str:
        """Generate test JSON response text according to configured scenario."""
        first_ev_id = sorted(list(valid_evidence_ids))[0] if valid_evidence_ids else "ev-test-1"

        if self.scenario == "valid":
            return json.dumps({
                "candidate_status": "proposed",
                "replacement_distribution": "httpx",
                "replacement_specifier": ">=0.27.0",
                "rationale": "Grounded in discovered usages; modern async-compatible HTTP library.",
                "api_differences": ["requests.get -> httpx.get", "Response.json() returns parsed dict"],
                "ordered_migration_steps": [
                    {
                        "step_number": 1,
                        "action": "Update requirements",
                        "description": "Replace requests with httpx in requirements.txt",
                        "target_file": "requirements.txt",
                        "human_review_required": True,
                    }
                ],
                "suggested_tests": [
                    {
                        "test_id": "sug-001",
                        "objective": "Verify HTTP requests succeed",
                        "relation_to_usage": "Validates app.py fetch_data function",
                        "suggested_profile": "pytest-unit",
                        "preconditions": ["httpx installed"],
                        "expected_signal": "Status 200 returned",
                    }
                ],
                "compatibility_concerns": ["Slight differences in session connection pooling"],
                "open_concerns_limitations": ["Verify streaming response handling"],
                "evidence_references": [first_ev_id],
                "optional_patch_proposal": (
                    "--- a/requirements.txt\n"
                    "+++ b/requirements.txt\n"
                    "@@ -1,1 +1,1 @@\n"
                    "-requests>=2.0.0\n"
                    "+httpx>=0.27.0\n"
                ),
            })

        elif self.scenario == "malformed_json":
            return "{ bad json: true, unclosed... "

        elif self.scenario == "unknown_evidence_ids":
            return json.dumps({
                "candidate_status": "proposed",
                "replacement_distribution": "httpx",
                "rationale": "Invented evidence test",
                "evidence_references": ["ev-hallucinated-999"],
            })

        elif self.scenario == "unsupported_status":
            return json.dumps({
                "candidate_status": "magical_fix_all",
                "rationale": "Unsupported status test",
                "evidence_references": [first_ev_id],
            })

        elif self.scenario == "unsafe_patch":
            return json.dumps({
                "candidate_status": "proposed",
                "replacement_distribution": "httpx",
                "rationale": "Unsafe patch test",
                "evidence_references": [first_ev_id],
                "optional_patch_proposal": (
                    "--- a/../../etc/passwd\n"
                    "+++ b/../../etc/passwd\n"
                    "@@ -1,1 +1,1 @@\n"
                    "+root:evil\n"
                ),
            })

        elif self.scenario == "repair_succeeds":
            if self.call_count == 1:
                return "{ invalid json attempt 1"
            # Second call succeeds
            return json.dumps({
                "candidate_status": "proposed",
                "replacement_distribution": "httpx",
                "rationale": "Repaired valid response",
                "evidence_references": [first_ev_id],
            })

        elif self.scenario == "repair_fails":
            return "{ invalid json attempt forever"

        return "{}"

    async def generate_migration_plan(
        self,
        evidence_bundle: List[EvidenceRecord],
        dependency_record: DependencyDetails,
        runtime_context: Optional[Dict[str, Any]] = None,
        test_profile_context: Optional[Dict[str, Any]] = None,
        risks: Optional[List[RiskIndicator]] = None,
        usages: Optional[List[UsageLocation]] = None,
        request_id: Optional[str] = None,
        dependency_id: Optional[str] = None,
        **kwargs: Any,
    ) -> RecommendationRecord:
        """Simulate generation and schema validation deterministically."""
        dep_id = dependency_id or f"dep-{dependency_record.distribution_name.lower().replace('_', '-')}"
        observed_time = utc_now_iso()

        if self.scenario == "timeout":
            return RecommendationRecord(
                dependency_id=dep_id,
                proposed_replacement=ProposedReplacement(
                    status=CandidateStatus.UNAVAILABLE.value,
                    rationale="Request timed out waiting for AI model response.",
                ),
                open_concerns_limitations=["Request timed out waiting for AI model response."],
                provenance=AiProvenance(
                    provider=self.provider_id,
                    model_id=self.model_name,
                    inference_method="test_fixture",
                    prompt_version=PROMPT_VERSION,
                    generated_at_utc=observed_time,
                    recommendation_status=CandidateStatus.UNAVAILABLE.value,
                    failure_category="timeout",
                    provenance_kind=ProvenanceKind.AI_RECOMMENDATION,
                ),
            )


        if self.scenario == "unavailable":
            return RecommendationRecord(
                dependency_id=dep_id,
                proposed_replacement=ProposedReplacement(
                    status=CandidateStatus.UNAVAILABLE.value,
                    rationale="Provider unavailable in test scenario",
                ),
                provenance=AiProvenance(
                    provider=self.provider_id,
                    model_id=self.model_name,
                    inference_method="test_fixture",
                    prompt_version=PROMPT_VERSION,
                    generated_at_utc=observed_time,
                    recommendation_status=CandidateStatus.UNAVAILABLE.value,
                    failure_category="test_unavailable",
                    provenance_kind=ProvenanceKind.AI_RECOMMENDATION,
                ),
            )

        prompt_str, valid_evidence_ids = build_migration_prompt(
            dependency=dependency_record,
            risks=risks,
            usages=usages,
            evidence_bundle=evidence_bundle,
            runtime_context=runtime_context,
            test_profile_context=test_profile_context,
        )

        self.call_count += 1
        raw_text = self._generate_raw_fixture(valid_evidence_ids)

        is_valid, val_err, rec = validate_and_parse_ai_response(
            raw_response_text=raw_text,
            dependency_id=dep_id,
            valid_evidence_ids=valid_evidence_ids,
            provider_id=self.provider_id,
            model_id=self.model_name,
            prompt_version=PROMPT_VERSION,
            generated_at_utc=observed_time,
            request_id=request_id,
        )

        if is_valid and rec:
            return rec

        # Schema repair retry attempt
        self.call_count += 1
        repair_raw = self._generate_raw_fixture(valid_evidence_ids)
        repair_valid, repair_err, repaired_rec = validate_and_parse_ai_response(
            raw_response_text=repair_raw,
            dependency_id=dep_id,
            valid_evidence_ids=valid_evidence_ids,
            provider_id=self.provider_id,
            model_id=self.model_name,
            prompt_version=PROMPT_VERSION,
            generated_at_utc=utc_now_iso(),
            request_id=request_id,
        )

        if repair_valid and repaired_rec:
            return repaired_rec

        return RecommendationRecord(
            dependency_id=dep_id,
            proposed_replacement=ProposedReplacement(
                status=CandidateStatus.INVALID_RESPONSE.value,
                rationale=f"Model response could not be validated after schema repair: {val_err}",
            ),
            provenance=AiProvenance(
                provider=self.provider_id,
                model_id=self.model_name,
                inference_method="test_fixture",
                prompt_version=PROMPT_VERSION,
                generated_at_utc=observed_time,
                recommendation_status=CandidateStatus.INVALID_RESPONSE.value,
                failure_category="schema_validation_failed",
                provenance_kind=ProvenanceKind.AI_RECOMMENDATION,
            ),
        )
