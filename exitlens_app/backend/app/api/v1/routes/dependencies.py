"""Dependency inspection endpoints for ExitLens analysis runs."""

from typing import List

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.schemas.capsule import CapsuleDependencyRecord
from app.services.analysis_service import AnalysisService

logger = get_logger("exitlens.routes.dependencies")
router = APIRouter(prefix="/analyses", tags=["Dependencies"])


def get_analysis_service(settings: Settings = Depends(get_settings)) -> AnalysisService:
    return AnalysisService(settings=settings)


@router.get(
    "/{analysis_id}/dependencies",
    response_model=List[CapsuleDependencyRecord],
    summary="List all flagged dependencies for an analysis run",
    description="Returns all scanned dependencies flagged for migration review with risk and usage summaries.",
)
async def list_dependencies(
    analysis_id: str,
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> List[CapsuleDependencyRecord]:
    """Retrieve all flagged dependency records from the analysis capsule."""
    # Ensure analysis exists
    analysis_service.get_analysis(analysis_id)

    try:
        capsule = analysis_service.get_capsule(analysis_id)
        return capsule.dependencies
    except NotFoundError:
        # Capsule not yet generated
        return []


@router.get(
    "/{analysis_id}/dependencies/{dependency_id}",
    response_model=CapsuleDependencyRecord,
    summary="Get full 9-section capsule data for a single dependency",
    description="Returns complete evidence, risks, usage locations, recommendations, and test results for one dependency.",
)
async def get_dependency_details(
    analysis_id: str,
    dependency_id: str,
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> CapsuleDependencyRecord:
    """Retrieve full 9-section record for a specific dependency ID."""
    analysis_service.get_analysis(analysis_id)

    try:
        capsule = analysis_service.get_capsule(analysis_id)
    except NotFoundError:
        raise NotFoundError(
            f"Analysis '{analysis_id}' has not yet generated a capsule deliverable.",
            code="CAPSULE_NOT_FOUND",
        )

    for dep in capsule.dependencies:
        if dep.dependency_id == dependency_id:
            return dep

    raise NotFoundError(
        f"Dependency '{dependency_id}' was not found in analysis '{analysis_id}'.",
        code="DEPENDENCY_NOT_FOUND",
        details={"requested_dependency_id": dependency_id},
    )
