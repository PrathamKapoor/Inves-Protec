"""Structured logging utilities for SANGYAN."""
from __future__ import annotations

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Return a standard configured logger."""
    return logging.getLogger(name)


def configure_logging(level: str = "INFO", json_format: bool = False) -> None:
    """Configure root logging level and format."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=log_level, format=fmt, stream=sys.stdout)
