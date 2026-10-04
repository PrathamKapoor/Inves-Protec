"""Comprehensive security test suite for Phase 6.

Validates:
- Cryptographic JWT validation, algorithms allowlist, claim checks, and clock skew.
- Hashed API key lifecycle, generation, prefix indexing, and constant-time verification.
- Mutual exclusivity of credentials (Bearer + X-API-Key -> 400).
- Strict multi-tenant isolation, IDOR/BOLA defense, and parameter tampering prevention.
- Contextual RBAC enforcement across sangyan_viewer, sangyan_analyst, and sangyan_admin.
- Token-bucket rate limiting, failed-authentication throttling, and traffic shaping.
- Defensive HTTP security headers, request body bounds (2 MB), and correlation IDs.
- Low-cardinality Prometheus telemetry metrics and sensitive-data redaction.
"""
from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import Generator

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.testclient import TestClient

from sangyan.api.app import create_app
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.security.api_keys import (
    generate_api_key,
    hash_api_key,
    parse_raw_api_key,
    verify_api_key,
)
from sangyan.security.auth import Authenticator, enforce_tenant_boundary, extract_credentials
from sangyan.security.jwt import JwtValidator, create_jwt_token
from sangyan.security.middleware import MAX_REQUEST_BODY_BYTES
from sangyan.security.models import (
    ApiKey,
    AuthenticationError,
    ExpiredTokenError,
    InvalidApiKeyError,
    InvalidTokenError,
    Principal,
    RevokedApiKeyError,
    SecurityConfig,
)
from sangyan.security.rate_limiter import FailedAuthTracker, TokenBucket, TokenBucketRateLimiter
from sangyan.security.telemetry import (
    MetricsRegistry,
    RedactingLogFilter,
    normalize_route,
    redact_sensitive_text,
)
from sangyan.tenancy.repository import TenantAdministration, TenantRepository
from sangyan.trust.service import TrustService
from sangyan.verification.engine import ClaimVerificationEngine
from sangyan.verification.trust_binding import TrustBindingService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_engine() -> Generator[SQLiteDatabaseEngine, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sec.db"
        engine = SQLiteDatabaseEngine(db_path)
        MigrationRunner(engine).migrate()
        yield engine
        engine.close()


@pytest.fixture
def tenancy_setup(temp_engine: SQLiteDatabaseEngine):
    admin = TenantAdministration(temp_engine)
    # Organization 1 (Alpha)
    org1_id = admin.create_organization("Alpha Org")
    user_viewer_id = admin.create_user("viewer@alpha.org", "Alpha Viewer")
    user_analyst_id = admin.create_user("analyst@alpha.org", "Alpha Analyst")
    user_admin_id = admin.create_user("admin@alpha.org", "Alpha Admin")

    admin.add_membership(org1_id, user_viewer_id, "sangyan_viewer")
    admin.add_membership(org1_id, user_analyst_id, "sangyan_analyst")
    admin.add_membership(org1_id, user_admin_id, "sangyan_admin")

    # Organization 2 (Beta) - for tenant isolation tests
    org2_id = admin.create_organization("Beta Org")
    user_beta_id = admin.create_user("analyst@beta.org", "Beta Analyst")
    admin.add_membership(org2_id, user_beta_id, "sangyan_analyst")

    return {
        "engine": temp_engine,
        "org1_id": org1_id,
        "user_viewer_id": user_viewer_id,
        "user_analyst_id": user_analyst_id,
        "user_admin_id": user_admin_id,
        "org2_id": org2_id,
        "user_beta_id": user_beta_id,
    }


# ---------------------------------------------------------------------------
# 1. JWT Validation Tests
# ---------------------------------------------------------------------------


class TestJwtValidation:
    def test_valid_jwt_validation(self):
        config = SecurityConfig(jwt_secret="strong-test-secret-key-at-least-32-bytes!")
        validator = JwtValidator(config)

        token = create_jwt_token(
            payload={"sub": "usr_123", "org_id": "org_456", "roles": ["sangyan_analyst"], "scopes": ["investigation:create"]},
            secret_or_key=config.jwt_secret,
            algorithm="HS256",
            issuer=config.jwt_issuer,
            audience=config.jwt_audience,
        )

        principal = validator.decode_and_validate(token)
        assert principal.principal_id == "usr_123"
        assert principal.organization_id == "org_456"
        assert principal.has_role("sangyan_analyst")
        assert principal.has_permission("investigation:create")
        assert principal.auth_method == "jwt"

    def test_expired_jwt_rejected(self):
        config = SecurityConfig(jwt_secret="strong-test-secret-key-at-least-32-bytes!", jwt_leeway=0)
        validator = JwtValidator(config)

        token = create_jwt_token(
            payload={"sub": "usr_123", "org_id": "org_456"},
            secret_or_key=config.jwt_secret,
            expires_in_seconds=-10,  # Expired 10 seconds ago
        )

        with pytest.raises(ExpiredTokenError):
            validator.decode_and_validate(token)

    def test_invalid_signature_rejected(self):
        config = SecurityConfig(jwt_secret="correct-secret-key-at-least-32-bytes!")
        validator = JwtValidator(config)

        token = create_jwt_token(
            payload={"sub": "usr_123", "org_id": "org_456"},
            secret_or_key="wrong-secret-key-at-least-32-bytes!!",
        )

        with pytest.raises(InvalidTokenError):
            validator.decode_and_validate(token)

    def test_algorithm_none_rejected(self):
        config = SecurityConfig(jwt_secret="test-secret-at-least-32-bytes-long!")
        validator = JwtValidator(config)

        # Forge token with alg="none"
        claims = {
            "sub": "usr_123",
            "org_id": "org_456",
            "iss": config.jwt_issuer,
            "aud": config.jwt_audience,
            "exp": int(time.time() + 3600),
            "iat": int(time.time()),
        }
        token = jwt.encode(claims, key="", algorithm="none")

        with pytest.raises(InvalidTokenError) as exc_info:
            validator.decode_and_validate(token)
        assert "algorithm" in str(exc_info.value).lower()

    def test_missing_mandatory_claims(self):
        config = SecurityConfig(jwt_secret="test-secret-at-least-32-bytes-long!")
        validator = JwtValidator(config)

        # Missing 'org_id'
        claims = {
            "sub": "usr_123",
            "iss": config.jwt_issuer,
            "aud": config.jwt_audience,
            "exp": int(time.time() + 3600),
            "iat": int(time.time()),
        }
        token = jwt.encode(claims, config.jwt_secret, algorithm="HS256")

        with pytest.raises(InvalidTokenError):
            validator.decode_and_validate(token)

    def test_clock_skew_leeway_tolerance(self):
        config = SecurityConfig(jwt_secret="test-secret-at-least-32-bytes-long!", jwt_leeway=30)
        validator = JwtValidator(config)

        # Expired 15s ago, but leeway is 30s -> should succeed
        now = time.time()
        claims = {
            "sub": "usr_123",
            "org_id": "org_456",
            "iss": config.jwt_issuer,
            "aud": config.jwt_audience,
            "exp": int(now - 15),
            "iat": int(now - 3600),
        }
        token = jwt.encode(claims, config.jwt_secret, algorithm="HS256")
        principal = validator.decode_and_validate(token)
        assert principal.principal_id == "usr_123"

    def test_asymmetric_rs256_validation(self):
        # Generate test RSA key pair
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem_private = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        pem_public = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        config = SecurityConfig(
            jwt_algorithms=["RS256"],
            jwt_public_key=pem_public,
            jwt_private_key=pem_private,
        )
        validator = JwtValidator(config)

        token = create_jwt_token(
            payload={"sub": "usr_rsa", "org_id": "org_rsa", "roles": ["sangyan_analyst"]},
            secret_or_key=pem_private,
            algorithm="RS256",
            issuer=config.jwt_issuer,
            audience=config.jwt_audience,
        )

        principal = validator.decode_and_validate(token)
        assert principal.principal_id == "usr_rsa"
        assert principal.organization_id == "org_rsa"


# ---------------------------------------------------------------------------
# 2. Hashed API Key Lifecycle Tests
# ---------------------------------------------------------------------------


class TestApiKeyEngine:
    def test_generate_and_parse_format(self):
        raw_key, api_key = generate_api_key(
            organization_id="org_1",
            user_id="usr_1",
            name="Institutional Pipeline Key",
            role="sangyan_analyst",
            expires_in_days=30,
        )
        assert raw_key.startswith("sgy_")
        prefix, secret = parse_raw_api_key(raw_key)
        assert len(prefix) == 8
        assert len(secret) == 32
        assert api_key.key_prefix == prefix
        # Plaintext secret MUST NOT be stored in the model
        assert secret not in api_key.key_hash
        assert api_key.key_hash == hash_api_key(prefix, secret)

    def test_malformed_key_parsing(self):
        with pytest.raises(InvalidApiKeyError):
            parse_raw_api_key("invalid_prefix_secret")
        with pytest.raises(InvalidApiKeyError):
            parse_raw_api_key("sgy_short_secret")
        with pytest.raises(InvalidApiKeyError):
            parse_raw_api_key("sgy_12345678_nothexcharacterzzzzzzzzzzzzzzzz")

    def test_verify_api_key_lifecycle(self, tenancy_setup):
        engine = tenancy_setup["engine"]
        org_id = tenancy_setup["org1_id"]
        user_id = tenancy_setup["user_admin_id"]

        repo = TenantRepository(engine, org_id, user_id)
        raw_key, api_key = generate_api_key(
            organization_id=org_id,
            user_id=user_id,
            name="CI Automation Key",
            role="sangyan_analyst",
        )
        repo.save_api_key(api_key)

        # Successful verification
        principal = verify_api_key(raw_key, repo)
        assert principal.principal_id == user_id
        assert principal.organization_id == org_id
        assert principal.has_role("sangyan_analyst")
        assert principal.auth_method == "api_key"

        # Verify global engine verification works too
        principal_global = verify_api_key(raw_key, engine)
        assert principal_global.principal_id == user_id

        # Verification updates last_used_at
        saved = repo.get_api_key(api_key.id)
        assert saved.last_used_at is not None

        # Revocation
        repo.revoke_api_key(api_key.id)
        with pytest.raises(RevokedApiKeyError):
            verify_api_key(raw_key, repo)

    def test_expired_api_key_rejected(self, tenancy_setup):
        engine = tenancy_setup["engine"]
        org_id = tenancy_setup["org1_id"]
        user_id = tenancy_setup["user_admin_id"]
        repo = TenantRepository(engine, org_id, user_id)

        raw_key, api_key = generate_api_key(
            organization_id=org_id,
            user_id=user_id,
            name="Expired Key",
        )
        # Set expiry in the past
        api_key.expires_at = time.time() - 3600
        repo.save_api_key(api_key)

        with pytest.raises(ExpiredTokenError):
            verify_api_key(raw_key, repo)

    def test_incorrect_secret_rejected(self, tenancy_setup):
        engine = tenancy_setup["engine"]
        org_id = tenancy_setup["org1_id"]
        user_id = tenancy_setup["user_admin_id"]
        repo = TenantRepository(engine, org_id, user_id)

        raw_key, api_key = generate_api_key(
            organization_id=org_id,
            user_id=user_id,
            name="Test Key",
        )
        repo.save_api_key(api_key)

        prefix, _ = parse_raw_api_key(raw_key)
        fake_secret = "00112233445566778899aabbccddeeff"
        fake_raw = f"sgy_{prefix}_{fake_secret}"

        with pytest.raises(InvalidApiKeyError):
            verify_api_key(fake_raw, repo)


# ---------------------------------------------------------------------------
# 3. Rate Limiter & Failed-Auth Throttling Tests
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_token_bucket_consumption_and_refill(self):
        # 5 tokens capacity, 10 tokens per second refill
        bucket = TokenBucket(capacity=5, refill_rate=10)
        # Consume 5 tokens
        for _ in range(5):
            allowed, rem, wait = bucket.consume(1)
            assert allowed is True

        # 6th should be rejected
        allowed, rem, wait = bucket.consume(1)
        assert allowed is False
        assert wait >= 1

        # Wait 0.2s (refills ~2 tokens)
        time.sleep(0.2)
        allowed, rem, wait = bucket.consume(1)
        assert allowed is True

    def test_failed_auth_throttle_lockout(self):
        tracker = FailedAuthTracker(failure_threshold=3, window_seconds=2.0)
        ip = "192.0.2.100"

        # Record 2 failures -> not throttled
        tracker.record_failure(ip)
        tracker.record_failure(ip)
        throttled, wait = tracker.is_throttled(ip)
        assert throttled is False

        # 3rd failure -> throttled
        tracker.record_failure(ip)
        throttled, wait = tracker.is_throttled(ip)
        assert throttled is True
        assert wait > 0

        # Successful auth resets failures
        tracker.record_success(ip)
        throttled, _ = tracker.is_throttled(ip)
        assert throttled is False

    def test_rate_limiter_stale_cleanup(self):
        limiter = TokenBucketRateLimiter()
        limiter.check_rate_limit("test_caller", "default")
        assert len(limiter._buckets) == 1
        # Artificially age bucket
        for b in limiter._buckets.values():
            b.last_accessed -= 500
        evicted = limiter.cleanup_stale_buckets(max_idle_seconds=300)
        assert evicted == 1
        assert len(limiter._buckets) == 0


# ---------------------------------------------------------------------------
# 4. Telemetry, Route Normalization & Redaction Tests
# ---------------------------------------------------------------------------


class TestTelemetryAndRedaction:
    def test_route_normalization_bounds_cardinality(self):
        assert normalize_route("/api/v1/investigations/inv_01hxabc123/scam_chain") == "/api/v1/investigations/{investigation_id}/scam_chain"
        assert normalize_route("/api/v1/claims/clm_887766/evidence") == "/api/v1/claims/{claim_id}/evidence"
        assert normalize_route("/api/v1/workflow/12345/resume") == "/api/v1/workflow/{workflow_id}/resume"
        assert normalize_route("/health") == "/health"
        assert normalize_route("/metrics") == "/metrics"

    def test_sensitive_text_redaction(self):
        text = (
            "User provided Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123xyz\n"
            "Also api_key is sgy_a1b2c3d4_0123456789abcdef0123456789abcdef\n"
            'and "password": "supersecretpassword123"'
        )
        sanitized = redact_sensitive_text(text)
        assert "Bearer [REDACTED_JWT]" in sanitized
        assert "sgy_[REDACTED_API_KEY]" in sanitized
        assert "[REDACTED]" in sanitized
        assert "supersecretpassword123" not in sanitized
        assert "a1b2c3d4" not in sanitized

    def test_redacting_log_filter(self):
        redacting_filter = RedactingLogFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Received key sgy_deadbeef_11223344556677889900aabbccddeeff",
            args=(),
            exc_info=None,
        )
        redacting_filter.filter(record)
        assert "sgy_[REDACTED_API_KEY]" in record.msg
        assert "deadbeef" not in record.msg

    def test_metrics_registry_export(self):
        registry = MetricsRegistry()
        registry.http_requests_total.labels(method="GET", route="/health", status_code="200").inc()
        registry.security_events_total.labels(event_type="auth_failure", status="rejected").inc()
        response = registry.export_metrics()
        assert response.status_code == 200
        content = response.body.decode("utf-8")
        assert "sangyan_http_requests_total" in content
        assert "sangyan_security_events_total" in content


# ---------------------------------------------------------------------------
# 5. Integration API Tests: Authentication, RBAC, Rate Limiting & Headers
# ---------------------------------------------------------------------------


class TestApiIntegrationSecurity:
    @pytest.fixture
    def secure_client(self, tenancy_setup):
        engine = tenancy_setup["engine"]
        config = SecurityConfig(
            jwt_secret="strong-test-secret-at-least-32-bytes-long!",
            rate_limit_enabled=True,
        )
        trust_service = TrustService(engine)
        verif_engine = ClaimVerificationEngine(trust_binding=TrustBindingService(trust_service))

        app = create_app(
            engine=engine,
            trust_service=trust_service,
            verification_engine=verif_engine,
            security_config=config,
            require_auth=True,  # Strict production mode
        )
        client = TestClient(app)
        return client, config, tenancy_setup

    def _mint_jwt(self, config, user_id, org_id, roles):
        return create_jwt_token(
            payload={"sub": user_id, "org_id": org_id, "roles": roles},
            secret_or_key=config.jwt_secret,
            issuer=config.jwt_issuer,
            audience=config.jwt_audience,
        )

    def test_unauthenticated_request_rejected(self, secure_client):
        client, _, data = secure_client
        res = client.get("/api/v1/investigations/inv_any")
        assert res.status_code == 401
        assert "WWW-Authenticate" in res.headers

    def test_ambiguous_credentials_rejected_with_400(self, secure_client):
        client, config, data = secure_client
        jwt_token = self._mint_jwt(config, data["user_analyst_id"], data["org1_id"], ["sangyan_analyst"])

        # Send BOTH Bearer and X-API-Key
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "X-API-Key": "sgy_12345678_0123456789abcdef0123456789abcdef",
        }
        res = client.get("/api/v1/investigations/inv_any", headers=headers)
        assert res.status_code == 400
        assert "Ambiguous credentials" in res.json()["detail"]

    def test_bearer_jwt_authentication_success(self, secure_client):
        client, config, data = secure_client
        jwt_token = self._mint_jwt(config, data["user_analyst_id"], data["org1_id"], ["sangyan_analyst"])

        headers = {"Authorization": f"Bearer {jwt_token}"}
        payload = {
            "statement": "Zerodha Broking Limited is SEBI registered under INZ000031633.",
            "claim_type": "regulatory",
        }
        res = client.post("/api/v1/verify/claim", json=payload, headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "SUPPORTED"

    def test_api_key_authentication_success(self, secure_client):
        client, config, data = secure_client
        engine = data["engine"]
        org_id = data["org1_id"]
        user_id = data["user_admin_id"]

        repo = TenantRepository(engine, org_id, user_id)
        raw_key, api_key = generate_api_key(org_id, user_id, "CI Test Key", role="sangyan_analyst")
        repo.save_api_key(api_key)

        headers = {"X-API-Key": raw_key}
        payload = {
            "statement": "Zerodha Broking Limited is SEBI registered under INZ000031633.",
            "claim_type": "regulatory",
        }
        res = client.post("/api/v1/verify/claim", json=payload, headers=headers)
        assert res.status_code == 200
        assert res.json()["status"] == "SUPPORTED"

    def test_rbac_viewer_denied_verification(self, secure_client):
        client, config, data = secure_client
        viewer_token = self._mint_jwt(config, data["user_viewer_id"], data["org1_id"], ["sangyan_viewer"])

        headers = {"Authorization": f"Bearer {viewer_token}"}
        payload = {"statement": "Some claim to verify", "claim_type": "regulatory"}
        res = client.post("/api/v1/verify/claim", json=payload, headers=headers)
        # Viewer lacks investigation:create permission -> 403 Forbidden
        assert res.status_code == 403
        assert "investigation:create" in res.json()["detail"]

    def test_rbac_analyst_denied_api_key_management(self, secure_client):
        client, config, data = secure_client
        analyst_token = self._mint_jwt(config, data["user_analyst_id"], data["org1_id"], ["sangyan_analyst"])

        headers = {"Authorization": f"Bearer {analyst_token}"}
        payload = {"name": "Unauthorized Key Provision", "role": "sangyan_analyst"}
        res = client.post("/api/v1/auth/api-keys", json=payload, headers=headers)
        # Analyst lacks api_key:manage -> 403 Forbidden
        assert res.status_code == 403

    def test_rbac_admin_allowed_api_key_management(self, secure_client):
        client, config, data = secure_client
        admin_token = self._mint_jwt(config, data["user_admin_id"], data["org1_id"], ["sangyan_admin"])

        headers = {"Authorization": f"Bearer {admin_token}"}
        # 1. Create API key
        payload = {"name": "Admin Generated Key", "role": "sangyan_analyst", "expires_in_days": 10}
        res = client.post("/api/v1/auth/api-keys", json=payload, headers=headers)
        assert res.status_code == 201
        body = res.json()
        raw_key = body["raw_api_key"]
        key_id = body["api_key"]["id"]
        assert raw_key.startswith("sgy_")

        # 2. List API keys
        list_res = client.get("/api/v1/auth/api-keys", headers=headers)
        assert list_res.status_code == 200
        assert any(k["id"] == key_id for k in list_res.json())

        # 3. Revoke API key
        del_res = client.delete(f"/api/v1/auth/api-keys/{key_id}", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["revoked_at"] is not None

    def test_tenant_boundary_mismatch_parameter_rejected(self, secure_client):
        client, config, data = secure_client
        # Caller belongs to org1
        jwt_token = self._mint_jwt(config, data["user_analyst_id"], data["org1_id"], ["sangyan_analyst"])

        headers = {"Authorization": f"Bearer {jwt_token}"}
        # Caller specifies org2_id in request payload
        payload = {
            "statement": "Zerodha Broking Limited is SEBI registered.",
            "organization_id": data["org2_id"],  # Foreign tenant
        }
        res = client.post("/api/v1/verify/claim", json=payload, headers=headers)
        assert res.status_code == 403
        assert "Tenant mismatch" in res.json()["detail"]

    def test_idor_foreign_tenant_investigation_not_found(self, secure_client):
        client, config, data = secure_client
        # Caller belongs to org2
        beta_token = self._mint_jwt(config, data["user_beta_id"], data["org2_id"], ["sangyan_analyst"])
        headers = {"Authorization": f"Bearer {beta_token}"}

        # Attempt to read non-existent or foreign investigation
        res = client.get("/api/v1/investigations/inv_org1_private", headers=headers)
        assert res.status_code == 404

    def test_security_headers_present(self, secure_client):
        client, _, _ = secure_client
        res = client.get("/health")
        assert res.status_code == 200
        assert res.headers.get("X-Content-Type-Options") == "nosniff"
        assert res.headers.get("X-Frame-Options") == "DENY"
        assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "default-src 'self'" in res.headers.get("Content-Security-Policy", "")
        assert "X-Request-ID" in res.headers

    def test_api_routes_cache_control_no_store(self, secure_client):
        client, config, data = secure_client
        analyst_token = self._mint_jwt(config, data["user_analyst_id"], data["org1_id"], ["sangyan_analyst"])
        headers = {"Authorization": f"Bearer {analyst_token}"}

        res = client.get("/api/v1/sources", headers=headers)
        assert res.status_code == 200
        cache_control = res.headers.get("Cache-Control", "")
        assert "no-store" in cache_control
        assert "no-cache" in cache_control

    def test_request_body_size_bound(self, secure_client):
        client, config, data = secure_client
        analyst_token = self._mint_jwt(config, data["user_analyst_id"], data["org1_id"], ["sangyan_analyst"])
        headers = {
            "Authorization": f"Bearer {analyst_token}",
            "Content-Type": "application/json",
            "Content-Length": str(MAX_REQUEST_BODY_BYTES + 5000),  # Exceeds 2 MB
        }
        res = client.post(
            "/api/v1/verify/content",
            content=b"x" * 100,  # Header triggers 413
            headers=headers,
        )
        assert res.status_code == 413
        assert "too large" in res.json()["detail"].lower()

    def test_prometheus_metrics_endpoint(self, secure_client):
        client, _, _ = secure_client
        res = client.get("/metrics")
        assert res.status_code == 200
        content = res.text
        assert "sangyan_http_requests_total" in content
