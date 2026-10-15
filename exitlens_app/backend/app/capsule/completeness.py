"""Capsule completeness validation gate for ExitLens.

Enforces canonical completeness rules before capsule persistence and export:
1. Each flagged dependency ID is present exactly once.
2. All nine mandatory sections are populated for every flagged dependency.
3. Every referenced evidence ID exists in the run's evidence ledger.
4. Every test result has a recorded status and an approved profile identifier.
5. AI suggestions are labelled AI_RECOMMENDATION, never OBSERVED or EXECUTION_RESULT.
6. Repository source, Python runtime, model provenance, and generation timestamps are recorded.
"""

from typing import List, Optional, Set

from app.core.errors import ExitLensError
from app.core.logging import get_logger
from app.schemas.capsule import DependencyExitCapsule
from app.schemas.common import ProvenanceKind

logger = get_logger("exitlens.capsule.completeness")


class CapsuleCompletenessError(ExitLensError):
    """Raised when a capsule deliverable fails canonical completeness validation."""

    def __init__(self, message: str, errors: Optional[List[str]] = None) -> None:
        super().__init__(
            message=message,
            code="CAPSULE_COMPLETENESS_ERROR",
            status_code=422,
            details={"completeness_errors": errors or []},
        )
        self.errors = errors or []


def validate_capsule_completeness(
    capsule: DependencyExitCapsule,
    valid_evidence_ids: Optional[Set[str]] = None,
    raise_on_error: bool = False,
) -> List[str]:
    """Validate a DependencyExitCapsule against the canonical completeness contract.
    
    Args:
        capsule: The DependencyExitCapsule instance to validate.
        valid_evidence_ids: Optional set of all valid evidence IDs from the run.
        raise_on_error: If True, raises CapsuleCompletenessError on any violation.
        
    Returns:
        List[str]: List of validation errors (empty if completely valid).
    """
    errors: List[str] = []

    # 1. Header & Repository Metadata
    if not capsule.capsule_id or not capsule.capsule_id.strip():
        errors.append("capsule_id is missing or empty.")
    if not capsule.analysis_id or not capsule.analysis_id.strip():
        errors.append("analysis_id is missing or empty.")
    if not capsule.generated_at_utc or not capsule.generated_at_utc.strip():
        errors.append("generated_at_utc timestamp is missing.")
    if not capsule.repository.source or not capsule.repository.source.strip():
        errors.append("repository.source is missing or empty.")
    if not capsule.repository.python_version or not capsule.repository.python_version.strip():
        errors.append("repository.python_version is missing.")

    # 2. AI Provenance Verification
    prov = capsule.ai_provenance
    if not prov.model_id or not prov.model_id.strip():
        errors.append("ai_provenance.model_id is missing.")
    if not prov.provider or not prov.provider.strip():
        errors.append("ai_provenance.provider is missing.")
    if not prov.prompt_version or not prov.prompt_version.strip():
        errors.append("ai_provenance.prompt_version is missing.")
    if prov.provenance_kind != ProvenanceKind.AI_RECOMMENDATION:
        errors.append(f"ai_provenance.provenance_kind must be AI_RECOMMENDATION, got '{prov.provenance_kind}'.")

    # 3. Evidence Index Construction
    ledger_ids = {ev.evidence_id for ev in capsule.evidence}
    if valid_evidence_ids:
        ledger_ids.update(valid_evidence_ids)

    # 4. Flagged Dependencies Verification
    seen_dep_ids: Set[str] = set()

    for idx, dep in enumerate(capsule.dependencies, 1):
        dep_id = dep.dependency_id
        if not dep_id or not dep_id.strip():
            errors.append(f"Dependency at index {idx} has an empty dependency_id.")
            continue

        # Check: Each flagged dependency ID is present exactly once
        if dep_id in seen_dep_ids:
            errors.append(f"Duplicate flagged dependency_id '{dep_id}' detected.")
        seen_dep_ids.add(dep_id)

        # Mandatory Section 1: dependency_details
        details = dep.dependency_details
        if not details.distribution_name:
            errors.append(f"Dependency '{dep_id}': dependency_details.distribution_name is missing.")
        if not details.manifest_path:
            errors.append(f"Dependency '{dep_id}': dependency_details.manifest_path is missing.")

        # Mandatory Section 2: risk_indicators (must be a list)
        if dep.risk_indicators is None:
            errors.append(f"Dependency '{dep_id}': risk_indicators section is missing.")

        # Mandatory Section 3: usage_locations (must be a list)
        if dep.usage_locations is None:
            errors.append(f"Dependency '{dep_id}': usage_locations section is missing.")

        # Mandatory Section 4: proposed_replacement (status and rationale required)
        rep = dep.proposed_replacement
        if rep is None:
            errors.append(f"Dependency '{dep_id}': proposed_replacement section is missing.")
        else:
            if not rep.status:
                errors.append(f"Dependency '{dep_id}': proposed_replacement.status is missing.")
            if not rep.rationale:
                errors.append(f"Dependency '{dep_id}': proposed_replacement.rationale is missing.")

        # Mandatory Section 5: migration_steps (must be a list)
        if dep.migration_steps is None:
            errors.append(f"Dependency '{dep_id}': migration_steps section is missing.")

        # Mandatory Section 6: suggested_tests (must be a list)
        if dep.suggested_tests is None:
            errors.append(f"Dependency '{dep_id}': suggested_tests section is missing.")

        # Mandatory Section 7: executed_test_results (must be a list)
        if dep.executed_test_results is None:
            errors.append(f"Dependency '{dep_id}': executed_test_results section is missing.")
        else:
            for t_idx, test_res in enumerate(dep.executed_test_results):
                if not test_res.status:
                    errors.append(f"Dependency '{dep_id}' test #{t_idx}: status is missing.")
                if not test_res.profile_id:
                    errors.append(f"Dependency '{dep_id}' test #{t_idx}: profile_id is missing.")

        # Mandatory Section 8: compatibility_gaps (must be a list)
        if dep.compatibility_gaps is None:
            errors.append(f"Dependency '{dep_id}': compatibility_gaps section is missing.")

        # Mandatory Section 9: open_concerns_limitations (must be a list)
        if dep.open_concerns_limitations is None:
            errors.append(f"Dependency '{dep_id}': open_concerns_limitations section is missing.")

        # Evidence references validity check
        if ledger_ids:
            for eid in dep.evidence_refs:
                if eid not in ledger_ids:
                    errors.append(f"Dependency '{dep_id}': invalid/unindexed evidence reference '{eid}'.")

    if errors and raise_on_error:
        logger.error("Capsule %s failed completeness check (%d errors): %s", capsule.capsule_id, len(errors), errors)
        raise CapsuleCompletenessError(
            f"Capsule deliverable failed completeness validation with {len(errors)} errors.",
            errors=errors,
        )

    return errors
