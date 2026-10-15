"""Identifier generation and validation utilities for ExitLens."""

import re
import uuid

# Safe ID pattern: letters, numbers, hyphens, underscores. Rejects traversal like "../"
SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")
UUID4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def generate_uuid() -> str:
    """Generate a standard lowercase UUID4 string."""
    return str(uuid.uuid4())


def generate_request_id() -> str:
    """Generate a unique request tracking ID."""
    return f"req-{uuid.uuid4().hex[:12]}"


def generate_analysis_id() -> str:
    """Generate a stable unique analysis ID."""
    return f"an-{uuid.uuid4().hex[:12]}"


def generate_evidence_id(counter: int | None = None) -> str:
    """Generate an evidence ID, optionally formatted with a sequential counter."""
    if counter is not None:
        return f"ev-{counter:06d}"
    return f"ev-{uuid.uuid4().hex[:8]}"


def is_safe_id(identifier: str) -> bool:
    """Validate that an ID string is safe to use in filesystem paths.
    
    Prevents path traversal, special characters, and null bytes.
    """
    if not identifier or not isinstance(identifier, str):
        return False
    if len(identifier) > 128:
        return False
    if ".." in identifier or "/" in identifier or "\\" in identifier:
        return False
    return bool(SAFE_ID_PATTERN.match(identifier))


def is_valid_uuid(val: str) -> bool:
    """Check if a string matches UUID4 format."""
    if not val or not isinstance(val, str):
        return False
    return bool(UUID4_PATTERN.match(val))
