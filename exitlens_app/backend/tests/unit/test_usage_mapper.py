"""Unit tests for AST Python dependency usage mapping."""

from pathlib import Path
import pytest

from app.core.ids import generate_evidence_id
from app.scanner.models import DiscoveredFile
from app.scanner.usage_mapper import UsageMapper
from tests.fixtures.repo_fixtures import (
    create_dynamic_and_malformed_fixture_repo,
    create_standard_fixture_repo,
)


def test_usage_mapper_accurate_line_and_symbol(temp_dir: Path):
    """Verify AST usage mapper locates imports, symbols, and line numbers accurately."""
    repo = create_standard_fixture_repo(temp_dir)
    ev_count = 0

    def id_gen():
        nonlocal ev_count
        ev_count += 1
        return generate_evidence_id(counter=ev_count)

    declared = {"requests", "urllib3", "pyyaml", "fastapi"}
    mapper = UsageMapper(repo_root=repo, id_generator=id_gen, declared_distributions=declared)

    app_file = DiscoveredFile(
        absolute_path=repo / "src" / "app.py",
        relative_path="src/app.py",
        size_bytes=300,
        is_python=True,
        is_test=False,
    )

    usages, evs, warns = mapper.map_file_usages(app_file)
    assert len(usages) >= 4
    assert len(evs) == len(usages)

    # 1. import requests at line 1
    req_usage = next(u for u in usages if "requests" in u.pattern)
    assert req_usage.line_start == 1
    assert req_usage.path == "src/app.py"

    # 2. from urllib3.util import Retry at line 2
    urllib3_usage = next(u for u in usages if "urllib3" in u.pattern)
    assert urllib3_usage.line_start == 2
    assert urllib3_usage.symbol == "Retry"

    # 3. import yaml mapped to pyyaml via alias database
    yaml_usage = next(u for u in usages if "yaml" in u.pattern)
    assert yaml_usage.line_start == 3
    # Check that alias was resolved and not uncertain
    assert yaml_usage.note is None


def test_test_file_usage_tagged_properly(temp_dir: Path):
    """Verify test file imports are tagged with kind=test_usage."""
    repo = create_standard_fixture_repo(temp_dir)
    ev_count = 0

    def id_gen():
        nonlocal ev_count
        ev_count += 1
        return generate_evidence_id(counter=ev_count)

    declared = {"pytest", "requests"}
    mapper = UsageMapper(repo_root=repo, id_generator=id_gen, declared_distributions=declared)

    test_file = DiscoveredFile(
        absolute_path=repo / "tests" / "test_app.py",
        relative_path="tests/test_app.py",
        size_bytes=200,
        is_python=True,
        is_test=True,
    )

    usages, evs, warns = mapper.map_file_usages(test_file)
    assert len(usages) >= 2
    for ev in evs:
        assert ev.kind == "test_usage"


def test_syntax_error_handled_gracefully(temp_dir: Path):
    """Verify malformed Python files generate coverage warnings and do not crash."""
    repo = create_dynamic_and_malformed_fixture_repo(temp_dir)
    ev_count = 0

    def id_gen():
        nonlocal ev_count
        ev_count += 1
        return generate_evidence_id(counter=ev_count)

    mapper = UsageMapper(repo_root=repo, id_generator=id_gen, declared_distributions=set())

    broken_file = DiscoveredFile(
        absolute_path=repo / "bad_syntax.py",
        relative_path="bad_syntax.py",
        size_bytes=100,
        is_python=True,
        is_test=False,
    )

    usages, evs, warns = mapper.map_file_usages(broken_file)
    assert len(usages) == 0
    assert len(warns) == 1
    assert "Syntax error" in warns[0]


def test_unmapped_import_uncertainty_handling(temp_dir: Path):
    """Verify unmapped external imports identify uncertainty and never claim 'unused'."""
    repo = temp_dir / "uncertain_repo"
    repo.mkdir(parents=True, exist_ok=True)
    code_file = repo / "handler.py"
    code_file.write_text(
        "import undeclared_custom_lib\n"
        "from mystery_module.sub import MysteryClass\n",
        encoding="utf-8",
    )

    ev_count = 0

    def id_gen():
        nonlocal ev_count
        ev_count += 1
        return generate_evidence_id(counter=ev_count)

    # Declared distributions list does not contain undeclared_custom_lib or mystery_module
    mapper = UsageMapper(repo_root=repo, id_generator=id_gen, declared_distributions={"requests"})
    discovered = DiscoveredFile(
        absolute_path=code_file,
        relative_path="handler.py",
        size_bytes=code_file.stat().st_size,
        is_python=True,
        is_test=False,
    )

    usages, evs, warns = mapper.map_file_usages(discovered)

    assert len(usages) == 2
    for u in usages:
        assert u.note is not None
        assert "Uncertain mapping" in u.note
        # ExitLens must NEVER label or claim dependencies as 'unused' simply because of static AST ambiguity
        assert "unused" not in (u.note or "").lower()

    # Evidence records created for both uncertain usages
    assert len(evs) == 2
    for ev in evs:
        assert ev.path == "handler.py"
        assert ev.provenance.value == "OBSERVED"


def test_dynamic_import_detection(temp_dir: Path):
    """Verify __import__ and import_module calls are detected with dynamic_import kind."""
    repo = temp_dir / "dynamic_import_repo"
    repo.mkdir(parents=True, exist_ok=True)
    code_file = repo / "dynamic_loader.py"
    code_file.write_text(
        "import importlib\n\n"
        "mod1 = __import__('dynamically_loaded_pkg')\n"
        "mod2 = importlib.import_module('another_dynamic_pkg')\n",
        encoding="utf-8",
    )

    ev_count = 0

    def id_gen():
        nonlocal ev_count
        ev_count += 1
        return generate_evidence_id(counter=ev_count)

    mapper = UsageMapper(repo_root=repo, id_generator=id_gen, declared_distributions=set())
    discovered = DiscoveredFile(
        absolute_path=code_file,
        relative_path="dynamic_loader.py",
        size_bytes=code_file.stat().st_size,
        is_python=True,
        is_test=False,
    )

    usages, evs, warns = mapper.map_file_usages(discovered)

    # Dynamic calls detected
    dyn_evs = [e for e in evs if e.kind == "dynamic_import"]
    assert len(dyn_evs) == 2

    symbols = {u.symbol for u in usages if "dynamic" in u.pattern}
    assert "dynamically_loaded_pkg" in symbols
    assert "another_dynamic_pkg" in symbols


def test_line_range_and_excerpt_accuracy(temp_dir: Path):
    """Verify line start, line end, and excerpt content accuracy across multi-statement files."""
    repo = temp_dir / "line_repo"
    repo.mkdir(parents=True, exist_ok=True)
    code_file = repo / "complex.py"
    code_file.write_text(
        "# Header comments\n"           # 1
        "# More comments\n"             # 2
        "import os\n"                   # 3
        "import sys\n"                  # 4
        "import requests\n"             # 5
        "\n"                            # 6
        "from urllib3.util import (\n"  # 7
        "    Retry,\n"                  # 8
        ")\n",                          # 9
        encoding="utf-8",
    )

    ev_count = 0

    def id_gen():
        nonlocal ev_count
        ev_count += 1
        return generate_evidence_id(counter=ev_count)

    mapper = UsageMapper(
        repo_root=repo,
        id_generator=id_gen,
        declared_distributions={"requests", "urllib3"},
    )
    discovered = DiscoveredFile(
        absolute_path=code_file,
        relative_path="complex.py",
        size_bytes=code_file.stat().st_size,
        is_python=True,
        is_test=False,
    )

    usages, evs, warns = mapper.map_file_usages(discovered)

    req_usage = next(u for u in usages if "requests" in u.pattern)
    assert req_usage.line_start == 5
    assert "import requests" in req_usage.import_statement

    retry_usage = next(u for u in usages if "urllib3" in u.pattern)
    assert retry_usage.line_start == 7
    assert retry_usage.symbol == "Retry"

