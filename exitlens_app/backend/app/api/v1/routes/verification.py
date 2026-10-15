"""Verification routes for executing baseline and replacement test checks."""

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.errors import ConfirmationRequiredError, NotFoundError
from app.core.logging import get_logger
from app.schemas.verification import (
    VerificationRecord,
    VerificationRequest,
)
from app.services.analysis_service import AnalysisService
from app.verification.profiles import TestProfile, discover_test_profiles
from app.verification.service import VerificationService

logger = get_logger("exitlens.routes.verification")
router = APIRouter(prefix="/analyses", tags=["Verification"])


def get_analysis_service(settings: Settings = Depends(get_settings)) -> AnalysisService:
    return AnalysisService(settings=settings)


def get_verification_service(
    service: AnalysisService = Depends(get_analysis_service),
    settings: Settings = Depends(get_settings),
) -> VerificationService:
    return VerificationService(analysis_service=service, settings=settings)


@router.get(
    "/{analysis_id}/test-profiles",
    response_model=List[TestProfile],
    summary="Discover available allow-listed test profiles for an analysis target",
)
async def get_test_profiles(
    analysis_id: str,
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> List[TestProfile]:
    """Inspect repository and return detected and available allow-listed test profiles."""
    analysis = analysis_service.get_analysis(analysis_id)
    repo_path = Path(analysis.repository.value)
    if not repo_path.is_dir():
        return []
    return discover_test_profiles(repo_path)


@router.post(
    "/{analysis_id}/verification",
    response_model=VerificationRecord,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Execute baseline and candidate replacement test verification",
    description=(
        "Executes baseline and candidate replacement tests in disposable copy workspaces. "
        "Strictly requires explicit confirmation (confirm_repository_code_execution=True) "
        "and allow-listed server-defined argument arrays."
    ),
)
async def trigger_verification(
    analysis_id: str,
    request: VerificationRequest,
    analysis_service: AnalysisService = Depends(get_analysis_service),
    verif_service: VerificationService = Depends(get_verification_service),
) -> VerificationRecord:
    """Queue and execute allow-listed baseline and replacement verification checks."""
    analysis = analysis_service.get_analysis(analysis_id)
    repo_path = Path(analysis.repository.value)

    if not request.confirm_repository_code_execution:
        raise ConfirmationRequiredError(
            "Explicit confirmation (confirm_repository_code_execution=True) is required "
            "before executing repository test code in disposable workspaces."
        )

    if not repo_path.is_dir():
        is_git = (
            hasattr(analysis.repository, "kind")
            and (analysis.repository.kind == "git_url" or getattr(analysis.repository.kind, "value", "") == "git_url")
        ) or str(analysis.repository.value).startswith(("http://", "https://"))

        if is_git:
            from app.scanner.git_cloner import safe_disposable_clone
            with safe_disposable_clone(
                git_url=str(analysis.repository.value),
                git_ref=analysis.repository.git_ref,
                enable_public_clone=True,
            ) as (cloned_path, _):
                return await verif_service.execute_verification_session(
                    analysis_id=analysis_id,
                    request=request,
                    repository_path=cloned_path,
                )

        raise NotFoundError(f"Repository path '{analysis.repository.value}' is not an accessible directory.")

    record = await verif_service.execute_verification_session(
        analysis_id=analysis_id,
        request=request,
        repository_path=repo_path,
    )
    return record


@router.get(
    "/{analysis_id}/verification/{verification_id}",
    response_model=VerificationRecord,
    summary="Retrieve single verification session record",
)
async def get_verification_session(
    analysis_id: str,
    verification_id: str,
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> VerificationRecord:
    """Fetch stored verification session record."""
    return analysis_service.get_verification(analysis_id, verification_id)
