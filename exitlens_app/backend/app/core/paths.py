"""Path-safety and filesystem validation utilities for ExitLens.

Guarantees canonicalization, traversal defenses, and repository boundary enforcement.
"""

import hashlib
import os
from pathlib import Path
import re
import tempfile
from typing import List, Union
from urllib.parse import urlparse


class PathSafetyError(Exception):
    """Raised when a path violates repository boundaries or security policy."""
    pass


class PathTraversalError(PathSafetyError):
    """Raised when directory traversal syntax or symlink escape is detected."""
    pass


class GitUrlSecurityError(PathSafetyError, ValueError):
    """Raised when a Git URL violates security requirements (credentials, unsafe protocol)."""
    pass


def canonicalize_path(path: Union[str, Path], base_dir: Union[Path, None] = None) -> Path:
    """Resolve a path to its canonical, absolute form with symlinks resolved."""
    p = Path(path)
    if not p.is_absolute():
        base = (base_dir or Path.cwd()).resolve()
        p = base / p
    try:
        return p.resolve()
    except Exception as exc:
        raise PathSafetyError(f"Failed to canonicalize path '{path}': {exc}") from exc


def is_safe_subpath(target: Union[str, Path], parent: Union[str, Path]) -> bool:
    """Return True if target resolves to a location within parent."""
    try:
        resolved_target = canonicalize_path(target)
        resolved_parent = canonicalize_path(parent)
        return resolved_target == resolved_parent or resolved_target.is_relative_to(resolved_parent)
    except Exception:
        return False


def check_symlink_safety(symlink_path: Union[str, Path], repo_root: Union[str, Path]) -> bool:
    """Return True if symlink target resolves safely inside repo_root.
    
    Rejects symlinks pointing outside the repository boundary.
    """
    p = Path(symlink_path)
    if not p.is_symlink():
        return True
    try:
        resolved_target = p.resolve()
        canonical_root = canonicalize_path(repo_root)
        return is_safe_subpath(resolved_target, canonical_root)
    except Exception:
        return False


def validate_repository_path(
    raw_path: Union[str, Path],
    allowed_roots: List[Union[str, Path]],
    base_dir: Union[Path, None] = None,
) -> Path:
    """Validate that a user-supplied repository path exists, is a directory,
    and resides strictly within one of the configured allowed roots.
    """
    raw_str = str(raw_path).strip()
    if not raw_str:
        raise PathSafetyError("Repository path cannot be empty.")

    # Rejection of dangerous patterns
    if "\x00" in raw_str:
        raise PathTraversalError("Null bytes in repository path are strictly forbidden.")

    resolved_path = canonicalize_path(raw_path, base_dir=base_dir)

    if not resolved_path.exists():
        raise PathSafetyError(f"Repository path does not exist: {raw_str}")

    if not resolved_path.is_dir():
        raise PathSafetyError(f"Repository path is not a directory: {raw_str}")

    # Check against allowed roots
    is_allowed = False
    for root in allowed_roots:
        resolved_root = canonicalize_path(root, base_dir=base_dir)
        if is_safe_subpath(resolved_path, resolved_root):
            is_allowed = True
            break

    if not is_allowed:
        raise PathSafetyError(
            f"Repository path '{raw_str}' is outside permitted repository roots."
        )

    return resolved_path


def validate_git_url(raw_url: str, enable_public_clone: bool = True) -> str:
    """Validate that a Git repository URL is a safe public HTTPS URL.
    
    Rejects:
    - Non-HTTPS protocols (http, git, ssh, file, ftp)
    - Embedded user/password credentials (e.g. https://token@github.com)
    - Shell injection meta-characters (; & | ` $ \n)
    """
    clean_url = str(raw_url).strip().strip("'\"")
    if not clean_url:
        raise GitUrlSecurityError("Git URL cannot be empty.")

    if not enable_public_clone:
        raise GitUrlSecurityError("Public HTTPS Git cloning is disabled by configuration.")

    # Auto-fix accidental duplicate 'https://' prefixes (e.g. 'https://https://github.com/...')
    clean_url = re.sub(r"^(https://)+", "https://", clean_url, flags=re.IGNORECASE)

    # Reject shell injection characters
    if re.search(r"[;&|`$\x00\r\n]", clean_url):
        raise GitUrlSecurityError(f"Unsafe characters detected in Git URL: '{clean_url}'")

    parsed = urlparse(clean_url)

    if parsed.scheme.lower() != "https":
        raise GitUrlSecurityError(
            f"Unsupported protocol '{parsed.scheme}://'. Only public HTTPS Git URLs are permitted."
        )

    if parsed.username or parsed.password or "@" in (parsed.netloc or ""):
        raise GitUrlSecurityError("Embedded credentials in Git repository URLs are strictly prohibited.")

    if not parsed.netloc:
        raise GitUrlSecurityError(f"Invalid host in Git URL: '{clean_url}'")

    domain = (parsed.hostname or "").lower()
    if domain != "github.com" and not domain.endswith(".github.com"):
        raise GitUrlSecurityError(
            f"Unsupported domain '{parsed.netloc}'. Only public GitHub repository URLs (github.com) are permitted."
        )

    return clean_url


def validate_patch_path(target_path: Union[str, Path], repo_root: Union[str, Path]) -> Path:
    """Validate a relative path intended for patch application.
    
    Rejects absolute paths, directory traversal, and paths resolving outside repo_root.
    """
    path_str = str(target_path).strip()
    if not path_str:
        raise PathSafetyError("Patch target path cannot be empty.")

    # Reject null bytes and absolute paths
    if "\x00" in path_str:
        raise PathTraversalError("Null byte in patch path.")
    
    p = Path(path_str)
    if p.is_absolute():
        raise PathTraversalError(f"Absolute paths in patches are forbidden: '{path_str}'")

    # Reject '..' components
    if ".." in p.parts:
        raise PathTraversalError(f"Traversal syntax '..' is forbidden in patch paths: '{path_str}'")

    canonical_root = canonicalize_path(repo_root)
    resolved_target = canonical_root / p

    try:
        resolved_target = resolved_target.resolve()
    except Exception as exc:
        raise PathSafetyError(f"Invalid patch path: {exc}") from exc

    if not is_safe_subpath(resolved_target, canonical_root):
        raise PathTraversalError(
            f"Patch target path '{path_str}' escapes repository root."
        )

    return resolved_target


def to_repo_relative_path(path: Union[str, Path], repo_root: Union[str, Path]) -> str:
    """Return a forward-slash relative path within the repository."""
    canonical_root = canonicalize_path(repo_root)
    canonical_file = canonicalize_path(path)
    try:
        rel = canonical_file.relative_to(canonical_root)
        return rel.as_posix()
    except ValueError:
        # Fallback to file name if not strictly relative
        return canonical_file.name


def calculate_file_sha256(file_path: Path) -> str:
    """Compute hex SHA-256 digest of a file without loading entire file in memory."""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def calculate_content_sha256(content: str) -> str:
    """Compute hex SHA-256 digest of a string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def atomic_write_file(target_file: Path, content: str, encoding: str = "utf-8") -> None:
    """Atomically write content to target_file using a temporary file in the same directory."""
    parent = target_file.parent
    parent.mkdir(parents=True, exist_ok=True)
    temp_file = tempfile.NamedTemporaryFile(
        dir=parent, mode="w", encoding=encoding, delete=False
    )
    temp_path = Path(temp_file.name)
    try:
        temp_file.write(content)
        temp_file.flush()
        os.fsync(temp_file.fileno())
        temp_file.close()
        # Atomic replace
        temp_path.replace(target_file)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
