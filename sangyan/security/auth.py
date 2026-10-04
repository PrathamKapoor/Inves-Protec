"""Authentication boundary, credential extraction, mutual exclusivity, and RBAC enforcement."""
from __future__ import annotations

import json
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sangyan.database.engine import DatabaseEngine
from sangyan.security.api_keys import verify_api_key
from sangyan.security.jwt import JwtValidator
from sangyan.security.models import (
    AmbiguousAuthenticationError,
    AuthenticationError,
    Principal,
    SecurityConfig,
)
from sangyan.security.rate_limiter import TokenBucketRateLimiter
from sangyan.security.telemetry import MetricsRegistry


def extract_credentials(request: Request) -> tuple[Optional[str], Optional[str]]:
    """Extract Bearer token and X-API-Key from request; enforces mutual exclusivity."""
    auth_header = request.headers.get("Authorization", "").strip()
    bearer_token: Optional[str] = None
    if auth_header.lower().startswith("bearer "):
        bearer_token = auth_header[7:].strip()

    api_key_header = request.headers.get("X-API-Key", "").strip()
    api_key: Optional[str] = api_key_header if api_key_header else None

    # Enforce strict mutual exclusivity to prevent credential confusion
    if bearer_token and api_key:
        raise AmbiguousAuthenticationError("Ambiguous credentials: both Bearer token and X-API-Key provided in request")

    return bearer_token, api_key


class Authenticator:
    """Gateway authentication engine resolving incoming credentials to canonical Principal."""

    def __init__(
        self,
        engine: DatabaseEngine,
        config: Optional[SecurityConfig] = None,
        rate_limiter: Optional[TokenBucketRateLimiter] = None,
        metrics_registry: Optional[MetricsRegistry] = None,
        require_auth: bool = True,
    ) -> None:
        self.engine = engine
        self.config = config or SecurityConfig()
        self.jwt_validator = JwtValidator(self.config)
        self.rate_limiter = rate_limiter
        self.metrics = metrics_registry or MetricsRegistry.get_default()
        self.require_auth = require_auth

    async def __call__(self, request: Request) -> Principal:
        client_ip = request.client.host if request.client else "unknown"

        # Check if rate limiter already locked this IP for failed auths
        if self.rate_limiter:
            is_locked, retry_after = self.rate_limiter.auth_tracker.is_throttled(client_ip)
            if is_locked:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many failed authentication attempts. Locked out for {retry_after}s.",
                    headers={"Retry-After": str(retry_after)},
                )

        try:
            bearer_token, api_key = extract_credentials(request)
        except AmbiguousAuthenticationError as e:
            if self.rate_limiter:
                self.rate_limiter.auth_tracker.record_failure(client_ip)
            self.metrics.security_events_total.labels(event_type="auth_ambiguous", status="rejected").inc()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        # 1. Bearer JWT
        if bearer_token:
            try:
                principal = self.jwt_validator.decode_and_validate(bearer_token)
                request.state.principal = principal
                if self.rate_limiter:
                    self.rate_limiter.auth_tracker.record_success(client_ip)
                return principal
            except AuthenticationError as e:
                if self.rate_limiter:
                    self.rate_limiter.auth_tracker.record_failure(client_ip)
                self.metrics.security_events_total.labels(event_type="auth_jwt_failure", status="rejected").inc()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=str(e),
                    headers={"WWW-Authenticate": 'Bearer realm="sangyan"'},
                )

        # 2. X-API-Key
        if api_key:
            try:
                principal = verify_api_key(api_key, self.engine)
                request.state.principal = principal
                if self.rate_limiter:
                    self.rate_limiter.auth_tracker.record_success(client_ip)
                return principal
            except AuthenticationError as e:
                if self.rate_limiter:
                    self.rate_limiter.auth_tracker.record_failure(client_ip)
                self.metrics.security_events_total.labels(event_type="auth_key_failure", status="rejected").inc()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=str(e),
                    headers={"WWW-Authenticate": 'Bearer realm="sangyan"'},
                )

        # 3. No credentials provided
        if not self.require_auth:
            # Fallback for development/testing when require_auth=False
            # Inspect query parameters or JSON body for organization_id & user_id
            org_id = request.query_params.get("organization_id")
            user_id = request.query_params.get("user_id")

            if not org_id or not user_id:
                try:
                    body_bytes = await request.body()
                    if body_bytes:
                        data = json.loads(body_bytes)
                        if isinstance(data, dict):
                            org_id = org_id or data.get("organization_id")
                            user_id = user_id or data.get("user_id")
                except Exception:
                    pass

            if org_id and user_id:
                # Resolve role from database membership
                row = self.engine.query_one(
                    "SELECT role FROM sangyan_memberships WHERE organization_id=? AND user_id=? AND status='active'",
                    (org_id, user_id),
                )
                role = row["role"] if row else "sangyan_viewer"
                principal = Principal(
                    principal_id=user_id,
                    organization_id=org_id,
                    roles=(role,),
                    scopes=(),
                    auth_method="development",
                )
                request.state.principal = principal
                return principal

        # Strict authentication required
        if self.rate_limiter:
            self.rate_limiter.auth_tracker.record_failure(client_ip)
        self.metrics.security_events_total.labels(event_type="auth_missing", status="rejected").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required (Bearer token or X-API-Key)",
            headers={"WWW-Authenticate": 'Bearer realm="sangyan"'},
        )


def enforce_tenant_boundary(
    principal: Principal,
    requested_organization_id: Optional[str],
    metrics_registry: Optional[MetricsRegistry] = None,
) -> None:
    """Enforce strict multi-tenant boundary. Disallow foreign tenant access."""
    if requested_organization_id and requested_organization_id != principal.organization_id:
        metrics = metrics_registry or MetricsRegistry.get_default()
        metrics.security_events_total.labels(event_type="tenant_mismatch", status="rejected").inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tenant mismatch: Caller tenant '{principal.organization_id}' does not match requested tenant '{requested_organization_id}'",
        )


def require_role(*allowed_roles: str) -> Callable[[Principal], Principal]:
    """Dependency factory checking that the authenticated principal possesses at least one required role."""

    def _role_checker(principal: Principal = Depends(lambda: None)) -> Principal:
        if not any(principal.has_role(r) for r in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: role '{principal.primary_role}' lacks required role ({', '.join(allowed_roles)})",
            )
        return principal

    return _role_checker


def require_permission(permission: str) -> Callable[[Principal], Principal]:
    """Dependency factory checking that the principal has the specific required permission."""

    def _perm_checker(principal: Principal = Depends(lambda: None)) -> Principal:
        if not principal.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: principal lacks required permission: '{permission}'",
            )
        return principal

    return _perm_checker
