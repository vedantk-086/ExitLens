"""Risk engine interface definition for ExitLens."""

from abc import ABC, abstractmethod
from typing import List

from app.schemas.capsule import DependencyDetails, UsageLocation
from app.schemas.evidence import EvidenceRecord
from app.schemas.risk import RiskIndicator


class BaseRiskEngine(ABC):
    """Abstract risk engine evaluating maintenance indicators from observed facts."""

    @property
    @abstractmethod
    def rule_set_version(self) -> str:
        """Return the stable version identifier for this risk ruleset."""
        pass

    @abstractmethod
    def assess_risks(
        self,
        dependencies: List[DependencyDetails],
        usages: List[UsageLocation],
        evidence: List[EvidenceRecord],
    ) -> List[RiskIndicator]:
        """Apply deterministic, versioned rules to produce explainable risk findings across all dependencies."""
        pass

    @abstractmethod
    def assess_for_dependency(
        self,
        dependency: DependencyDetails,
        all_dependencies: List[DependencyDetails],
        usages: List[UsageLocation],
        evidence: List[EvidenceRecord],
    ) -> List[RiskIndicator]:
        """Produce risk indicators specifically associated with a single dependency."""
        pass

