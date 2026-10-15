"""Pydantic validation and security checks for AI recommendations."""

import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.schemas.common import ProvenanceKind
from app.schemas.recommendation import (
    AiProvenance,
    CandidateStatus,
    MigrationStep,
    ProposedReplacement,
    RecommendationRecord,
    SuggestedTest,
)


def extract_json_from_response(raw_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Extract and parse JSON object from raw model output."""
    clean = raw_text.strip()
    if "```json" in clean:
        parts = clean.split("```json", 1)[1].split("```", 1)
        clean = parts[0].strip()
    elif "```" in clean:
        parts = clean.split("```", 1)[1].split("```", 1)
        clean = parts[0].strip()

    try:
        data = json.loads(clean)
        if isinstance(data, dict):
            return data, None
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            return data[0], None
    except Exception:
        pass

    first_brace = clean.find("{")
    last_brace = clean.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = clean[first_brace:last_brace + 1]
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data, None
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                return data[0], None
        except Exception as exc:
            return None, f"JSON parsing error: {exc}"

    return None, "Root JSON structure must be an object/dict"


def validate_patch_security(patch_text: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Check that a proposed unified diff does not target absolute paths or perform path traversal."""
    if not patch_text or not patch_text.strip():
        return True, None

    for line in patch_text.splitlines():
        if line.startswith(("--- ", "+++ ")):
            path_part = line[4:].strip().split("\t", 1)[0].strip()
            # Strip a/ or b/ prefixes standard in git diffs
            if path_part.startswith(("a/", "b/")):
                path_part = path_part[2:]

            # Reject /dev/null if used as deletion, which is safe
            if path_part == "/dev/null":
                continue

            # Check absolute path
            if path_part.startswith("/") or path_part.startswith("\\"):
                return False, f"Unsafe absolute path in patch header: '{line}'"
            if len(path_part) >= 2 and path_part[1] == ":":
                return False, f"Unsafe Windows drive absolute path in patch header: '{line}'"

            # Check traversal
            if ".." in path_part.replace("\\", "/").split("/"):
                return False, f"Unsafe path traversal ('..') detected in patch: '{line}'"

    return True, None


def validate_and_parse_ai_response(
    raw_response_text: str,
    dependency_id: str,
    valid_evidence_ids: Set[str],
    provider_id: str,
    model_id: str,
    prompt_version: str,
    generated_at_utc: str,
    request_id: Optional[str] = None,
) -> Tuple[bool, Optional[str], Optional[RecommendationRecord]]:
    """Strictly validate AI output and assemble RecommendationRecord.
    
    Returns (is_valid, validation_error_message, recommendation_record).
    """
    data, json_err = extract_json_from_response(raw_response_text)
    if json_err or not data:
        return False, f"Malformed response: {json_err}", None

    # 1. Validate status
    status_raw = str(data.get("candidate_status", "")).lower()
    valid_statuses = {s.value for s in CandidateStatus}
    if status_raw not in valid_statuses:
        return False, f"Unsupported candidate_status: '{status_raw}'. Must be one of {valid_statuses}", None

    # 2. Validate evidence references: MUST exist in valid_evidence_ids
    raw_ev_refs = data.get("evidence_references", [])
    if not isinstance(raw_ev_refs, list):
        return False, "evidence_references must be a list of strings", None

    invalid_refs = [ref for ref in raw_ev_refs if ref not in valid_evidence_ids]
    if invalid_refs:
        return False, f"Response referenced unknown/invented evidence IDs: {invalid_refs}", None

    # 3. Validate patch proposal security
    patch = data.get("optional_patch_proposal")
    is_safe, patch_err = validate_patch_security(patch)
    if not is_safe:
        return False, f"Security validation failed for patch: {patch_err}", None

    # 4. Build migration steps
    migration_steps: List[MigrationStep] = []
    raw_steps = data.get("ordered_migration_steps", [])
    if isinstance(raw_steps, list):
        for idx, s in enumerate(raw_steps, 1):
            if isinstance(s, dict):
                migration_steps.append(
                    MigrationStep(
                        step_number=s.get("step_number", idx),
                        action=str(s.get("action", f"Step {idx}")),
                        description=str(s.get("description", "")),
                        target_file=s.get("target_file"),
                        human_review_required=bool(s.get("human_review_required", True)),
                    )
                )

    # 5. Build suggested tests
    suggested_tests: List[SuggestedTest] = []
    raw_tests = data.get("suggested_tests", [])
    if isinstance(raw_tests, list):
        for idx, t in enumerate(raw_tests, 1):
            if isinstance(t, dict):
                suggested_tests.append(
                    SuggestedTest(
                        test_id=str(t.get("test_id", f"sug-chk-{idx}")),
                        objective=str(t.get("objective", "Validate migration")),
                        relation_to_usage=str(t.get("relation_to_usage", "Observed usage validation")),
                        suggested_profile=str(t.get("suggested_profile", "pytest-default")),
                        preconditions=t.get("preconditions", []),
                        expected_signal=str(t.get("expected_signal", "Passing exit code")),
                    )
                )

    # 6. Build ProposedReplacement
    proposed_replacement = ProposedReplacement(
        status=status_raw,
        distribution_name=data.get("replacement_distribution"),
        specifier=data.get("replacement_specifier"),
        rationale=str(data.get("rationale", "No rationale provided.")),
        candidate_validation_status="NOT_VERIFIED",
    )

    # 7. Build Provenance strictly as AI_RECOMMENDATION
    provenance = AiProvenance(
        provider=provider_id,
        model_id=model_id,
        inference_method="hosted_google_ai_studio" if "google" in provider_id else "test_fixture",
        prompt_version=prompt_version,
        generated_at_utc=generated_at_utc,
        evidence_references=raw_ev_refs,
        recommendation_status=status_raw,
        request_id=request_id,
        terms_url="https://ai.google.dev/terms",
        provenance_kind=ProvenanceKind.AI_RECOMMENDATION,
    )

    rec_record = RecommendationRecord(
        dependency_id=dependency_id,
        proposed_replacement=proposed_replacement,
        migration_steps=migration_steps,
        api_differences=data.get("api_differences", []),
        suggested_tests=suggested_tests,
        compatibility_concerns=data.get("compatibility_concerns", []),
        open_concerns_limitations=data.get("open_concerns_limitations", []),
        patch_proposal=patch,
        provenance=provenance,
    )

    return True, None, rec_record
