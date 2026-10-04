"""Structured logging utilities for SANGYAN.

All handlers installed through :func:`configure_logging` carry the
sensitive-data redaction filter so credentials, JWTs, API keys, and
OTP-shaped values are scrubbed before any record reaches an output stream.
"""
from __future__ import annotations

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Return a standard configured logger."""
    return logging.getLogger(name)


def configure_logging(level: str = "INFO", json_format: bool = False) -> None:
    """Configure root logging level, format, and sensitive-data redaction."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=log_level, format=fmt, stream=sys.stdout)

    # Defense-in-depth: scrub credentials/JWTs/API keys from every record that
    # flows through root handlers, regardless of which module emitted it.
    # Imported lazily to avoid a circular import with the security package.
    from sangyan.security.telemetry import RedactingLogFilter

    redacting_filter = RedactingLogFilter()
    root = logging.getLogger()
    for handler in root.handlers:
        handler.addFilter(redacting_filter)
