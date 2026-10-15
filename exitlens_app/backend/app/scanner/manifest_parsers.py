"""Non-executing manifest and lockfile parsers for Python dependencies.

Strictly non-executing: never imports or executes setup.py or manifest code.
"""

import ast
import configparser
import json
from pathlib import Path
import re
import tomllib
from typing import Callable, Dict, List, Optional, Set, Tuple

from app.core.paths import calculate_content_sha256, calculate_file_sha256, to_repo_relative_path
from app.core.time import utc_now_iso
from app.schemas.capsule import DependencyDetails
from app.schemas.common import ProvenanceKind
from app.schemas.evidence import EvidenceRecord

# Regular expression parsing standard pip requirement specifications
# e.g.: "requests >= 2.25.0, < 3.0.0 ; python_version > '3.8'"
REQ_SPEC_REGEX = re.compile(
    r"^([a-zA-Z0-9_\-\.]+)(?:\[([a-zA-Z0-9_\-\.,\s]+)\])?\s*([=><!~^].*)?$"
)

# Unsupported pip directives that must trigger scanner coverage warnings
UNSUPPORTED_PIP_DIRECTIVES = {
    "-c": "constraints directive (-c)",
    "--constraint": "constraints directive (--constraint)",
    "-i": "custom index directive (-i)",
    "--index-url": "custom index directive (--index-url)",
    "--extra-index-url": "extra index directive (--extra-index-url)",
    "-f": "find-links directive (-f)",
    "--find-links": "find-links directive (--find-links)",
    "-e": "editable installation (-e)",
    "--editable": "editable installation (--editable)",
    "--no-binary": "binary restriction directive (--no-binary)",
    "--only-binary": "binary restriction directive (--only-binary)",
    "--trusted-host": "trusted host directive (--trusted-host)",
}


def clean_specifier_string(raw: str) -> Tuple[str, str, Optional[str]]:
    """Parse distribution name, constraint, and environment markers from requirement string.
    
    Returns (distribution_name, declared_specifier, runtime_markers).
    """
    clean = raw.strip()
    markers = None
    if ";" in clean:
        parts = clean.split(";", 1)
        clean = parts[0].strip()
        markers = parts[1].strip()

    match = REQ_SPEC_REGEX.match(clean)
    if match:
        name = match.group(1).strip()
        extras = match.group(2)
        constraint = match.group(3).strip() if match.group(3) else "*"
        spec = f"{constraint}"
        if extras:
            spec = f"[{extras}]{spec}"
        return name, spec, markers

    # Fallback when no explicit version constraint is given
    name_clean = clean.split()[0] if clean else "unknown"
    return name_clean, "*", markers


class ManifestParser:
    """Orchestrates non-executing static extraction of dependencies from manifests."""

    def __init__(self, repo_root: Path, id_generator: Callable[[], str]) -> None:
        self.repo_root = repo_root.resolve()
        self.id_generator = id_generator
        self.observed_at = utc_now_iso()

    # -------------------------------------------------------------------------
    # Requirements.txt and Requirements*.txt
    # -------------------------------------------------------------------------

    def parse_requirements(
        self,
        file_path: Path,
        visited_files: Optional[Set[Path]] = None,
        depth: int = 0,
        max_depth: int = 5,
    ) -> Tuple[List[DependencyDetails], List[EvidenceRecord], List[str]]:
        """Parse requirements file and follow bounded recursive -r includes."""
        dependencies: List[DependencyDetails] = []
        evidence_list: List[EvidenceRecord] = []
        warnings: List[str] = []

        visited = visited_files or set()
        resolved_file = file_path.resolve()
        rel_path = to_repo_relative_path(resolved_file, self.repo_root)

        if resolved_file in visited:
            warnings.append(f"Recursive requirement loop detected for '{rel_path}'. Skipping circular include.")
            return dependencies, evidence_list, warnings

        visited.add(resolved_file)

        if depth > max_depth:
            warnings.append(f"Maximum recursive requirement depth ({max_depth}) exceeded at '{rel_path}'.")
            return dependencies, evidence_list, warnings

        if not resolved_file.is_file():
            warnings.append(f"Referenced requirement file '{rel_path}' does not exist.")
            return dependencies, evidence_list, warnings

        file_hash = calculate_file_sha256(resolved_file)

        try:
            lines = resolved_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as exc:
            warnings.append(f"Failed to read requirements file '{rel_path}': {exc}")
            return dependencies, evidence_list, warnings

        for line_idx, line in enumerate(lines, 1):
            stripped = line.strip()

            # Ignore empty lines and pure comments
            if not stripped or stripped.startswith("#"):
                continue

            # Strip inline comments if not part of URL
            if " #" in stripped:
                stripped = stripped.split(" #", 1)[0].strip()

            # Check for recursive includes: -r or --requirement
            if stripped.startswith(("-r ", "--requirement ")):
                parts = stripped.split(None, 1)
                if len(parts) > 1:
                    include_target = parts[1].strip()
                    include_path = (resolved_file.parent / include_target).resolve()
                    sub_deps, sub_evs, sub_warns = self.parse_requirements(
                        include_path,
                        visited_files=visited,
                        depth=depth + 1,
                        max_depth=max_depth,
                    )
                    dependencies.extend(sub_deps)
                    evidence_list.extend(sub_evs)
                    warnings.extend(sub_warns)
                continue

            # Check for unsupported directives
            directive_found = False
            for directive, desc in UNSUPPORTED_PIP_DIRECTIVES.items():
                if stripped.startswith(f"{directive} ") or stripped == directive:
                    warnings.append(
                        f"Unsupported pip {desc} at {rel_path}:{line_idx} ('{stripped[:40]}...'). Directive was skipped."
                    )
                    directive_found = True
                    break
            if directive_found:
                continue

            # Skip direct URLs, git+ URLs, or wheel paths (generate warning)
            if stripped.startswith(("http://", "https://", "git+", "svn+", "hg+", "./", "../", "/")):
                warnings.append(
                    f"Direct URL/VCS dependency at {rel_path}:{line_idx} ('{stripped[:50]}...') cannot be resolved statically to a standard PyPI package."
                )
                continue

            # Parse requirement
            dist_name, spec, markers = clean_specifier_string(stripped)
            if not dist_name or dist_name == "unknown":
                warnings.append(f"Malformed requirement declaration at {rel_path}:{line_idx}: '{stripped}'")
                continue

            ev_id = self.id_generator()
            ev = EvidenceRecord(
                evidence_id=ev_id,
                kind="manifest_declaration",
                provenance=ProvenanceKind.OBSERVED,
                path=rel_path,
                line_start=line_idx,
                line_end=line_idx,
                excerpt=stripped[:200],
                sha256=file_hash,
                observed_at_utc=self.observed_at,
            )
            evidence_list.append(ev)

            dep = DependencyDetails(
                distribution_name=dist_name,
                manifest_path=rel_path,
                declared_specifier=spec,
                package_manager="pip",
                dependency_type="direct",
                runtime_markers=markers,
            )
            dependencies.append(dep)

        return dependencies, evidence_list, warnings

    # -------------------------------------------------------------------------
    # pyproject.toml (PEP 621, Poetry, uv)
    # -------------------------------------------------------------------------

    def parse_pyproject(
        self,
        file_path: Path,
    ) -> Tuple[List[DependencyDetails], List[EvidenceRecord], List[str]]:
        """Parse pyproject.toml for PEP 621, Poetry, and uv static dependencies."""
        dependencies: List[DependencyDetails] = []
        evidence_list: List[EvidenceRecord] = []
        warnings: List[str] = []

        rel_path = to_repo_relative_path(file_path, self.repo_root)
        file_hash = calculate_file_sha256(file_path)

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            data = tomllib.loads(content)
        except Exception as exc:
            warnings.append(f"Malformed pyproject.toml at '{rel_path}': {exc}")
            return dependencies, evidence_list, warnings

        # 1. PEP 621 [project.dependencies]
        project = data.get("project", {})
        if isinstance(project, dict):
            # Check dynamic dependencies
            dynamic_fields = project.get("dynamic", [])
            if "dependencies" in dynamic_fields or "optional-dependencies" in dynamic_fields:
                warnings.append(
                    f"Dynamic dependencies declared in '{rel_path}' ([project].dynamic). Static inspection cannot resolve dynamically derived packages."
                )

            pep621_deps = project.get("dependencies", [])
            if isinstance(pep621_deps, list):
                for raw_req in pep621_deps:
                    if isinstance(raw_req, str):
                        dist_name, spec, markers = clean_specifier_string(raw_req)
                        ev_id = self.id_generator()
                        ev = EvidenceRecord(
                            evidence_id=ev_id,
                            kind="manifest_declaration",
                            provenance=ProvenanceKind.OBSERVED,
                            path=rel_path,
                            excerpt=raw_req[:200],
                            sha256=file_hash,
                            observed_at_utc=self.observed_at,
                        )
                        evidence_list.append(ev)
                        dependencies.append(
                            DependencyDetails(
                                distribution_name=dist_name,
                                manifest_path=rel_path,
                                declared_specifier=spec,
                                package_manager="pep621",
                                dependency_type="direct",
                                runtime_markers=markers,
                            )
                        )

            # PEP 621 [project.optional-dependencies]
            opt_deps = project.get("optional-dependencies", {})
            if isinstance(opt_deps, dict):
                for group_name, group_reqs in opt_deps.items():
                    if isinstance(group_reqs, list):
                        for raw_req in group_reqs:
                            if isinstance(raw_req, str):
                                dist_name, spec, markers = clean_specifier_string(raw_req)
                                ev_id = self.id_generator()
                                ev = EvidenceRecord(
                                    evidence_id=ev_id,
                                    kind="manifest_declaration",
                                    provenance=ProvenanceKind.OBSERVED,
                                    path=rel_path,
                                    excerpt=f"[{group_name}] {raw_req[:180]}",
                                    sha256=file_hash,
                                    observed_at_utc=self.observed_at,
                                )
                                evidence_list.append(ev)
                                dependencies.append(
                                    DependencyDetails(
                                        distribution_name=dist_name,
                                        manifest_path=rel_path,
                                        declared_specifier=spec,
                                        package_manager="pep621",
                                        dependency_type="optional",
                                        runtime_markers=markers,
                                    )
                                )

        # 2. Poetry [tool.poetry.dependencies]
        tool = data.get("tool", {})
        if isinstance(tool, dict):
            poetry = tool.get("poetry", {})
            if isinstance(poetry, dict):
                poetry_deps = poetry.get("dependencies", {})
                if isinstance(poetry_deps, dict):
                    for pkg_name, spec_val in poetry_deps.items():
                        if pkg_name.lower() == "python":
                            continue  # Python runtime constraint, not a package
                        spec_str = str(spec_val) if isinstance(spec_val, str) else spec_val.get("version", "*") if isinstance(spec_val, dict) else "*"
                        ev_id = self.id_generator()
                        evidence_list.append(
                            EvidenceRecord(
                                evidence_id=ev_id,
                                kind="manifest_declaration",
                                provenance=ProvenanceKind.OBSERVED,
                                path=rel_path,
                                excerpt=f"{pkg_name} = {spec_str}",
                                sha256=file_hash,
                                observed_at_utc=self.observed_at,
                            )
                        )
                        dependencies.append(
                            DependencyDetails(
                                distribution_name=pkg_name,
                                manifest_path=rel_path,
                                declared_specifier=spec_str,
                                package_manager="poetry",
                                dependency_type="direct",
                            )
                        )

            # 3. uv [tool.uv.dependencies]
            uv_section = tool.get("uv", {})
            if isinstance(uv_section, dict):
                uv_deps = uv_section.get("dependencies", [])
                if isinstance(uv_deps, list):
                    for raw_req in uv_deps:
                        if isinstance(raw_req, str):
                            dist_name, spec, markers = clean_specifier_string(raw_req)
                            ev_id = self.id_generator()
                            evidence_list.append(
                                EvidenceRecord(
                                    evidence_id=ev_id,
                                    kind="manifest_declaration",
                                    provenance=ProvenanceKind.OBSERVED,
                                    path=rel_path,
                                    excerpt=f"tool.uv: {raw_req[:180]}",
                                    sha256=file_hash,
                                    observed_at_utc=self.observed_at,
                                )
                            )
                            dependencies.append(
                                DependencyDetails(
                                    distribution_name=dist_name,
                                    manifest_path=rel_path,
                                    declared_specifier=spec,
                                    package_manager="uv",
                                    dependency_type="direct",
                                    runtime_markers=markers,
                                )
                            )

        return dependencies, evidence_list, warnings

    # -------------------------------------------------------------------------
    # Lockfiles: poetry.lock, uv.lock, Pipfile.lock
    # -------------------------------------------------------------------------

    def parse_lockfile(
        self,
        file_path: Path,
    ) -> Tuple[List[DependencyDetails], List[EvidenceRecord], List[str]]:
        """Parse poetry.lock, uv.lock, or Pipfile.lock into locked dependency records."""
        dependencies: List[DependencyDetails] = []
        evidence_list: List[EvidenceRecord] = []
        warnings: List[str] = []

        filename = file_path.name.lower()
        rel_path = to_repo_relative_path(file_path, self.repo_root)
        file_hash = calculate_file_sha256(file_path)

        if filename in ("poetry.lock", "uv.lock"):
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                data = tomllib.loads(content)
            except Exception as exc:
                warnings.append(f"Malformed lockfile at '{rel_path}': {exc}")
                return dependencies, evidence_list, warnings

            packages = data.get("package", [])
            if isinstance(packages, list):
                mgr = "poetry" if filename == "poetry.lock" else "uv"
                for pkg in packages:
                    if isinstance(pkg, dict):
                        name = pkg.get("name")
                        ver = pkg.get("version")
                        cat = pkg.get("category", "main")
                        is_optional = pkg.get("optional", False)
                        if name:
                            ev_id = self.id_generator()
                            evidence_list.append(
                                EvidenceRecord(
                                    evidence_id=ev_id,
                                    kind="lockfile_entry",
                                    provenance=ProvenanceKind.OBSERVED,
                                    path=rel_path,
                                    excerpt=f"{name}=={ver}",
                                    sha256=file_hash,
                                    observed_at_utc=self.observed_at,
                                )
                            )
                            dep_type = "optional" if is_optional else "dev" if cat == "dev" else "direct"
                            dependencies.append(
                                DependencyDetails(
                                    distribution_name=name,
                                    manifest_path=rel_path,
                                    declared_specifier=f"=={ver}" if ver else "*",
                                    resolved_version=ver,
                                    package_manager=mgr,
                                    dependency_type=dep_type,
                                )
                            )

        elif filename == "pipfile.lock":
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                data = json.loads(content)
            except Exception as exc:
                warnings.append(f"Malformed Pipfile.lock at '{rel_path}': {exc}")
                return dependencies, evidence_list, warnings

            for section_name, dep_type in (("default", "direct"), ("develop", "dev")):
                section = data.get(section_name, {})
                if isinstance(section, dict):
                    for name, meta in section.items():
                        ver = meta.get("version", "").lstrip("=") if isinstance(meta, dict) else ""
                        ev_id = self.id_generator()
                        evidence_list.append(
                            EvidenceRecord(
                                evidence_id=ev_id,
                                kind="lockfile_entry",
                                provenance=ProvenanceKind.OBSERVED,
                                path=rel_path,
                                excerpt=f"{name}=={ver}",
                                sha256=file_hash,
                                observed_at_utc=self.observed_at,
                            )
                        )
                        dependencies.append(
                            DependencyDetails(
                                distribution_name=name,
                                manifest_path=rel_path,
                                declared_specifier=f"=={ver}" if ver else "*",
                                resolved_version=ver or None,
                                package_manager="pipfile",
                                dependency_type=dep_type,
                            )
                        )

        return dependencies, evidence_list, warnings

    # -------------------------------------------------------------------------
    # Pipfile
    # -------------------------------------------------------------------------

    def parse_pipfile(
        self,
        file_path: Path,
    ) -> Tuple[List[DependencyDetails], List[EvidenceRecord], List[str]]:
        """Parse Pipfile using tomllib."""
        dependencies: List[DependencyDetails] = []
        evidence_list: List[EvidenceRecord] = []
        warnings: List[str] = []

        rel_path = to_repo_relative_path(file_path, self.repo_root)
        file_hash = calculate_file_sha256(file_path)

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            data = tomllib.loads(content)
        except Exception as exc:
            warnings.append(f"Malformed Pipfile at '{rel_path}': {exc}")
            return dependencies, evidence_list, warnings

        for section_name, dep_type in (("packages", "direct"), ("dev-packages", "dev")):
            section = data.get(section_name, {})
            if isinstance(section, dict):
                for name, spec_val in section.items():
                    spec_str = str(spec_val) if isinstance(spec_val, str) else spec_val.get("version", "*") if isinstance(spec_val, dict) else "*"
                    ev_id = self.id_generator()
                    evidence_list.append(
                        EvidenceRecord(
                            evidence_id=ev_id,
                            kind="manifest_declaration",
                            provenance=ProvenanceKind.OBSERVED,
                            path=rel_path,
                            excerpt=f"{name} = {spec_str}",
                            sha256=file_hash,
                            observed_at_utc=self.observed_at,
                        )
                    )
                    dependencies.append(
                        DependencyDetails(
                            distribution_name=name,
                            manifest_path=rel_path,
                            declared_specifier=spec_str,
                            package_manager="pipfile",
                            dependency_type=dep_type,
                        )
                    )

        return dependencies, evidence_list, warnings

    # -------------------------------------------------------------------------
    # setup.cfg
    # -------------------------------------------------------------------------

    def parse_setup_cfg(
        self,
        file_path: Path,
    ) -> Tuple[List[DependencyDetails], List[EvidenceRecord], List[str]]:
        """Parse setup.cfg static dependency declarations."""
        dependencies: List[DependencyDetails] = []
        evidence_list: List[EvidenceRecord] = []
        warnings: List[str] = []

        rel_path = to_repo_relative_path(file_path, self.repo_root)
        file_hash = calculate_file_sha256(file_path)

        config = configparser.ConfigParser()
        try:
            config.read(file_path, encoding="utf-8")
        except Exception as exc:
            warnings.append(f"Malformed setup.cfg at '{rel_path}': {exc}")
            return dependencies, evidence_list, warnings

        if config.has_section("options"):
            # install_requires
            if config.has_option("options", "install_requires"):
                raw_requires = config.get("options", "install_requires")
                for line in raw_requires.splitlines():
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        dist_name, spec, markers = clean_specifier_string(stripped)
                        ev_id = self.id_generator()
                        evidence_list.append(
                            EvidenceRecord(
                                evidence_id=ev_id,
                                kind="manifest_declaration",
                                provenance=ProvenanceKind.OBSERVED,
                                path=rel_path,
                                excerpt=stripped[:200],
                                sha256=file_hash,
                                observed_at_utc=self.observed_at,
                            )
                        )
                        dependencies.append(
                            DependencyDetails(
                                distribution_name=dist_name,
                                manifest_path=rel_path,
                                declared_specifier=spec,
                                package_manager="setuptools",
                                dependency_type="direct",
                                runtime_markers=markers,
                            )
                        )

            # tests_require
            if config.has_option("options", "tests_require"):
                raw_requires = config.get("options", "tests_require")
                for line in raw_requires.splitlines():
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        dist_name, spec, markers = clean_specifier_string(stripped)
                        ev_id = self.id_generator()
                        evidence_list.append(
                            EvidenceRecord(
                                evidence_id=ev_id,
                                kind="manifest_declaration",
                                provenance=ProvenanceKind.OBSERVED,
                                path=rel_path,
                                excerpt=f"[tests] {stripped[:180]}",
                                sha256=file_hash,
                                observed_at_utc=self.observed_at,
                            )
                        )
                        dependencies.append(
                            DependencyDetails(
                                distribution_name=dist_name,
                                manifest_path=rel_path,
                                declared_specifier=spec,
                                package_manager="setuptools",
                                dependency_type="dev",
                                runtime_markers=markers,
                            )
                        )

        # options.extras_require
        if config.has_section("options.extras_require"):
            for extra_group in config.options("options.extras_require"):
                raw_extra = config.get("options.extras_require", extra_group)
                for line in raw_extra.splitlines():
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        dist_name, spec, markers = clean_specifier_string(stripped)
                        ev_id = self.id_generator()
                        evidence_list.append(
                            EvidenceRecord(
                                evidence_id=ev_id,
                                kind="manifest_declaration",
                                provenance=ProvenanceKind.OBSERVED,
                                path=rel_path,
                                excerpt=f"[{extra_group}] {stripped[:180]}",
                                sha256=file_hash,
                                observed_at_utc=self.observed_at,
                            )
                        )
                        dependencies.append(
                            DependencyDetails(
                                distribution_name=dist_name,
                                manifest_path=rel_path,
                                declared_specifier=spec,
                                package_manager="setuptools",
                                dependency_type="optional",
                                runtime_markers=markers,
                            )
                        )

        return dependencies, evidence_list, warnings

    # -------------------------------------------------------------------------
    # setup.py (Static AST inspection only — NEVER import or execute!)
    # -------------------------------------------------------------------------

    def parse_setup_py(
        self,
        file_path: Path,
    ) -> Tuple[List[DependencyDetails], List[EvidenceRecord], List[str]]:
        """Statically inspect setup.py using AST. NEVER imports or executes the file."""
        dependencies: List[DependencyDetails] = []
        evidence_list: List[EvidenceRecord] = []
        warnings: List[str] = []

        rel_path = to_repo_relative_path(file_path, self.repo_root)
        file_hash = calculate_file_sha256(file_path)

        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as syn_err:
            warnings.append(
                f"setup.py at '{rel_path}' contains syntax errors ({syn_err}) and could not be statically parsed."
            )
            return dependencies, evidence_list, warnings
        except Exception as exc:
            warnings.append(f"Failed to read setup.py at '{rel_path}': {exc}")
            return dependencies, evidence_list, warnings

        # Look for setup(...) function call in AST
        setup_call_found = False

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                func_name = getattr(func, "id", None) or getattr(func, "attr", None)
                if func_name == "setup":
                    setup_call_found = True
                    for kw in node.keywords:
                        if kw.arg in ("install_requires", "tests_require", "setup_requires"):
                            dep_type = "dev" if kw.arg == "tests_require" else "direct"
                            val_node = kw.value

                            # Static list or tuple literal
                            if isinstance(val_node, (ast.List, ast.Tuple)):
                                for elt in val_node.elts:
                                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                        req_str = elt.value.strip()
                                        if req_str:
                                            dist_name, spec, markers = clean_specifier_string(req_str)
                                            line_no = getattr(elt, "lineno", getattr(node, "lineno", None))
                                            ev_id = self.id_generator()
                                            evidence_list.append(
                                                EvidenceRecord(
                                                    evidence_id=ev_id,
                                                    kind="manifest_declaration",
                                                    provenance=ProvenanceKind.OBSERVED,
                                                    path=rel_path,
                                                    line_start=line_no,
                                                    line_end=line_no,
                                                    excerpt=req_str[:200],
                                                    sha256=file_hash,
                                                    observed_at_utc=self.observed_at,
                                                )
                                            )
                                            dependencies.append(
                                                DependencyDetails(
                                                    distribution_name=dist_name,
                                                    manifest_path=rel_path,
                                                    declared_specifier=spec,
                                                    package_manager="setuptools",
                                                    dependency_type=dep_type,
                                                    runtime_markers=markers,
                                                )
                                            )
                                    else:
                                        warnings.append(
                                            f"Non-literal entry in {kw.arg} in '{rel_path}' (line {getattr(elt, 'lineno', '?')}). Static inspection cannot resolve dynamic values."
                                        )
                            elif isinstance(val_node, (ast.Call, ast.Name, ast.Attribute)):
                                warnings.append(
                                    f"Dynamic dependency declaration in '{rel_path}' ({kw.arg} is a {type(val_node).__name__}). Execution of setup.py is strictly forbidden; dependencies must be declared in static manifests."
                                )

        if not setup_call_found:
            warnings.append(f"No standard setup(...) call detected in '{rel_path}'.")

        return dependencies, evidence_list, warnings
