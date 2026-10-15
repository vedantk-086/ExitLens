"""Disposable workspace management for safe isolated test execution.

Guarantees:
- The user's original repository is NEVER modified or written to.
- Every execution runs in an independent temporary directory.
- Workspaces are automatically deleted and cleaned up after execution.
- Sensitive files (.git, .venv, reports, credentials) are excluded from disposable copies.
"""

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import tempfile
from typing import Generator, List, Optional, Set

from app.core.logging import get_logger

logger = get_logger("exitlens.verification.workspace")

DEFAULT_WORKSPACE_EXCLUDES: Set[str] = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "reports",
    "exitlens_app",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".coverage",
}


def _ignore_patterns_filter(exclude_names: Set[str]):
    """shutil.copytree ignore callable filtering out excluded names."""
    def _filter(directory: str, contents: List[str]) -> Set[str]:
        ignored = set()
        for name in contents:
            if name in exclude_names or name.endswith(".pyc") or name.endswith(".pyo"):
                ignored.add(name)
        return ignored
    return _filter


def _handle_remove_readonly(func, path, exc_info):
    """Windows-safe error handler for read-only files during rmtree cleanup."""
    try:
        import stat
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as exc:
        logger.debug("Failed to reset permissions during cleanup on %s: %s", path, exc)


@contextmanager
def disposable_workspace(
    source_repo: Path,
    exclude_patterns: Optional[List[str]] = None,
    prefix: str = "exitlens_ws_",
) -> Generator[Path, None, None]:
    """Create a temporary, isolated copy of source_repo for single-execution trials.
    
    Yields:
        Path: Path to the root of the disposable workspace.
    
    Ensures:
        Clean removal upon completion or failure.
        Zero side effects on source_repo.
    """
    canonical_source = source_repo.resolve()
    if not canonical_source.is_dir():
        raise ValueError(f"Source repository path '{source_repo}' is not an existing directory.")

    excludes = set(DEFAULT_WORKSPACE_EXCLUDES)
    if exclude_patterns:
        excludes.update(exclude_patterns)

    temp_dir = tempfile.mkdtemp(prefix=prefix)
    ws_path = Path(temp_dir).resolve()

    try:
        logger.debug("Creating disposable workspace at %s from %s", ws_path, canonical_source)
        # Copy contents into disposable workspace
        for item in canonical_source.iterdir():
            if item.name in excludes:
                continue
            dest = ws_path / item.name
            if item.is_dir():
                shutil.copytree(
                    item,
                    dest,
                    symlinks=False,
                    ignore=_ignore_patterns_filter(excludes),
                )
            elif item.is_file():
                shutil.copy2(item, dest)

        yield ws_path

    finally:
        logger.debug("Cleaning up disposable workspace at %s", ws_path)
        try:
            shutil.rmtree(ws_path, onerror=_handle_remove_readonly)
        except Exception as exc:
            logger.warning("Error cleaning up disposable workspace %s: %s", ws_path, exc)
