"""Verification runner executing allow-listed profiles in disposable workspaces.

Guarantees:
- Only allow-listed server-defined argument arrays are executed.
- Model-generated or user-supplied shell commands are strictly rejected.
- Strict subprocess timeout enforcement with termination/killing.
- Restricted environment with no secret inheritance and default network block.
- Bounded stdout/stderr truncation and credential redaction.
- Duration, exit codes, and timestamps captured with full transparency.
"""

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import time
from typing import Dict, List, Optional

from app.core.config import Settings, get_settings
from app.core.ids import generate_uuid
from app.core.logging import get_logger
from app.core.time import utc_now_iso
from app.schemas.verification import ExecutedTestResult, TestStatus
from app.verification.base import BaseVerificationRunner
from app.verification.environment import (
    build_restricted_environment,
    redact_and_truncate_output,
)
from app.verification.profiles import get_allowlisted_profile

logger = get_logger("exitlens.verification.runner")


class VerificationRunner(BaseVerificationRunner):
    """Subprocess runner for allow-listed test profiles within disposable workspaces."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    async def execute_profile(
        self,
        workspace_path: Path,
        profile_id: str,
        run_kind: str,
        timeout_seconds: int = 90,
        allow_network: bool = False,
        patch_file: Optional[Path] = None,
        patch_id: Optional[str] = None,
    ) -> ExecutedTestResult:
        """Execute an allow-listed test profile inside an isolated workspace.
        
        Args:
            workspace_path: Directory of the isolated disposable workspace.
            profile_id: Server allow-listed profile ID.
            run_kind: 'baseline' or 'replacement'.
            timeout_seconds: Max execution seconds (bounded by MAX_TEST_TIMEOUT_SECONDS).
            allow_network: Whether to permit network traffic (default False).
            patch_file: Optional path to applied patch.
            patch_id: Optional ID of the migration patch.
            
        Returns:
            ExecutedTestResult: Detailed execution record.
        """
        check_id = f"chk-{generate_uuid()[:8]}"
        
        # 1. Validate allow-listed profile
        profile = get_allowlisted_profile(profile_id)
        cmd_argv = list(profile.server_argv)

        # 2. Bound timeout limit
        max_allowed = self.settings.MAX_TEST_TIMEOUT_SECONDS
        clamped_timeout = max(1, min(max_allowed, timeout_seconds))

        # 3. Construct restricted environment
        env = build_restricted_environment(allow_network=allow_network)

        # Safe runtime summary (no sensitive info)
        runtime_env: Dict[str, str] = {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "os_platform": sys.platform,
            "allow_network": str(allow_network).lower(),
            "timeout_seconds": str(clamped_timeout),
            "profile_framework": profile.framework,
        }

        started_at = utc_now_iso()
        start_time = time.monotonic()
        exit_code: Optional[int] = None
        status: TestStatus = TestStatus.ERROR
        skip_or_error_reason: Optional[str] = None
        stdout_raw = ""
        stderr_raw = ""

        logger.info(
            "Executing profile '%s' [%s] in %s (timeout=%ds, network=%s)",
            profile.profile_id,
            run_kind,
            workspace_path,
            clamped_timeout,
            allow_network,
        )

        try:
            # Subprocess execution: NEVER use shell=True
            process = await asyncio.create_subprocess_exec(
                *cmd_argv,
                cwd=str(workspace_path),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=float(clamped_timeout),
                )
                stdout_raw = stdout_bytes.decode("utf-8", errors="replace")
                stderr_raw = stderr_bytes.decode("utf-8", errors="replace")
                exit_code = process.returncode

                if exit_code == 0:
                    status = TestStatus.PASSED
                else:
                    status = TestStatus.FAILED

            except asyncio.TimeoutError:
                logger.warning("Profile '%s' execution timed out after %ds", profile.profile_id, clamped_timeout)
                try:
                    process.kill()
                    await process.wait()
                except Exception as kill_err:
                    logger.debug("Error killing timed out process: %s", kill_err)

                status = TestStatus.TIMED_OUT
                skip_or_error_reason = f"Execution timed out after {clamped_timeout} seconds."

        except Exception as exc:
            logger.error("Failed to execute profile '%s': %s", profile.profile_id, exc)
            status = TestStatus.ERROR
            skip_or_error_reason = f"Process invocation failed: {str(exc)}"

        duration_seconds = round(time.monotonic() - start_time, 3)
        completed_at = utc_now_iso()

        # Redact and truncate captured output streams
        max_bytes = self.settings.MAX_CAPTURED_OUTPUT_BYTES
        stdout_excerpt, stdout_trunc = redact_and_truncate_output(stdout_raw, max_bytes=max_bytes)
        stderr_excerpt, stderr_trunc = redact_and_truncate_output(stderr_raw, max_bytes=max_bytes)
        output_truncated = stdout_trunc or stderr_trunc

        return ExecutedTestResult(
            check_id=check_id,
            run_kind=run_kind,
            status=status,
            profile_id=profile.profile_id,
            argv=cmd_argv,
            started_at_utc=started_at,
            completed_at_utc=completed_at,
            duration_seconds=duration_seconds,
            exit_code=exit_code,
            runtime_environment=runtime_env,
            stdout_excerpt=stdout_excerpt,
            stderr_excerpt=stderr_excerpt,
            output_truncated=output_truncated,
            patch_id=patch_id,
            skip_or_error_reason=skip_or_error_reason,
            evidence_id=None,
        )
