"""ExitLens Pydantic domain schemas package."""

from app.schemas.analysis import (
    AnalysisRecord,
    AnalysisStatusResponse,
    ArtifactAvailability,
    ProgressSummary,
)
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
from app.schemas.common import (
    AnalysisStatus,
    ErrorDetail,
    ErrorResponse,
    ProvenanceKind,
)
from app.schemas.evidence import (
    EvidencePackage,
    EvidenceRecord,
)
from app.schemas.health import (
    AiStatus,
    ApiStatus,
    HealthResponse,
    PythonStatus,
    StorageStatus,
)
from app.schemas.recommendation import (
    AiProvenance,
    MigrationStep,
    ProposedReplacement,
    RecommendationRecord,
    SuggestedTest,
)
from app.schemas.repository import (
    AnalysisOptions,
    CreateAnalysisRequest,
    CreateAnalysisResponse,
    RepositoryInput,
    RepositoryKind,
)
from app.schemas.risk import (
    RiskIndicator,
    RiskSeverity,
)
from app.schemas.verification import (
    ExecutedTestResult,
    TestStatus,
    VerificationRecord,
    VerificationRequest,
)

__all__ = [
    # Common & Errors
    "AnalysisStatus",
    "ErrorDetail",
    "ErrorResponse",
    "ProvenanceKind",
    # Health
    "HealthResponse",
    "ApiStatus",
    "PythonStatus",
    "AiStatus",
    "StorageStatus",
    # Repository & Options
    "RepositoryKind",
    "RepositoryInput",
    "AnalysisOptions",
    "CreateAnalysisRequest",
    "CreateAnalysisResponse",
    # Evidence
    "EvidenceRecord",
    "EvidencePackage",
    # Risk
    "RiskSeverity",
    "RiskIndicator",
    # Recommendation
    "MigrationStep",
    "SuggestedTest",
    "ProposedReplacement",
    "AiProvenance",
    "RecommendationRecord",
    # Verification
    "TestStatus",
    "ExecutedTestResult",
    "VerificationRequest",
    "VerificationRecord",
    # Capsule
    "UsageLocation",
    "CompatibilityGap",
    "DependencyDetails",
    "CapsuleDependencyRecord",
    "ToolInfo",
    "RepositoryScope",
    "CapsuleSummary",
    "DependencyExitCapsule",
    # Analysis
    "ProgressSummary",
    "ArtifactAvailability",
    "AnalysisRecord",
    "AnalysisStatusResponse",
]
