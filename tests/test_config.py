"""Unit tests for centralized runtime configuration and fail-closed production safety guards."""
from __future__ import annotations

import pytest

from sangyan.config import (
    ConfigurationError,
    ENV_DEVELOPMENT,
    ENV_PRODUCTION,
    ENV_TEST,
    INSECURE_TEST_JWT_SECRET,
    SangyanConfig,
    load_config,
    validate_production_config,
)


def test_load_config_defaults():
    cfg = load_config({})
    assert cfg.env == ENV_DEVELOPMENT
    assert cfg.database_url == "sqlite:///sangyan.db"
    assert cfg.jwt_secret == INSECURE_TEST_JWT_SECRET
    assert cfg.require_auth is False  # False by default in development
    assert cfg.allowed_origins == ["*"]
    assert cfg.port == 8000
    assert cfg.is_production is False


def test_load_config_custom_env():
    env = {
        "SANGYAN_ENV": "production",
        "SANGYAN_DATABASE_URL": "postgresql://usr:pwd@dbhost:5432/sangyandb",
        "SANGYAN_JWT_SECRET": "a" * 64,
        "SANGYAN_ALLOWED_ORIGINS": "https://sangyan.gov.in, https://app.sangyan.gov.in",
        "SANGYAN_REQUIRE_AUTH": "true",
        "SANGYAN_PORT": "9000",
        "SANGYAN_LOG_LEVEL": "WARNING",
    }
    cfg = load_config(env)
    assert cfg.env == ENV_PRODUCTION
    assert cfg.is_production is True
    assert cfg.database_url == "postgresql://usr:pwd@dbhost:5432/sangyandb"
    assert cfg.jwt_secret == "a" * 64
    assert cfg.allowed_origins == ["https://sangyan.gov.in", "https://app.sangyan.gov.in"]
    assert cfg.require_auth is True
    assert cfg.port == 9000
    assert cfg.log_level == "WARNING"


def test_validate_production_config_rejects_insecure_jwt_secret():
    cfg = SangyanConfig(
        env=ENV_PRODUCTION,
        database_url="postgresql://usr:pwd@dbhost:5432/sangyandb",
        jwt_secret=INSECURE_TEST_JWT_SECRET,
        require_auth=True,
        allowed_origins=["https://sangyan.gov.in"],
    )
    with pytest.raises(ConfigurationError) as exc_info:
        validate_production_config(cfg)
    assert "default test JWT secret" in str(exc_info.value)


def test_validate_production_config_rejects_short_jwt_secret():
    cfg = SangyanConfig(
        env=ENV_PRODUCTION,
        database_url="postgresql://usr:pwd@dbhost:5432/sangyandb",
        jwt_secret="short-secret-under-32-chars",
        require_auth=True,
        allowed_origins=["https://sangyan.gov.in"],
    )
    with pytest.raises(ConfigurationError) as exc_info:
        validate_production_config(cfg)
    assert "minimum 32 bytes required" in str(exc_info.value)


def test_validate_production_config_rejects_disabled_auth():
    cfg = SangyanConfig(
        env=ENV_PRODUCTION,
        database_url="postgresql://usr:pwd@dbhost:5432/sangyandb",
        jwt_secret="a" * 64,
        require_auth=False,
        allowed_origins=["https://sangyan.gov.in"],
    )
    with pytest.raises(ConfigurationError) as exc_info:
        validate_production_config(cfg)
    assert "SANGYAN_REQUIRE_AUTH=true" in str(exc_info.value)


def test_validate_production_config_rejects_wildcard_cors():
    cfg = SangyanConfig(
        env=ENV_PRODUCTION,
        database_url="postgresql://usr:pwd@dbhost:5432/sangyandb",
        jwt_secret="a" * 64,
        require_auth=True,
        allowed_origins=["*"],
    )
    with pytest.raises(ConfigurationError) as exc_info:
        validate_production_config(cfg)
    assert "wildcard CORS origin" in str(exc_info.value)


def test_validate_production_config_rejects_in_memory_db():
    cfg = SangyanConfig(
        env=ENV_PRODUCTION,
        database_url=":memory:",
        jwt_secret="a" * 64,
        require_auth=True,
        allowed_origins=["https://sangyan.gov.in"],
    )
    with pytest.raises(ConfigurationError) as exc_info:
        validate_production_config(cfg)
    assert "in-memory SQLite ':memory:' is strictly forbidden" in str(exc_info.value)


def test_validate_production_config_passes_valid_prod():
    cfg = SangyanConfig(
        env=ENV_PRODUCTION,
        database_url="sqlite:////app/data/sangyan.db",
        jwt_secret="super-secure-production-jwt-signing-secret-with-high-entropy-2026",
        require_auth=True,
        allowed_origins=["https://sangyan.gov.in"],
        checkpoint_db_path="/app/checkpoints/workflow_checkpoints.db",
    )
    # Should not raise
    validate_production_config(cfg)


def test_sanitized_dict_redacts_credentials():
    cfg = SangyanConfig(
        database_url="postgresql://admin:super_secret_password@db.sangyan.internal:5432/prod_db",
        jwt_secret="super_secret_jwt_key_that_must_never_be_logged",
        backup_encryption_key="super_secret_backup_key",
    )
    sanitized = cfg.sanitized_dict()
    assert "super_secret_password" not in sanitized["database_url"]
    assert "[REDACTED]" in sanitized["database_url"]
    assert sanitized["jwt_secret"] == "[REDACTED]"
    assert "backup_encryption_key" not in sanitized
    assert sanitized["backup_encryption_configured"] is True
