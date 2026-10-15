"""Analysis orchestration service.

Executes the end-to-end repository dependency migration analysis pipeline:
validate repository → scan → usage mapping → risk assessment → recommendations → capsule generation

Guarantees:
- Decoupled from API routes: business logic lives entirely within services.
- Never executes repository code during scanning or analysis.
- Graceful degradation: if AI inference is unavailable or fails, scan findings and risk
  indicators are preserved, and the run transitions to completed_with_warnings.
- All 9 required capsule sections are populated honestly for every flagged dependency.
- Capsule JSON and Markdown deliverables are generated from the single canonical model.
- Supports regenerating recommendations for selected dependency IDs without re-scanning.
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from app.ai import BaseAiProvider, get_ai_provider
from app.capsule.completeness import validate_capsule_completeness
from app.capsule.renderer import render_capsule_markdown
from app.core.config import Settings, get_settings
from app.core.errors import (
    ModelUnavailableError,
    NotFoundError,
    StateConflictError,
    ValidationError,
)
from app.core.ids import generate_uuid
from app.core.logging import get_logger
from app.core.paths import validate_repository_path
from app.core.time import utc_now_iso
from app.risk.engine import RiskEngine
from app.scanner.git_cloner import safe_disposable_clone
from app.scanner.mapping import map_import_to_distribution, normalize_package_name
from app.scanner.scanner import Scanner
from app.schemas.analysis import AnalysisRecord
from app.schemas.capsule import (
    CapsuleDependencyRecord,
    CapsuleSummary,
    CompatibilityGap,
    DependencyDetails,
    DependencyExitCapsule,
    RepositoryScope,
    ToolInfo,
    UsageLocation,
)
from app.schemas.common import AnalysisStatus, ProvenanceKind
from app.schemas.evidence import EvidenceRecord
from app.schemas.recommendation import (
    AiProvenance,
    CandidateStatus,
    MigrationStep,
    ProposedReplacement,
    RecommendationRecord,
    SuggestedTest,
)
from app.schemas.repository import RepositoryKind
from app.schemas.risk import RiskIndicator
from app.services.analysis_service import AnalysisService

logger = get_logger("exitlens.orchestrator")


class OrchestrationService:
    """Orchestrates multi-stage dependency migration analysis pipelines."""

    def __init__(
        self,
        analysis_service: Optional[AnalysisService] = None,
        scanner: Optional[Scanner] = None,
        risk_engine: Optional[RiskEngine] = None,
        ai_provider: Optional[BaseAiProvider] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.analysis_service = analysis_service or AnalysisService(settings=self.settings)
        self.scanner = scanner or Scanner(settings=self.settings)
        self.risk_engine = risk_engine or RiskEngine(target_python_version="3.12")
        self.ai_provider = ai_provider or get_ai_provider(settings=self.settings)

    async def run_pipeline(self, analysis_id: str) -> AnalysisRecord:
        """Run the full end-to-end analysis pipeline synchronously or in background."""
        logger.info("Starting pipeline execution for analysis %s", analysis_id)
        record = self.analysis_service.get_analysis(analysis_id)

        # ---------------------------------------------------------------------
        # 1. Validate Repository Input & Clone If Needed
        # ---------------------------------------------------------------------
        self.analysis_service.update_stage(
            analysis_id,
            AnalysisStatus.VALIDATING_REPOSITORY,
            progress_percent=5,
            message="Validating repository input and security constraints...",
        )

        if record.repository.kind == RepositoryKind.GIT_URL:
            try:
                with safe_disposable_clone(
                    record.repository.value,
                    git_ref=record.repository.git_ref,
                    timeout_seconds=self.settings.COMMAND_TIMEOUT_SECONDS,
                    enable_public_clone=True,
                ) as (repo_path, revision):
                    return await self._execute_pipeline(
                        analysis_id=analysis_id,
                        record=record,
                        repo_path=repo_path,
                        resolved_revision=revision,
                    )
            except Exception as exc:
                self.analysis_service.record_error(analysis_id, f"Git clone failed: {exc}")
                raise
        else:
            try:
                allowed_roots = self.settings.get_canonical_allowed_roots()
                repo_path = validate_repository_path(
                    record.repository.value,
                    allowed_roots=allowed_roots,
                )
            except Exception as exc:
                self.analysis_service.record_error(analysis_id, f"Repository validation failed: {exc}")
                raise

            return await self._execute_pipeline(
                analysis_id=analysis_id,
                record=record,
                repo_path=repo_path,
                resolved_revision=None,
            )

    async def _execute_pipeline(
        self,
        analysis_id: str,
        record: AnalysisRecord,
        repo_path: Path,
        resolved_revision: Optional[str] = None,
    ) -> AnalysisRecord:
        """Execute pipeline stages against a validated local or disposable clone directory."""
        # ---------------------------------------------------------------------
        # 2. Scanning & Usage Mapping
        # ---------------------------------------------------------------------
        self.analysis_service.update_stage(
            analysis_id,
            AnalysisStatus.SCANNING,
            progress_percent=20,
            message="Scanning manifests, lockfiles, and project configurations...",
        )
        try:
            allowed_roots = [repo_path] if record.repository.kind == RepositoryKind.GIT_URL else None
            scan_result = await self.scanner.run_full_scan(
                repo_path=repo_path,
                exclude_paths=record.options.exclude_paths,
                include_tests=record.options.include_tests,
                allowed_roots=allowed_roots,
            )
        except Exception as exc:
            self.analysis_service.record_error(analysis_id, f"Scanning failed: {exc}")
            raise

        # Save discovered evidence
        evidence = scan_result.evidence
        self.analysis_service.save_evidence(analysis_id, evidence)

        # Record non-fatal scanner warnings
        for w in scan_result.warnings:
            self.analysis_service.record_warning(analysis_id, w)

        # Advance through usage mapping
        self.analysis_service.update_stage(
            analysis_id,
            AnalysisStatus.MAPPING_USAGE,
            progress_percent=40,
            message=f"Mapped usages across {scan_result.file_count} files.",
        )

        dependencies = scan_result.dependencies
        usages = scan_result.usages

        # ---------------------------------------------------------------------
        # 3. Assessing Risk
        # ---------------------------------------------------------------------
        self.analysis_service.update_stage(
            analysis_id,
            AnalysisStatus.ASSESSING_RISK,
            progress_percent=60,
            message="Evaluating deterministic maintenance risk rules...",
        )
        all_risk_indicators = self.risk_engine.assess_risks(
            dependencies=dependencies,
            usages=usages,
            evidence=evidence,
        )

        # Map risks and usages to dependencies
        evidence_index = {ev.evidence_id: ev for ev in evidence}
        flagged_dep_dict: Dict[str, Tuple[str, DependencyDetails, List[RiskIndicator], List[UsageLocation], Set[str]]] = {}

        for idx, dep in enumerate(dependencies, 1):
            dep_norm = normalize_package_name(dep.distribution_name)
            dep_id = f"dep-{dep_norm}"

            # Match risks associated specifically with this dependency
            if hasattr(self.risk_engine, "assess_for_dependency"):
                dep_risks = self.risk_engine.assess_for_dependency(
                    dependency=dep,
                    all_dependencies=dependencies,
                    usages=usages,
                    evidence=evidence,
                )
            else:
                dep_risks = [
                    r for r in all_risk_indicators
                    if dep_norm in r.title.lower()
                ]

            # Match usages specifically for this dependency
            dep_usages = []
            for u in usages:
                mod = ""
                if u.pattern:
                    parts = u.pattern.split()
                    if len(parts) >= 2:
                        mod = parts[1].split(".")[0].strip()
                elif u.import_statement:
                    parts = u.import_statement.split()
                    if len(parts) >= 2:
                        mod = parts[1].split(".")[0].strip()

                mapped_dist, _ = map_import_to_distribution(mod, {dep.distribution_name})
                if mapped_dist and normalize_package_name(mapped_dist) == dep_norm:
                    dep_usages.append(u)
                elif mod and normalize_package_name(mod) == dep_norm:
                    dep_usages.append(u)

            # Collect evidence refs
            ev_refs: Set[str] = set()
            for r in dep_risks:
                ev_refs.update(r.evidence_refs)
            for u in dep_usages:
                if u.evidence_id:
                    ev_refs.add(u.evidence_id)

            # A dependency is flagged if it triggered any risk rule
            if dep_risks:
                if dep_id not in flagged_dep_dict:
                    flagged_dep_dict[dep_id] = (dep_id, dep, list(dep_risks), list(dep_usages), ev_refs)
                else:
                    # Merge multi-manifest declarations of the same package distribution
                    existing_id, existing_dep, existing_risks, existing_usages, existing_ev = flagged_dep_dict[dep_id]
                    # Combine manifests
                    if dep.manifest_path and dep.manifest_path not in existing_dep.manifest_path:
                        combined_manifest = f"{existing_dep.manifest_path}, {dep.manifest_path}"
                        combined_specifier = existing_dep.declared_specifier
                        if dep.declared_specifier and dep.declared_specifier != existing_dep.declared_specifier:
                            combined_specifier = f"{existing_dep.declared_specifier} | {dep.declared_specifier}"
                        combined_dep = existing_dep.model_copy(
                            update={
                                "manifest_path": combined_manifest,
                                "declared_specifier": combined_specifier,
                            }
                        )
                    else:
                        combined_dep = existing_dep

                    # Merge risks without duplicate rule IDs
                    seen_rule_ids = {r.rule_id for r in existing_risks}
                    for r in dep_risks:
                        if r.rule_id not in seen_rule_ids:
                            existing_risks.append(r)
                            seen_rule_ids.add(r.rule_id)

                    # Merge usages without duplicate usage IDs
                    seen_uids = {u.usage_id for u in existing_usages}
                    for u in dep_usages:
                        if u.usage_id not in seen_uids:
                            existing_usages.append(u)
                            seen_uids.add(u.usage_id)

                    existing_ev.update(ev_refs)
                    flagged_dep_dict[dep_id] = (dep_id, combined_dep, existing_risks, existing_usages, existing_ev)

        flagged_dep_records = [
            (d_id, d_dep, d_risks, d_usages, sorted(list(d_ev)))
            for d_id, (d_id, d_dep, d_risks, d_usages, d_ev) in flagged_dep_dict.items()
        ]

        logger.info(
            "Discovered %d dependencies; %d flagged for migration review",
            len(dependencies),
            len(flagged_dep_records),
        )

        # ---------------------------------------------------------------------
        # 4. Generating Recommendations
        # ---------------------------------------------------------------------
        recommendations: Dict[str, RecommendationRecord] = {}
        ai_failure_encountered = False

        if record.options.generate_recommendations and flagged_dep_records:
            self.analysis_service.update_stage(
                analysis_id,
                AnalysisStatus.GENERATING_RECOMMENDATIONS,
                progress_percent=80,
                message=f"Generating Google AI Studio Gemma 4 recommendations for {len(flagged_dep_records)} flagged dependencies...",
            )

            from app.ai.google_studio import GoogleAiStudioProvider
            if isinstance(self.ai_provider, GoogleAiStudioProvider):
                try:
                    recommendations = await self.ai_provider.generate_batch_migration_plans(
                        flagged_dependencies=flagged_dep_records,
                        runtime_context={"python_version": "3.12", "os": "windows"},
                        test_profile_context={"detected_profiles": ["pytest-default", "unittest-discover"]},
                        evidence_index=evidence_index,
                        analysis_id=analysis_id,
                    )
                except Exception as batch_exc:
                    ai_failure_encountered = True
                    logger.warning("Batch recommendation generation error: %s", batch_exc)
                    for dep_tuple in flagged_dep_records:
                        d_id, d_dep = dep_tuple[0], dep_tuple[1]
                        warn_msg = f"AI recommendation unavailable for '{d_dep.distribution_name}': {str(batch_exc)}"
                        self.analysis_service.record_warning(analysis_id, warn_msg)
                        recommendations[d_id] = self._build_unavailable_rec(d_id, d_dep.distribution_name, str(batch_exc))

            if not recommendations:
                sem = asyncio.Semaphore(5)

                async def process_dep(dep_tuple):
                    nonlocal ai_failure_encountered
                    dep_id, dep, dep_risks, dep_usages, ev_refs = dep_tuple
                    async with sem:
                        try:
                            evidence_bundle = [evidence_index[eid] for eid in ev_refs if eid in evidence_index]
                            rec = await self.ai_provider.generate_migration_plan(
                                evidence_bundle=evidence_bundle,
                                dependency_record=dep,
                                runtime_context={"python_version": "3.12", "os": "windows"},
                                test_profile_context={"detected_profiles": ["pytest-default", "unittest-discover"]},
                                dependency_id=dep_id,
                                analysis_id=analysis_id,
                                valid_evidence_ids=set(evidence_index.keys()),
                                risks=dep_risks,
                                usages=dep_usages,
                            )
                            return dep_id, rec, None
                        except Exception as ai_exc:
                            ai_failure_encountered = True
                            logger.warning("AI recommendation failed for %s: %s", dep.distribution_name, ai_exc)
                            unavailable_rec = self._build_unavailable_rec(dep_id, dep.distribution_name, str(ai_exc))
                            warn_msg = f"AI recommendation unavailable for '{dep.distribution_name}': {str(ai_exc)}"
                            return dep_id, unavailable_rec, warn_msg

                results = await asyncio.gather(*(process_dep(t) for t in flagged_dep_records))
                for dep_id, rec, warn in results:
                    recommendations[dep_id] = rec
                    if warn:
                        self.analysis_service.record_warning(analysis_id, warn)

        # ---------------------------------------------------------------------
        # 5. Capsule Deliverable Generation
        # ---------------------------------------------------------------------
        capsule_deps: List[CapsuleDependencyRecord] = []
        rec_available_count = 0

        for dep_id, dep, dep_risks, dep_usages, ev_refs in flagged_dep_records:
            rec = recommendations.get(dep_id)
            if rec and rec.proposed_replacement.status == "proposed":
                rec_available_count += 1

            comp_gaps: List[CompatibilityGap] = []
            if rec:
                for gap_idx, diff in enumerate(rec.api_differences, 1):
                    comp_gaps.append(
                        CompatibilityGap(
                            gap_id=f"gap-{dep_id}-{gap_idx:02d}",
                            title=f"API Difference: {diff[:60]}",
                            description=diff,
                            evidence_refs=ev_refs[:2] if ev_refs else [],
                            verified=False,
                        )
                    )
                for gap_idx, concern in enumerate(rec.compatibility_concerns, len(comp_gaps) + 1):
                    comp_gaps.append(
                        CompatibilityGap(
                            gap_id=f"gap-{dep_id}-{gap_idx:02d}",
                            title=f"Compatibility Concern: {concern[:60]}",
                            description=concern,
                            evidence_refs=ev_refs[:2] if ev_refs else [],
                            verified=False,
                        )
                    )

            dep_details = DependencyDetails(
                distribution_name=dep.distribution_name,
                name=dep.distribution_name,
                manifest_path=dep.manifest_path,
                declared_specifier=dep.declared_specifier or "",
                declared_version=dep.declared_specifier or "",
                resolved_version=dep.resolved_version,
                package_manager=dep.package_manager,
                dependency_type=dep.dependency_type.value if hasattr(dep.dependency_type, "value") else str(dep.dependency_type),
                runtime_markers=dep.runtime_markers,
                metadata_availability=dep.metadata_availability,
                summary=f"Python dependency declared in {dep.manifest_path}",
            )

            # Enrich risk indicators
            enriched_risks = [
                r.model_copy(update={"signal": r.title, "evidence_ids": list(r.evidence_refs)})
                for r in dep_risks
            ]

            # Enrich usage locations
            enriched_usages = [
                u.model_copy(update={
                    "file_path": u.path,
                    "import_name": u.import_statement or u.symbol or "",
                    "excerpt": u.pattern or u.import_statement or "",
                })
                for u in dep_usages
            ]

            # Enrich proposed replacement
            if rec and rec.proposed_replacement:
                rep = rec.proposed_replacement
                enriched_replacement = rep.model_copy(update={
                    "candidate_distribution": rep.candidate_distribution or rep.distribution_name,
                    "candidate_specifier": rep.candidate_specifier or rep.specifier,
                })
            else:
                enriched_replacement = ProposedReplacement(
                    status=CandidateStatus.NO_CANDIDATE_IDENTIFIED.value,
                    distribution_name=None,
                    candidate_distribution=None,
                    specifier=None,
                    candidate_specifier=None,
                    rationale="No migration candidate requested or identified.",
                    candidate_validation_status="NOT_VERIFIED",
                )

            # Enrich migration steps
            enriched_steps = []
            if rec and rec.migration_steps:
                for s in rec.migration_steps:
                    code_ex = s.code_example or (f"# Action on {s.target_file}\n# {s.description}" if s.target_file else None)
                    enriched_steps.append(s.model_copy(update={"code_example": code_ex}))

            # Enrich suggested tests
            enriched_tests = []
            if rec and rec.suggested_tests:
                for t in rec.suggested_tests:
                    enriched_tests.append(t.model_copy(update={
                        "description": t.description or t.objective,
                        "test_type": t.test_type or t.suggested_profile,
                        "code_example": t.code_example or f"# Expected signal:\n# {t.expected_signal}",
                    }))

            # Ensure compatibility gaps have severity
            enriched_gaps = []
            for g in comp_gaps:
                enriched_gaps.append(g.model_copy(update={
                    "severity": g.severity or "medium",
                    "evidence_ids": list(g.evidence_refs),
                }))

            capsule_dep = CapsuleDependencyRecord(
                dependency_id=dep_id,
                name=dep.distribution_name,
                dependency_details=dep_details,
                risk_indicators=enriched_risks,
                usage_locations=enriched_usages,
                proposed_replacement=enriched_replacement,
                migration_steps=enriched_steps,
                suggested_tests=enriched_tests,
                executed_test_results=[],  # Populated during verification phase
                compatibility_gaps=enriched_gaps,
                open_concerns_limitations=rec.open_concerns_limitations if rec else [],
                evidence_refs=ev_refs,
            )
            capsule_deps.append(capsule_dep)

        summary = CapsuleSummary(
            dependencies_discovered=len(dependencies),
            dependencies_flagged=len(flagged_dep_records),
            recommendations_available=rec_available_count,
            baseline_checks=0,
            replacement_checks=0,
            checks_passed=0,
            checks_failed=0,
            checks_skipped_or_unverified=0,
        )

        capsule = DependencyExitCapsule(
            capsule_id=f"cap-{generate_uuid()[:12]}",
            analysis_id=analysis_id,
            generated_at_utc=utc_now_iso(),
            tool=ToolInfo(name="ExitLens", version="0.1.0"),
            repository=RepositoryScope(
                source=record.repository.value,
                revision=resolved_revision or record.repository.git_ref,
                python_version="3.12",
                analysis_scope="all_discovered",
            ),
            summary=summary,
            dependencies=capsule_deps,
            ai_provenance=AiProvenance(
                provider=self.settings.GEMMA_PROVIDER,
                model_id=self.settings.GOOGLE_AI_MODEL,
                inference_method="hosted_google_ai_studio" if self.settings.GEMMA_PROVIDER == "google_ai_studio" else "test_fixture",
                prompt_version=self.settings.PROMPT_VERSION,
                generated_at_utc=utc_now_iso(),
            ),
            evidence=evidence,
            known_limitations=[
                "Static AST analysis cannot resolve dynamic __import__ or sys.modules lookups.",
                "Model-generated suggestions require human review before verification.",
            ],
        )

        # Validate capsule completeness before persistence
        valid_ev_ids = {ev.evidence_id for ev in evidence}
        validate_capsule_completeness(capsule, valid_evidence_ids=valid_ev_ids, raise_on_error=True)

        # Save canonical JSON and Markdown capsules
        self.analysis_service.save_capsule(capsule)

        # Determine terminal state
        final_record = self.analysis_service.get_analysis(analysis_id)
        if ai_failure_encountered or final_record.warnings:
            final_stage = AnalysisStatus.COMPLETED_WITH_WARNINGS
            msg = "Analysis completed with warnings."
        else:
            final_stage = AnalysisStatus.COMPLETED
            msg = "Analysis pipeline completed successfully."

        final_record = self.analysis_service.update_stage(
            analysis_id=analysis_id,
            stage=final_stage,
            progress_percent=100,
            message=msg,
        )
        logger.info("Pipeline completed for %s with stage %s", analysis_id, final_stage.value)
        return final_record

    async def regenerate_recommendations(
        self,
        analysis_id: str,
        dependency_ids: List[str],
        force_regenerate: bool = False,
    ) -> List[RecommendationRecord]:
        """Regenerate recommendations for selected dependency IDs without re-scanning."""
        logger.info("Regenerating recommendations for %s (deps=%s)", analysis_id, dependency_ids)
        capsule = self.analysis_service.get_capsule(analysis_id)
        evidence = self.analysis_service.get_evidence(analysis_id)
        evidence_index = {ev.evidence_id: ev for ev in evidence}

        deps_by_id = {d.dependency_id: d for d in capsule.dependencies}
        unknown_ids = [did for did in dependency_ids if did not in deps_by_id]
        if unknown_ids:
            raise NotFoundError(
                f"Dependency IDs {unknown_ids} not found in analysis '{analysis_id}'.",
                code="DEPENDENCY_NOT_FOUND",
            )

        regenerated: List[RecommendationRecord] = []
        updated_capsule_deps = list(capsule.dependencies)

        for dep_id in dependency_ids:
            cap_dep = deps_by_id[dep_id]
            dep_details = cap_dep.dependency_details
            evidence_bundle = [evidence_index[eid] for eid in cap_dep.evidence_refs if eid in evidence_index]

            rec = await self.ai_provider.generate_migration_plan(
                evidence_bundle=evidence_bundle,
                dependency_record=dep_details,
                runtime_context={"python_version": "3.12", "os": "windows"},
                test_profile_context={"detected_profiles": ["pytest-default", "unittest-discover"]},
                dependency_id=dep_id,
                analysis_id=analysis_id,
                valid_evidence_ids=set(evidence_index.keys()),
                risks=cap_dep.risk_indicators,
                usages=cap_dep.usage_locations,
            )
            regenerated.append(rec)

            # Update the in-memory capsule record
            cap_dep.proposed_replacement = rec.proposed_replacement
            cap_dep.migration_steps = rec.migration_steps
            cap_dep.suggested_tests = rec.suggested_tests
            cap_dep.open_concerns_limitations = rec.open_concerns_limitations

        # Update capsule summary
        rec_count = sum(1 for d in updated_capsule_deps if d.proposed_replacement.status == "proposed")
        capsule.summary.recommendations_available = rec_count
        capsule.dependencies = updated_capsule_deps

        # Persist updated capsule
        self.analysis_service.save_capsule(capsule)
        return regenerated

    def _build_unavailable_rec(self, dep_id: str, dist_name: str, reason: str) -> RecommendationRecord:
        """Create a safe unavailable recommendation record for failed AI generation."""
        return RecommendationRecord(
            dependency_id=dep_id,
            proposed_replacement=ProposedReplacement(
                status=CandidateStatus.UNAVAILABLE.value,
                distribution_name=None,
                specifier=None,
                rationale=f"AI recommendation provider unavailable: {reason}",
                candidate_validation_status="NOT_VERIFIED",
            ),
            migration_steps=[],
            api_differences=[],
            suggested_tests=[],
            compatibility_concerns=[],
            open_concerns_limitations=["AI provider was unavailable or timed out during recommendation generation."],
            patch_proposal=None,
            provenance=AiProvenance(
                provider=self.settings.GEMMA_PROVIDER,
                model_id=self.settings.GOOGLE_AI_MODEL,
                inference_method="hosted_google_ai_studio",
                prompt_version=self.settings.PROMPT_VERSION,
                generated_at_utc=utc_now_iso(),
                recommendation_status=CandidateStatus.UNAVAILABLE.value,
                failure_category="provider_unavailable",
            ),
        )
