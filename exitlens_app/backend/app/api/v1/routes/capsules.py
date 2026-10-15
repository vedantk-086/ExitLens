"""Capsule deliverable export routes for ExitLens."""

from typing import Literal, Union

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.schemas.capsule import DependencyExitCapsule
from app.services.analysis_service import AnalysisService

logger = get_logger("exitlens.routes.capsules")
router = APIRouter(prefix="/analyses", tags=["Capsules"])


def get_analysis_service(settings: Settings = Depends(get_settings)) -> AnalysisService:
    return AnalysisService(settings=settings)


@router.get(
    "/{analysis_id}/capsule",
    summary="Download canonical Dependency Exit Capsule in JSON or Markdown",
    description="Returns the exported deliverable. format=json returns application/json; format=md returns text/markdown.",
    responses={
        200: {
            "content": {
                "application/json": {},
                "text/markdown": {},
            },
            "description": "Exported Dependency Exit Capsule in requested format.",
        }
    },
)
async def get_capsule_export(
    analysis_id: str,
    format: str = Query(default="json", description="Export format: 'json' or 'md'"),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> Response:
    """Serve canonical capsule deliverable in JSON or Markdown format."""
    clean_fmt = (format or "json").lower().strip()

    if clean_fmt not in ("json", "md", "markdown", "pdf"):
        raise ValidationError(
            f"Invalid export format '{format}'. Supported formats are 'json', 'md', and 'pdf'.",
            code="INVALID_EXPORT_FORMAT",
            details={"requested_format": format, "supported_formats": ["json", "md", "pdf"]},
        )

    # Ensure analysis exists
    analysis_service.get_analysis(analysis_id)

    if clean_fmt == "json":
        capsule = analysis_service.get_capsule(analysis_id)
        return JSONResponse(
            content=capsule.model_dump(mode="json"),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=exitlens-capsule-{analysis_id}.json"},
        )
    elif clean_fmt in ("md", "markdown"):
        md_text = analysis_service.get_capsule_markdown(analysis_id)
        return Response(
            content=md_text,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=exitlens-capsule-{analysis_id}.md"},
        )
    else:
        pdf_bytes = analysis_service.get_capsule_pdf(analysis_id)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=exitlens-capsule-{analysis_id}.pdf"},
        )
