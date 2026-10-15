"""Repository scanner and Python dependency usage mapper implementation."""

from pathlib import Path
from typing import Callable, List, Optional, Set, Tuple, Union

from app.core.config import Settings, get_settings
from app.core.ids import generate_evidence_id
from app.core.logging import get_logger
from app.core.paths import validate_repository_path
from app.scanner.base import BaseScanner
from app.scanner.manifest_parsers import ManifestParser
from app.scanner.models import ScanResult, WalkSummary
from app.scanner.usage_mapper import UsageMapper
from app.scanner.walker import walk_repository
from app.schemas.capsule import DependencyDetails, UsageLocation
from app.schemas.evidence import EvidenceRecord

logger = get_logger("exitlens.scanner")


class Scanner(BaseScanner):
    """Concrete repository scanner and static AST dependency mapper."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    async def scan_manifests(
        self,
        repo_path: Path,
        exclude_paths: List[str],
    ) -> Tuple[List[DependencyDetails], List[EvidenceRecord]]:
        """Statically discover dependencies from supported manifests without executing code."""
        result = await self.run_full_scan(repo_path=repo_path, exclude_paths=exclude_paths)
        return result.dependencies, result.evidence

    async def map_usages(
        self,
        repo_path: Path,
        dependencies: List[DependencyDetails],
        exclude_paths: List[str],
        include_tests: bool = True,
    ) -> Tuple[List[UsageLocation], List[EvidenceRecord]]:
        """Statically inspect Python files for imports and symbol usages."""
        declared_names = {d.distribution_name for d in dependencies}
        counter = 0

        def id_gen() -> str:
            nonlocal counter
            counter += 1
            return generate_evidence_id(counter=counter)

        walk_summary = walk_repository(
            repo_root=repo_path,
            exclude_paths=exclude_paths,
            max_files=self.settings.MAX_ANALYSIS_FILES,
            max_single_file_bytes=self.settings.MAX_SINGLE_FILE_BYTES,
            max_total_source_bytes=self.settings.MAX_TOTAL_SOURCE_BYTES,
        )

        mapper = UsageMapper(
            repo_root=repo_path,
            id_generator=id_gen,
            declared_distributions=declared_names,
        )

        all_usages: List[UsageLocation] = []
        all_evidence: List[EvidenceRecord] = []

        for py_file in walk_summary.python_files:
            if not include_tests and py_file.is_test:
                continue
            file_usages, file_evidence, _ = mapper.map_file_usages(py_file)
            all_usages.extend(file_usages)
            all_evidence.extend(file_evidence)

        return all_usages, all_evidence

    async def run_full_scan(
        self,
        repo_path: Path,
        exclude_paths: Optional[List[str]] = None,
        include_tests: bool = True,
        allowed_roots: Optional[List[Union[str, Path]]] = None,
    ) -> ScanResult:
        """Execute complete bounded repository traversal, manifest parsing, and usage mapping."""
        # 1. Validate repository path
        effective_allowed_roots = allowed_roots or self.settings.get_canonical_allowed_roots()
        canonical_repo = validate_repository_path(repo_path, allowed_roots=effective_allowed_roots)

        # 2. Bounded walk
        walk_summary: WalkSummary = walk_repository(
            repo_root=canonical_repo,
            exclude_paths=exclude_paths,
            max_files=self.settings.MAX_ANALYSIS_FILES,
            max_single_file_bytes=self.settings.MAX_SINGLE_FILE_BYTES,
            max_total_source_bytes=self.settings.MAX_TOTAL_SOURCE_BYTES,
        )

        all_warnings: List[str] = list(walk_summary.warnings)
        evidence_counter = 0

        def id_gen() -> str:
            nonlocal evidence_counter
            evidence_counter += 1
            return generate_evidence_id(counter=evidence_counter)

        # 3. Parse Manifests
        parser = ManifestParser(repo_root=canonical_repo, id_generator=id_gen)
        all_dependencies: List[DependencyDetails] = []
        all_evidence: List[EvidenceRecord] = []

        for m_file in walk_summary.manifest_files:
            filename = m_file.absolute_path.name.lower()
            deps: List[DependencyDetails] = []
            evs: List[EvidenceRecord] = []
            warns: List[str] = []

            if filename == "requirements.txt" or filename.startswith("requirements") or filename.endswith("-requirements.txt"):
                deps, evs, warns = parser.parse_requirements(m_file.absolute_path)
            elif filename == "pyproject.toml":
                deps, evs, warns = parser.parse_pyproject(m_file.absolute_path)
            elif filename in ("poetry.lock", "uv.lock", "pipfile.lock"):
                deps, evs, warns = parser.parse_lockfile(m_file.absolute_path)
            elif filename == "pipfile":
                deps, evs, warns = parser.parse_pipfile(m_file.absolute_path)
            elif filename == "setup.cfg":
                deps, evs, warns = parser.parse_setup_cfg(m_file.absolute_path)
            elif filename == "setup.py":
                deps, evs, warns = parser.parse_setup_py(m_file.absolute_path)

            all_dependencies.extend(deps)
            all_evidence.extend(evs)
            all_warnings.extend(warns)

        # 4. Map Usages
        declared_names = {d.distribution_name for d in all_dependencies}
        mapper = UsageMapper(
            repo_root=canonical_repo,
            id_generator=id_gen,
            declared_distributions=declared_names,
        )

        all_usages: List[UsageLocation] = []

        for py_file in walk_summary.python_files:
            if not include_tests and py_file.is_test:
                continue
            usages, evs, warns = mapper.map_file_usages(py_file)
            all_usages.extend(usages)
            all_evidence.extend(evs)
            all_warnings.extend(warns)

        # 5. Coverage warning if no manifests were found
        if not walk_summary.manifest_files:
            all_warnings.append(
                "No supported dependency manifests or lockfiles were detected in the scanned repository."
            )

        logger.info(
            "Scan completed: %d files, %d dependencies, %d usages, %d evidence records, %d warnings",
            walk_summary.scanned_file_count,
            len(all_dependencies),
            len(all_usages),
            len(all_evidence),
            len(all_warnings),
        )

        return ScanResult(
            dependencies=all_dependencies,
            usages=all_usages,
            evidence=all_evidence,
            warnings=all_warnings,
            file_count=walk_summary.scanned_file_count,
            total_bytes=walk_summary.scanned_byte_count,
        )
