"""Restricted environment variable isolation and bounded output redaction.

Ensures:
- No inherited secrets, credentials, or private environment variables.
- Strict network disabling by default (offline pip, dead-end proxy, no-index).
- Subprocess output redaction for common API keys and tokens.
- Bounded stdout/stderr truncation up to MAX_CAPTURED_OUTPUT_BYTES.
"""

import os
import re
from typing import Dict, List, Optional, Set, Tuple

from app.core.logging import get_logger

logger = get_logger("exitlens.verification.environment")

# Strict allow-list of standard system/runtime environment variables.
# Anything not explicitly listed here is excluded.
SAFE_ENV_ALLOWLIST: Set[str] = {
    # Windows core
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "TEMP",
    "TMP",
    # Unix core
    "HOME",
    "SHELL",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    # Python runtime control
    "PATH",
    "PYTHONPATH",
    "PYTHONHASHSEED",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONUNBUFFERED",
}

# Substring matches for secret or credential indicators to forcefully block
SECRET_KEYWORD_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"KEY",
        r"SECRET",
        r"TOKEN",
        r"PASSWORD",
        r"PASSWD",
        r"CREDENTIAL",
        r"AUTH",
        r"BEARER",
        r"PRIVATE",
        r"API",
    ]
]

# Sensitive content redaction regexes for captured output
OUTPUT_REDACTION_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"AIza[0-9A-Za-z-_]{30,45}"), "[REDACTED_GOOGLE_API_KEY]"),
    (re.compile(r"sk-[0-9A-Za-z-_]{20,}"), "[REDACTED_API_SECRET]"),
    (re.compile(r"bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"(password\s*[:=]\s*['\"]?)(?!\[REDACTED)[^\s;\"']+(['\"]?)", re.IGNORECASE), r"\1[REDACTED]\2"),
    (re.compile(r"(token\s*[:=]\s*['\"]?)(?!\[REDACTED)[^\s;\"']+(['\"]?)", re.IGNORECASE), r"\1[REDACTED]\2"),
    (re.compile(r"(api_key\s*[:=]\s*['\"]?)(?!\[REDACTED)[^\s;\"']+(['\"]?)", re.IGNORECASE), r"\1[REDACTED]\2"),
]


def build_restricted_environment(
    allow_network: bool = False,
    extra_env: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Construct an isolated environment dictionary stripped of secrets.
    
    Args:
        allow_network: Whether to permit network traffic. Default False (offline).
        extra_env: Optional safe variables to include.
    
    Returns:
        Dict[str, str]: Sanitized environment map for subprocess execution.
    """
    clean_env: Dict[str, str] = {}

    # 1. Selectively copy only safe variables from current process environment
    for var_name, var_value in os.environ.items():
        var_upper = var_name.upper()
        if var_upper not in SAFE_ENV_ALLOWLIST:
            continue

        # Double-check against secret keywords (e.g. avoid PATH_KEY or USER_TOKEN)
        is_secret = any(pat.search(var_upper) for pat in SECRET_KEYWORD_PATTERNS)
        if is_secret:
            logger.debug("Scrubbing suspicious environment variable: %s", var_name)
            continue

        clean_env[var_name] = var_value

    # 2. Strict Network Disabling by default
    if not allow_network:
        # Instruct pip never to search online indexes or wheels
        clean_env["PIP_NO_INDEX"] = "1"
        clean_env["PIP_OFFLINE"] = "1"
        # Dead-end proxy settings to neutralize accidental network attempts
        clean_env["HTTP_PROXY"] = "http://127.0.0.1:0"
        clean_env["HTTPS_PROXY"] = "http://127.0.0.1:0"
        clean_env["ALL_PROXY"] = "http://127.0.0.1:0"
        clean_env["NO_PROXY"] = ""

    # 3. Add explicit Python deterministic flags
    clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
    clean_env["PYTHONUNBUFFERED"] = "1"

    # 4. Merge extra allowed variables
    if extra_env:
        for k, v in extra_env.items():
            k_upper = k.upper()
            if not any(pat.search(k_upper) for pat in SECRET_KEYWORD_PATTERNS):
                clean_env[k] = v

    return clean_env


def redact_and_truncate_output(
    text: Optional[str],
    max_bytes: int = 16000,
) -> Tuple[Optional[str], bool]:
    """Redact sensitive credentials and bound output size.
    
    Args:
        text: Raw output stream text.
        max_bytes: Maximum allowed bytes before truncation.
    
    Returns:
        Tuple[Optional[str], bool]: (sanitized_and_truncated_text, was_truncated)
    """
    if text is None:
        return None, False

    # 1. Redact credentials
    sanitized = text
    for pattern, replacement in OUTPUT_REDACTION_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    # 2. Truncate byte length
    encoded = sanitized.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return sanitized, False

    # Truncate at max_bytes boundary
    truncated_bytes = encoded[:max_bytes]
    truncated_text = truncated_bytes.decode("utf-8", errors="ignore")
    truncated_text += f"\n... [OUTPUT TRUNCATED: Exceeded capture limit of {max_bytes} bytes]"
    return truncated_text, True
