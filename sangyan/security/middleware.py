"""HTTP Security Headers, Request Size Bounding, Correlation IDs, and Rate Limiting Middlewares."""
from __future__ import annotations

import uuid
from typing import Callable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from sangyan.security.models import SecurityConfig
from sangyan.security.rate_limiter import TokenBucketRateLimiter

MAX_REQUEST_BODY_BYTES = 2 * 1024 * 1024  # 2 MB


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces standard defensive HTTP security headers and prevents caching of sensitive investigation data."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Standard defense-in-depth security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        # Prevent browser and proxy caching of sensitive grievance / investigation endpoints
        if request.url.path.startswith("/api/v1/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"

        return response


class RequestSizeLimiterMiddleware(BaseHTTPMiddleware):
    """Rejects incoming request bodies exceeding the maximum bound (2 MB) before parsing."""

    def __init__(self, app, max_body_bytes: int = MAX_REQUEST_BODY_BYTES) -> None:
        super().__init__(app)
        self.max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length_str = request.headers.get("content-length")
        if content_length_str is not None:
            try:
                content_length = int(content_length_str)
                if content_length > self.max_body_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"Request body too large ({content_length} bytes). Limit is {self.max_body_bytes} bytes."
                        },
                    )
            except ValueError:
                pass

        return await call_next(request)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Propagates or mints canonical X-Request-ID for distributed tracing and audit correlation."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID")
        if not request_id or not request_id.strip():
            request_id = f"req_{uuid.uuid4().hex}"
        else:
            request_id = request_id.strip()

        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Evaluates sliding token-bucket limits and failed-authentication throttling."""

    def __init__(self, app, rate_limiter: TokenBucketRateLimiter, enabled: bool = True) -> None:
        super().__init__(app)
        self.limiter = rate_limiter
        self.enabled = enabled

    def _classify_endpoint(self, path: str, method: str) -> str:
        if "/auth/" in path:
            return "auth"
        if "/workflow/" in path and method in ("POST", "PUT", "DELETE"):
            return "workflow_mutate"
        if "/verify/" in path or path.endswith("/investigate"):
            return "investigation"
        if method == "GET":
            return "read"
        return "default"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled or request.url.path in ("/health", "/metrics", "/docs", "/openapi.json"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        # Check IP-level failed authentication throttle
        is_locked, retry_after = self.limiter.auth_tracker.is_throttled(client_ip)
        if is_locked:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Too many authentication failures. Locked out. Please wait {retry_after}s."
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": "5",
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(retry_after),
                },
            )

        endpoint_class = self._classify_endpoint(request.url.path, request.method)

        # Derive identifier: prefer principal if already attached, else IP
        principal = getattr(request.state, "principal", None)
        if principal and hasattr(principal, "principal_id"):
            identifier = f"principal:{principal.principal_id}"
        else:
            identifier = f"ip:{client_ip}"

        allowed, capacity, remaining, retry_after = self.limiter.check_rate_limit(
            identifier=identifier,
            endpoint_class=endpoint_class,
        )

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded for {endpoint_class} operations. Please retry in {retry_after}s."
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(capacity),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(retry_after),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(capacity)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
