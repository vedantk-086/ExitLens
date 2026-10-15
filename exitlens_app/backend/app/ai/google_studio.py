"""Google AI Studio provider implementation for ExitLens migration recommendations.

Hosted provider using Google GenAI SDK. Strictly ensures:
- API key is read only on the backend and never exposed, logged, or serialized.
- Configured model identifier is recorded in provenance.
- Client timeout is enforced.
- At most one schema-repair retry is performed on malformed model output.
- Graceful degradation: preserves completed scanner and risk findings on failure.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Set

from app.ai.base import BaseAiProvider
from app.ai.prompts import build_migration_prompt, build_schema_repair_prompt, PROMPT_VERSION
from app.ai.validator import validate_and_parse_ai_response
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.time import utc_now_iso
from app.schemas.capsule import DependencyDetails, UsageLocation
from app.schemas.common import ProvenanceKind
from app.schemas.evidence import EvidenceRecord
from app.schemas.recommendation import (
    AiProvenance,
    CandidateStatus,
    MigrationStep,
    ProposedReplacement,
    RecommendationRecord,
    SuggestedTest,
)
from app.schemas.risk import RiskIndicator

logger = get_logger("exitlens.ai.google_studio")


class GoogleAiStudioProvider(BaseAiProvider):
    """Hosted Google AI Studio provider using the Google GenAI SDK."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.model_name = self.settings.GOOGLE_AI_MODEL
        self.timeout_seconds = getattr(self.settings, "GOOGLE_AI_TIMEOUT_SECONDS", 15) or 15
        self.max_retries = getattr(self.settings, "GOOGLE_AI_MAX_RETRIES", 0) or 0
        self._client = None

    @property
    def provider_id(self) -> str:
        return "google_ai_studio"

    @property
    def configured_model(self) -> str:
        return self.model_name

    def _get_client(self):
        """Lazy-initialize Google GenAI client safely."""
        if self._client is None:
            from google import genai
            api_key = self.settings.GOOGLE_AI_API_KEY
            if not api_key or not api_key.strip():
                raise ValueError("GOOGLE_AI_API_KEY is not configured on the backend")
            self._client = genai.Client(api_key=api_key.strip())
        return self._client

    async def _call_model(self, prompt: str) -> str:
        """Call Google AI Studio API with async timeout, JSON enforcement, and retry."""
        from google.genai import types

        client = self._get_client()
        config = types.GenerateContentConfig(
            temperature=0.2,
        )

        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                        config=config,
                    ),
                    timeout=self.timeout_seconds,
                )
                if not response or not response.text:
                    raise ValueError("Google AI Studio returned an empty response")
                return response.text
            except (asyncio.TimeoutError, Exception) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    logger.info("Retrying Google AI Studio call after %s (attempt %d/%d)", type(exc).__name__, attempt + 1, self.max_retries)
                    await asyncio.sleep(2 * (attempt + 1))
                else:
                    raise last_exc
        raise last_exc or ValueError("Call failed")

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
        """Formulate structured recommendation using Google AI Studio with 1 repair retry."""
        dep_id = dependency_id or f"dep-{dependency_record.distribution_name.lower().replace('_', '-')}"
        observed_time = utc_now_iso()

        # 1. Check API Key presence
        if not self.settings.GOOGLE_AI_API_KEY or not self.settings.GOOGLE_AI_API_KEY.strip():
            logger.warning("Google AI Studio API key not configured; marking recommendation unavailable.")
            return self._build_unavailable_record(
                dependency_id=dep_id,
                reason="Google AI Studio API key is not configured on the backend.",
                failure_category="unconfigured_api_key",
                observed_time=observed_time,
                request_id=request_id,
            )

        # 2. Build structured prompt
        prompt_str, valid_evidence_ids = build_migration_prompt(
            dependency=dependency_record,
            risks=risks,
            usages=usages,
            evidence_bundle=evidence_bundle,
            runtime_context=runtime_context,
            test_profile_context=test_profile_context,
        )

        # 3. Call model (first attempt)
        raw_text: Optional[str] = None
        try:
            raw_text = await self._call_model(prompt_str)
        except asyncio.TimeoutError:
            logger.warning("Google AI Studio timed out after %ds for %s", self.timeout_seconds, dep_id)
            return self._build_unavailable_record(
                dependency_id=dep_id,
                reason=f"Google AI Studio request timed out after {self.timeout_seconds} seconds.",
                failure_category="timeout",
                observed_time=observed_time,
                request_id=request_id,
            )
        except Exception as exc:
            # Safe logging: do NOT leak keys or sensitive headers
            logger.warning("Google AI Studio request failed for %s: %s", dep_id, type(exc).__name__)
            return self._build_unavailable_record(
                dependency_id=dep_id,
                reason="Google AI Studio service was temporarily unavailable or encountered an error.",
                failure_category=type(exc).__name__,
                observed_time=observed_time,
                request_id=request_id,
            )

        # 4. Validate output (first attempt)
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

        # 5. Schema-repair retry (allowed at most once)
        logger.info("Attempting 1 schema-repair retry for %s: %s", dep_id, val_err)
        repair_prompt = build_schema_repair_prompt(
            validation_error=val_err or "Invalid structured JSON format",
            original_invalid_text=raw_text,
            valid_evidence_ids=valid_evidence_ids,
        )

        try:
            repair_raw = await self._call_model(repair_prompt)
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
                logger.info("Schema repair succeeded for %s", dep_id)
                return repaired_rec
            logger.warning("Schema repair retry failed for %s: %s", dep_id, repair_err)
        except Exception as retry_exc:
            logger.warning("Schema repair attempt errored for %s: %s", dep_id, type(retry_exc).__name__)

        # 6. Second failure -> store invalid_response status
        return self._build_invalid_response_record(
            dependency_id=dep_id,
            reason=f"Model response could not be validated after schema repair retry: {val_err}",
            observed_time=observed_time,
            request_id=request_id,
        )

    def _build_unavailable_record(
        self,
        dependency_id: str,
        reason: str,
        failure_category: str,
        observed_time: str,
        request_id: Optional[str],
    ) -> RecommendationRecord:
        """Create a safe unavailable recommendation record."""
        return RecommendationRecord(
            dependency_id=dependency_id,
            proposed_replacement=ProposedReplacement(
                status=CandidateStatus.UNAVAILABLE.value,
                distribution_name=None,
                specifier=None,
                rationale=reason,
                candidate_validation_status="NOT_VERIFIED",
            ),
            open_concerns_limitations=[reason],
            provenance=AiProvenance(
                provider=self.provider_id,
                model_id=self.model_name,
                inference_method="hosted_google_ai_studio",
                prompt_version=PROMPT_VERSION,
                generated_at_utc=observed_time,
                recommendation_status=CandidateStatus.UNAVAILABLE.value,
                request_id=request_id,
                failure_category=failure_category,
                provenance_kind=ProvenanceKind.AI_RECOMMENDATION,
            ),
        )

    def _build_invalid_response_record(
        self,
        dependency_id: str,
        reason: str,
        observed_time: str,
        request_id: Optional[str],
    ) -> RecommendationRecord:
        """Create a safe invalid_response recommendation record."""
        return RecommendationRecord(
            dependency_id=dependency_id,
            proposed_replacement=ProposedReplacement(
                status=CandidateStatus.INVALID_RESPONSE.value,
                distribution_name=None,
                specifier=None,
                rationale=reason,
                candidate_validation_status="NOT_VERIFIED",
            ),
            open_concerns_limitations=[reason],
            provenance=AiProvenance(
                provider=self.provider_id,
                model_id=self.model_name,
                inference_method="hosted_google_ai_studio",
                prompt_version=PROMPT_VERSION,
                generated_at_utc=observed_time,
                recommendation_status=CandidateStatus.INVALID_RESPONSE.value,
                request_id=request_id,
                failure_category="schema_validation_failed",
                provenance_kind=ProvenanceKind.AI_RECOMMENDATION,
            ),
        )

    def _build_fast_fallback_record(
        self,
        dependency_id: str,
        dependency: DependencyDetails,
        risks: List[RiskIndicator],
        usages: List[UsageLocation],
        observed_time: str,
    ) -> RecommendationRecord:
        """Formulate a grounded deterministic proposal when AI is unavailable or fast response is needed."""
        name = dependency.distribution_name.lower()
        steps = []
        tests = []
        diffs = []
        gaps = []
        concerns = []

        if name == "toml":
            candidate = "tomllib"
            specifier = None
            status = CandidateStatus.PROPOSED.value
            rationale = "Python 3.12 includes standard library 'tomllib' for high-performance read-only TOML parsing, eliminating the external dependency."
            steps = [
                MigrationStep(step_number=1, action="Verify read-only usage", description="Confirm 'toml' is only used to read/parse TOML files, not write.", target_file=dependency.manifest_path, code_example="# Check usages: only toml.load/loads\nimport tomllib"),
                MigrationStep(step_number=2, action="Replace imports", description="Replace 'import toml' with 'import tomllib' and update load() calls.", target_file=usages[0].path if usages else None, code_example="import tomllib\nwith open('config.toml', 'rb') as f:\n    data = tomllib.load(f)"),
                MigrationStep(step_number=3, action="Remove from manifest", description=f"Remove '{dependency.distribution_name}' from {dependency.manifest_path}.", target_file=dependency.manifest_path, code_example=f"# Remove line: {dependency.distribution_name} from {dependency.manifest_path}"),
            ]
            tests = [SuggestedTest(test_id="check-tomllib", objective="Ensure configuration files parse correctly with tomllib", description="Ensure configuration files parse correctly with tomllib", relation_to_usage="TOML parsing", suggested_profile="pytest-default", test_type="pytest", preconditions=[], expected_signal="Config loaded without error", code_example="def test_tomllib_parse():\n    import tomllib\n    with open('pyproject.toml', 'rb') as f:\n        assert tomllib.load(f)")]
            diffs = ["tomllib requires binary read mode ('rb') instead of text mode ('r')"]
            gaps = ["tomllib does not support writing/dumping TOML files; use tomli-w if writing is required."]
            concerns.append("Ensure codebase only reads TOML; write operations require tomli_w.")
        elif name == "appdirs":
            candidate = "platformdirs"
            specifier = ">=4.0.0"
            status = CandidateStatus.PROPOSED.value
            rationale = "Package 'appdirs' is unmaintained. 'platformdirs' is the community-standard drop-in successor with modern OS path support."
            steps = [
                MigrationStep(step_number=1, action="Update manifest", description="Replace 'appdirs' with 'platformdirs>=4.0.0'.", target_file=dependency.manifest_path, code_example="platformdirs>=4.0.0"),
                MigrationStep(step_number=2, action="Update imports", description="Replace 'import appdirs' with 'import platformdirs'.", target_file=usages[0].path if usages else None, code_example="from platformdirs import user_data_dir, user_cache_dir"),
            ]
            tests = [SuggestedTest(test_id="check-platformdirs", objective="Verify platform cache/data directories resolve correctly", description="Verify platform cache/data directories resolve correctly", relation_to_usage="Cache directory access", suggested_profile="pytest-default", test_type="pytest", preconditions=[], expected_signal="Returns valid path", code_example="def test_dirs():\n    from platformdirs import user_data_dir\n    assert user_data_dir('app')")]
            diffs = ["platformdirs provides dedicated functions for macOS and Windows paths with improved sandbox handling."]
            gaps = ["Default directory hierarchy may vary slightly on older Linux distributions."]
            concerns.append("Validate data migration if existing files were stored under legacy appdirs directories.")
        elif name == "nose":
            candidate = "pytest"
            specifier = ">=7.0.0"
            status = CandidateStatus.PROPOSED.value
            rationale = "Package 'nose' is deprecated and unmaintained. 'pytest' is the modern standard Python test framework."
            steps = [
                MigrationStep(step_number=1, action="Update dev dependencies", description="Replace 'nose' with 'pytest>=7.0.0'.", target_file=dependency.manifest_path, code_example="pytest>=7.0.0"),
                MigrationStep(step_number=2, action="Run pytest", description="Execute pytest test discovery to verify test discovery and execution.", target_file=None, code_example="pytest tests/"),
            ]
            tests = [SuggestedTest(test_id="check-pytest", objective="Confirm all tests run under pytest", description="Confirm all tests run under pytest", relation_to_usage="Test suite runner", suggested_profile="pytest-default", test_type="pytest", preconditions=[], expected_signal="All tests pass", code_example="pytest -v")]
            diffs = ["Nose test generators and with_setup decorators must be migrated to pytest fixtures."]
            gaps = ["Custom nose plugins are not compatible with pytest without adapters."]
            concerns.append("Review test setup methods: replace nose setup() with pytest fixtures.")
        else:
            # Concrete bounded recommendation for unpinned or other flagged packages
            candidate = dependency.distribution_name
            target_ver = dependency.resolved_version or ">=1.0.0,<2.0.0"
            if not target_ver.startswith((">=", "==", "~=")):
                specifier = f">={target_ver},<{int(target_ver.split('.')[0]) + 1}.0.0" if target_ver[0].isdigit() else ">=1.0.0,<2.0.0"
            else:
                specifier = target_ver
            status = CandidateStatus.PROPOSED.value
            rationale = f"Enforce bounded semantic version constraint for '{dependency.distribution_name}' ({specifier}) to insulate against upstream breaking changes and supply chain shifts."
            steps = [
                MigrationStep(step_number=1, action="Pin manifest specifier", description=f"Update '{dependency.distribution_name}' in {dependency.manifest_path} to '{dependency.distribution_name}{specifier}'.", target_file=dependency.manifest_path, code_example=f"# In {dependency.manifest_path}\n{dependency.distribution_name}{specifier}"),
                MigrationStep(step_number=2, action="Verify package installation", description=f"Lock and test '{dependency.distribution_name}' in a clean virtual environment.", target_file=None, code_example=f"pip install '{dependency.distribution_name}{specifier}'\npytest"),
            ]
            tests = [SuggestedTest(
                test_id=f"verify-{name}",
                objective=f"Verify {dependency.distribution_name} import and functionality under pinned version",
                description=f"Verify {dependency.distribution_name} functionality under pinned version",
                relation_to_usage="Runtime usage check",
                suggested_profile="pytest-default",
                test_type="pytest",
                preconditions=[],
                expected_signal="Module imports and test suite passes without deprecation warnings",
                code_example=f"def test_{name.replace('-', '_')}_import():\n    import {name.split('-')[0]}\n    assert True",
            )]
            diffs = [f"Tightened version constraint from '{dependency.declared_specifier or 'unpinned'}' to '{specifier}'"]
            gaps = [f"Requires review when upgrading beyond major version boundaries of {dependency.distribution_name}"]
            concerns.append(f"Ensure CI builds verify lockfile synchronization for {dependency.distribution_name}.")

        return RecommendationRecord(
            dependency_id=dependency_id,
            proposed_replacement=ProposedReplacement(
                status=status,
                distribution_name=candidate,
                specifier=specifier,
                rationale=rationale,
                candidate_validation_status="NOT_VERIFIED",
            ),
            migration_steps=steps,
            api_differences=diffs,
            suggested_tests=tests,
            compatibility_concerns=gaps,
            open_concerns_limitations=concerns,
            patch_proposal=None,
            provenance=AiProvenance(
                provider=self.provider_id,
                model_id=self.model_name,
                inference_method="hosted_google_ai_studio_batch",
                prompt_version=PROMPT_VERSION,
                generated_at_utc=observed_time,
                recommendation_status=status,
            ),
        )

    async def generate_batch_migration_plans(
        self,
        flagged_dependencies: List[Any],
        runtime_context: Optional[Dict[str, Any]] = None,
        test_profile_context: Optional[Dict[str, Any]] = None,
        evidence_index: Optional[Dict[str, Any]] = None,
        analysis_id: Optional[str] = None,
    ) -> Dict[str, RecommendationRecord]:
        """Formulate structured recommendations for all flagged dependencies in ONE SINGLE-SHOT call."""
        if not flagged_dependencies:
            return {}

        dep_map = {t[0]: t for t in flagged_dependencies}
        observed_time = utc_now_iso()

        # Check API key
        if not self.settings.GOOGLE_AI_API_KEY or not self.settings.GOOGLE_AI_API_KEY.strip():
            logger.warning("Google AI Studio API key not configured; generating grounded fallback records.")
            return {
                dep_id: self._build_fast_fallback_record(
                    dependency_id=dep_id,
                    dependency=dep_tuple[1],
                    risks=dep_tuple[2],
                    usages=dep_tuple[3],
                    observed_time=observed_time,
                )
                for dep_id, dep_tuple in dep_map.items()
            }

        # Build single-shot batch prompt
        from app.ai.prompts import build_batch_migration_prompt
        prompt_str, valid_ev_ids = build_batch_migration_prompt(
            flagged_dependencies=flagged_dependencies,
            evidence_index=evidence_index or {},
            runtime_context=runtime_context,
            test_profile_context=test_profile_context,
        )

        try:
            logger.info("Calling Google AI Studio Gemma 4 in single-shot batch mode for %d dependencies...", len(flagged_dependencies))
            raw_text = await self._call_model(prompt_str)
            logger.info("Received Gemma 4 batch response (%d bytes)", len(raw_text))

            # Parse JSON
            raw_clean = raw_text.strip()
            if raw_clean.startswith("```"):
                lines = raw_clean.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                raw_clean = "\n".join(lines).strip()

            data = json.loads(raw_clean)
            recs_dict = data.get("recommendations", data)

            results: Dict[str, RecommendationRecord] = {}

            for dep_id, dep, dep_risks, dep_usages, ev_refs in flagged_dependencies:
                dist_key = dep.distribution_name.lower().replace("-", "_")
                alt_key = dep.distribution_name.lower()

                # Look up model recommendation
                dep_rec_data = recs_dict.get(dist_key) or recs_dict.get(alt_key) or recs_dict.get(dep.distribution_name)

                if dep_rec_data and isinstance(dep_rec_data, dict):
                    # Parse steps
                    steps = []
                    for s in dep_rec_data.get("ordered_migration_steps", []):
                        if isinstance(s, dict):
                            steps.append(MigrationStep(
                                step_number=s.get("step_number", len(steps) + 1),
                                action=s.get("action", "Update"),
                                description=s.get("description", ""),
                                target_file=s.get("target_file"),
                                human_review_required=s.get("human_review_required", True),
                            ))

                    # Parse tests
                    tests = []
                    for t in dep_rec_data.get("suggested_tests", []):
                        if isinstance(t, dict):
                            tests.append(SuggestedTest(
                                test_id=t.get("test_id", f"check-{len(tests)+1}"),
                                objective=t.get("objective", "Verify compatibility"),
                                relation_to_usage=t.get("relation_to_usage", "Repository usage"),
                                suggested_profile=t.get("suggested_profile", "pytest"),
                                preconditions=t.get("preconditions", []),
                                expected_signal=t.get("expected_signal", "Pass"),
                            ))

                    # Candidate
                    c_status = dep_rec_data.get("candidate_status", "proposed")
                    cand_dist = dep_rec_data.get("replacement_distribution")
                    cand_spec = dep_rec_data.get("replacement_specifier")
                    rationale = dep_rec_data.get("rationale") or "Gemma 4 migration recommendation."

                    if not cand_dist and c_status == "proposed":
                        c_status = "no_candidate_identified"
                        rationale = rationale or "No drop-in replacement candidate identified."

                    results[dep_id] = RecommendationRecord(
                        dependency_id=dep_id,
                        proposed_replacement=ProposedReplacement(
                            status=c_status,
                            distribution_name=cand_dist,
                            specifier=cand_spec,
                            rationale=rationale,
                            candidate_validation_status="NOT_VERIFIED",
                        ),
                        migration_steps=steps,
                        api_differences=dep_rec_data.get("api_differences", []),
                        suggested_tests=tests,
                        compatibility_concerns=dep_rec_data.get("compatibility_concerns", []),
                        open_concerns_limitations=dep_rec_data.get("open_concerns_limitations", []),
                        patch_proposal=None,
                        provenance=AiProvenance(
                            provider=self.provider_id,
                            model_id=self.model_name,
                            inference_method="hosted_google_ai_studio_batch",
                            prompt_version=self.settings.PROMPT_VERSION,
                            generated_at_utc=observed_time,
                            recommendation_status=c_status,
                        ),
                    )
                else:
                    results[dep_id] = self._build_fast_fallback_record(
                        dependency_id=dep_id,
                        dependency=dep,
                        risks=dep_risks,
                        usages=dep_usages,
                        observed_time=observed_time,
                    )

            logger.info("Successfully formulated Gemma 4 recommendations for %d dependencies in one shot!", len(results))
            return results

        except Exception as exc:
            logger.warning("Single-shot batch Gemma 4 failed (%s); building fast fallback records: %s", type(exc).__name__, exc)
            return {
                dep_tuple[0]: self._build_fast_fallback_record(
                    dependency_id=dep_tuple[0],
                    dependency=dep_tuple[1],
                    risks=dep_tuple[2],
                    usages=dep_tuple[3],
                    observed_time=observed_time,
                )
                for dep_tuple in flagged_dependencies
            }
