"""Verification runner interface definition for ExitLens."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from app.schemas.verification import ExecutedTestResult


class BaseVerificationRunner(ABC):
    """Abstract runner contract for allow-listed test profiles in disposable workspaces."""

    @abstractmethod
    async def execute_profile(
        self,
        workspace_path: Path,
        profile_id: str,
        run_kind: str,
        timeout_seconds: int = 90,
        allow_network: bool = False,
        patch_file: Optional[Path] = None,
    ) -> ExecutedTestResult:
        """Run an allow-listed test profile in an isolated copy."""
        pass
