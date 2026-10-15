"""Verification module for ExitLens."""

from app.verification.base import BaseVerificationRunner
from app.verification.environment import (
    SAFE_ENV_ALLOWLIST,
    build_restricted_environment,
    redact_and_truncate_output,
)
from app.verification.patch_applier import (
    PatchApplicationError,
    apply_patch_to_workspace,
)
from app.verification.profiles import (
    ALLOWLISTED_PROFILES,
    TestProfile,
    discover_test_profiles,
    get_allowlisted_profile,
)
from app.verification.runner import VerificationRunner
from app.verification.service import VerificationService
from app.verification.workspace import disposable_workspace

__all__ = [
    "ALLOWLISTED_PROFILES",
    "BaseVerificationRunner",
    "PatchApplicationError",
    "SAFE_ENV_ALLOWLIST",
    "TestProfile",
    "VerificationRunner",
    "VerificationService",
    "apply_patch_to_workspace",
    "build_restricted_environment",
    "discover_test_profiles",
    "disposable_workspace",
    "get_allowlisted_profile",
    "redact_and_truncate_output",
]
