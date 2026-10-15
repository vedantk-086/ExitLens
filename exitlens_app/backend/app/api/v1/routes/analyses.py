"""Analysis run lifecycle endpoints for ExitLens."""

from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.schemas.analysis import AnalysisRecord, AnalysisStatusResponse
from app.schemas.repository import (
    CreateAnalysisRequest,
    CreateAnalysisResponse,
)
from app.services.analysis_service import AnalysisService
from app.services.orchestrator import OrchestrationService

logger = get_logger("exitlens.routes.analyses")
router = APIRouter(prefix="/analyses", tags=["Analyses"])


def get_analysis_service(settings: Settings = Depends(get_settings)) -> AnalysisService:
    return AnalysisService(settings=settings)


def get_orchestration_service(
    service: AnalysisService = Depends(get_analysis_service),
    settings: Settings = Depends(get_settings),
) -> OrchestrationService:
    return OrchestrationService(analysis_service=service, settings=settings)


@router.post(
    "",
    response_model=CreateAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a new repository analysis run",
    description="Validates repository input, initializes analysis state, and queues the analysis pipeline.",
)
async def create_analysis(
    request: CreateAnalysisRequest,
    background_tasks: BackgroundTasks,
    analysis_service: AnalysisService = Depends(get_analysis_service),
    orchestrator: OrchestrationService = Depends(get_orchestration_service),
) -> CreateAnalysisResponse:
    """Create a new analysis run and enqueue execution."""
    record = analysis_service.create_analysis(request)
    
    # Enqueue pipeline in background
    background_tasks.add_task(orchestrator.run_pipeline, record.analysis_id)

    return CreateAnalysisResponse(
        analysis_id=record.analysis_id,
        status=record.status,
        stage=record.stage,
        created_at=record.created_at_utc,
    )


@router.get(
    "",
    response_model=List[AnalysisStatusResponse],
    summary="List all persisted repository analysis runs",
)
async def list_analyses(
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> List[AnalysisStatusResponse]:
    """Return all stored analysis runs."""
    analyses = analysis_service.list_analyses()
    return [
        AnalysisStatusResponse(
            analysis_id=a.analysis_id,
            status=a.status,
            stage=a.stage,
            created_at_utc=a.created_at_utc,
            updated_at_utc=a.updated_at_utc,
            completed_at_utc=a.completed_at_utc,
            progress=a.progress,
            summary=a.summary,
            warnings=a.warnings,
            artifacts=a.artifacts,
        )
        for a in analyses
    ]


@router.get(
    "/{analysis_id}",
    response_model=AnalysisStatusResponse,
    summary="Get status and progress of an analysis run",
    description="Returns current lifecycle stage, real progress percentage, summary counts, and artifact availability.",
)
async def get_analysis_status(
    analysis_id: str,
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisStatusResponse:
    """Retrieve analysis state, progress, and artifact availability."""
    record = analysis_service.get_analysis(analysis_id)
    return AnalysisStatusResponse(
        analysis_id=record.analysis_id,
        status=record.status,
        stage=record.stage,
        created_at_utc=record.created_at_utc,
        updated_at_utc=record.updated_at_utc,
        completed_at_utc=record.completed_at_utc,
        progress=record.progress,
        summary=record.summary,
        warnings=record.warnings,
        artifacts=record.artifacts,
    )
