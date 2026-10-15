"""Unit tests for UTC time and identifier utilities."""

from datetime import datetime, timezone
import pytest

from app.core.ids import (
    generate_analysis_id,
    generate_evidence_id,
    generate_request_id,
    generate_uuid,
    is_safe_id,
    is_valid_uuid,
)
from app.core.time import format_utc_iso, parse_utc_iso, utc_now, utc_now_iso


def test_utc_now_timezone_aware():
    """Verify utc_now returns timezone-aware UTC datetime."""
    now = utc_now()
    assert now.tzinfo is not None
    assert now.tzinfo == timezone.utc


def test_utc_now_iso_format():
    """Verify ISO string format ends with Z."""
    iso_str = utc_now_iso()
    assert iso_str.endswith("Z")
    parsed = parse_utc_iso(iso_str)
    assert parsed.tzinfo == timezone.utc


def test_format_utc_iso_naive():
    """Verify naive datetime is assumed UTC and formatted correctly."""
    naive_dt = datetime(2026, 10, 15, 12, 0, 0)
    iso_str = format_utc_iso(naive_dt)
    assert iso_str == "2026-10-15T12:00:00Z"


def test_id_generation():
    """Verify ID generation prefixes and formats."""
    req_id = generate_request_id()
    assert req_id.startswith("req-")

    an_id = generate_analysis_id()
    assert an_id.startswith("an-")

    ev_id = generate_evidence_id(counter=42)
    assert ev_id == "ev-000042"

    raw_uuid = generate_uuid()
    assert is_valid_uuid(raw_uuid) is True
    assert is_valid_uuid("not-a-uuid") is False
    assert is_valid_uuid("") is False


def test_is_safe_id():
    """Verify safe ID validation protects against path traversal."""
    assert is_safe_id("an-abc12345") is True
    assert is_safe_id("req-998877") is True
    assert is_safe_id("ev-000123") is True
    assert is_safe_id("valid_id-123") is True

    # Traversal and illegal character attacks
    assert is_safe_id("../evil") is False
    assert is_safe_id("evil/subdir") is False
    assert is_safe_id("evil\\subdir") is False
    assert is_safe_id("evil\x00null") is False
    assert is_safe_id("evil id with spaces") is False
    assert is_safe_id("") is False
    assert is_safe_id("a" * 200) is False
