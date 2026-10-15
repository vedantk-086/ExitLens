"""Unit tests for the complete repository scanner, limits, and path safety."""

import os
from pathlib import Path
import pytest

from app.core.config import Settings
from app.core.errors import PathSafetyError
from app.core.paths import GitUrlSecurityError, validate_git_url
from app.scanner.scanner import Scanner
from app.scanner.walker import walk_repository
from tests.fixtures.repo_fixtures import (
    create_dynamic_and_malformed_fixture_repo,
    create_lockfiles_and_pipfile_fixture_repo,
    create_standard_fixture_repo,
)


@pytest.mark.asyncio
async def test_full_repository_scan_standard_repo(temp_dir: Path):
    """Verify end-to-end repository scan discovers dependencies and maps usages."""
    repo = create_standard_fixture_repo(temp_dir)
    settings = Settings(
        ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)],
        MAX_ANALYSIS_FILES=1000,
        MAX_SINGLE_FILE_BYTES=500000,
        MAX_TOTAL_SOURCE_BYTES=20000000,
    )
    scanner = Scanner(settings=settings)

    result = await scanner.run_full_scan(repo_path=repo)

    assert result.file_count > 0
    assert len(result.dependencies) >= 8
    assert len(result.usages) >= 4
    assert len(result.evidence) > 0

    dep_names = {d.distribution_name for d in result.dependencies}
    assert "requests" in dep_names
    assert "urllib3" in dep_names
    assert "fastapi" in dep_names
    assert "pyyaml" in dep_names

    # Ensure hidden files in .venv and .git were completely excluded
    all_evidence_paths = {e.path for e in result.evidence}
    for p in all_evidence_paths:
        assert not p.startswith(".venv")
        assert not p.startswith(".git")


@pytest.mark.asyncio
async def test_scanner_exclusion_rules(temp_dir: Path):
    """Verify custom exclusion patterns are honored."""
    repo = create_standard_fixture_repo(temp_dir)
    settings = Settings(ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)])
    scanner = Scanner(settings=settings)

    # Exclude tests/ directory
    result = await scanner.run_full_scan(repo_path=repo, exclude_paths=["tests"])
    for u in result.usages:
        assert not u.path.startswith("tests")


def test_walker_single_file_size_limit(temp_dir: Path):
    """Verify files exceeding MAX_SINGLE_FILE_BYTES are skipped with a warning."""
    repo = temp_dir / "repo_large"
    repo.mkdir(parents=True, exist_ok=True)

    # Create a 20KB file
    large_file = repo / "huge.py"
    large_file.write_text("x = 1\n" * 4000, encoding="utf-8")
    actual_size = large_file.stat().st_size

    # Walk with limit of 5000 bytes
    summary = walk_repository(
        repo_root=repo,
        max_single_file_bytes=5000,
    )

    assert len(summary.python_files) == 0
    assert len(summary.warnings) == 1
    assert "exceeds MAX_SINGLE_FILE_BYTES" in summary.warnings[0]


def test_walker_max_files_limit(temp_dir: Path):
    """Verify walker stops when MAX_ANALYSIS_FILES is reached."""
    repo = temp_dir / "repo_many"
    repo.mkdir(parents=True, exist_ok=True)

    for i in range(10):
        (repo / f"file_{i}.py").write_text("pass\n", encoding="utf-8")

    # Walk with limit of 3 files
    summary = walk_repository(
        repo_root=repo,
        max_files=3,
    )

    assert summary.scanned_file_count == 3
    assert any("Maximum analysis file limit" in w for w in summary.warnings)


def test_walker_symlink_escape_detection(temp_dir: Path):
    """Verify symlinks pointing outside the repository boundary are skipped."""
    repo = temp_dir / "repo_sym"
    repo.mkdir(parents=True, exist_ok=True)

    outside = temp_dir / "secret_outside.py"
    outside.write_text("import secret_outside\n", encoding="utf-8")

    symlink_file = repo / "sym_link.py"
    try:
        symlink_file.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not supported or requires admin privilege on this host")

    summary = walk_repository(repo_root=repo)
    # The escaped symlink must not be included as a valid python source
    escaped_paths = [f.relative_path for f in summary.python_files if "sym_link" in f.relative_path]
    assert len(escaped_paths) == 0
    assert any("escapes repository boundary" in w or "outside repository boundary" in w for w in summary.warnings)


def test_git_url_security_validation():
    """Verify Git URL validation rejects unsafe protocols and credentials."""
    # 1. Valid public HTTPS accepted
    valid_url = "https://github.com/rishrek/LinkWatch.git"
    assert validate_git_url(valid_url) == valid_url

    # 2. Insecure protocol rejected
    with pytest.raises(GitUrlSecurityError) as exc:
        validate_git_url("http://github.com/rishrek/LinkWatch.git")
    assert "Only public HTTPS" in str(exc.value)

    with pytest.raises(GitUrlSecurityError):
        validate_git_url("ssh://git@github.com/repo.git")

    # 3. Embedded credentials rejected
    with pytest.raises(GitUrlSecurityError) as exc:
        validate_git_url("https://token:secret@github.com/repo.git")
    assert "Embedded credentials" in str(exc.value)

    # 4. Command injection characters rejected
    with pytest.raises(GitUrlSecurityError) as exc:
        validate_git_url("https://github.com/repo.git; rm -rf /")
    assert "Unsafe characters detected" in str(exc.value)


def test_walker_total_source_bytes_limit(temp_dir: Path):
    """Verify walker halts and warns when MAX_TOTAL_SOURCE_BYTES is reached."""
    repo = temp_dir / "repo_total_bytes"
    repo.mkdir(parents=True, exist_ok=True)

    # Create 3 files of 4KB each = 12KB total
    for i in range(3):
        (repo / f"code_{i}.py").write_text("# padding\n" * 400, encoding="utf-8")

    # Set total source limit to 7KB
    summary = walk_repository(
        repo_root=repo,
        max_total_source_bytes=7000,
    )

    assert any("source size limit" in w.lower() for w in summary.warnings)
    assert summary.scanned_byte_count <= 7000



@pytest.mark.asyncio
async def test_scanner_with_lockfiles_and_pipfile(temp_dir: Path):
    """Verify full repository scan discovers dependencies across Pipfile and lockfiles."""
    repo = create_lockfiles_and_pipfile_fixture_repo(temp_dir)
    settings = Settings(ALLOWED_REPOSITORY_ROOTS=[str(temp_dir)])
    scanner = Scanner(settings=settings)

    result = await scanner.run_full_scan(repo_path=repo)

    dep_names = {d.distribution_name for d in result.dependencies}
    assert "requests" in dep_names
    assert "flask" in dep_names
    assert "pytest" in dep_names
    assert "urllib3" in dep_names
    assert "certifi" in dep_names

    # Check lockfile entries have resolved versions
    urllib3_dep = next(d for d in result.dependencies if d.distribution_name == "urllib3")
    assert urllib3_dep.resolved_version == "1.26.12"
    assert urllib3_dep.package_manager == "uv"

