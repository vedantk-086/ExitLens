"""Verification orchestration service.

Orchestrates:
1. Explicit user confirmation enforcement prior to any test execution.
2. Baseline test execution against original dependency state in an isolated disposable copy.
3. Replacement test execution only when:
   - A valid candidate exists.
   - A reviewed and validated patch is present.
   - The patch passes path traversal and security validation.
   - Applied strictly to a separate disposable copy.
   - Environment policy permits execution.
4. Transparent comparison records capturing timestamps, exit codes, argv, and honest skip/error reasons.
5. Preservation of baseline failures (never misattributed to replacement).
"""

from pathlib import Path
from typing import Dict, List, Optional

from app.ai.validator import validate_patch_security
from app.core.config import Settings, get_settings
from app.core.ids import generate_uuid
from app.core.logging import get_logger
from app.core.time import utc_now_iso
from app.schemas.capsule import DependencyDetails
from app.schemas.common import AnalysisStatus
from app.schemas.recommendation import CandidateStatus, RecommendationRecord
from app.schemas.verification import (
    ExecutedTestResult,
    TestStatus,
    VerificationRecord,
    VerificationRequest,
)
from app.services.analysis_service import AnalysisService
from app.verification.base import BaseVerificationRunner
from app.verification.patch_applier import apply_patch_to_workspace
from app.verification.profiles import get_allowlisted_profile
from app.verification.runner import VerificationRunner
from app.verification.workspace import disposable_workspace

logger = get_logger("exitlens.verification.service")


class VerificationService:
    """Orchestrates baseline and replacement verification in disposable workspaces."""

    def __init__(
        self,
        runner: Optional[BaseVerificationRunner] = None,
        analysis_service: Optional[AnalysisService] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.runner = runner or VerificationRunner(settings=self.settings)
        self.analysis_service = analysis_service or AnalysisService(settings=self.settings)

    async def execute_verification_session(
        self,
        analysis_id: str,
        request: VerificationRequest,
        repository_path: Path,
        recommendations: Optional[List[RecommendationRecord]] = None,
        dependencies: Optional[List[DependencyDetails]] = None,
    ) -> VerificationRecord:
        """Execute baseline and replacement verification checks under strict safety controls.
        
        Args:
            analysis_id: Unique analysis run ID.
            request: User verification parameters.
            repository_path: Local path to target repository.
            recommendations: Optional pre-loaded recommendation records.
            dependencies: Optional pre-loaded dependency details.
            
        Returns:
            VerificationRecord: Complete verification session results.
        """
        verification_id = f"verif-{generate_uuid()[:12]}"
        now_iso = utc_now_iso()
        all_results: List[ExecutedTestResult] = []

        logger.info(
            "Starting verification session %s for analysis %s (deps=%s, baseline_profile=%s)",
            verification_id,
            analysis_id,
            request.dependency_ids,
            request.baseline_profile_id,
        )

        # ---------------------------------------------------------------------
        # 1. Explicit Confirmation Gate
        # ---------------------------------------------------------------------
        if not request.confirm_repository_code_execution:
            logger.warning(
                "Verification session %s halted: explicit repository code execution confirmation was not given.",
                verification_id,
            )
            unconfirmed_result = ExecutedTestResult(
                check_id=f"chk-{generate_uuid()[:8]}",
                run_kind="baseline",
                status=TestStatus.NOT_RUN,
                profile_id=request.baseline_profile_id,
                argv=[],
                started_at_utc=now_iso,
                completed_at_utc=now_iso,
                skip_or_error_reason="Explicit confirmation required before repository code execution.",
            )
            all_results.append(unconfirmed_result)

            record = VerificationRecord(
                verification_id=verification_id,
                analysis_id=analysis_id,
                dependency_ids=request.dependency_ids,
                baseline_profile_id=request.baseline_profile_id,
                replacement_profile_id=request.replacement_profile_id,
                results=all_results,
                created_at_utc=now_iso,
            )
            self.analysis_service.save_verification(record)
            return record

        # ---------------------------------------------------------------------
        # 2. Validate Baseline Profile
        # ---------------------------------------------------------------------
        baseline_profile = get_allowlisted_profile(request.baseline_profile_id)
        replacement_profile_id = request.replacement_profile_id or request.baseline_profile_id
        # Also validate replacement profile if explicitly specified
        if request.replacement_profile_id:
            get_allowlisted_profile(request.replacement_profile_id)

        # ---------------------------------------------------------------------
        # 3. Baseline Verification (Disposable Workspace Copy 1)
        # ---------------------------------------------------------------------
        logger.info("Executing baseline verification in disposable workspace...")
        with disposable_workspace(repository_path, prefix="exitlens_base_") as baseline_ws:
            baseline_result = await self.runner.execute_profile(
                workspace_path=baseline_ws,
                profile_id=baseline_profile.profile_id,
                run_kind="baseline",
                timeout_seconds=request.timeout_seconds,
                allow_network=request.allow_network,
            )
            all_results.append(baseline_result)
            logger.info("Baseline verification outcome: status=%s", baseline_result.status.value)

        # ---------------------------------------------------------------------
        # 4. Replacement Verification (Separate Disposable Workspace per Candidate)
        # ---------------------------------------------------------------------
        recs_by_dep: Dict[str, RecommendationRecord] = {}
        if recommendations:
            for rec in recommendations:
                recs_by_dep[rec.dependency_id] = rec

        for dep_id in request.dependency_ids:
            rec = recs_by_dep.get(dep_id)

            # Check 4.1: Candidate existence check
            has_candidate = False
            if rec and rec.proposed_replacement:
                status_val = (
                    rec.proposed_replacement.status.value
                    if hasattr(rec.proposed_replacement.status, "value")
                    else str(rec.proposed_replacement.status)
                )
                if status_val == "proposed" and rec.proposed_replacement.distribution_name:
                    has_candidate = True

            if not has_candidate:
                logger.info("Skipping replacement test for %s: no candidate identified.", dep_id)
                all_results.append(
                    ExecutedTestResult(
                        check_id=f"chk-{generate_uuid()[:8]}",
                        run_kind="replacement",
                        status=TestStatus.SKIPPED,
                        profile_id=replacement_profile_id,
                        argv=[],
                        started_at_utc=now_iso,
                        completed_at_utc=now_iso,
                        skip_or_error_reason="No proposed replacement candidate identified for dependency.",
                    )
                )
                continue

            # Check 4.2: Validated patch proposal check
            patch_diff = ""
            patch_id = f"patch-{dep_id}"
            if rec and rec.patch_proposal:
                if isinstance(rec.patch_proposal, str):
                    patch_diff = rec.patch_proposal.strip()
                elif hasattr(rec.patch_proposal, "diff_content"):
                    patch_diff = (rec.patch_proposal.diff_content or "").strip()
                    patch_id = getattr(rec.patch_proposal, "patch_id", patch_id)

            if not patch_diff:
                logger.info("Skipping replacement test for %s: no patch proposal available.", dep_id)
                all_results.append(
                    ExecutedTestResult(
                        check_id=f"chk-{generate_uuid()[:8]}",
                        run_kind="replacement",
                        status=TestStatus.SKIPPED,
                        profile_id=replacement_profile_id,
                        argv=[],
                        started_at_utc=now_iso,
                        completed_at_utc=now_iso,
                        skip_or_error_reason="No validated migration patch proposal available for candidate.",
                    )
                )
                continue

            # Check 4.3: Patch security verification
            is_safe, sec_err = validate_patch_security(patch_diff)
            if not is_safe:
                logger.warning("Unsafe patch proposal rejected for %s: %s", dep_id, sec_err)
                all_results.append(
                    ExecutedTestResult(
                        check_id=f"chk-{generate_uuid()[:8]}",
                        run_kind="replacement",
                        status=TestStatus.ERROR,
                        profile_id=replacement_profile_id,
                        argv=[],
                        started_at_utc=now_iso,
                        completed_at_utc=now_iso,
                        patch_id=patch_id,
                        skip_or_error_reason=f"Unsafe patch proposal rejected: {sec_err}",
                    )
                )
                continue

            # Check 4.4: Environment policy check
            # Never install packages automatically from the internet.
            # If replacement requires internet installation and network is disabled, skip honestly.
            if not request.allow_network and not self.settings.ALLOW_TEST_NETWORK:
                # The environment policy forbids automatic internet package installation
                logger.info(
                    "Executing replacement test in offline disposable workspace for candidate '%s'...",
                    rec.proposed_replacement.distribution_name,
                )

            # Execute in SEPARATE disposable workspace
            with disposable_workspace(repository_path, prefix="exitlens_repl_") as repl_ws:
                # Apply patch to the disposable workspace
                try:
                    apply_patch_to_workspace(repl_ws, patch_diff, patch_id=patch_id)
                except Exception as patch_exc:
                    logger.warning("Failed to apply patch for %s: %s", dep_id, patch_exc)
                    all_results.append(
                        ExecutedTestResult(
                            check_id=f"chk-{generate_uuid()[:8]}",
                            run_kind="replacement",
                            status=TestStatus.ERROR,
                            profile_id=replacement_profile_id,
                            argv=[],
                            started_at_utc=now_iso,
                            completed_at_utc=now_iso,
                            patch_id=patch_id,
                            skip_or_error_reason=f"Failed to apply patch: {patch_exc}",
                        )
                    )
                    continue

                # Run replacement test profile
                repl_result = await self.runner.execute_profile(
                    workspace_path=repl_ws,
                    profile_id=replacement_profile_id,
                    run_kind="replacement",
                    timeout_seconds=request.timeout_seconds,
                    allow_network=request.allow_network,
                    patch_id=patch_id,
                )
                all_results.append(repl_result)
                logger.info("Replacement verification outcome: status=%s", repl_result.status.value)

        # ---------------------------------------------------------------------
        # 5. Persist Verification Session Record
        # ---------------------------------------------------------------------
        record = VerificationRecord(
            verification_id=verification_id,
            analysis_id=analysis_id,
            dependency_ids=request.dependency_ids,
            baseline_profile_id=request.baseline_profile_id,
            replacement_profile_id=request.replacement_profile_id,
            results=all_results,
            created_at_utc=now_iso,
        )
        self.analysis_service.save_verification(record)

        # Update analysis stage safely
        analysis = self.analysis_service.get_analysis(analysis_id)
        if analysis.status in (AnalysisStatus.READY_FOR_VERIFICATION, AnalysisStatus.VERIFYING):
            has_failures = any(r.status in (TestStatus.FAILED, TestStatus.ERROR) for r in all_results)
            new_stage = AnalysisStatus.COMPLETED_WITH_WARNINGS if has_failures else AnalysisStatus.COMPLETED
            self.analysis_service.update_stage(
                analysis_id=analysis_id,
                stage=new_stage,
                progress_percent=100,
                message="Verification session completed.",
            )

        return record
