"""Unit tests for the ExitLens deterministic maintenance risk engine."""

import pytest
from app.risk.engine import RiskEngine, RULE_SET_VERSION, are_specs_conflicting, is_wide_or_unpinned
from app.risk.metadata import LocalApprovedMetadataRegistry
from app.schemas.capsule import DependencyDetails, UsageLocation
from app.schemas.common import ProvenanceKind
from app.schemas.evidence import EvidenceRecord
from app.schemas.risk import RiskSeverity


def create_dummy_evidence(ev_id: str, path: str, excerpt: str) -> EvidenceRecord:
    """Helper to create test evidence record."""
    return EvidenceRecord(
        evidence_id=ev_id,
        kind="manifest_declaration",
        provenance=ProvenanceKind.OBSERVED,
        path=path,
        line_start=1,
        line_end=1,
        excerpt=excerpt,
        sha256="dummy_hash",
        observed_at_utc="2026-10-15T12:00:00Z",
    )


def test_rule_set_version_and_provenance():
    """Verify rule set version is explicitly defined and all findings are INFERRED."""
    engine = RiskEngine()
    assert engine.rule_set_version == RULE_SET_VERSION
    assert engine.rule_set_version == "exitlens-risk-v1"

    ev = create_dummy_evidence("ev-1", "requirements.txt", "unpinned_pkg")
    dep = DependencyDetails(
        distribution_name="unpinned_pkg",
        manifest_path="requirements.txt",
        declared_specifier="*",
    )

    findings = engine.assess_risks(dependencies=[dep], usages=[], evidence=[ev])
    assert len(findings) > 0
    for f in findings:
        assert f.provenance == ProvenanceKind.INFERRED
        assert f.rule_id != ""
        assert f.title != ""
        assert f.explanation != ""
        assert len(f.evidence_refs) > 0


def test_rule_unpinned_or_wide_constraint():
    """Verify Rule 1 flags unpinned/wide constraints and prevents false positives on tight bounds."""
    engine = RiskEngine()

    ev1 = create_dummy_evidence("ev-1", "requirements.txt", "wide_pkg>=1.0.0")
    ev2 = create_dummy_evidence("ev-2", "requirements.txt", "pinned_pkg==1.2.3")
    ev3 = create_dummy_evidence("ev-3", "requirements.txt", "bounded_pkg>=2.0.0, <3.0.0")
    ev4 = create_dummy_evidence("ev-4", "requirements.txt", "compat_pkg~=1.4.0")
    ev5 = create_dummy_evidence("ev-5", "pyproject.toml", "poetry_pkg = ^1.2.0")

    deps = [
        # Positive case: open >=
        DependencyDetails(distribution_name="wide_pkg", manifest_path="requirements.txt", declared_specifier=">=1.0.0"),
        # Positive case: completely unpinned *
        DependencyDetails(distribution_name="star_pkg", manifest_path="requirements.txt", declared_specifier="*"),
        # False-positive prevention: exact pin
        DependencyDetails(distribution_name="pinned_pkg", manifest_path="requirements.txt", declared_specifier="==1.2.3"),
        # False-positive prevention: bounded major range
        DependencyDetails(distribution_name="bounded_pkg", manifest_path="requirements.txt", declared_specifier=">=2.0.0, <3.0.0"),
        # False-positive prevention: compatible release ~=
        DependencyDetails(distribution_name="compat_pkg", manifest_path="requirements.txt", declared_specifier="~=1.4.0"),
        # False-positive prevention: Poetry caret ^1.2.0 (locks to <2.0.0)
        DependencyDetails(distribution_name="poetry_pkg", manifest_path="pyproject.toml", declared_specifier="^1.2.0"),
    ]

    findings = engine.assess_risks(dependencies=deps, usages=[], evidence=[ev1, ev2, ev3, ev4, ev5])
    unpinned_rules = [f for f in findings if f.rule_id == "UNPINNED_OR_WIDE_CONSTRAINT"]

    flagged_names = {f.title for f in unpinned_rules}
    assert any("wide_pkg" in t for t in flagged_names)
    assert any("star_pkg" in t for t in flagged_names)

    # Must NOT flag pinned, bounded, or compatible versions
    assert not any("pinned_pkg" in t for t in flagged_names)
    assert not any("bounded_pkg" in t for t in flagged_names)
    assert not any("compat_pkg" in t for t in flagged_names)
    assert not any("poetry_pkg" in t for t in flagged_names)


def test_rule_manifest_lock_drift():
    """Verify Rule 2 flags locked versions that do not satisfy manifest specifiers."""
    engine = RiskEngine()

    ev_m = create_dummy_evidence("ev-m", "requirements.txt", "urllib3==1.26.15")
    ev_l = create_dummy_evidence("ev-l", "poetry.lock", "urllib3==2.0.0")

    # Manifest requires ==1.26.15, but lockfile has 2.0.0
    manifest_dep = DependencyDetails(
        distribution_name="urllib3",
        manifest_path="requirements.txt",
        declared_specifier="==1.26.15",
    )
    locked_dep = DependencyDetails(
        distribution_name="urllib3",
        manifest_path="poetry.lock",
        declared_specifier="==2.0.0",
        resolved_version="2.0.0",
    )

    # Compatible pair: manifest requests>=2.0.0, <3.0.0 and lockfile 2.28.1
    compat_manifest = DependencyDetails(
        distribution_name="requests",
        manifest_path="requirements.txt",
        declared_specifier=">=2.0.0, <3.0.0",
    )
    compat_lock = DependencyDetails(
        distribution_name="requests",
        manifest_path="poetry.lock",
        declared_specifier="==2.28.1",
        resolved_version="2.28.1",
    )

    findings = engine.assess_risks(
        dependencies=[manifest_dep, locked_dep, compat_manifest, compat_lock],
        usages=[],
        evidence=[ev_m, ev_l],
    )

    drift_rules = [f for f in findings if f.rule_id == "MANIFEST_LOCK_DRIFT"]
    assert len(drift_rules) == 1
    assert "urllib3" in drift_rules[0].title
    assert drift_rules[0].severity == RiskSeverity.HIGH
    # Evidence refs must link both manifest and lockfile
    assert "ev-m" in drift_rules[0].evidence_refs
    assert "ev-l" in drift_rules[0].evidence_refs

    # requests must NOT be flagged as drift
    assert not any("requests" in f.title for f in drift_rules)


def test_rule_conflicting_declarations():
    """Verify Rule 3 flags incompatible constraints across manifests but honors disjoint markers."""
    engine = RiskEngine()

    ev1 = create_dummy_evidence("ev-1", "requirements.txt", "urllib3==1.26.15")
    ev2 = create_dummy_evidence("ev-2", "setup.cfg", "urllib3>=2.0.0")
    ev3 = create_dummy_evidence("ev-3", "requirements.txt", "colorama==0.4.4; sys_platform == 'win32'")
    ev4 = create_dummy_evidence("ev-4", "setup.cfg", "colorama==0.4.6; sys_platform == 'linux'")

    deps = [
        # Incompatible conflicting pair
        DependencyDetails(distribution_name="urllib3", manifest_path="requirements.txt", declared_specifier="==1.26.15"),
        DependencyDetails(distribution_name="urllib3", manifest_path="setup.cfg", declared_specifier=">=2.0.0"),
        # Disjoint platform markers (win32 vs linux) -> NOT a conflict!
        DependencyDetails(
            distribution_name="colorama",
            manifest_path="requirements.txt",
            declared_specifier="==0.4.4",
            runtime_markers="sys_platform == 'win32'",
        ),
        DependencyDetails(
            distribution_name="colorama",
            manifest_path="setup.cfg",
            declared_specifier="==0.4.6",
            runtime_markers="sys_platform == 'linux'",
        ),
    ]

    findings = engine.assess_risks(dependencies=deps, usages=[], evidence=[ev1, ev2, ev3, ev4])
    conflict_rules = [f for f in findings if f.rule_id == "CONFLICTING_DECLARATIONS"]

    assert len(conflict_rules) == 1
    assert "urllib3" in conflict_rules[0].title
    assert conflict_rules[0].severity == RiskSeverity.HIGH
    assert "ev-1" in conflict_rules[0].evidence_refs
    assert "ev-2" in conflict_rules[0].evidence_refs

    # colorama must NOT be flagged because markers are platform-disjoint
    assert not any("colorama" in f.title for f in conflict_rules)


def test_rule_lockfile_missing_where_expected():
    """Verify Rule 4 flags missing lockfiles for Poetry/Pipfile/uv projects."""
    engine = RiskEngine()
    ev = create_dummy_evidence("ev-p", "pyproject.toml", "poetry dependencies")

    # Poetry project without poetry.lock
    poetry_dep = DependencyDetails(
        distribution_name="httpx",
        manifest_path="pyproject.toml",
        declared_specifier=">=0.24.0",
        package_manager="poetry",
    )

    findings = engine.assess_risks(dependencies=[poetry_dep], usages=[], evidence=[ev])
    missing_lock = [f for f in findings if f.rule_id == "LOCKFILE_MISSING_WHERE_EXPECTED"]
    assert len(missing_lock) == 1
    assert "poetry.lock" in missing_lock[0].title

    # When poetry.lock is present, NO missing lockfile finding is emitted
    lock_dep = DependencyDetails(
        distribution_name="httpx",
        manifest_path="poetry.lock",
        declared_specifier="==0.24.0",
        resolved_version="0.24.0",
        package_manager="poetry",
    )
    findings_with_lock = engine.assess_risks(
        dependencies=[poetry_dep, lock_dep],
        usages=[],
        evidence=[ev],
    )
    missing_lock_resolved = [f for f in findings_with_lock if f.rule_id == "LOCKFILE_MISSING_WHERE_EXPECTED"]
    assert len(missing_lock_resolved) == 0


def test_rule_declared_no_static_usage_found():
    """Verify Rule 5 is review-only and does not claim code is unused."""
    engine = RiskEngine()
    ev1 = create_dummy_evidence("ev-1", "requirements.txt", "unused_tool==1.0")
    ev2 = create_dummy_evidence("ev-2", "requirements.txt", "pyyaml==6.0")

    dep_unused = DependencyDetails(
        distribution_name="unused_tool",
        manifest_path="requirements.txt",
        declared_specifier="==1.0",
        dependency_type="direct",
    )
    dep_used = DependencyDetails(
        distribution_name="pyyaml",
        manifest_path="requirements.txt",
        declared_specifier="==6.0",
        dependency_type="direct",
    )

    # Usage observed for pyyaml via import yaml
    yaml_usage = UsageLocation(
        usage_id="usg-1",
        path="src/main.py",
        line_start=5,
        symbol="yaml",
        pattern="import yaml",
        evidence_id="ev-u1",
    )

    findings = engine.assess_risks(
        dependencies=[dep_unused, dep_used],
        usages=[yaml_usage],
        evidence=[ev1, ev2],
    )

    no_usage_rules = [f for f in findings if f.rule_id == "DECLARED_NO_STATIC_USAGE_FOUND"]
    assert len(no_usage_rules) == 1
    rule = no_usage_rules[0]
    assert "unused_tool" in rule.title
    assert rule.severity == RiskSeverity.LOW
    assert rule.confidence == "REVIEW_ONLY"
    assert "review-only" in rule.explanation.lower()
    assert "does not prove the dependency is unused" in rule.explanation.lower()

    # pyyaml had usage via alias 'yaml', must not be flagged
    assert not any("pyyaml" in f.title for f in no_usage_rules)


def test_rule_import_not_mapped_to_distribution():
    """Verify Rule 6 flags unmapped external imports while filtering standard library."""
    engine = RiskEngine()

    ev_m = create_dummy_evidence("ev-u1", "src/job.py", "import mystery_tool")
    unmapped_usage = UsageLocation(
        usage_id="usg-unmapped",
        path="src/job.py",
        line_start=12,
        symbol="mystery_tool",
        pattern="import mystery_tool",
        evidence_id="ev-u1",
        note="Uncertain mapping: module does not directly match a declared manifest package.",
    )

    findings = engine.assess_risks(
        dependencies=[],
        usages=[unmapped_usage],
        evidence=[ev_m],
    )

    unmapped_rules = [f for f in findings if f.rule_id == "IMPORT_NOT_MAPPED_TO_DISTRIBUTION"]
    assert len(unmapped_rules) == 1
    assert "mystery_tool" in unmapped_rules[0].title
    assert unmapped_rules[0].severity == RiskSeverity.MEDIUM
    assert unmapped_rules[0].evidence_refs == ["ev-u1"]


def test_rule_runtime_constraint_mismatch():
    """Verify Rule 7 flags environment markers incompatible with target Python."""
    engine = RiskEngine(target_python_version="3.12")

    ev1 = create_dummy_evidence("ev-1", "requirements.txt", "old_pkg; python_version < '3.8'")
    ev2 = create_dummy_evidence("ev-2", "requirements.txt", "valid_pkg; python_version >= '3.8'")

    dep_old = DependencyDetails(
        distribution_name="old_pkg",
        manifest_path="requirements.txt",
        declared_specifier="==1.0",
        runtime_markers="python_version < '3.8'",
    )
    dep_valid = DependencyDetails(
        distribution_name="valid_pkg",
        manifest_path="requirements.txt",
        declared_specifier="==2.0",
        runtime_markers="python_version >= '3.8'",
    )

    findings = engine.assess_risks(
        dependencies=[dep_old, dep_valid],
        usages=[],
        evidence=[ev1, ev2],
    )

    mismatch_rules = [f for f in findings if f.rule_id == "RUNTIME_CONSTRAINT_MISMATCH"]
    assert len(mismatch_rules) == 1
    assert "old_pkg" in mismatch_rules[0].title
    assert mismatch_rules[0].severity == RiskSeverity.HIGH

    # valid_pkg matches Python 3.12, must not be flagged
    assert not any("valid_pkg" in f.title for f in mismatch_rules)


def test_rule_deprecated_or_stale_metadata():
    """Verify Rule 8 only flags packages explicitly deprecated in approved metadata."""
    custom_metadata = LocalApprovedMetadataRegistry(
        custom_deprecations={"my_retired_lib": "Officially superseded by modern_lib."}
    )
    engine = RiskEngine(metadata_source=custom_metadata)

    ev1 = create_dummy_evidence("ev-1", "requirements.txt", "my_retired_lib==0.5.0")
    ev2 = create_dummy_evidence("ev-2", "requirements.txt", "optparse")
    ev3 = create_dummy_evidence("ev-3", "requirements.txt", "very_old_pkg==0.1.0")

    dep_retired = DependencyDetails(
        distribution_name="my_retired_lib",
        manifest_path="requirements.txt",
        declared_specifier="==0.5.0",
    )
    dep_optparse = DependencyDetails(
        distribution_name="optparse",
        manifest_path="requirements.txt",
        declared_specifier="*",
    )
    # Old version of an unknown package: must NOT be flagged as deprecated
    dep_old_unknown = DependencyDetails(
        distribution_name="very_old_pkg",
        manifest_path="requirements.txt",
        declared_specifier="==0.1.0",
    )

    findings = engine.assess_risks(
        dependencies=[dep_retired, dep_optparse, dep_old_unknown],
        usages=[],
        evidence=[ev1, ev2, ev3],
    )

    deprecated_rules = [f for f in findings if f.rule_id == "DEPRECATED_OR_STALE_METADATA"]
    flagged = {f.title for f in deprecated_rules}

    assert any("my_retired_lib" in t for t in flagged)
    assert any("optparse" in t for t in flagged)

    # STRICT CONSTRAINT: Never label a package unmaintained solely because its version is old!
    assert not any("very_old_pkg" in t for t in flagged)
    # Status of unknown metadata must be 'not_assessed', not an inferred risk
    assert custom_metadata.get_metadata_status("very_old_pkg") == "not_assessed"
