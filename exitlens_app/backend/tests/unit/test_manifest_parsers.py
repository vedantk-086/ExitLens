"""Unit tests for non-executing manifest parsers."""

from pathlib import Path
import pytest

from app.core.ids import generate_evidence_id
from app.scanner.manifest_parsers import ManifestParser
from tests.fixtures.repo_fixtures import (
    create_dynamic_and_malformed_fixture_repo,
    create_lockfiles_and_pipfile_fixture_repo,
    create_malformed_manifests_fixture_repo,
    create_standard_fixture_repo,
)


def test_requirements_parser_standard_and_recursive(temp_dir: Path):
    """Verify requirements.txt parsing with recursive includes and line references."""
    repo = create_standard_fixture_repo(temp_dir)
    ev_count = 0

    def id_gen():
        nonlocal ev_count
        ev_count += 1
        return generate_evidence_id(counter=ev_count)

    parser = ManifestParser(repo_root=repo, id_generator=id_gen)
    deps, evs, warns = parser.parse_requirements(repo / "requirements.txt")

    # Should discover requests, urllib3, colorama, and included pyyaml & click
    names = {d.distribution_name for d in deps}
    assert "requests" in names
    assert "urllib3" in names
    assert "colorama" in names
    assert "pyyaml" in names
    assert "click" in names

    # Check evidence structure
    assert len(evs) == len(deps)
    urllib3_ev = next(e for e in evs if "urllib3" in e.excerpt)
    assert urllib3_ev.line_start == 3
    assert urllib3_ev.sha256 != ""
    assert urllib3_ev.path == "requirements.txt"

    # Check included file evidence
    pyyaml_ev = next(e for e in evs if "pyyaml" in e.excerpt)
    assert pyyaml_ev.path == "extra-requirements.txt"


def test_requirements_circular_include_defense(temp_dir: Path):
    """Verify circular -r dependencies do not cause infinite recursion."""
    repo = create_dynamic_and_malformed_fixture_repo(temp_dir)
    ev_count = 0

    def id_gen():
        nonlocal ev_count
        ev_count += 1
        return generate_evidence_id(counter=ev_count)

    parser = ManifestParser(repo_root=repo, id_generator=id_gen)
    deps, evs, warns = parser.parse_requirements(repo / "req_a.txt")

    # Both packages discovered
    names = {d.distribution_name for d in deps}
    assert "pkg-a" in names
    assert "pkg-b" in names

    # Warning generated for loop
    assert any("Recursive requirement loop detected" in w for w in warns)


def test_unsupported_pip_directives_generate_warnings(temp_dir: Path):
    """Verify -c, -i, -e directives generate scanner coverage warnings."""
    repo = create_dynamic_and_malformed_fixture_repo(temp_dir)
    ev_count = 0

    def id_gen():
        nonlocal ev_count
        ev_count += 1
        return generate_evidence_id(counter=ev_count)

    parser = ManifestParser(repo_root=repo, id_generator=id_gen)
    deps, evs, warns = parser.parse_requirements(repo / "requirements.txt")

    # Valid package still discovered
    names = {d.distribution_name for d in deps}
    assert "valid-pkg" in names

    # Warnings for unsupported directives
    assert any("constraints directive" in w for w in warns)
    assert any("custom index directive" in w for w in warns)
    assert any("editable installation" in w for w in warns)


def test_pyproject_toml_parser(temp_dir: Path):
    """Verify pyproject.toml PEP 621 and Poetry parsing."""
    repo = create_standard_fixture_repo(temp_dir)
    ev_count = 0

    def id_gen():
        nonlocal ev_count
        ev_count += 1
        return generate_evidence_id(counter=ev_count)

    parser = ManifestParser(repo_root=repo, id_generator=id_gen)
    deps, evs, warns = parser.parse_pyproject(repo / "pyproject.toml")

    names = {d.distribution_name for d in deps}
    assert "fastapi" in names
    assert "pydantic" in names
    assert "pytest" in names
    assert "httpx" in names
    # python itself is filtered out as runtime, not a dependency
    assert "python" not in names


def test_setup_cfg_parser(temp_dir: Path):
    """Verify setup.cfg parsing."""
    repo = create_standard_fixture_repo(temp_dir)
    ev_count = 0

    def id_gen():
        nonlocal ev_count
        ev_count += 1
        return generate_evidence_id(counter=ev_count)

    parser = ManifestParser(repo_root=repo, id_generator=id_gen)
    deps, evs, warns = parser.parse_setup_cfg(repo / "setup.cfg")

    names = {d.distribution_name for d in deps}
    assert "tqdm" in names
    assert "packaging" in names
    assert "pytest-mock" in names


def test_setup_py_ast_inspection_only(temp_dir: Path):
    """Verify setup.py uses static AST inspection only and NEVER executes code."""
    repo = create_dynamic_and_malformed_fixture_repo(temp_dir)
    ev_count = 0

    def id_gen():
        nonlocal ev_count
        ev_count += 1
        return generate_evidence_id(counter=ev_count)

    parser = ManifestParser(repo_root=repo, id_generator=id_gen)
    deps, evs, warns = parser.parse_setup_py(repo / "setup.py")

    # Static literal in tests_require is parsed
    names = {d.distribution_name for d in deps}
    assert "static-test-dep" in names

    # Dynamic call triggers warning rather than execution
    assert any("Dynamic dependency declaration" in w for w in warns)


def test_poetry_lock_parser(temp_dir: Path):
    """Verify poetry.lock parsing extracts package names, versions, and categories."""
    repo = create_lockfiles_and_pipfile_fixture_repo(temp_dir)
    ev_count = 0

    def id_gen():
        nonlocal ev_count
        ev_count += 1
        return generate_evidence_id(counter=ev_count)

    parser = ManifestParser(repo_root=repo, id_generator=id_gen)
    deps, evs, warns = parser.parse_lockfile(repo / "poetry.lock")

    names = {d.distribution_name for d in deps}
    assert "requests" in names
    assert "pytest" in names

    req_dep = next(d for d in deps if d.distribution_name == "requests")
    assert req_dep.resolved_version == "2.28.1"
    assert req_dep.dependency_type == "direct"
    assert req_dep.package_manager == "poetry"

    pytest_dep = next(d for d in deps if d.distribution_name == "pytest")
    assert pytest_dep.resolved_version == "7.1.3"
    assert pytest_dep.dependency_type == "dev"


def test_uv_lock_parser(temp_dir: Path):
    """Verify uv.lock parsing extracts packages and resolved versions."""
    repo = create_lockfiles_and_pipfile_fixture_repo(temp_dir)
    ev_count = 0

    def id_gen():
        nonlocal ev_count
        ev_count += 1
        return generate_evidence_id(counter=ev_count)

    parser = ManifestParser(repo_root=repo, id_generator=id_gen)
    deps, evs, warns = parser.parse_lockfile(repo / "uv.lock")

    names = {d.distribution_name for d in deps}
    assert "urllib3" in names
    assert "certifi" in names

    urllib3_dep = next(d for d in deps if d.distribution_name == "urllib3")
    assert urllib3_dep.resolved_version == "1.26.12"
    assert urllib3_dep.package_manager == "uv"


def test_pipfile_and_pipfile_lock_parser(temp_dir: Path):
    """Verify Pipfile and Pipfile.lock parsing for default and dev sections."""
    repo = create_lockfiles_and_pipfile_fixture_repo(temp_dir)
    ev_count = 0

    def id_gen():
        nonlocal ev_count
        ev_count += 1
        return generate_evidence_id(counter=ev_count)

    parser = ManifestParser(repo_root=repo, id_generator=id_gen)

    # 1. Pipfile
    deps, evs, warns = parser.parse_pipfile(repo / "Pipfile")
    names = {d.distribution_name for d in deps}
    assert "requests" in names
    assert "flask" in names
    assert "pytest" in names

    pytest_dep = next(d for d in deps if d.distribution_name == "pytest")
    assert pytest_dep.dependency_type == "dev"
    assert pytest_dep.package_manager == "pipfile"

    # 2. Pipfile.lock
    lock_deps, lock_evs, lock_warns = parser.parse_lockfile(repo / "Pipfile.lock")
    lock_names = {d.distribution_name for d in lock_deps}
    assert "requests" in lock_names
    assert "flask" in lock_names
    assert "pytest" in lock_names

    req_lock = next(d for d in lock_deps if d.distribution_name == "requests")
    assert req_lock.resolved_version == "2.28.1"
    assert req_lock.declared_specifier == "==2.28.1"


def test_malformed_manifests_generate_warnings(temp_dir: Path):
    """Verify malformed TOML, JSON, and INI manifests generate coverage warnings without crashing."""
    repo = create_malformed_manifests_fixture_repo(temp_dir)
    ev_count = 0

    def id_gen():
        nonlocal ev_count
        ev_count += 1
        return generate_evidence_id(counter=ev_count)

    parser = ManifestParser(repo_root=repo, id_generator=id_gen)

    # Corrupted pyproject.toml
    deps, evs, warns = parser.parse_pyproject(repo / "pyproject.toml")
    assert len(deps) == 0
    assert any("Malformed pyproject.toml" in w for w in warns)

    # Corrupted Pipfile
    deps, evs, warns = parser.parse_pipfile(repo / "Pipfile")
    assert len(deps) == 0
    assert any("Malformed Pipfile" in w for w in warns)

    # Corrupted Pipfile.lock
    deps, evs, warns = parser.parse_lockfile(repo / "Pipfile.lock")
    assert len(deps) == 0
    assert any("Malformed Pipfile.lock" in w for w in warns)

    # Corrupted setup.cfg
    deps, evs, warns = parser.parse_setup_cfg(repo / "setup.cfg")
    assert len(deps) == 0
    assert any("Malformed setup.cfg" in w for w in warns)

