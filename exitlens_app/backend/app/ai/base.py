"""AI provider interface definition for ExitLens."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.schemas.capsule import DependencyDetails, UsageLocation
from app.schemas.evidence import EvidenceRecord
from app.schemas.recommendation import RecommendationRecord
from app.schemas.risk import RiskIndicator


class BaseAiProvider(ABC):
    """Abstract interface for AI migration recommendation providers."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Return unique provider identifier (e.g. 'google_ai_studio', 'test_fixture')."""
        pass

    @property
    @abstractmethod
    def configured_model(self) -> str:
        """Return configured model identifier."""
        pass

    @abstractmethod
    async def generate_migration_plan(
        self,
        evidence_bundle: List[EvidenceRecord],
        dependency_record: DependencyDetails,
        runtime_context: Optional[Dict[str, Any]] = None,
        test_profile_context: Optional[Dict[str, Any]] = None,
        risks: Optional[List[RiskIndicator]] = None,
        usages: Optional[List[UsageLocation]] = None,
        request_id: Optional[str] = None,
        **kwargs: Any,
    ) -> RecommendationRecord:
        """Formulate structured migration recommendation grounded strictly in observed facts."""
        pass

    async def generate_recommendation(
        self,
        dependency: DependencyDetails,
        risks: List[RiskIndicator],
        usages: List[UsageLocation],
        evidence_snippets: List[EvidenceRecord],
        target_python: str,
        request_id: Optional[str] = None,
    ) -> RecommendationRecord:
        """Backward-compatible delegation to generate_migration_plan."""
        return await self.generate_migration_plan(
            evidence_bundle=evidence_snippets,
            dependency_record=dependency,
            runtime_context={"target_python": target_python},
            risks=risks,
            usages=usages,
            request_id=request_id,
        )

    async def generate_batch_migration_plans(
        self,
        flagged_dependencies: List[Any],
        runtime_context: Optional[Dict[str, Any]] = None,
        test_profile_context: Optional[Dict[str, Any]] = None,
        evidence_index: Optional[Dict[str, Any]] = None,
        analysis_id: Optional[str] = None,
    ) -> Dict[str, RecommendationRecord]:
        """Formulate recommendations for a batch of dependencies."""
        results: Dict[str, RecommendationRecord] = {}
        for item in flagged_dependencies:
            dep_id, dep, dep_risks, dep_usages, ev_refs = item
            ev_bundle = [evidence_index[eid] for eid in ev_refs if eid in evidence_index] if evidence_index else []
            rec = await self.generate_migration_plan(
                evidence_bundle=ev_bundle,
                dependency_record=dep,
                runtime_context=runtime_context,
                test_profile_context=test_profile_context,
                risks=dep_risks,
                usages=dep_usages,
                dependency_id=dep_id,
                analysis_id=analysis_id,
            )
            results[dep_id] = rec
        return results
