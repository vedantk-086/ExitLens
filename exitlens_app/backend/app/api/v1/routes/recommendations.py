"""Recommendation regeneration endpoints for ExitLens analysis runs."""

from fastapi import APIRouter, Depends, status

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.schemas.recommendation import (
    RegenerateRecommendationsRequest,
    RegenerateRecommendationsResponse,
)
from app.services.analysis_service import AnalysisService
from app.services.orchestrator import OrchestrationService

logger = get_logger("exitlens.routes.recommendations")
router = APIRouter(prefix="/analyses", tags=["Recommendations"])


def get_analysis_service(settings: Settings = Depends(get_settings)) -> AnalysisService:
    return AnalysisService(settings=settings)


def get_orchestration_service(
    service: AnalysisService = Depends(get_analysis_service),
    settings: Settings = Depends(get_settings),
) -> OrchestrationService:
    return OrchestrationService(analysis_service=service, settings=settings)


@router.post(
    "/{analysis_id}/recommendations",
    response_model=RegenerateRecommendationsResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Regenerate migration recommendations for selected dependency IDs",
    description="Regenerates AI migration recommendations from stored evidence without re-scanning the repository.",
)
async def regenerate_recommendations(
    analysis_id: str,
    request: RegenerateRecommendationsRequest,
    analysis_service: AnalysisService = Depends(get_analysis_service),
    orchestrator: OrchestrationService = Depends(get_orchestration_service),
) -> RegenerateRecommendationsResponse:
    """Regenerate recommendations for specific dependencies from saved evidence."""
    # Ensure analysis exists
    analysis_service.get_analysis(analysis_id)

    recs = await orchestrator.regenerate_recommendations(
        analysis_id=analysis_id,
        dependency_ids=request.dependency_ids,
        force_regenerate=request.force_regenerate,
    )

    return RegenerateRecommendationsResponse(
        analysis_id=analysis_id,
        status="completed",
        stage="generating_recommendations",
        regenerated_count=len(recs),
        recommendations=recs,
    )
