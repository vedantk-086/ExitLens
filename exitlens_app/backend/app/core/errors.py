"""ExitLens exceptions and standard error response handlers."""

from contextvars import ContextVar
from typing import Any, Dict, Optional, Union

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.ids import generate_request_id
from app.core.logging import get_logger
from app.core.paths import GitUrlSecurityError, PathSafetyError, PathTraversalError

logger = get_logger("exitlens.errors")

# Context variable tracking current request ID
request_id_ctx: ContextVar[str] = ContextVar("request_id_ctx", default="")


def get_current_request_id(request: Optional[Request] = None) -> str:
    """Retrieve current request ID from state, header, or contextvar, or generate new one."""
    if request is not None and hasattr(request, "state") and hasattr(request.state, "request_id"):
        return request.state.request_id
    ctx_id = request_id_ctx.get()
    if ctx_id:
        return ctx_id
    if request is not None:
        header_id = request.headers.get("X-Request-ID")
        if header_id:
            return header_id
    return generate_request_id()


class ExitLensError(Exception):
    """Base exception for all ExitLens domain errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(ExitLensError):
    """Resource not found (404)."""

    def __init__(
        self,
        message: str = "Resource not found.",
        code: str = "NOT_FOUND",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=404, details=details)


class ValidationError(ExitLensError):
    """Invalid input or malformed data (422)."""

    def __init__(
        self,
        message: str = "Invalid input data.",
        code: str = "VALIDATION_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=422, details=details)


class StateConflictError(ExitLensError):
    """Run state conflict or invalid state transition (409)."""

    def __init__(
        self,
        message: str = "Operation conflicts with current analysis state.",
        code: str = "CONFLICT",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=409, details=details)


class ServiceUnavailableError(ExitLensError):
    """Service or dependency unavailable (503)."""

    def __init__(
        self,
        message: str = "Required service operation is unavailable.",
        code: str = "SERVICE_UNAVAILABLE",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=503, details=details)


class ModelUnavailableError(ServiceUnavailableError):
    """Gemma 4 model or local Ollama provider is unreachable (503)."""

    def __init__(
        self,
        message: str = "Gemma 4 is not reachable from the configured local provider.",
        code: str = "MODEL_UNAVAILABLE",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details)


class PathForbiddenError(ExitLensError):
    """Target path is outside allowed repository roots (403)."""

    def __init__(
        self,
        message: str = "Repository path is outside allowed roots.",
        code: str = "PATH_NOT_ALLOWED",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=403, details=details)


class PathTraversalDetectedError(ExitLensError):
    """Directory traversal attack detected (400)."""

    def __init__(
        self,
        message: str = "Path traversal attempt detected.",
        code: str = "PATH_TRAVERSAL_DETECTED",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=400, details=details)


class ConfirmationRequiredError(ExitLensError):
    """Explicit confirmation required before repository test code execution (422)."""

    def __init__(
        self,
        message: str = "Explicit confirmation is required before repository code can execute.",
        code: str = "CONFIRMATION_REQUIRED",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=422, details=details)


class VerificationSecurityError(ExitLensError):
    """Security violation in verification parameters or patch proposals (400)."""

    def __init__(
        self,
        message: str = "Verification security check failed.",
        code: str = "VERIFICATION_SECURITY_VIOLATION",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=400, details=details)


def format_error_dict(
    code: str,
    message: str,
    request_id: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build standard ExitLens error envelope dictionary."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        }
    }


async def exitlens_error_handler(request: Request, exc: ExitLensError) -> JSONResponse:
    """Handle custom ExitLensError exceptions."""
    req_id = get_current_request_id(request)
    logger.warning("ExitLensError [%s] %s (status=%d, req=%s)", exc.code, exc.message, exc.status_code, req_id)
    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_dict(
            code=exc.code,
            message=exc.message,
            request_id=req_id,
            details=exc.details,
        ),
    )


async def path_safety_error_handler(request: Request, exc: PathSafetyError) -> JSONResponse:
    """Handle path safety and traversal errors."""
    req_id = get_current_request_id(request)
    if isinstance(exc, PathTraversalError):
        status_code = 400
        code = "PATH_TRAVERSAL_DETECTED"
    else:
        status_code = 403
        code = "PATH_NOT_ALLOWED"
    logger.warning("PathSafetyError [%s] %s (status=%d, req=%s)", code, str(exc), status_code, req_id)
    return JSONResponse(
        status_code=status_code,
        content=format_error_dict(
            code=code,
            message=str(exc),
            request_id=req_id,
        ),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Format FastAPI / Pydantic validation errors into standard format."""
    req_id = get_current_request_id(request)
    details = {"errors": exc.errors()}
    logger.info("Validation error on %s %s: %s (req=%s)", request.method, request.url.path, exc.errors(), req_id)
    return JSONResponse(
        status_code=422,
        content=format_error_dict(
            code="VALIDATION_ERROR",
            message="Request input validation failed.",
            request_id=req_id,
            details=details,
        ),
    )


async def http_exception_handler(
    request: Request,
    exc: Union[HTTPException, StarletteHTTPException],
) -> JSONResponse:
    """Format standard FastAPI / Starlette HTTPExceptions."""
    req_id = get_current_request_id(request)
    code_map = {
        404: "NOT_FOUND",
        422: "VALIDATION_ERROR",
        409: "CONFLICT",
        403: "FORBIDDEN",
        401: "UNAUTHORIZED",
        400: "BAD_REQUEST",
        503: "SERVICE_UNAVAILABLE",
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    msg = exc.detail if isinstance(exc.detail, str) else "An HTTP error occurred."
    details = exc.detail if isinstance(exc.detail, dict) else {}
    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_dict(
            code=code,
            message=msg,
            request_id=req_id,
            details=details,
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all unhandled exception handler.
    
    Never exposes stack traces or secret details in production or test responses.
    """
    req_id = get_current_request_id(request)
    logger.exception("Unhandled exception on %s %s (req=%s): %s", request.method, request.url.path, req_id, exc)
    return JSONResponse(
        status_code=500,
        content=format_error_dict(
            code="INTERNAL_ERROR",
            message="An unexpected server error occurred.",
            request_id=req_id,
        ),
    )
