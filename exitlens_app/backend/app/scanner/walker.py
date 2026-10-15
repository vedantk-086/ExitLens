"""Bounded repository walker with strict exclusion and symlink defense."""

import fnmatch
from pathlib import Path
from typing import List, Optional, Set

from app.core.paths import (
    canonicalize_path,
    check_symlink_safety,
    is_safe_subpath,
    to_repo_relative_path,
)
from app.scanner.models import DiscoveredFile, WalkSummary

DEFAULT_EXCLUDE_NAMES: Set[str] = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "reports",
    "exitlens_app",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "dist",
    "build",
    ".eggs",
}


def is_manifest_filename(filename: str) -> bool:
    """Identify if a filename matches known dependency manifests or lockfiles."""
    lower = filename.lower()
    if lower == "requirements.txt" or lower.startswith("requirements") and lower.endswith(".txt"):
        return True
    if lower.endswith("-requirements.txt") or lower.endswith("_requirements.txt"):
        return True
    if lower in ("pyproject.toml", "poetry.lock", "uv.lock", "pipfile", "pipfile.lock", "setup.cfg", "setup.py"):
        return True
    return False


def is_test_path(rel_path: str) -> bool:
    """Identify whether a relative file path is located in a test directory or test file."""
    parts = rel_path.lower().replace("\\", "/").split("/")
    filename = parts[-1]
    # Check directory names
    if any(p in ("tests", "test", "testing", "fixtures") for p in parts[:-1]):
        return True
    # Check filename prefixes/suffixes
    if filename.startswith("test_") or filename.endswith("_test.py"):
        return True
    return False


def walk_repository(
    repo_root: Path,
    exclude_paths: Optional[List[str]] = None,
    max_files: int = 5000,
    max_single_file_bytes: int = 500000,
    max_total_source_bytes: int = 20000000,
) -> WalkSummary:
    """Perform a bounded, secure filesystem walk of the repository."""
    canonical_root = canonicalize_path(repo_root)
    summary = WalkSummary()

    # Compile exclusion patterns
    custom_excludes = [p.strip().replace("\\", "/").rstrip("/") for p in (exclude_paths or []) if p.strip()]

    def is_excluded(dir_or_file_rel: str, name: str) -> bool:
        # Check standard directory names
        if name in DEFAULT_EXCLUDE_NAMES:
            return True
        # Check custom patterns
        norm_rel = dir_or_file_rel.replace("\\", "/").strip("/")
        for pattern in custom_excludes:
            clean_pat = pattern.strip("/")
            if name == clean_pat or norm_rel == clean_pat:
                return True
            if norm_rel.startswith(f"{clean_pat}/"):
                return True
            if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(norm_rel, pattern):
                return True
        return False

    limit_files_reached = False
    limit_bytes_reached = False

    for root, dirs, files in os_walk_bounded(canonical_root):
        rel_root = to_repo_relative_path(root, canonical_root)

        # Filter directories in-place to prevent traversing into excluded trees
        filtered_dirs = []
        for d in dirs:
            dir_full = root / d
            dir_rel = to_repo_relative_path(dir_full, canonical_root)

            # Check symlink safety on directory
            if dir_full.is_symlink():
                if not check_symlink_safety(dir_full, canonical_root):
                    summary.warnings.append(
                        f"Symlink directory '{dir_rel}' points outside repository boundary and was skipped."
                    )
                    continue

            if not is_excluded(dir_rel, d):
                filtered_dirs.append(d)
        dirs[:] = filtered_dirs

        for f in files:
            if summary.scanned_file_count >= max_files:
                if not limit_files_reached:
                    summary.warnings.append(
                        f"Maximum analysis file limit ({max_files}) reached. Remaining files skipped."
                    )
                    limit_files_reached = True
                break

            file_path = root / f
            file_rel = to_repo_relative_path(file_path, canonical_root)

            # Check symlink safety on file
            if file_path.is_symlink():
                if not check_symlink_safety(file_path, canonical_root):
                    summary.warnings.append(
                        f"Symlink '{file_rel}' points outside repository boundary and was skipped."
                    )
                    continue

            if is_excluded(file_rel, f):
                continue

            # Stat file size safely
            try:
                st = file_path.stat()
                file_size = st.st_size
            except Exception as stat_err:
                summary.warnings.append(f"Cannot read file metadata for '{file_rel}': {stat_err}")
                continue

            is_manifest = is_manifest_filename(f)
            is_py = f.lower().endswith(".py")

            if not (is_manifest or is_py):
                continue

            # Check single file size limit
            if file_size > max_single_file_bytes:
                summary.warnings.append(
                    f"File '{file_rel}' ({file_size} bytes) exceeds MAX_SINGLE_FILE_BYTES ({max_single_file_bytes}) and was skipped."
                )
                continue

            # Check total source byte limit
            if summary.scanned_byte_count + file_size > max_total_source_bytes:
                if not limit_bytes_reached:
                    summary.warnings.append(
                        f"Maximum source size limit ({max_total_source_bytes} bytes) reached. Further files skipped."
                    )
                    limit_bytes_reached = True
                continue

            # File accepted
            summary.scanned_file_count += 1
            summary.scanned_byte_count += file_size

            disc_file = DiscoveredFile(
                absolute_path=file_path.resolve(),
                relative_path=file_rel,
                size_bytes=file_size,
                is_manifest=is_manifest,
                is_python=is_py,
                is_test=is_test_path(file_rel),
            )

            if is_manifest:
                summary.manifest_files.append(disc_file)
            if is_py:
                summary.python_files.append(disc_file)

        if limit_files_reached or limit_bytes_reached:
            break

    return summary


def os_walk_bounded(top: Path):
    """Safe generator yielding (root_path, dirnames, filenames)."""
    import os
    for root, dirs, files in os.walk(top, followlinks=False):
        yield Path(root), dirs, files
