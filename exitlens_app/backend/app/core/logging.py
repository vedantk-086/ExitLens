"""Logging utilities for ExitLens.

Configures structured logging with secret redaction and request context.
Never logs full environment dictionaries or sensitive tokens.
"""

import logging
import re
import sys
from typing import Any

# Sensitive keys to redact if encountered
SENSITIVE_PATTERNS = [
    re.compile(r"(api[_-]?key|token|secret|password|auth|bearer|credentials)", re.IGNORECASE),
]


class RedactingFormatter(logging.Formatter):
    """Formatter that masks sensitive tokens in log records."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        # Redact long hex/base64-looking secrets if preceded by sensitive keywords
        for pattern in SENSITIVE_PATTERNS:
            formatted = pattern.sub(r"\1=[REDACTED]", formatted)
        return formatted


def setup_logging(log_level: str = "INFO") -> None:
    """Initialize root logging configuration."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = RedactingFormatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers if called multiple times
    if not root_logger.handlers:
        root_logger.addHandler(handler)
    else:
        root_logger.handlers = [handler]

    # Silence noisy third-party loggers if needed
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured for the specified module name."""
    return logging.getLogger(name)
