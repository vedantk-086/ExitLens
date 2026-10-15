"""Versioned prompt builder for ExitLens migration recommendations.

Scoping policy:
- Sends only dependency declarations, observed usages, linked risk indicators, and valid evidence.
- Never sends entire repositories, environment variables, credentials, or secrets.
- Enforces strict anti-hallucination rules regarding evidence IDs and execution status.
"""

import json
from typing import Any, Dict, List, Optional, Set, Tuple


from app.schemas.capsule import DependencyDetails, UsageLocation
from app.schemas.evidence import EvidenceRecord
from app.schemas.risk import RiskIndicator

PROMPT_VERSION = "exitlens-v1"

JSON_SCHEMA_INSTRUCTIONS = """
{
  "candidate_status": "proposed | no_candidate_identified | unavailable | invalid_response",
  "replacement_distribution": "string or null",
  "replacement_specifier": "string or null",
  "rationale": "Evidence-grounded rationale for the proposal or why no replacement exists",
  "api_differences": ["list of notable API discrepancies or import differences"],
  "ordered_migration_steps": [
    {
      "step_number": 1,
      "action": "Short action summary",
      "description": "Step details for developer",
      "target_file": "repository-relative file path or null",
      "human_review_required": true
    }
  ],
  "suggested_tests": [
    {
      "test_id": "suggested-check-1",
      "objective": "Validation objective",
      "relation_to_usage": "How this relates to discovered code usage",
      "suggested_profile": "pytest-unit or similar detected profile",
      "preconditions": ["preconditions"],
      "expected_signal": "Expected outcome"
    }
  ],
  "compatibility_concerns": ["list of known compatibility or behavioral risks"],
  "open_concerns_limitations": ["list of open questions or unknowns"],
  "evidence_references": ["list of evidence_ids strictly from VALID_EVIDENCE_IDS"],
  "optional_patch_proposal": "unified diff string or null"
}
"""


def build_migration_prompt(
    dependency: DependencyDetails,
    risks: Optional[List[RiskIndicator]] = None,
    usages: Optional[List[UsageLocation]] = None,
    evidence_bundle: Optional[List[EvidenceRecord]] = None,
    runtime_context: Optional[Dict[str, Any]] = None,
    test_profile_context: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Set[str]]:
    """Build structured, versioned prompt string and return the set of valid evidence IDs."""
    risks = risks or []
    usages = usages or []
    evidence_bundle = evidence_bundle or []
    runtime_context = runtime_context or {}
    test_profile_context = test_profile_context or {}

    valid_evidence_ids: Set[str] = {ev.evidence_id for ev in evidence_bundle}

    # Format bounded evidence items
    evidence_items = []
    for ev in evidence_bundle:
        evidence_items.append({
            "evidence_id": ev.evidence_id,
            "kind": ev.kind,
            "path": ev.path,
            "line_range": f"{ev.line_start}-{ev.line_end}" if ev.line_start else "file",
            "excerpt": ev.excerpt[:200],
        })

    # Format risk indicators
    risk_items = []
    for r in risks:
        risk_items.append({
            "rule_id": r.rule_id,
            "severity": r.severity.value,
            "title": r.title,
            "explanation": r.explanation,
            "evidence_refs": [ref for ref in r.evidence_refs if ref in valid_evidence_ids],
        })

    # Format usages
    usage_items = []
    for u in usages[:20]:  # Limit to 20 representative usages
        usage_items.append({
            "path": u.path,
            "line_start": u.line_start,
            "symbol": u.symbol,
            "import_statement": u.import_statement,
            "note": u.note,
        })

    prompt_data = {
        "prompt_version": PROMPT_VERSION,
        "instructions": (
            "You are ExitLens AI, a local-first software dependency migration assistant. "
            "Formulate a structured migration recommendation grounded strictly in the provided observed facts.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. State uncertainty explicitly when a replacement or compatibility difference is unknown.\n"
            "2. NEVER invent or hallucinate evidence IDs. Every referenced evidence ID MUST be from the VALID_EVIDENCE_IDS list.\n"
            "3. NEVER claim a step, patch, or test has been executed or verified. (All recommendations are unverified suggestions).\n"
            "4. Do NOT propose arbitrary execution commands or shell commands.\n"
            "5. If proposing a patch, it MUST be formatted as a valid unified diff targeting repository-relative paths only. "
            "NEVER use absolute paths or directory traversal ('../').\n"
            "6. Output MUST be valid JSON strictly adhering to the specified schema."
        ),
        "target_dependency": {
            "distribution_name": dependency.distribution_name,
            "manifest_path": dependency.manifest_path,
            "declared_specifier": dependency.declared_specifier,
            "resolved_version": dependency.resolved_version,
            "package_manager": dependency.package_manager,
            "runtime_markers": dependency.runtime_markers,
        },
        "target_runtime": {
            "python_version": runtime_context.get("target_python", "3.12"),
            "test_profile": test_profile_context.get("profile_id", "detected-python-tests"),
        },
        "deterministic_risk_findings": risk_items,
        "observed_source_usages": usage_items,
        "valid_evidence_items": evidence_items,
        "valid_evidence_ids": sorted(list(valid_evidence_ids)),
        "required_response_schema": JSON_SCHEMA_INSTRUCTIONS,
    }

    prompt_str = (
        f"ExitLens Migration Analysis Request [{PROMPT_VERSION}]\n\n"
        f"{json.dumps(prompt_data, indent=2)}\n\n"
        "Respond with strictly valid JSON only. Do not include markdown code fences or conversational text."
    )

    return prompt_str, valid_evidence_ids


def build_schema_repair_prompt(
    validation_error: str,
    original_invalid_text: str,
    valid_evidence_ids: Set[str],
) -> str:
    """Build single schema-repair retry prompt containing only the error and required format."""
    repair_data = {
        "prompt_version": PROMPT_VERSION,
        "task": "SCHEMA_REPAIR",
        "instruction": (
            "Your previous response failed validation. Correct the specific validation error "
            "and output strictly valid JSON conforming to the schema. Do not output anything else."
        ),
        "validation_error": validation_error,
        "valid_evidence_ids": sorted(list(valid_evidence_ids)),
        "previous_attempt_excerpt": original_invalid_text[:500],
        "required_response_schema": JSON_SCHEMA_INSTRUCTIONS,
    }

    return (
        f"ExitLens Schema Repair Request [{PROMPT_VERSION}]\n\n"
        f"{json.dumps(repair_data, indent=2)}\n\n"
        "Respond with strictly valid JSON only. No markdown fences."
    )


def build_batch_migration_prompt(
    flagged_dependencies: List[Any],
    evidence_index: Dict[str, Any],
    runtime_context: Optional[Dict[str, Any]] = None,
    test_profile_context: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Set[str]]:
    """Build single-shot batch prompt for all flagged dependencies in the repository."""
    all_valid_ev_ids: Set[str] = set()
    dep_payloads = []

    for dep_tuple in flagged_dependencies:
        dep_id, dep, dep_risks, dep_usages, ev_refs = dep_tuple
        dep_valid_ev = set(ev_refs)
        all_valid_ev_ids.update(dep_valid_ev)

        # Usages (compact, up to 2 key usage references)
        usage_items = []
        for u in dep_usages[:2]:
            usage_items.append({
                "path": u.path,
                "lines": f"L{u.line_start}-{u.line_end}" if u.line_start else "file",
                "symbol": u.symbol or "import",
                "evidence_id": u.evidence_id,
            })

        # Risks (up to 2 primary signals)
        risk_items = []
        for r in dep_risks[:2]:
            risk_items.append({
                "rule_id": r.rule_id,
                "severity": r.severity.value,
                "title": r.title,
                "explanation": r.explanation[:90],
            })

        dep_payloads.append({
            "distribution_name": dep.distribution_name,
            "declared_specifier": dep.declared_specifier,
            "resolved_version": dep.resolved_version,
            "manifest_path": dep.manifest_path,
            "package_manager": dep.package_manager,
            "deterministic_risks": risk_items,
            "observed_usages": usage_items,
        })

    prompt_data = {
        "prompt_version": PROMPT_VERSION,
        "task": "BATCH_DEPENDENCY_MIGRATION_ANALYSIS",
        "instructions": (
            "You are ExitLens AI, an expert dependency migration engineer powered by Gemma 4. "
            "Analyze the flagged Python dependencies for modernization and migration in ONE SINGLE SHOT.\n"
            "REQUIREMENTS:\n"
            "- Return a strictly valid JSON object where keys are the lowercase distribution names, and values are the migration plan.\n"
            "- Keep rationale to 1 concise, actionable sentence.\n"
            "- Include at most 2 migration steps and 1 suggested test per package to ensure fast output.\n\n"
            "SCHEMA FOR EACH PACKAGE VALUE:\n"
            "{\n"
            '  "candidate_status": "proposed | no_candidate_identified | unavailable",\n'
            '  "replacement_distribution": "package_name or null",\n'
            '  "replacement_specifier": "version constraint (e.g. >=2.0.0) or null",\n'
            '  "rationale": "One-sentence migration rationale",\n'
            '  "api_differences": ["notable API differences or empty"],\n'
            '  "ordered_migration_steps": [{"step_number": 1, "action": "Action", "description": "Details", "target_file": "path", "human_review_required": true}],\n'
            '  "suggested_tests": [{"test_id": "check-1", "objective": "Verify compatibility", "relation_to_usage": "Usage check", "suggested_profile": "pytest", "preconditions": [], "expected_signal": "pass"}],\n'
            '  "compatibility_concerns": ["caveats or empty"],\n'
            '  "open_concerns_limitations": ["open questions or empty"]\n'
            "}"
        ),
        "target_runtime": {
            "python_version": (runtime_context or {}).get("python_version", "3.12"),
            "os": (runtime_context or {}).get("os", "windows"),
        },
        "flagged_dependencies": dep_payloads,
    }

    prompt_str = (
        f"ExitLens Single-Shot Batch Analysis [{PROMPT_VERSION}]\n\n"
        f"{json.dumps(prompt_data, indent=2)}\n\n"
        "Respond with strictly valid JSON only. Format as a single JSON object mapping distribution_name to recommendation. Do not include markdown code fences or conversational text."
    )
    return prompt_str, all_valid_ev_ids
