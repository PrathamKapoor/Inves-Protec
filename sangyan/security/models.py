"""Security models, principal representations, API key definitions, and configuration."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from sangyan.domain.base import CURRENT_SCHEMA_VERSION, new_id


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AuthenticationError(Exception):
    """Base exception for authentication failures at the API boundary."""

    def __init__(self, message: str = "Authentication failed", status_code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AmbiguousAuthenticationError(AuthenticationError):
    """Raised when mutually exclusive authentication schemes (e.g. Bearer and API key) are supplied."""

    def __init__(self, message: str = "Ambiguous credentials: both Bearer token and X-API-Key provided") -> None:
        super().__init__(message=message, status_code=400)


class InvalidTokenError(AuthenticationError):
    """Raised when a JWT is malformed, invalid signature, or fails claim checks."""

    def __init__(self, message: str = "Invalid or unverified token") -> None:
        super().__init__(message=message, status_code=401)


class ExpiredTokenError(AuthenticationError):
    """Raised when a JWT has expired."""

    def __init__(self, message: str = "Token has expired") -> None:
        super().__init__(message=message, status_code=401)


class InvalidApiKeyError(AuthenticationError):
    """Raised when an API key is malformed or invalid."""

    def __init__(self, message: str = "Invalid API key") -> None:
        super().__init__(message=message, status_code=401)


class RevokedApiKeyError(AuthenticationError):
    """Raised when an API key has been explicitly revoked."""

    def __init__(self, message: str = "API key has been revoked") -> None:
        super().__init__(message=message, status_code=401)


class RateLimitExceededError(Exception):
    """Raised when token-bucket rate limit or failed-auth throttle is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after
        self.status_code = 429


class PayloadTooLargeError(Exception):
    """Raised when request body exceeds maximum allowed size."""

    def __init__(self, message: str = "Request payload exceeds 2 MB limit") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = 413


# ---------------------------------------------------------------------------
# Principal & Domain Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Principal:
    """Canonical representation of an authenticated calling identity."""

    principal_id: str
    organization_id: str
    roles: tuple[str, ...] = ("sangyan_viewer",)
    scopes: tuple[str, ...] = ()
    auth_method: str = "jwt"  # jwt | api_key | session | development
    credential_id: Optional[str] = None
    issued_at: Optional[float] = None
    expires_at: Optional[float] = None

    @property
    def primary_role(self) -> str:
        return self.roles[0] if self.roles else "sangyan_viewer"

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        # Check explicit scopes first
        if permission in self.scopes or "all" in self.scopes:
            return True
        from sangyan.tenancy.models import has_permission as check_role_permission
        # Check assigned role permissions
        return any(check_role_permission(r, permission) for r in self.roles)

    def to_dict(self) -> dict[str, Any]:
        return {
            "principal_id": self.principal_id,
            "organization_id": self.organization_id,
            "roles": list(self.roles),
            "scopes": list(self.scopes),
            "auth_method": self.auth_method,
            "credential_id": self.credential_id,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
        }


@dataclass
class ApiKey:
    """Relational model for hashed machine-to-machine API credentials."""

    organization_id: str
    user_id: str
    name: str
    key_prefix: str
    key_hash: str
    role: str = "sangyan_analyst"
    scopes: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: new_id("key"))
    expires_at: Optional[float] = None
    revoked_at: Optional[float] = None
    last_used_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    schema_version: int = CURRENT_SCHEMA_VERSION

    def is_active(self, now: Optional[float] = None) -> bool:
        current_time = now if now is not None else time.time()
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and current_time >= self.expires_at:
            return False
        return True

    def to_dict(self, include_hash: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "role": self.role,
            "scopes": list(self.scopes),
            "expires_at": self.expires_at,
            "revoked_at": self.revoked_at,
            "last_used_at": self.last_used_at,
            "created_at": self.created_at,
            "is_active": self.is_active(),
            "schema_version": self.schema_version,
        }
        if include_hash:
            data["key_hash"] = self.key_hash
        return data


@dataclass
class SecurityConfig:
    """Configuration for API security, token verification, and rate limiting."""

    jwt_secret: str = "sangyan-insecure-test-secret-change-in-prod-min32bytes"
    jwt_public_key: Optional[str] = None
    jwt_private_key: Optional[str] = None
    jwt_algorithms: list[str] = field(default_factory=lambda: ["HS256"])
    jwt_issuer: str = "sangyan-auth"
    jwt_audience: str = "sangyan-api"
    jwt_leeway: int = 30  # RFC 7519 clock skew leeway in seconds
    api_key_prefix: str = "sgy_"
    max_request_body_bytes: int = 2 * 1024 * 1024  # 2 MB
    allowed_origins: list[str] = field(default_factory=lambda: ["*"])
    rate_limit_enabled: bool = True
