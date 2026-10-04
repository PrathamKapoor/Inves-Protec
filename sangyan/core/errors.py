"""Core exceptions and base error hierarchy for SANGYAN."""
from __future__ import annotations


class SangyanError(Exception):
    """Base error for all SANGYAN platform and domain exceptions."""

    def __init__(self, message: str, code: str = "SANGYAN_ERROR", status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class DomainValidationError(SangyanError):
    """Raised when a domain model fails structural or semantic validation."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message, code="DOMAIN_VALIDATION_ERROR", status_code=422)
        self.errors = errors or []


class NotFoundError(SangyanError):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="NOT_FOUND", status_code=404)


class DuplicateEntryError(SangyanError):
    """Raised when a duplicate unique key constraint is violated."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="DUPLICATE_ENTRY", status_code=409)


class PermissionDeniedError(SangyanError):
    """Raised when an operation or tenant access boundary is violated."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="PERMISSION_DENIED", status_code=403)


class AuthenticationError(SangyanError):
    """Raised on missing or invalid authentication credentials."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="UNAUTHORIZED", status_code=401)


class StorageError(SangyanError):
    """Raised on database or object storage connection and operation failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="STORAGE_ERROR", status_code=500)


class CryptoError(SangyanError):
    """Raised on cryptographic signature, verification, or key generation failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="CRYPTO_ERROR", status_code=500)


class SecurityViolationError(SangyanError, ValueError):
    """Raised when a security control (such as SSRF or rate limit) is triggered."""

    def __init__(self, message: str, code: str = "SECURITY_VIOLATION", status_code: int = 400) -> None:
        super().__init__(message, code=code, status_code=status_code)


class InvalidStateTransitionError(SangyanError):
    """Raised when an entity state transition is invalid or rejected due to concurrent mutation."""

    def __init__(self, message: str, code: str = "INVALID_STATE_TRANSITION", status_code: int = 409) -> None:
        super().__init__(message, code=code, status_code=status_code)

