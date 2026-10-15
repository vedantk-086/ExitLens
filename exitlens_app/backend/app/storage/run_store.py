"""Filesystem-backed storage for ExitLens analysis runs.

Strictly adheres to:
- reports/exitlens/runs/<analysis_id>/
    analysis.json
    evidence.json
    capsule.json
    capsule.md
    verification/<verification_id>.json
- Generated UUID analysis IDs only
- Atomic JSON writes
- Path traversal protection
- Sanitization of secrets and sensitive tokens
- Preservation of warnings and stage transitions
"""

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import Settings, get_settings
from app.core.errors import (
    NotFoundError,
    PathForbiddenError,
    PathTraversalDetectedError,
    ValidationError,
)
from app.core.ids import is_safe_id, is_valid_uuid
from app.core.logging import get_logger
from app.core.paths import atomic_write_file, canonicalize_path, is_safe_subpath
from app.schemas.analysis import AnalysisRecord
from app.schemas.capsule import DependencyExitCapsule
from app.schemas.evidence import EvidenceRecord
from app.schemas.verification import VerificationRecord

logger = get_logger("exitlens.storage")

# Redaction patterns for tokens, keys, passwords
SECRET_PATTERN = re.compile(
    r"(api[_-]?key|token|secret|password|bearer|auth)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?",
    re.IGNORECASE,
)


def redact_sensitive_string(text: str) -> str:
    """Mask obvious secret key patterns in text."""
    if not text or not isinstance(text, str):
        return text
    return SECRET_PATTERN.sub(r"\1=[REDACTED]", text)


def sanitize_dict_for_storage(data: Any) -> Any:
    """Recursively scrub sensitive keys or values before writing to disk."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if any(term in k.lower() for term in ["secret", "password", "token", "api_key", "bearer"]):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_dict_for_storage(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_dict_for_storage(item) for item in data]
    elif isinstance(data, str):
        return redact_sensitive_string(data)
    return data


class FileSystemRunStore:
    """Filesystem storage manager for analysis runs."""

    def __init__(self, base_data_dir: Optional[Path] = None, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.base_dir = (base_data_dir or self.settings.get_canonical_data_dir()).resolve()
        self.runs_dir = (self.base_dir / "runs").resolve()
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def validate_analysis_id(self, analysis_id: str) -> str:
        """Enforce that analysis_id is strictly a valid UUID4 string with no traversal characters."""
        clean_id = str(analysis_id).strip()
        if not clean_id:
            raise ValidationError("analysis_id cannot be empty.")
        if ".." in clean_id or "/" in clean_id or "\\" in clean_id or "\x00" in clean_id:
            raise PathTraversalDetectedError(f"Directory traversal detected in analysis_id: '{clean_id}'")
        if not is_valid_uuid(clean_id):
            raise ValidationError(
                f"Invalid analysis_id '{clean_id}'. Analysis IDs must be valid UUID4 strings."
            )
        return clean_id

    def validate_verification_id(self, verification_id: str) -> str:
        """Enforce that verification_id is safe for filenames."""
        clean_id = str(verification_id).strip()
        if not clean_id or not is_safe_id(clean_id):
            raise ValidationError(
                f"Invalid verification_id '{clean_id}'. Must be alphanumeric with hyphens/underscores."
            )
        return clean_id

    def get_run_dir(self, analysis_id: str) -> Path:
        """Resolve and validate the canonical directory for a specific analysis run."""
        clean_id = self.validate_analysis_id(analysis_id)
        run_dir = (self.runs_dir / clean_id).resolve()

        if not is_safe_subpath(run_dir, self.runs_dir):
            raise PathTraversalDetectedError(f"Run directory for '{clean_id}' escapes base storage.")

        return run_dir

    def run_exists(self, analysis_id: str) -> bool:
        """Return True if the run directory and analysis.json exist."""
        try:
            run_dir = self.get_run_dir(analysis_id)
            return (run_dir / "analysis.json").is_file()
        except (ValidationError, PathTraversalDetectedError):
            return False

    # -------------------------------------------------------------------------
    # Analysis Record Persistence (analysis.json)
    # -------------------------------------------------------------------------

    def save_analysis(self, analysis: AnalysisRecord) -> Path:
        """Atomically persist analysis metadata and stage state to analysis.json."""
        run_dir = self.get_run_dir(analysis.analysis_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        target_file = run_dir / "analysis.json"
        raw_dict = analysis.model_dump(mode="json")
        sanitized_dict = sanitize_dict_for_storage(raw_dict)
        json_content = json.dumps(sanitized_dict, indent=2, ensure_ascii=False)

        atomic_write_file(target_file, json_content)
        logger.debug("Saved analysis record to %s (stage=%s)", target_file, analysis.stage.value)
        return target_file

    def load_analysis(self, analysis_id: str) -> Optional[AnalysisRecord]:
        """Load and deserialize analysis.json for the specified run."""
        run_dir = self.get_run_dir(analysis_id)
        target_file = run_dir / "analysis.json"

        if not target_file.is_file():
            return None

        try:
            content = target_file.read_text(encoding="utf-8")
            data = json.loads(content)
            return AnalysisRecord.model_validate(data)
        except Exception as exc:
            logger.error("Failed to load analysis.json for '%s': %s", analysis_id, exc)
            raise

    # -------------------------------------------------------------------------
    # Evidence Persistence (evidence.json)
    # -------------------------------------------------------------------------

    def save_evidence(self, analysis_id: str, items: List[EvidenceRecord]) -> Path:
        """Atomically persist evidence ledger to evidence.json with relative paths."""
        run_dir = self.get_run_dir(analysis_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        # Enforce relative paths on evidence items
        sanitized_items = []
        for item in items:
            item_dict = item.model_dump(mode="json")
            # Ensure path is forward-slash and not absolute
            p_str = item_dict.get("path", "").replace("\\", "/")
            if p_str.startswith("/") or ":" in p_str:
                # Strip leading drive or absolute slash
                parts = Path(p_str).parts
                p_str = "/".join(parts[1:]) if len(parts) > 1 else parts[0]
            item_dict["path"] = p_str
            sanitized_items.append(sanitize_dict_for_storage(item_dict))

        target_file = run_dir / "evidence.json"
        json_content = json.dumps(sanitized_items, indent=2, ensure_ascii=False)
        atomic_write_file(target_file, json_content)
        logger.debug("Saved %d evidence records to %s", len(items), target_file)
        return target_file

    def load_evidence(self, analysis_id: str) -> Optional[List[EvidenceRecord]]:
        """Load evidence ledger from evidence.json."""
        run_dir = self.get_run_dir(analysis_id)
        target_file = run_dir / "evidence.json"

        if not target_file.is_file():
            return None

        try:
            content = target_file.read_text(encoding="utf-8")
            data = json.loads(content)
            if not isinstance(data, list):
                return []
            return [EvidenceRecord.model_validate(item) for item in data]
        except Exception as exc:
            logger.error("Failed to load evidence.json for '%s': %s", analysis_id, exc)
            raise

    # -------------------------------------------------------------------------
    # Capsule Persistence (capsule.json and capsule.md)
    # -------------------------------------------------------------------------

    def save_capsule(
        self,
        capsule: DependencyExitCapsule,
        markdown_content: Optional[str] = None,
    ) -> Tuple[Path, Path]:
        """Atomically persist capsule deliverable in both JSON and Markdown formats."""
        run_dir = self.get_run_dir(capsule.analysis_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        # 1. capsule.json
        json_file = run_dir / "capsule.json"
        raw_dict = capsule.model_dump(mode="json")
        sanitized_dict = sanitize_dict_for_storage(raw_dict)
        json_content = json.dumps(sanitized_dict, indent=2, ensure_ascii=False)
        atomic_write_file(json_file, json_content)

        # 2. capsule.md
        md_file = run_dir / "capsule.md"
        md_str = markdown_content if markdown_content is not None else self._default_markdown_summary(capsule)
        atomic_write_file(md_file, md_str)

        # 3. capsule.pdf
        try:
            from app.capsule.pdf_renderer import save_capsule_pdf
            pdf_file = run_dir / "capsule.pdf"
            save_capsule_pdf(capsule, pdf_file)
        except Exception as pdf_err:
            logger.warning("Could not generate capsule.pdf for '%s': %s", capsule.analysis_id, pdf_err)

        logger.debug("Saved capsule.json, capsule.md, and capsule.pdf to %s", run_dir)
        return json_file, md_file

    def save_capsule_pdf(self, analysis_id: str, pdf_bytes: bytes) -> Path:
        """Write raw PDF bytes to capsule.pdf in run storage directory."""
        run_dir = self.get_run_dir(analysis_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        pdf_file = run_dir / "capsule.pdf"
        pdf_file.write_bytes(pdf_bytes)
        return pdf_file

    def load_capsule_pdf(self, analysis_id: str) -> Optional[bytes]:
        """Load capsule.pdf deliverable as raw bytes, generating on demand if needed."""
        run_dir = self.get_run_dir(analysis_id)
        target_file = run_dir / "capsule.pdf"

        if target_file.is_file():
            return target_file.read_bytes()

        capsule = self.load_capsule(analysis_id)
        if capsule:
            try:
                from app.capsule.pdf_renderer import save_capsule_pdf
                save_capsule_pdf(capsule, target_file)
                if target_file.is_file():
                    return target_file.read_bytes()
            except Exception as pdf_err:
                logger.warning("Failed on-demand generation of capsule.pdf for '%s': %s", analysis_id, pdf_err)
        return None

    def load_capsule(self, analysis_id: str) -> Optional[DependencyExitCapsule]:
        """Load capsule.json deliverable."""
        run_dir = self.get_run_dir(analysis_id)
        target_file = run_dir / "capsule.json"

        if not target_file.is_file():
            return None

        try:
            content = target_file.read_text(encoding="utf-8")
            data = json.loads(content)
            return DependencyExitCapsule.model_validate(data)
        except Exception as exc:
            logger.error("Failed to load capsule.json for '%s': %s", analysis_id, exc)
            raise

    def load_capsule_md(self, analysis_id: str) -> Optional[str]:
        """Load capsule.md content as plain string."""
        run_dir = self.get_run_dir(analysis_id)
        target_file = run_dir / "capsule.md"

        if not target_file.is_file():
            return None

        return target_file.read_text(encoding="utf-8")

    # -------------------------------------------------------------------------
    # Verification Persistence (verification/<verification_id>.json)
    # -------------------------------------------------------------------------

    def save_verification(self, verification: VerificationRecord) -> Path:
        """Atomically persist verification results under verification/<verification_id>.json."""
        run_dir = self.get_run_dir(verification.analysis_id)
        verif_dir = run_dir / "verification"
        verif_dir.mkdir(parents=True, exist_ok=True)

        clean_v_id = self.validate_verification_id(verification.verification_id)
        target_file = verif_dir / f"{clean_v_id}.json"

        raw_dict = verification.model_dump(mode="json")
        sanitized_dict = sanitize_dict_for_storage(raw_dict)
        json_content = json.dumps(sanitized_dict, indent=2, ensure_ascii=False)

        atomic_write_file(target_file, json_content)
        logger.debug("Saved verification record to %s", target_file)
        return target_file

    def load_verification(self, analysis_id: str, verification_id: str) -> Optional[VerificationRecord]:
        """Load a single verification record."""
        run_dir = self.get_run_dir(analysis_id)
        clean_v_id = self.validate_verification_id(verification_id)
        target_file = run_dir / "verification" / f"{clean_v_id}.json"

        if not target_file.is_file():
            return None

        try:
            content = target_file.read_text(encoding="utf-8")
            data = json.loads(content)
            return VerificationRecord.model_validate(data)
        except Exception as exc:
            logger.error("Failed to load verification '%s': %s", verification_id, exc)
            raise

    def list_verifications(self, analysis_id: str) -> List[VerificationRecord]:
        """List all verification records for an analysis run."""
        run_dir = self.get_run_dir(analysis_id)
        verif_dir = run_dir / "verification"
        if not verif_dir.is_dir():
            return []

        records: List[VerificationRecord] = []
        for file in verif_dir.glob("*.json"):
            try:
                content = file.read_text(encoding="utf-8")
                data = json.loads(content)
                records.append(VerificationRecord.model_validate(data))
            except Exception as exc:
                logger.warning("Skipping corrupted verification file %s: %s", file.name, exc)

        return sorted(records, key=lambda r: r.created_at_utc)

    # -------------------------------------------------------------------------
    # Run Listing and Indexing
    # -------------------------------------------------------------------------

    def list_analyses(self) -> List[AnalysisRecord]:
        """Return all persisted analysis runs ordered by creation time descending."""
        records: List[AnalysisRecord] = []
        if not self.runs_dir.is_dir():
            return records

        for run_path in self.runs_dir.iterdir():
            if run_path.is_dir():
                analysis_file = run_path / "analysis.json"
                if analysis_file.is_file():
                    try:
                        content = analysis_file.read_text(encoding="utf-8")
                        record = AnalysisRecord.model_validate(json.loads(content))
                        records.append(record)
                    except Exception as exc:
                        logger.warning("Skipping unreadable analysis in %s: %s", run_path.name, exc)

        return sorted(records, key=lambda r: r.created_at_utc, reverse=True)

    def _default_markdown_summary(self, capsule: DependencyExitCapsule) -> str:
        """Render a readable fallback Markdown summary for the capsule."""
        lines = [
            f"# Dependency Exit Capsule: {capsule.capsule_id}",
            f"",
            f"- **Analysis ID:** `{capsule.analysis_id}`",
            f"- **Generated at:** {capsule.generated_at_utc}",
            f"- **Repository:** `{capsule.repository.source}`",
            f"- **Runtime:** Python {capsule.repository.python_version}",
            f"- **Model:** {capsule.ai_provenance.model_id} ({capsule.ai_provenance.inference_method})",
            f"",
            f"## Summary Metrics",
            f"- Dependencies Discovered: {capsule.summary.dependencies_discovered}",
            f"- Dependencies Flagged: {capsule.summary.dependencies_flagged}",
            f"- Recommendations Available: {capsule.summary.recommendations_available}",
            f"- Baseline Checks: {capsule.summary.baseline_checks}",
            f"- Replacement Checks: {capsule.summary.replacement_checks}",
            f"- Checks Passed: {capsule.summary.checks_passed}",
            f"- Checks Failed: {capsule.summary.checks_failed}",
            f"- Checks Skipped/Unverified: {capsule.summary.checks_skipped_or_unverified}",
            f"",
            f"## Flagged Dependencies ({len(capsule.dependencies)})",
            f"",
        ]

        for dep in capsule.dependencies:
            details = dep.dependency_details
            lines.extend([
                f"### {details.distribution_name} ({details.declared_specifier})",
                f"- **Manifest:** `{details.manifest_path}`",
                f"- **Package Manager:** {details.package_manager}",
                f"- **Proposed Replacement:** {dep.proposed_replacement.distribution_name or 'None'} ({dep.proposed_replacement.status})",
                f"- **Rationale:** {dep.proposed_replacement.rationale}",
                f"- **Risk Indicators:** {len(dep.risk_indicators)}",
                f"- **Usage Locations:** {len(dep.usage_locations)}",
                f"- **Migration Steps:** {len(dep.migration_steps)}",
                f"- **Executed Checks:** {len(dep.executed_test_results)}",
                f"- **Compatibility Gaps:** {len(dep.compatibility_gaps)}",
                f"- **Open Concerns:** {len(dep.open_concerns_limitations)}",
                f"",
            ])

        return "\n".join(lines)
