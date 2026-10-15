"""Deterministic maintenance risk assessment engine for ExitLens.

Consumes observed facts only (DependencyDetails, UsageLocation, EvidenceRecord)
and outputs explainable, versioned INFERRED risk indicators.
"""

from typing import Dict, List, Optional, Set, Tuple
import re

from packaging.markers import InvalidMarker, Marker
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from app.core.logging import get_logger
from app.risk.base import BaseRiskEngine
from app.risk.metadata import ApprovedMetadataSource, LocalApprovedMetadataRegistry
from app.scanner.mapping import normalize_package_name
from app.schemas.capsule import DependencyDetails, UsageLocation
from app.schemas.common import ProvenanceKind
from app.schemas.evidence import EvidenceRecord
from app.schemas.risk import RiskIndicator, RiskSeverity

logger = get_logger("exitlens.risk")

RULE_SET_VERSION = "exitlens-risk-v1"


def poetry_spec_to_pep440(spec: str) -> str:
    """Convert Poetry ^ and ~ specifiers to standard PEP 440 clauses."""
    s = spec.strip()
    if s.startswith("^"):
        v_str = s[1:].strip()
        parts = v_str.split(".")
        try:
            major = int(parts[0])
            if major > 0:
                return f">={v_str},<{major + 1}.0.0"
            if len(parts) > 1:
                minor = int(parts[1])
                if minor > 0:
                    return f">={v_str},<0.{minor + 1}.0"
            if len(parts) > 2:
                patch = int(parts[2])
                return f">={v_str},<0.0.{patch + 1}"
            return f"=={v_str}"
        except ValueError:
            return s
    elif s.startswith("~") and not s.startswith("~="):
        v_str = s[1:].strip()
        parts = v_str.split(".")
        try:
            major = int(parts[0])
            if len(parts) == 1:
                return f">={v_str},<{major + 1}.0.0"
            minor = int(parts[1])
            return f">={v_str},<{major}.{minor + 1}.0"
        except ValueError:
            return s
    return s


def is_wide_or_unpinned(spec_str: str) -> Tuple[bool, bool]:
    """Determine if a version specifier is unpinned or excessively wide.
    
    Returns (is_unpinned_or_wide, is_completely_unpinned).
    """
    clean = spec_str.strip()
    if not clean or clean in ("*", ">=0", ">=0.0", ">=0.0.0"):
        return True, True

    # Single open >= or > without upper bound
    if (clean.startswith(">=") or clean.startswith(">")) and "," not in clean:
        return True, False

    # Lone !=
    if clean.startswith("!=") and "," not in clean:
        return True, False

    # Check wide multi-bounds (e.g. >=1.0, <10.0)
    pep440 = poetry_spec_to_pep440(clean)
    try:
        spec_set = SpecifierSet(pep440)
        lowers: List[Version] = []
        uppers: List[Version] = []
        for s in spec_set:
            if s.operator in (">=", ">"):
                lowers.append(Version(s.version))
            elif s.operator in ("<=", "<"):
                uppers.append(Version(s.version))
        if lowers and uppers:
            min_lower = min(lowers)
            max_upper = max(uppers)
            if max_upper.major - min_lower.major >= 5:
                return True, False
    except Exception:
        pass

    return False, False


def are_specs_conflicting(spec1_raw: str, spec2_raw: str) -> bool:
    """Evaluate whether two dependency version constraints are mutually incompatible."""
    s1 = poetry_spec_to_pep440(spec1_raw)
    s2 = poetry_spec_to_pep440(spec2_raw)

    if s1 in ("*", "") or s2 in ("*", ""):
        return False

    try:
        set1 = SpecifierSet(s1)
        set2 = SpecifierSet(s2)
    except Exception:
        return False

    if set1 == set2:
        return False

    pin1: Optional[str] = None
    pin2: Optional[str] = None
    for s in set1:
        if s.operator in ("==", "==="):
            pin1 = s.version
    for s in set2:
        if s.operator in ("==", "==="):
            pin2 = s.version

    if pin1 and pin2:
        try:
            return Version(pin1) != Version(pin2)
        except InvalidVersion:
            return pin1 != pin2

    if pin1:
        try:
            return Version(pin1) not in set2
        except InvalidVersion:
            return False

    if pin2:
        try:
            return Version(pin2) not in set1
        except InvalidVersion:
            return False

    # Check disjoint bounds: e.g. <2.0.0 and >=2.0.0
    try:
        uppers1 = [Version(s.version) for s in set1 if s.operator in ("<", "<=")]
        lowers2 = [Version(s.version) for s in set2 if s.operator in (">", ">=")]
        if uppers1 and lowers2 and min(uppers1) <= max(lowers2):
            return True

        uppers2 = [Version(s.version) for s in set2 if s.operator in ("<", "<=")]
        lowers1 = [Version(s.version) for s in set1 if s.operator in (">", ">=")]
        if uppers2 and lowers1 and min(uppers2) <= max(lowers1):
            return True
    except InvalidVersion:
        pass

    return False


class RiskEngine(BaseRiskEngine):
    """Deterministic, versioned maintenance risk engine for ExitLens."""

    def __init__(
        self,
        metadata_source: Optional[ApprovedMetadataSource] = None,
        target_python_version: str = "3.12",
    ) -> None:
        self.metadata_source = metadata_source or LocalApprovedMetadataRegistry()
        self.target_python_version = target_python_version

    @property
    def rule_set_version(self) -> str:
        return RULE_SET_VERSION

    def assess_risks(
        self,
        dependencies: List[DependencyDetails],
        usages: List[UsageLocation],
        evidence: List[EvidenceRecord],
    ) -> List[RiskIndicator]:
        """Run all deterministic risk rules against observed records."""
        findings: List[RiskIndicator] = []
        evidence_map = self._build_evidence_map(evidence)

        # 1. Dependency-specific rules
        for dep in dependencies:
            dep_ev_ids = self._get_evidence_for_dependency(dep, evidence_map)
            findings.extend(self.assess_for_dependency(dep, dependencies, usages, evidence))

        # 2. Repository-wide manifest checks
        findings.extend(self._check_lockfile_missing_where_expected(dependencies, evidence_map))

        # 3. Usage-level unmapped import checks
        findings.extend(self._check_unmapped_imports(usages, dependencies, evidence))

        return self._deduplicate_findings(findings)

    def assess_for_dependency(
        self,
        dependency: DependencyDetails,
        all_dependencies: List[DependencyDetails],
        usages: List[UsageLocation],
        evidence: List[EvidenceRecord],
    ) -> List[RiskIndicator]:
        """Produce risk indicators specifically associated with a single dependency."""
        findings: List[RiskIndicator] = []
        evidence_map = self._build_evidence_map(evidence)
        dep_ev_ids = self._get_evidence_for_dependency(dependency, evidence_map)

        # Rule 1: UNPINNED_OR_WIDE_CONSTRAINT
        r1 = self._check_unpinned_or_wide(dependency, dep_ev_ids)
        if r1:
            findings.append(r1)

        # Rule 2: MANIFEST_LOCK_DRIFT
        r2 = self._check_manifest_lock_drift(dependency, all_dependencies, evidence_map)
        if r2:
            findings.append(r2)

        # Rule 3: CONFLICTING_DECLARATIONS
        r3 = self._check_conflicting_declarations(dependency, all_dependencies, evidence_map)
        if r3:
            findings.append(r3)

        # Rule 5: DECLARED_NO_STATIC_USAGE_FOUND
        r5 = self._check_declared_no_static_usage(dependency, usages, dep_ev_ids)
        if r5:
            findings.append(r5)

        # Rule 7: RUNTIME_CONSTRAINT_MISMATCH
        r7 = self._check_runtime_constraint_mismatch(dependency, dep_ev_ids)
        if r7:
            findings.append(r7)

        # Rule 8: DEPRECATED_OR_STALE_METADATA
        r8 = self._check_deprecated_or_stale_metadata(dependency, dep_ev_ids)
        if r8:
            findings.append(r8)

        return findings

    # -------------------------------------------------------------------------
    # Rule Implementations
    # -------------------------------------------------------------------------

    def _check_unpinned_or_wide(
        self,
        dep: DependencyDetails,
        evidence_ids: List[str],
    ) -> Optional[RiskIndicator]:
        """Rule 1: Flag unpinned or wide version constraints."""
        # Lockfiles contain locked versions, not floating declarations
        if dep.manifest_path.lower().endswith((".lock", "pipfile.lock")):
            return None

        is_wide, is_completely_unpinned = is_wide_or_unpinned(dep.declared_specifier)
        if not is_wide:
            return None

        severity = RiskSeverity.HIGH if is_completely_unpinned else RiskSeverity.MEDIUM
        title = f"Unpinned or wide version constraint for {dep.distribution_name}"
        explanation = (
            f"Dependency '{dep.distribution_name}' declared in '{dep.manifest_path}' uses constraint "
            f"'{dep.declared_specifier}'. Without an explicit upper bound, upstream breaking releases "
            "can introduce API incompatibilities unexpectedly."
        )

        return RiskIndicator(
            rule_id="UNPINNED_OR_WIDE_CONSTRAINT",
            severity=severity,
            provenance=ProvenanceKind.INFERRED,
            title=title,
            explanation=explanation,
            signal_source="manifest",
            evidence_refs=evidence_ids,
            confidence="HIGH",
            limitations="Does not account for external build-time constraints or private index version locks.",
        )

    def _check_manifest_lock_drift(
        self,
        dep: DependencyDetails,
        all_dependencies: List[DependencyDetails],
        evidence_map: Dict[Tuple[str, str], List[str]],
    ) -> Optional[RiskIndicator]:
        """Rule 2: Flag drift when locked version contradicts declared manifest constraint."""
        if dep.manifest_path.lower().endswith((".lock", "pipfile.lock")):
            return None

        norm_name = normalize_package_name(dep.distribution_name)
        clean_spec = poetry_spec_to_pep440(dep.declared_specifier)

        if clean_spec in ("", "*"):
            return None

        try:
            spec_set = SpecifierSet(clean_spec)
        except Exception:
            return None

        # Look for corresponding lockfile entries
        for other in all_dependencies:
            if not other.manifest_path.lower().endswith((".lock", "pipfile.lock")):
                continue
            if normalize_package_name(other.distribution_name) != norm_name:
                continue

            locked_ver = other.resolved_version
            if not locked_ver:
                continue

            try:
                ver_obj = Version(locked_ver)
                if ver_obj not in spec_set:
                    # Drift detected!
                    manifest_ev = evidence_map.get((dep.manifest_path, norm_name), [])
                    lock_ev = evidence_map.get((other.manifest_path, norm_name), [])
                    combined_ev = list(dict.fromkeys(manifest_ev + lock_ev))

                    title = f"Manifest-to-lockfile version drift for {dep.distribution_name}"
                    explanation = (
                        f"Dependency '{dep.distribution_name}' declared as '{dep.declared_specifier}' in "
                        f"'{dep.manifest_path}' does not match locked version '{locked_ver}' in '{other.manifest_path}'. "
                        "This indicates an out-of-sync lockfile where development and CI builds may resolve differently."
                    )
                    return RiskIndicator(
                        rule_id="MANIFEST_LOCK_DRIFT",
                        severity=RiskSeverity.HIGH,
                        provenance=ProvenanceKind.INFERRED,
                        title=title,
                        explanation=explanation,
                        signal_source="manifest_and_lockfile",
                        evidence_refs=combined_ev,
                        confidence="HIGH",
                        limitations="Assumes repository lockfile is intended to correspond to the manifest.",
                    )
            except InvalidVersion:
                continue

        return None

    def _check_conflicting_declarations(
        self,
        dep: DependencyDetails,
        all_dependencies: List[DependencyDetails],
        evidence_map: Dict[Tuple[str, str], List[str]],
    ) -> Optional[RiskIndicator]:
        """Rule 3: Flag conflicting constraints for the same package across manifests."""
        if dep.manifest_path.lower().endswith((".lock", "pipfile.lock")):
            return None

        norm_name = normalize_package_name(dep.distribution_name)

        for other in all_dependencies:
            if other.manifest_path.lower().endswith((".lock", "pipfile.lock")):
                continue
            if other.manifest_path == dep.manifest_path and other.declared_specifier == dep.declared_specifier:
                continue
            if normalize_package_name(other.distribution_name) != norm_name:
                continue

            # Check if environment markers make them disjoint (e.g. win32 vs linux)
            if self._are_markers_disjoint(dep.runtime_markers, other.runtime_markers):
                continue

            if are_specs_conflicting(dep.declared_specifier, other.declared_specifier):
                m1, s1 = dep.manifest_path, dep.declared_specifier
                m2, s2 = other.manifest_path, other.declared_specifier
                if m1 > m2:
                    m1, m2 = m2, m1
                    s1, s2 = s2, s1

                ev1 = evidence_map.get((m1, norm_name), [])
                ev2 = evidence_map.get((m2, norm_name), [])
                combined_ev = list(dict.fromkeys(ev1 + ev2))

                title = f"Conflicting declarations for {dep.distribution_name}"
                explanation = (
                    f"Dependency '{dep.distribution_name}' has incompatible requirements: '{s1}' "
                    f"in '{m1}' vs '{s2}' in '{m2}'. "
                    "Installing both in a single environment will result in dependency resolution failure."
                )
                return RiskIndicator(
                    rule_id="CONFLICTING_DECLARATIONS",

                    severity=RiskSeverity.HIGH,
                    provenance=ProvenanceKind.INFERRED,
                    title=title,
                    explanation=explanation,
                    signal_source="multiple_manifests",
                    evidence_refs=combined_ev,
                    confidence="HIGH",
                    limitations="Evaluates static version constraints without complex multi-marker SAT solving.",
                )

        return None

    def _check_lockfile_missing_where_expected(
        self,
        dependencies: List[DependencyDetails],
        evidence_map: Dict[Tuple[str, str], List[str]],
    ) -> List[RiskIndicator]:
        """Rule 4: Flag projects missing a lockfile where the packaging tool expects one."""
        findings: List[RiskIndicator] = []
        lockfile_paths = {d.manifest_path.lower() for d in dependencies if d.manifest_path.lower().endswith((".lock", "pipfile.lock"))}

        # Track distinct managers in manifests
        has_poetry_manifest = any(d.package_manager == "poetry" for d in dependencies)
        has_pipfile_manifest = any(d.package_manager == "pipfile" and not d.manifest_path.lower().endswith(".lock") for d in dependencies)
        has_uv_manifest = any(d.package_manager == "uv" and not d.manifest_path.lower().endswith(".lock") for d in dependencies)

        if has_poetry_manifest and not any("poetry.lock" in p for p in lockfile_paths):
            ev_ids = [e for (path, _), evs in evidence_map.items() if "pyproject.toml" in path for e in evs]
            findings.append(
                RiskIndicator(
                    rule_id="LOCKFILE_MISSING_WHERE_EXPECTED",
                    severity=RiskSeverity.MEDIUM,
                    provenance=ProvenanceKind.INFERRED,
                    title="Missing poetry.lock for Poetry project",
                    explanation="Poetry dependencies are declared in pyproject.toml, but no poetry.lock file was found in the repository. Deployments may resolve non-deterministic transitive dependencies.",
                    signal_source="repository_structure",
                    evidence_refs=ev_ids[:1],
                    confidence="HIGH",
                    limitations="Library packages intended for distribution on PyPI frequently omit lockfiles by design.",
                )
            )

        if has_pipfile_manifest and not any("pipfile.lock" in p for p in lockfile_paths):
            ev_ids = [e for (path, _), evs in evidence_map.items() if "pipfile" in path.lower() for e in evs]
            findings.append(
                RiskIndicator(
                    rule_id="LOCKFILE_MISSING_WHERE_EXPECTED",
                    severity=RiskSeverity.MEDIUM,
                    provenance=ProvenanceKind.INFERRED,
                    title="Missing Pipfile.lock for Pipenv project",
                    explanation="Pipfile dependencies are defined without an accompanying Pipfile.lock file in the repository.",
                    signal_source="repository_structure",
                    evidence_refs=ev_ids[:1],
                    confidence="HIGH",
                    limitations="Applies primarily to application services requiring deterministic builds.",
                )
            )

        if has_uv_manifest and not any("uv.lock" in p for p in lockfile_paths):
            ev_ids = [e for (path, _), evs in evidence_map.items() if "pyproject.toml" in path for e in evs]
            findings.append(
                RiskIndicator(
                    rule_id="LOCKFILE_MISSING_WHERE_EXPECTED",
                    severity=RiskSeverity.MEDIUM,
                    provenance=ProvenanceKind.INFERRED,
                    title="Missing uv.lock for uv project",
                    explanation="uv dependency configuration detected without an accompanying uv.lock file.",
                    signal_source="repository_structure",
                    evidence_refs=ev_ids[:1],
                    confidence="HIGH",
                    limitations="Applies primarily to application services requiring deterministic builds.",
                )
            )

        return findings

    def _check_declared_no_static_usage(
        self,
        dep: DependencyDetails,
        usages: List[UsageLocation],
        evidence_ids: List[str],
    ) -> Optional[RiskIndicator]:
        """Rule 5: Flag direct manifest dependencies that have no observed static imports."""
        if dep.manifest_path.lower().endswith((".lock", "pipfile.lock")):
            return None
        if dep.dependency_type != "direct":
            return None

        norm_name = normalize_package_name(dep.distribution_name)

        # Check if any static usage maps to this distribution
        has_usage = False
        for u in usages:
            sym_clean = normalize_package_name(u.symbol or "")
            pattern_clean = normalize_package_name(u.pattern or "")
            if sym_clean == norm_name or pattern_clean == norm_name:
                has_usage = True
                break
            # Common aliases
            if norm_name == "pyyaml" and ("yaml" in sym_clean or "yaml" in pattern_clean):
                has_usage = True
                break
            if norm_name == "pillow" and ("pil" in sym_clean or "pil" in pattern_clean):
                has_usage = True
                break
            if norm_name == "python-dateutil" and ("dateutil" in sym_clean or "dateutil" in pattern_clean):
                has_usage = True
                break

        if not has_usage:
            title = f"Declared dependency '{dep.distribution_name}' has no observed static usage"
            explanation = (
                f"Dependency '{dep.distribution_name}' declared in '{dep.manifest_path}' was not observed in any "
                "static AST import statement across scanned Python files. This is a review-only signal and does not "
                "prove the dependency is unused, as it may be invoked dynamically via plugins, CLI entry points, "
                "framework hooks, or runtime reflection."
            )
            return RiskIndicator(
                rule_id="DECLARED_NO_STATIC_USAGE_FOUND",
                severity=RiskSeverity.LOW,
                provenance=ProvenanceKind.INFERRED,
                title=title,
                explanation=explanation,
                signal_source="ast_usage_mapping",
                evidence_refs=evidence_ids,
                confidence="REVIEW_ONLY",
                limitations="Static AST analysis cannot detect dynamic imports (importlib), entry points, CLI tools, runtime plugin registries, or implicit dependencies loaded by third-party frameworks.",
            )

        return None

    def _check_unmapped_imports(
        self,
        usages: List[UsageLocation],
        all_dependencies: List[DependencyDetails],
        evidence: List[EvidenceRecord],
    ) -> List[RiskIndicator]:
        """Rule 6: Flag imports in source code that do not map to declared dependencies."""
        findings: List[RiskIndicator] = []
        import sys
        stdlib_names = set(sys.stdlib_module_names)

        declared_norms = {normalize_package_name(d.distribution_name) for d in all_dependencies}

        for u in usages:
            if not u.note or "Uncertain mapping" not in u.note:
                continue

            sym = u.symbol or ""
            root_module = sym.split(".")[0].lower()

            if root_module in stdlib_names:
                continue
            if normalize_package_name(root_module) in declared_norms:
                continue

            title = f"Unmapped module import '{sym}' detected in {u.path}"
            explanation = (
                f"Module '{sym}' is imported at '{u.path}:{u.line_start}' but does not map to any package declared "
                "in project manifests. It may be an undeclared transitive dependency, a missing manifest requirement, "
                "or an unmapped internal package."
            )
            findings.append(
                RiskIndicator(
                    rule_id="IMPORT_NOT_MAPPED_TO_DISTRIBUTION",
                    severity=RiskSeverity.MEDIUM,
                    provenance=ProvenanceKind.INFERRED,
                    title=title,
                    explanation=explanation,
                    signal_source="ast_usage_mapping",
                    evidence_refs=[u.evidence_id],
                    confidence="MEDIUM",
                    limitations="Module name may differ from its PyPI distribution name, or the package may be installed out-of-band in the execution environment.",
                )
            )

        return findings

    def _check_runtime_constraint_mismatch(
        self,
        dep: DependencyDetails,
        evidence_ids: List[str],
    ) -> Optional[RiskIndicator]:
        """Rule 7: Flag dependencies with environment markers incompatible with target Python."""
        if not dep.runtime_markers:
            return None

        raw_marker = dep.runtime_markers.strip()
        try:
            marker = Marker(raw_marker)
        except InvalidMarker:
            return None

        # Check if marker evaluates to False for the target runtime across standard platforms
        win_eval = marker.evaluate({"python_version": self.target_python_version, "sys_platform": "win32", "os_name": "nt"})
        linux_eval = marker.evaluate({"python_version": self.target_python_version, "sys_platform": "linux", "os_name": "posix"})

        # If it is strictly Python-version based and fails for target Python across environments
        if not win_eval and not linux_eval and "python_version" in raw_marker:
            title = f"Runtime constraint mismatch for {dep.distribution_name}"
            explanation = (
                f"Dependency '{dep.distribution_name}' in '{dep.manifest_path}' specifies runtime marker '{raw_marker}', "
                f"which conflicts with the target runtime Python {self.target_python_version}."
            )
            return RiskIndicator(
                rule_id="RUNTIME_CONSTRAINT_MISMATCH",
                severity=RiskSeverity.HIGH,
                provenance=ProvenanceKind.INFERRED,
                title=title,
                explanation=explanation,
                signal_source="manifest_marker",
                evidence_refs=evidence_ids,
                confidence="HIGH",
                limitations=f"Evaluated against configured target Python version {self.target_python_version}.",
            )

        return None

    def _check_deprecated_or_stale_metadata(
        self,
        dep: DependencyDetails,
        evidence_ids: List[str],
    ) -> Optional[RiskIndicator]:
        """Rule 8: Flag deprecated or superseded packages ONLY when approved metadata explicitly supports it."""
        is_depr, reason = self.metadata_source.is_deprecated(dep.distribution_name)
        if not is_depr or not reason:
            # Unknown metadata is not_assessed, NOT a risk fact!
            return None

        title = f"Deprecated or superseded package '{dep.distribution_name}'"
        explanation = (
            f"Package '{dep.distribution_name}' has an explicit deprecation notice in approved metadata: {reason} "
            "Continued reliance presents operational and maintenance hazards."
        )

        return RiskIndicator(
            rule_id="DEPRECATED_OR_STALE_METADATA",
            severity=RiskSeverity.HIGH,
            provenance=ProvenanceKind.INFERRED,
            title=title,
            explanation=explanation,
            signal_source="approved_metadata",
            evidence_refs=evidence_ids,
            confidence="HIGH",
            limitations="Relies on explicit deprecation announcements in approved metadata; packages without published deprecation metadata are classified as not_assessed.",
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _are_markers_disjoint(self, m1: Optional[str], m2: Optional[str]) -> bool:
        """Check if two markers represent mutually exclusive execution targets."""
        if not m1 or not m2:
            return False
        # Platform exclusivity check
        platforms = {"win32", "linux", "darwin"}
        p1 = next((p for p in platforms if f"sys_platform == '{p}'" in m1 or f'sys_platform == "{p}"' in m1), None)
        p2 = next((p for p in platforms if f"sys_platform == '{p}'" in m2 or f'sys_platform == "{p}"' in m2), None)
        if p1 and p2 and p1 != p2:
            return True
        return False

    def _build_evidence_map(self, evidence: List[EvidenceRecord]) -> Dict[Tuple[str, str], List[str]]:
        """Index evidence by (relative_path, normalized_name_substring)."""
        mapping: Dict[Tuple[str, str], List[str]] = {}
        for ev in evidence:
            clean_path = ev.path.replace("\\", "/")
            # Extract package names mentioned in excerpt
            words = re.findall(r"[a-zA-Z0-9_\-\.]+", ev.excerpt.lower())
            for w in words:
                key = (clean_path, normalize_package_name(w))
                mapping.setdefault(key, []).append(ev.evidence_id)
            # Also store general file key
            mapping.setdefault((clean_path, "*"), []).append(ev.evidence_id)
        return mapping

    def _get_evidence_for_dependency(
        self,
        dep: DependencyDetails,
        evidence_map: Dict[Tuple[str, str], List[str]],
    ) -> List[str]:
        """Retrieve evidence IDs linked to a specific dependency declaration."""
        clean_path = dep.manifest_path.replace("\\", "/")
        norm_name = normalize_package_name(dep.distribution_name)
        evs = evidence_map.get((clean_path, norm_name), [])
        if not evs:
            evs = evidence_map.get((clean_path, "*"), [])
        return evs[:3]

    def _deduplicate_findings(self, findings: List[RiskIndicator]) -> List[RiskIndicator]:
        """Deduplicate risk indicators based on (rule_id, title, explanation)."""
        unique: List[RiskIndicator] = []
        seen = set()
        for f in findings:
            key = (f.rule_id, f.title, f.explanation)
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique
