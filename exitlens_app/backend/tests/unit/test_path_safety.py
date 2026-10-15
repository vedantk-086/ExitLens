"""Unit tests for path safety and traversal defense utilities."""

from pathlib import Path
import pytest

from app.core.paths import (
    PathSafetyError,
    PathTraversalError,
    canonicalize_path,
    is_safe_subpath,
    to_repo_relative_path,
    validate_patch_path,
    validate_repository_path,
)


def test_is_safe_subpath(temp_dir: Path):
    """Verify child paths within parent are considered safe."""
    sub = temp_dir / "subdir" / "child"
    sub.mkdir(parents=True, exist_ok=True)

    assert is_safe_subpath(sub, temp_dir) is True
    assert is_safe_subpath(temp_dir, sub) is False

    outside = temp_dir.parent
    assert is_safe_subpath(outside, temp_dir) is False


def test_validate_repository_path_success(temp_dir: Path):
    """Verify an existing directory within allowed roots is accepted."""
    repo = temp_dir / "my_project"
    repo.mkdir(parents=True, exist_ok=True)

    validated = validate_repository_path(
        raw_path=str(repo),
        allowed_roots=[temp_dir],
    )
    assert validated == repo.resolve()


def test_validate_repository_path_outside_allowed_roots(temp_dir: Path):
    """Verify paths outside allowed roots are rejected."""
    outside_dir = temp_dir.parent / "unauthorized_dir"
    outside_dir.mkdir(parents=True, exist_ok=True)
    try:
        with pytest.raises(PathSafetyError) as exc_info:
            validate_repository_path(
                raw_path=str(outside_dir),
                allowed_roots=[temp_dir],
            )
        assert "outside permitted repository roots" in str(exc_info.value)
    finally:
        if outside_dir.exists():
            outside_dir.rmdir()


def test_validate_repository_path_null_byte():
    """Verify null bytes in repository paths are rejected."""
    with pytest.raises(PathTraversalError):
        validate_repository_path("repo\x00/sub", allowed_roots=["."])


def test_validate_patch_path_safe(temp_dir: Path):
    """Verify safe relative patch paths are accepted."""
    repo = temp_dir / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    target = validate_patch_path("src/app/main.py", repo_root=repo)
    assert target == (repo / "src" / "app" / "main.py").resolve()


def test_validate_patch_path_rejects_absolute_path(temp_dir: Path):
    """Verify absolute paths in patch files are rejected."""
    repo = temp_dir / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    with pytest.raises(PathTraversalError) as exc_info:
        validate_patch_path("C:/windows/system32/cmd.exe", repo_root=repo)
    assert "Absolute paths in patches are forbidden" in str(exc_info.value)


def test_validate_patch_path_rejects_traversal(temp_dir: Path):
    """Verify directory traversal '..' in patch files is rejected."""
    repo = temp_dir / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    with pytest.raises(PathTraversalError) as exc_info:
        validate_patch_path("../outside.py", repo_root=repo)
    assert "Traversal syntax '..' is forbidden" in str(exc_info.value)


def test_to_repo_relative_path(temp_dir: Path):
    """Verify paths are correctly relativized to repository root."""
    repo = temp_dir / "repo"
    file_path = repo / "tests" / "test_one.py"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.touch()

    rel = to_repo_relative_path(file_path, repo_root=repo)
    assert rel == "tests/test_one.py"
