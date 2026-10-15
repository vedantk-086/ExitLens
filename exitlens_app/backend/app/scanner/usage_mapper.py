"""AST-based Python source code dependency usage mapper."""

import ast
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from app.core.paths import calculate_file_sha256, to_repo_relative_path
from app.core.time import utc_now_iso
from app.scanner.mapping import map_import_to_distribution, normalize_package_name
from app.scanner.models import DiscoveredFile
from app.schemas.capsule import UsageLocation
from app.schemas.common import ProvenanceKind
from app.schemas.evidence import EvidenceRecord


class UsageMapper:
    """Extracts import locations and symbol usages statically using Python AST."""

    def __init__(
        self,
        repo_root: Path,
        id_generator: Callable[[], str],
        declared_distributions: Set[str],
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.id_generator = id_generator
        self.declared_distributions = declared_distributions
        self.observed_at = utc_now_iso()

    def map_file_usages(
        self,
        discovered_file: DiscoveredFile,
    ) -> Tuple[List[UsageLocation], List[EvidenceRecord], List[str]]:
        """Inspect a single Python file using AST parsing."""
        usages: List[UsageLocation] = []
        evidence_list: List[EvidenceRecord] = []
        warnings: List[str] = []

        file_path = discovered_file.absolute_path
        rel_path = discovered_file.relative_path
        file_hash = calculate_file_sha256(file_path)

        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(file_path))
            lines = source.splitlines()
        except SyntaxError as syn_err:
            warnings.append(
                f"Syntax error parsing '{rel_path}' at line {syn_err.lineno}: {syn_err.msg}. File usages were skipped."
            )
            return usages, evidence_list, warnings
        except Exception as exc:
            warnings.append(f"Failed to inspect Python file '{rel_path}': {exc}")
            return usages, evidence_list, warnings

        usage_counter = 0

        for node in ast.walk(tree):
            line_no = getattr(node, "lineno", None)
            end_line_no = getattr(node, "end_lineno", line_no)

            line_excerpt = ""
            if line_no and 1 <= line_no <= len(lines):
                line_excerpt = lines[line_no - 1].strip()[:200]

            # 1. Direct Imports: import requests, import urllib3.util
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    matched_dist, is_uncertain = map_import_to_distribution(
                        module_name, self.declared_distributions
                    )

                    # Only record usage if it relates to a declared dependency or known external package
                    if matched_dist or is_uncertain:
                        ev_id = self.id_generator()
                        usage_counter += 1
                        usage_id = f"usg-{discovered_file.relative_path.replace('/', '_')}-{usage_counter}"

                        note = (
                            "Uncertain mapping: module does not directly match a declared manifest package."
                            if is_uncertain
                            else None
                        )

                        evidence_kind = "test_usage" if discovered_file.is_test else "ast_import"
                        ev = EvidenceRecord(
                            evidence_id=ev_id,
                            kind=evidence_kind,
                            provenance=ProvenanceKind.OBSERVED,
                            path=rel_path,
                            line_start=line_no,
                            line_end=end_line_no,
                            excerpt=line_excerpt or f"import {module_name}",
                            sha256=file_hash,
                            observed_at_utc=self.observed_at,
                        )
                        evidence_list.append(ev)

                        usg = UsageLocation(
                            usage_id=usage_id,
                            path=rel_path,
                            line_start=line_no,
                            line_end=end_line_no,
                            import_statement=line_excerpt or f"import {module_name}",
                            symbol=alias.asname or module_name,
                            pattern=f"import {module_name}",
                            evidence_id=ev_id,
                            note=note,
                        )
                        usages.append(usg)

            # 2. From Imports: from urllib3.util import Retry
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                matched_dist, is_uncertain = map_import_to_distribution(
                    module_name, self.declared_distributions
                )

                if matched_dist or is_uncertain:
                    for alias in node.names:
                        ev_id = self.id_generator()
                        usage_counter += 1
                        usage_id = f"usg-{discovered_file.relative_path.replace('/', '_')}-{usage_counter}"

                        note = (
                            "Uncertain mapping: module does not directly match a declared manifest package."
                            if is_uncertain
                            else None
                        )

                        symbol_str = alias.name
                        evidence_kind = "test_usage" if discovered_file.is_test else "ast_import"
                        ev = EvidenceRecord(
                            evidence_id=ev_id,
                            kind=evidence_kind,
                            provenance=ProvenanceKind.OBSERVED,
                            path=rel_path,
                            line_start=line_no,
                            line_end=end_line_no,
                            excerpt=line_excerpt or f"from {module_name} import {symbol_str}",
                            sha256=file_hash,
                            observed_at_utc=self.observed_at,
                        )
                        evidence_list.append(ev)

                        usg = UsageLocation(
                            usage_id=usage_id,
                            path=rel_path,
                            line_start=line_no,
                            line_end=end_line_no,
                            import_statement=line_excerpt or f"from {module_name} import {symbol_str}",
                            symbol=symbol_str,
                            pattern=f"from {module_name} import {symbol_str}",
                            evidence_id=ev_id,
                            note=note,
                        )
                        usages.append(usg)

            # 3. Dynamic imports: __import__("foo") or importlib.import_module("foo")
            elif isinstance(node, ast.Call):
                func = node.func
                func_name = getattr(func, "id", None) or getattr(func, "attr", None)
                if func_name in ("__import__", "import_module"):
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        mod_name = node.args[0].value
                        ev_id = self.id_generator()
                        ev = EvidenceRecord(
                            evidence_id=ev_id,
                            kind="dynamic_import",
                            provenance=ProvenanceKind.OBSERVED,
                            path=rel_path,
                            line_start=line_no,
                            line_end=end_line_no,
                            excerpt=line_excerpt or f"dynamic import of {mod_name}",
                            sha256=file_hash,
                            observed_at_utc=self.observed_at,
                        )
                        evidence_list.append(ev)
                        usages.append(
                            UsageLocation(
                                usage_id=f"dyn-{discovered_file.relative_path.replace('/', '_')}-{line_no}",
                                path=rel_path,
                                line_start=line_no,
                                line_end=end_line_no,
                                import_statement=line_excerpt,
                                symbol=mod_name,
                                pattern=f"dynamic import call: {mod_name}",
                                evidence_id=ev_id,
                                note="Dynamic import detected. Static usage mapping may be incomplete.",
                            )
                        )

        return usages, evidence_list, warnings
