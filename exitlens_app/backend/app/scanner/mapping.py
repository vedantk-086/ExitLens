"""Module-to-distribution mapping and normalization database for Python packages."""

import re
from typing import Dict, Optional, Set, Tuple

# Common ecosystem mappings from Python import module root name to PyPI distribution name
MODULE_TO_DISTRIBUTION: Dict[str, str] = {
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "pil": "pillow",
    "dotenv": "python-dotenv",
    "dateutil": "python-dateutil",
    "jose": "python-jose",
    "jwt": "pyjwt",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "git": "gitpython",
    "docker": "docker",
    "pkg_resources": "setuptools",
    "pydantic_settings": "pydantic-settings",
    "magic": "python-magic",
    "openssl": "pyopenssl",
    "bio": "biopython",
    "serial": "pyserial",
    "websocket": "websocket-client",
    "paho": "paho-mqtt",
    "attr": "attrs",
    "flask_cors": "flask-cors",
    "flask_sqlalchemy": "flask-sqlalchemy",
    "google.protobuf": "protobuf",
    "fastapi": "fastapi",
    "pydantic": "pydantic",
    "httpx": "httpx",
    "requests": "requests",
    "urllib3": "urllib3",
    "pytest": "pytest",
    "click": "click",
    "uvicorn": "uvicorn",
    "starlette": "starlette",
}


def normalize_package_name(name: str) -> str:
    """Canonicalize a package name per PEP 503 (lowercase, dashes instead of underscores)."""
    if not name:
        return ""
    return re.sub(r"[-_.]+", "-", name).lower()


def map_import_to_distribution(
    module_name: str,
    declared_distributions: Set[str],
) -> Tuple[Optional[str], bool]:
    """Map an imported Python module name to a declared distribution.
    
    Returns:
        (distribution_name, is_uncertain)
        - If direct match: (dist_name, False)
        - If mapped via known alias: (dist_name, False)
        - If matching normalized prefix/name: (dist_name, False)
        - If no match found: (None, True)
    """
    if not module_name:
        return None, True

    root_module = module_name.split(".")[0].strip()
    norm_root = normalize_package_name(root_module)

    # Check against declared distributions (normalized)
    declared_norm_map = {normalize_package_name(d): d for d in declared_distributions}

    # 1. Direct exact match (e.g. import requests -> distribution requests)
    if norm_root in declared_norm_map:
        return declared_norm_map[norm_root], False

    # 2. Known alias map match (e.g. import yaml -> pyyaml)
    alias_candidate = MODULE_TO_DISTRIBUTION.get(root_module.lower())
    if alias_candidate:
        norm_alias = normalize_package_name(alias_candidate)
        if norm_alias in declared_norm_map:
            return declared_norm_map[norm_alias], False
        # Known distribution, but not declared in project
        return alias_candidate, False

    # 3. Check if any declared package contains or starts with the module name
    for declared_norm, original_name in declared_norm_map.items():
        if declared_norm == norm_root or declared_norm.replace("-", "") == norm_root.replace("-", ""):
            return original_name, False
        if declared_norm.startswith(f"python-{norm_root}") or declared_norm.endswith(f"-{norm_root}"):
            return original_name, True

    return None, True
