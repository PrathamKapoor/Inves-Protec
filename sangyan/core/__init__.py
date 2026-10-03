"""Core module for errors, logging, and platform utilities."""
from sangyan.core.errors import (
    AuthenticationError,
    CryptoError,
    DomainValidationError,
    DuplicateEntryError,
    NotFoundError,
    PermissionDeniedError,
    SangyanError,
    SecurityViolationError,
    StorageError,
)
from sangyan.core.logging import configure_logging, get_logger

__all__ = [
    "SangyanError",
    "DomainValidationError",
    "NotFoundError",
    "DuplicateEntryError",
    "PermissionDeniedError",
    "AuthenticationError",
    "StorageError",
    "CryptoError",
    "SecurityViolationError",
    "get_logger",
    "configure_logging",
]
