"""ExitLens core utilities: settings, errors, IDs, logging, time, and path-safety."""

from app.core.config import Settings, get_settings
from app.core.errors import (
    ExitLensError,
    ModelUnavailableError,
    NotFoundError,
    PathForbiddenError,
    PathTraversalDetectedError,
    ServiceUnavailableError,
    StateConflictError,
    ValidationError,
)
from app.core.ids import (
    generate_analysis_id,
    generate_evidence_id,
    generate_request_id,
    is_safe_id,
    is_valid_uuid,
)
from app.core.logging import get_logger, setup_logging
from app.core.paths import (
    canonicalize_path,
    is_safe_subpath,
    to_repo_relative_path,
    validate_patch_path,
    validate_repository_path,
)
from app.core.time import format_utc_iso, parse_utc_iso, utc_now, utc_now_iso

__all__ = [
    "Settings",
    "get_settings",
    "ExitLensError",
    "NotFoundError",
    "ValidationError",
    "StateConflictError",
    "ServiceUnavailableError",
    "ModelUnavailableError",
    "PathForbiddenError",
    "PathTraversalDetectedError",
    "generate_request_id",
    "generate_analysis_id",
    "generate_evidence_id",
    "is_safe_id",
    "is_valid_uuid",
    "get_logger",
    "setup_logging",
    "canonicalize_path",
    "is_safe_subpath",
    "validate_repository_path",
    "validate_patch_path",
    "to_repo_relative_path",
    "utc_now",
    "utc_now_iso",
    "format_utc_iso",
    "parse_utc_iso",
]
