"""Security controls, authentication, authorization, rate limiting, and network boundaries."""
from sangyan.security.api_keys import (
    generate_api_key,
    hash_api_key,
    parse_raw_api_key,
    verify_api_key,
)
from sangyan.security.auth import (
    Authenticator,
    enforce_tenant_boundary,
    extract_credentials,
    require_permission,
    require_role,
)
from sangyan.security.jwt import (
    ALLOWED_JWT_ALGORITHMS,
    JwtValidator,
    create_jwt_token,
)
from sangyan.security.middleware import (
    MAX_REQUEST_BODY_BYTES,
    CorrelationIdMiddleware,
    RateLimiterMiddleware,
    RequestSizeLimiterMiddleware,
    SecurityHeadersMiddleware,
)
from sangyan.security.models import (
    AmbiguousAuthenticationError,
    ApiKey,
    AuthenticationError,
    ExpiredTokenError,
    InvalidApiKeyError,
    InvalidTokenError,
    PayloadTooLargeError,
    Principal,
    RateLimitExceededError,
    RevokedApiKeyError,
    SecurityConfig,
)
from sangyan.security.rate_limiter import (
    FailedAuthTracker,
    RATE_LIMIT_POLICIES,
    TokenBucket,
    TokenBucketRateLimiter,
)
from sangyan.security.ssrf import (
    is_unsafe_ip,
    ssrf_safe_connections,
    validate_url_shape,
    validate_url_ssrf,
)
from sangyan.security.telemetry import (
    MetricsRegistry,
    PrometheusMetricsMiddleware,
    RedactingLogFilter,
    normalize_route,
    redact_sensitive_text,
)

__all__ = [
    # SSRF & Network
    "validate_url_shape",
    "is_unsafe_ip",
    "validate_url_ssrf",
    "ssrf_safe_connections",
    # Models & Config
    "Principal",
    "ApiKey",
    "SecurityConfig",
    "AuthenticationError",
    "AmbiguousAuthenticationError",
    "InvalidTokenError",
    "ExpiredTokenError",
    "InvalidApiKeyError",
    "RevokedApiKeyError",
    "RateLimitExceededError",
    "PayloadTooLargeError",
    # JWT
    "ALLOWED_JWT_ALGORITHMS",
    "create_jwt_token",
    "JwtValidator",
    # API Keys
    "generate_api_key",
    "verify_api_key",
    "hash_api_key",
    "parse_raw_api_key",
    # Rate Limiting
    "TokenBucket",
    "FailedAuthTracker",
    "TokenBucketRateLimiter",
    "RATE_LIMIT_POLICIES",
    # Middlewares
    "MAX_REQUEST_BODY_BYTES",
    "SecurityHeadersMiddleware",
    "RequestSizeLimiterMiddleware",
    "CorrelationIdMiddleware",
    "RateLimiterMiddleware",
    # Telemetry & Redaction
    "MetricsRegistry",
    "PrometheusMetricsMiddleware",
    "RedactingLogFilter",
    "redact_sensitive_text",
    "normalize_route",
    # Auth & RBAC
    "Authenticator",
    "extract_credentials",
    "enforce_tenant_boundary",
    "require_role",
    "require_permission",
]
