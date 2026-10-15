"""Test profile discovery and allow-listed argument definition.

Discovers available Python test setups (pytest, unittest) through non-executing
filesystem inspection, and strictly binds test execution to allow-listed,
server-defined argument arrays.
"""

from pathlib import Path
import sys
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import ValidationError
from app.core.logging import get_logger

logger = get_logger("exitlens.verification.profiles")


class TestProfile(BaseModel):
    """Allow-listed server-defined test profile for verification execution."""
    model_config = ConfigDict(extra="ignore")

    profile_id: str = Field(..., description="Unique allow-listed profile identifier")
    framework: str = Field(..., description="'pytest' or 'unittest'")
    display_name: str = Field(..., description="Human-readable profile title")
    description: str = Field(..., description="Profile explanation and scope")
    server_argv: List[str] = Field(..., description="Strict allow-listed server-defined argv")
    is_detected: bool = Field(default=False, description="True if detected in repository")
    detection_reason: str = Field(default="", description="Non-executing detection evidence")


# Explicit, immutable registry of allow-listed profiles.
# Model or client input NEVER controls argv; only profile_id may be selected.
ALLOWLISTED_PROFILES: Dict[str, TestProfile] = {
    "pytest-default": TestProfile(
        profile_id="pytest-default",
        framework="pytest",
        display_name="pytest (quiet)",
        description="Run test suite using pytest with quiet reporting and short tracebacks.",
        server_argv=[sys.executable, "-m", "pytest", "-q", "--tb=short"],
    ),
    "pytest-verbose": TestProfile(
        profile_id="pytest-verbose",
        framework="pytest",
        display_name="pytest (verbose)",
        description="Run test suite using pytest with verbose per-test reporting.",
        server_argv=[sys.executable, "-m", "pytest", "-v", "--tb=short"],
    ),
    "unittest-discover": TestProfile(
        profile_id="unittest-discover",
        framework="unittest",
        display_name="unittest (discovery)",
        description="Discover and run standard library unittest test suite from root.",
        server_argv=[sys.executable, "-m", "unittest", "discover", "-s", "."],
    ),
}


def get_allowlisted_profile(profile_id: str) -> TestProfile:
    """Validate that profile_id is in the server allow-list.
    
    Raises:
        ValidationError: If profile_id is unknown or unauthorized.
    """
    clean_id = (profile_id or "").strip()
    if clean_id not in ALLOWLISTED_PROFILES:
        valid_ids = sorted(list(ALLOWLISTED_PROFILES.keys()))
        raise ValidationError(
            f"Unauthorized or unknown test profile '{clean_id}'. "
            f"Only allow-listed server-defined profiles may be executed: {valid_ids}",
            code="UNAUTHORIZED_TEST_PROFILE",
            details={"requested_profile": clean_id, "allowlisted_profiles": valid_ids},
        )
    return ALLOWLISTED_PROFILES[clean_id]


def discover_test_profiles(repo_path: Path) -> List[TestProfile]:
    """Statically discover Python test profiles in a repository without executing code.
    
    Inspects config files and directory structures safely.
    """
    detected_profiles: List[TestProfile] = []
    
    # 1. Pytest detection heuristics
    pytest_detected = False
    pytest_reasons: List[str] = []

    # Config files
    pytest_ini = repo_path / "pytest.ini"
    if pytest_ini.is_file():
        pytest_detected = True
        pytest_reasons.append("pytest.ini found")

    pyproject_toml = repo_path / "pyproject.toml"
    if pyproject_toml.is_file():
        try:
            content = pyproject_toml.read_text(encoding="utf-8", errors="ignore")
            if "[tool.pytest" in content:
                pytest_detected = True
                pytest_reasons.append("tool.pytest section in pyproject.toml")
        except Exception:
            pass

    setup_cfg = repo_path / "setup.cfg"
    if setup_cfg.is_file():
        try:
            content = setup_cfg.read_text(encoding="utf-8", errors="ignore")
            if "[tool:pytest]" in content or "[pytest]" in content:
                pytest_detected = True
                pytest_reasons.append("pytest section in setup.cfg")
        except Exception:
            pass

    # Directory / test file patterns
    tests_dir = repo_path / "tests"
    test_dir = repo_path / "test"
    has_test_dir = (tests_dir.is_dir() or test_dir.is_dir())
    if has_test_dir:
        pytest_reasons.append("test directory found")

    # Look for test_*.py or *_test.py
    has_test_files = False
    try:
        search_dirs = [tests_dir, test_dir, repo_path]
        for sdir in search_dirs:
            if sdir.is_dir():
                for p in sdir.glob("test_*.py"):
                    has_test_files = True
                    break
                if not has_test_files:
                    for p in sdir.glob("*_test.py"):
                        has_test_files = True
                        break
            if has_test_files:
                break
    except Exception:
        pass

    if has_test_files and not pytest_detected:
        pytest_detected = True
        pytest_reasons.append("test_*.py test files present")

    # 2. Build profile list with detection metadata
    reason_str = ", ".join(pytest_reasons) if pytest_reasons else "standard Python pytest setup"

    p_default = ALLOWLISTED_PROFILES["pytest-default"].model_copy(
        update={"is_detected": pytest_detected, "detection_reason": reason_str if pytest_detected else ""}
    )
    p_verbose = ALLOWLISTED_PROFILES["pytest-verbose"].model_copy(
        update={"is_detected": pytest_detected, "detection_reason": reason_str if pytest_detected else ""}
    )
    
    # unittest is always a detected or fallback option if test files exist
    unittest_detected = has_test_dir or has_test_files
    u_reason = "Standard library unittest discovery" if unittest_detected else ""
    p_unittest = ALLOWLISTED_PROFILES["unittest-discover"].model_copy(
        update={"is_detected": unittest_detected, "detection_reason": u_reason}
    )

    # Return detected first
    all_profiles = [p_default, p_verbose, p_unittest]
    all_profiles.sort(key=lambda p: (not p.is_detected, p.profile_id))
    return all_profiles
