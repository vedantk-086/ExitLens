"""Approved metadata source interface and offline verified registry.

ExitLens enforces strict rules regarding package metadata:
- Never label a package unmaintained solely because its version is old.
- Unknown metadata must be treated as 'not_assessed', not an inferred risk fact.
- Do not make network calls unless an explicitly approved metadata adapter exists.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

from app.scanner.mapping import normalize_package_name


class ApprovedMetadataSource(ABC):
    """Abstract interface for querying trusted, verified package metadata."""

    @abstractmethod
    def is_deprecated(self, distribution_name: str) -> Tuple[bool, Optional[str]]:
        """Return (is_deprecated, reason) if an approved source provides verified deprecation facts.
        
        Returns (False, None) if the package is active or metadata is not assessed.
        """
        pass

    @abstractmethod
    def get_metadata_status(self, distribution_name: str) -> str:
        """Return metadata assessment status: 'available' or 'not_assessed'."""
        pass


class LocalApprovedMetadataRegistry(ApprovedMetadataSource):
    """Offline, deterministic repository of verified package deprecation and obsolescence notices.
    
    Strictly avoids network requests. Only contains explicitly deprecated, renamed,
    or officially superseded packages.
    """

    # Normalized package name -> Verified deprecation explanation
    VERIFIED_DEPRECATIONS: Dict[str, str] = {
        "optparse": "Officially deprecated in Python standard library; superseded by argparse.",
        "pep8": "Deprecated and renamed to pycodestyle to reduce confusion with the PEP 8 style guide.",
        "pycrypto": "Abandoned and obsolete cryptographic package; superseded by cryptography or pycryptodome.",
        "pkg_resources": "Deprecated in setuptools; superseded by importlib.resources and importlib.metadata.",
        "nose": "Unmaintained test runner with known compatibility limitations; superseded by pytest.",
        "mock": "External package deprecated for modern Python (3.3+); standard library unittest.mock should be used.",
        "distutils": "Deprecated in Python 3.10 and removed in Python 3.12; packaging/build tools or setuptools should be used.",
    }

    def __init__(self, custom_deprecations: Optional[Dict[str, str]] = None) -> None:
        self._deprecations: Dict[str, str] = dict(self.VERIFIED_DEPRECATIONS)
        if custom_deprecations:
            for k, v in custom_deprecations.items():
                self._deprecations[normalize_package_name(k)] = v

    def is_deprecated(self, distribution_name: str) -> Tuple[bool, Optional[str]]:
        norm = normalize_package_name(distribution_name)
        if norm in self._deprecations:
            return True, self._deprecations[norm]
        return False, None

    def get_metadata_status(self, distribution_name: str) -> str:
        norm = normalize_package_name(distribution_name)
        if norm in self._deprecations:
            return "available"
        # Unknown metadata must be treated as not_assessed, never assumed negative
        return "not_assessed"
