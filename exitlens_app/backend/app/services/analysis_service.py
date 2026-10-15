"""Analysis lifecycle orchestration and management service.

Implements the single source of truth for:
- Repository input validation
- Unique UUID-based analysis creation
- Preserving stage transitions through all 11 lifecycle states
- Warning and error tracking
- Evidence, capsule, and verification persistence
"""

from typing import List, Optional

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, ValidationError
from app.core.ids import generate_uuid
from app.core.logging import get_logger
from app.core.paths import validate_git_url, validate_repository_path
from app.core.time import utc_now_iso
from app.capsule.renderer import render_capsule_markdown
from app.schemas.analysis import (
    AnalysisRecord,
    ArtifactAvailability,
    ProgressSummary,
)
from app.schemas.capsule import CapsuleSummary, DependencyExitCapsule
from app.schemas.common import AnalysisStatus
from app.schemas.evidence import EvidenceRecord
from app.schemas.repository import (
    AnalysisOptions,
    CreateAnalysisRequest,
    RepositoryInput,
    RepositoryKind,
)
from app.schemas.verification import VerificationRecord
from app.storage.run_store import FileSystemRunStore

logger = get_logger("exitlens.service")


class AnalysisService:
    """Service interface for managing analysis lifecycles and run data."""

    def __init__(
        self,
        store: Optional[FileSystemRunStore] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.store = store or FileSystemRunStore(settings=self.settings)

    def create_analysis(self, request: CreateAnalysisRequest) -> AnalysisRecord:
        """Create and persist a new analysis run with a generated UUID4."""
        analysis_id = generate_uuid()
        now_iso = utc_now_iso()

        # Validate local repository paths if kind is local_path
        if request.repository.kind == RepositoryKind.LOCAL_PATH:
            allowed_roots = self.settings.get_canonical_allowed_roots()
            canonical_repo = validate_repository_path(request.repository.value, allowed_roots=allowed_roots)
            repo_value = canonical_repo.as_posix()
        else:
            repo_value = validate_git_url(
                request.repository.value,
                enable_public_clone=self.settings.ENABLE_PUBLIC_HTTPS_GIT_CLONE,
            )

        validated_repo = RepositoryInput(
            kind=request.repository.kind,
            value=repo_value,
            git_ref=request.repository.git_ref,
        )

        record = AnalysisRecord(
            analysis_id=analysis_id,
            status=AnalysisStatus.QUEUED,
            stage=AnalysisStatus.VALIDATING_REPOSITORY,
            created_at_utc=now_iso,
            updated_at_utc=now_iso,
            repository=validated_repo,
            options=request.options or AnalysisOptions(),
            progress=ProgressSummary(
                stage=AnalysisStatus.VALIDATING_REPOSITORY,
                percent=5,
                message="Repository input validated.",
            ),
            summary=CapsuleSummary(),
            artifacts=ArtifactAvailability(has_analysis_json=True),
        )

        self.store.save_analysis(record)
        logger.info("Created analysis run %s (target=%s)", analysis_id, repo_value)
        return record

    def get_analysis(self, analysis_id: str) -> AnalysisRecord:
        """Load an analysis record by ID, raising NotFoundError if missing."""
        record = self.store.load_analysis(analysis_id)
        if record is None:
            raise NotFoundError(f"Analysis '{analysis_id}' was not found.")

        # Refresh artifact flags based on filesystem state
        run_dir = self.store.get_run_dir(analysis_id)
        verif_dir = run_dir / "verification"
        verif_count = len(list(verif_dir.glob("*.json"))) if verif_dir.is_dir() else 0

        record.artifacts.has_analysis_json = (run_dir / "analysis.json").is_file()
        record.artifacts.has_evidence_json = (run_dir / "evidence.json").is_file()
        record.artifacts.has_capsule_json = (run_dir / "capsule.json").is_file()
        record.artifacts.has_capsule_md = (run_dir / "capsule.md").is_file()
        record.artifacts.has_capsule_pdf = (run_dir / "capsule.pdf").is_file()
        record.artifacts.verification_count = verif_count

        return record

    def list_analyses(self) -> List[AnalysisRecord]:
        """Return all persisted analysis runs."""
        return self.store.list_analyses()

    def update_stage(
        self,
        analysis_id: str,
        stage: AnalysisStatus,
        progress_percent: int = 0,
        message: str = "",
    ) -> AnalysisRecord:
        """Advance the analysis stage and persist progress updates."""
        record = self.get_analysis(analysis_id)
        now_iso = utc_now_iso()

        record.stage = stage
        record.updated_at_utc = now_iso
        record.progress.stage = stage
        record.progress.percent = max(0, min(100, progress_percent))
        if message:
            record.progress.message = message

        # Terminal state transitions
        if stage in (AnalysisStatus.COMPLETED, AnalysisStatus.COMPLETED_WITH_WARNINGS, AnalysisStatus.FAILED):
            record.status = stage
            record.completed_at_utc = now_iso

        self.store.save_analysis(record)
        logger.info("Analysis %s transitioned to stage '%s' (%d%%)", analysis_id, stage.value, progress_percent)
        return record

    def record_warning(self, analysis_id: str, warning_message: str) -> AnalysisRecord:
        """Record a non-fatal coverage or scan warning."""
        record = self.get_analysis(analysis_id)
        clean_msg = warning_message.strip()
        if clean_msg and clean_msg not in record.warnings:
            record.warnings.append(clean_msg)
            record.updated_at_utc = utc_now_iso()
            self.store.save_analysis(record)
            logger.warning("Analysis %s warning: %s", analysis_id, clean_msg)
        return record

    def record_error(self, analysis_id: str, error_message: str) -> AnalysisRecord:
        """Record an error and mark analysis as failed."""
        record = self.get_analysis(analysis_id)
        clean_msg = error_message.strip()
        if clean_msg not in record.errors:
            record.errors.append(clean_msg)
        now_iso = utc_now_iso()
        record.status = AnalysisStatus.FAILED
        record.stage = AnalysisStatus.FAILED
        record.updated_at_utc = now_iso
        record.completed_at_utc = now_iso
        record.progress.stage = AnalysisStatus.FAILED
        record.progress.message = f"Error: {clean_msg}"
        self.store.save_analysis(record)
        logger.error("Analysis %s failed: %s", analysis_id, clean_msg)
        return record

    # -------------------------------------------------------------------------
    # Evidence Management
    # -------------------------------------------------------------------------

    def save_evidence(self, analysis_id: str, items: List[EvidenceRecord]) -> List[EvidenceRecord]:
        """Save evidence items to evidence.json and update analysis artifact flag."""
        self.store.save_evidence(analysis_id, items)
        record = self.get_analysis(analysis_id)
        record.artifacts.has_evidence_json = True
        record.updated_at_utc = utc_now_iso()
        self.store.save_analysis(record)
        return items

    def get_evidence(self, analysis_id: str) -> List[EvidenceRecord]:
        """Load evidence records for an analysis run."""
        # Ensure analysis exists
        self.get_analysis(analysis_id)
        items = self.store.load_evidence(analysis_id)
        return items if items is not None else []

    # -------------------------------------------------------------------------
    # Capsule Deliverable Management
    # -------------------------------------------------------------------------

    def save_capsule(
        self,
        capsule: DependencyExitCapsule,
        markdown_content: Optional[str] = None,
    ) -> DependencyExitCapsule:
        """Persist canonical capsule deliverable in both JSON and Markdown formats."""
        # Ensure Markdown rendering matches canonical schema if not explicitly provided
        md_text = markdown_content if markdown_content is not None else render_capsule_markdown(capsule)
        self.store.save_capsule(capsule, markdown_content=md_text)

        # Update analysis summary and artifact flags
        record = self.get_analysis(capsule.analysis_id)
        record.summary = capsule.summary
        record.artifacts.has_capsule_json = True
        record.artifacts.has_capsule_md = True
        record.artifacts.has_capsule_pdf = True
        record.updated_at_utc = utc_now_iso()
        self.store.save_analysis(record)

        return capsule

    def get_capsule(self, analysis_id: str) -> DependencyExitCapsule:
        """Load the JSON capsule deliverable."""
        self.get_analysis(analysis_id)
        capsule = self.store.load_capsule(analysis_id)
        if capsule is None:
            raise NotFoundError(f"Capsule for analysis '{analysis_id}' has not been generated.")
        return capsule

    def get_capsule_markdown(self, analysis_id: str) -> str:
        """Load the Markdown capsule deliverable."""
        self.get_analysis(analysis_id)
        md = self.store.load_capsule_md(analysis_id)
        if md is None:
            raise NotFoundError(f"Capsule markdown for analysis '{analysis_id}' has not been generated.")
        return md

    def get_capsule_pdf(self, analysis_id: str) -> bytes:
        """Load or dynamically generate the PDF capsule deliverable as raw bytes."""
        self.get_analysis(analysis_id)
        capsule = self.get_capsule(analysis_id)
        from app.capsule.pdf_renderer import build_capsule_pdf_bytes
        pdf_bytes = build_capsule_pdf_bytes(capsule)
        self.store.save_capsule_pdf(analysis_id, pdf_bytes)
        return pdf_bytes

    # -------------------------------------------------------------------------
    # Verification Record Management
    # -------------------------------------------------------------------------

    def save_verification(self, verification: VerificationRecord) -> VerificationRecord:
        """Save verification session record and update analysis metrics."""
        self.store.save_verification(verification)
        record = self.get_analysis(verification.analysis_id)
        record.artifacts.verification_count += 1
        record.updated_at_utc = utc_now_iso()
        self.store.save_analysis(record)
        return verification

    def get_verification(self, analysis_id: str, verification_id: str) -> VerificationRecord:
        """Load single verification record."""
        self.get_analysis(analysis_id)
        v = self.store.load_verification(analysis_id, verification_id)
        if v is None:
            raise NotFoundError(f"Verification '{verification_id}' not found for analysis '{analysis_id}'.")
        return v

    def list_verifications(self, analysis_id: str) -> List[VerificationRecord]:
        """List all verification records for an analysis."""
        self.get_analysis(analysis_id)
        return self.store.list_verifications(analysis_id)
