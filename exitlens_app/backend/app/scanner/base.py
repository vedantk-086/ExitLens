"""Scanner interface definition for ExitLens.

Scans manifests and Python source without executing repository code.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple

from app.schemas.capsule import DependencyDetails, UsageLocation
from app.schemas.evidence import EvidenceRecord


class BaseScanner(ABC):
    """Abstract scanner contract for non-executing manifest and AST inspection."""

    @abstractmethod
    async def scan_manifests(
        self,
        repo_path: Path,
        exclude_paths: List[str],
    ) -> Tuple[List[DependencyDetails], List[EvidenceRecord]]:
        """Statically discover dependencies from supported manifests.
        
        Must never execute manifest or repository code.
        """
        pass

    @abstractmethod
    async def map_usages(
        self,
        repo_path: Path,
        dependencies: List[DependencyDetails],
        exclude_paths: List[str],
        include_tests: bool = True,
    ) -> Tuple[List[UsageLocation], List[EvidenceRecord]]:
        """Statically inspect Python files for imports and symbol usages."""
        pass
