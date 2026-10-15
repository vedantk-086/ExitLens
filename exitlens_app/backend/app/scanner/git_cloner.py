"""Safe disposable Git repository cloner for ExitLens."""

import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Tuple

from app.core.logging import get_logger
from app.core.paths import GitUrlSecurityError, validate_git_url

logger = get_logger("exitlens.git_cloner")


class GitCloneError(GitUrlSecurityError):
    """Raised when cloning a repository fails or violates safety rules."""
    pass


@contextmanager
def safe_disposable_clone(
    git_url: str,
    git_ref: Optional[str] = None,
    timeout_seconds: int = 120,
    enable_public_clone: bool = True,
) -> Generator[Tuple[Path, Optional[str]], None, None]:
    """Clone a public HTTPS GitHub repository into a disposable temporary directory.
    
    Safety controls:
    - Strictly validates public HTTPS GitHub URL.
    - No git hooks: passes -c core.hooksPath="" preventing hook execution.
    - No submodules: passes --no-recurse-submodules.
    - Bounded depth: --depth 1.
    - Bounded execution timeout.
    - Disposable: deletes the cloned directory when context exits.
    - Extracts revision SHA if available.
    """
    clean_url = validate_git_url(git_url, enable_public_clone=enable_public_clone)

    temp_dir = tempfile.mkdtemp(prefix="exitlens_git_clone_")
    clone_dest = Path(temp_dir) / "repo"

    try:
        cmd = [
            "git",
            "-c", "core.hooksPath=",
            "clone",
            "--depth", "1",
            "--no-recurse-submodules",
            clean_url,
            str(clone_dest),
        ]
        if git_ref and git_ref.strip():
            cmd.extend(["--branch", git_ref.strip()])

        logger.info("Executing safe shallow clone of %s into disposable directory", clean_url)
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )

        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip() or "Unknown git error"
            logger.error("Git clone failed (code=%d): %s", proc.returncode, err_msg)
            raise GitCloneError(f"Failed to clone repository from '{clean_url}': {err_msg}")

        # Extract commit hash
        revision = None
        try:
            rev_proc = subprocess.run(
                ["git", "-C", str(clone_dest), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if rev_proc.returncode == 0:
                revision = rev_proc.stdout.strip()
        except Exception:
            pass

        yield clone_dest, revision

    finally:
        logger.info("Cleaning up disposable clone directory %s", temp_dir)
        try:
            # On Windows, git objects can be read-only; handle read-only on rmtree
            def remove_readonly(func, path, excinfo):
                try:
                    os.chmod(path, 0o777)
                    func(path)
                except Exception:
                    pass

            shutil.rmtree(temp_dir, onerror=remove_readonly)
        except Exception as cleanup_err:
            logger.warning("Error cleaning up clone dir %s: %s", temp_dir, cleanup_err)
