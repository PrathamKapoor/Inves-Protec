"""Centralized environment configuration, validation, and production safety guards."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

from sangyan.security.models import SecurityConfig

ENV_DEVELOPMENT = "development"
ENV_TEST = "test"
ENV_PRODUCTION = "production"
VALID_ENVIRONMENTS = (ENV_DEVELOPMENT, ENV_TEST, ENV_PRODUCTION)

INSECURE_TEST_JWT_SECRET = "sangyan-insecure-test-secret-change-in-prod-min32bytes"


class ConfigurationError(Exception):
    """Raised when application configuration fails validation or security invariants."""


def _str_to_bool(val: Optional[str], default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "t", "on")


def _split_csv(val: Optional[str], default: list[str]) -> list[str]:
    if not val or not val.strip():
        return default
    return [item.strip() for item in val.split(",") if item.strip()]


@dataclass
class SangyanConfig:
    """Runtime configuration model for SANGYAN services."""

    env: str = ENV_DEVELOPMENT
    database_url: str = "sqlite:///sangyan.db"
    checkpoint_db_path: Optional[str] = None
    key_dir: Optional[str] = None

    # Security & Auth
    jwt_secret: str = INSECURE_TEST_JWT_SECRET
    jwt_public_key: Optional[str] = None
    jwt_private_key: Optional[str] = None
    jwt_algorithms: list[str] = field(default_factory=lambda: ["HS256"])
    jwt_issuer: str = "sangyan-auth"
    jwt_audience: str = "sangyan-api"
    jwt_leeway: int = 30
    require_auth: bool = False  # default False in dev for test convenience; MUST be True in production
    api_key_prefix: str = "sgy_"

    # HTTP & Transport
    allowed_origins: list[str] = field(default_factory=lambda: ["*"])
    max_request_body_bytes: int = 2 * 1024 * 1024  # 2 MB
    rate_limit_enabled: bool = True

    # Database & Migrations
    auto_migrate: bool = True

    # Backup & Disaster Recovery
    backup_dir: str = "backups"
    backup_encryption_key: Optional[str] = None
    backup_retention_count: int = 7
    backup_storage_provider: str = "local"  # local | s3
    backup_s3_bucket: Optional[str] = None
    backup_s3_endpoint_url: Optional[str] = None
    backup_s3_region: str = "ap-south-1"
    backup_s3_prefix: str = "backups"

    # Distributed Architecture & Controls (Phase 8)
    redis_url: Optional[str] = None
    redis_failure_mode: str = "fail_closed_mutations"  # fail_closed_mutations | fail_open | local_fallback
    checkpoint_backend: Optional[str] = None  # auto | postgres | sqlite

    # Distributed Tracing & Observability (Phase 8)
    tracing_enabled: bool = False
    otel_exporter_endpoint: Optional[str] = None
    trace_sample_rate: float = 1.0

    # Asynchronous Execution & Task Queue (Phase 9)
    task_queue_type: str = "redis_stream"  # redis_stream | in_memory
    task_queue_stream: str = "sangyan:tasks:stream"
    task_queue_group: str = "sangyan:task_workers"
    task_lease_duration_sec: float = 60.0
    task_max_retries: int = 3
    task_dead_letter_stream: str = "sangyan:tasks:dead_letter"
    worker_concurrency: int = 4

    # Multi-Region Disaster Recovery & Split-Brain Fencing (Phase 9)
    region_id: str = "primary-south-1"
    dr_cluster_epoch: int = 1
    dr_role: str = "PRIMARY_ACTIVE"  # PRIMARY_ACTIVE | STANDBY_READY | DEMOTED | FENCED
    dr_fencing_enabled: bool = True
    secondary_database_url: Optional[str] = None
    secondary_backup_s3_bucket: Optional[str] = None
    secondary_backup_s3_region: Optional[str] = None

    # Server execution
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.env.lower() == ENV_PRODUCTION

    def to_security_config(self) -> SecurityConfig:
        """Derive SecurityConfig for the security gateway from this runtime config."""
        return SecurityConfig(
            jwt_secret=self.jwt_secret,
            jwt_public_key=self.jwt_public_key,
            jwt_private_key=self.jwt_private_key,
            jwt_algorithms=list(self.jwt_algorithms),
            jwt_issuer=self.jwt_issuer,
            jwt_audience=self.jwt_audience,
            jwt_leeway=self.jwt_leeway,
            api_key_prefix=self.api_key_prefix,
            max_request_body_bytes=self.max_request_body_bytes,
            allowed_origins=list(self.allowed_origins),
            rate_limit_enabled=self.rate_limit_enabled,
        )

    def sanitized_dict(self) -> dict[str, Any]:
        """Return a dict of configuration with secrets safely redacted for logging."""
        return {
            "env": self.env,
            "database_url": self._sanitize_db_url(self.database_url),
            "checkpoint_db_path": self.checkpoint_db_path,
            "checkpoint_backend": self.checkpoint_backend,
            "redis_url": self._sanitize_db_url(self.redis_url) if self.redis_url else None,
            "redis_failure_mode": self.redis_failure_mode,
            "backup_storage_provider": self.backup_storage_provider,
            "backup_s3_bucket": self.backup_s3_bucket,
            "tracing_enabled": self.tracing_enabled,
            "key_dir": self.key_dir,
            "jwt_secret": "[REDACTED]" if self.jwt_secret else None,
            "jwt_public_key": "[SET]" if self.jwt_public_key else None,
            "jwt_private_key": "[REDACTED]" if self.jwt_private_key else None,
            "jwt_algorithms": self.jwt_algorithms,
            "jwt_issuer": self.jwt_issuer,
            "jwt_audience": self.jwt_audience,
            "require_auth": self.require_auth,
            "allowed_origins": self.allowed_origins,
            "max_request_body_bytes": self.max_request_body_bytes,
            "rate_limit_enabled": self.rate_limit_enabled,
            "auto_migrate": self.auto_migrate,
            "backup_dir": self.backup_dir,
            "backup_encryption_configured": bool(self.backup_encryption_key),
            "backup_retention_count": self.backup_retention_count,
            "task_queue_type": self.task_queue_type,
            "region_id": self.region_id,
            "dr_role": self.dr_role,
            "dr_cluster_epoch": self.dr_cluster_epoch,
            "dr_fencing_enabled": self.dr_fencing_enabled,
            "secondary_database_url": self._sanitize_db_url(self.secondary_database_url) if self.secondary_database_url else None,
            "host": self.host,
            "port": self.port,
            "log_level": self.log_level,
        }

    @staticmethod
    def _sanitize_db_url(url: str) -> str:
        if "@" in url:
            prefix, rest = url.split("@", 1)
            if "://" in prefix:
                scheme, auth = prefix.split("://", 1)
                user = auth.split(":", 1)[0]
                return f"{scheme}://{user}:[REDACTED]@{rest}"
        return url


def load_config(env_source: Optional[Mapping[str, str]] = None) -> SangyanConfig:
    """Load configuration from environment variables or provided mapping with defaults."""
    env = env_source if env_source is not None else os.environ

    raw_env = env.get("SANGYAN_ENV", ENV_DEVELOPMENT).strip().lower()
    is_prod = raw_env == ENV_PRODUCTION

    # Default require_auth is True for production, False for dev/test if not explicitly set
    require_auth_default = True if is_prod else False
    require_auth = _str_to_bool(env.get("SANGYAN_REQUIRE_AUTH"), default=require_auth_default)

    # In production, require explicit origins; in dev/test default to wildcard
    allowed_origins_default = [] if is_prod else ["*"]
    allowed_origins = _split_csv(env.get("SANGYAN_ALLOWED_ORIGINS"), default=allowed_origins_default)

    # Database URL
    db_url = env.get("SANGYAN_DATABASE_URL", "sqlite:///sangyan.db")

    # JWT algorithms
    jwt_algs = _split_csv(env.get("SANGYAN_JWT_ALGORITHMS"), default=["HS256"])

    # Port
    raw_port = env.get("SANGYAN_PORT", "8000")
    try:
        port = int(raw_port)
    except ValueError:
        port = 8000

    # Max body bytes
    raw_max_body = env.get("SANGYAN_MAX_REQUEST_BODY_BYTES", str(2 * 1024 * 1024))
    try:
        max_body_bytes = int(raw_max_body)
    except ValueError:
        max_body_bytes = 2 * 1024 * 1024

    # Backup retention
    raw_retention = env.get("SANGYAN_BACKUP_RETENTION_COUNT", "7")
    try:
        backup_retention = int(raw_retention)
    except ValueError:
        backup_retention = 7

    # Phase 8 Distributed & Cloud configs
    raw_sample_rate = env.get("SANGYAN_TRACE_SAMPLE_RATE", "1.0")
    try:
        trace_sample_rate = float(raw_sample_rate)
    except ValueError:
        trace_sample_rate = 1.0

    # Phase 9 Async & Multi-Region DR configs
    task_queue_type = env.get("SANGYAN_TASK_QUEUE_TYPE", "redis_stream")
    task_queue_stream = env.get("SANGYAN_TASK_QUEUE_STREAM", "sangyan:tasks:stream")
    task_queue_group = env.get("SANGYAN_TASK_QUEUE_GROUP", "sangyan:task_workers")
    raw_lease_sec = env.get("SANGYAN_TASK_LEASE_DURATION_SEC", "60.0")
    try:
        task_lease_sec = float(raw_lease_sec)
    except ValueError:
        task_lease_sec = 60.0

    raw_max_retries = env.get("SANGYAN_TASK_MAX_RETRIES", "3")
    try:
        task_max_retries = int(raw_max_retries)
    except ValueError:
        task_max_retries = 3

    task_dl_stream = env.get("SANGYAN_TASK_DEAD_LETTER_STREAM", "sangyan:tasks:dead_letter")
    raw_concurrency = env.get("SANGYAN_WORKER_CONCURRENCY", "4")
    try:
        worker_concurrency = int(raw_concurrency)
    except ValueError:
        worker_concurrency = 4

    region_id = env.get("SANGYAN_REGION_ID", "primary-south-1")
    raw_epoch = env.get("SANGYAN_DR_CLUSTER_EPOCH", "1")
    try:
        dr_cluster_epoch = int(raw_epoch)
    except ValueError:
        dr_cluster_epoch = 1

    dr_role = env.get("SANGYAN_DR_ROLE", "PRIMARY_ACTIVE")
    dr_fencing_enabled = _str_to_bool(env.get("SANGYAN_DR_FENCING_ENABLED"), default=True)

    cfg = SangyanConfig(
        env=raw_env,
        database_url=db_url,
        checkpoint_db_path=env.get("SANGYAN_CHECKPOINT_DB_PATH"),
        key_dir=env.get("SANGYAN_KEY_DIR"),
        jwt_secret=env.get("SANGYAN_JWT_SECRET", INSECURE_TEST_JWT_SECRET),
        jwt_public_key=env.get("SANGYAN_JWT_PUBLIC_KEY"),
        jwt_private_key=env.get("SANGYAN_JWT_PRIVATE_KEY"),
        jwt_algorithms=jwt_algs,
        jwt_issuer=env.get("SANGYAN_JWT_ISSUER", "sangyan-auth"),
        jwt_audience=env.get("SANGYAN_JWT_AUDIENCE", "sangyan-api"),
        jwt_leeway=int(env.get("SANGYAN_JWT_LEEWAY", "30")),
        require_auth=require_auth,
        api_key_prefix=env.get("SANGYAN_API_KEY_PREFIX", "sgy_"),
        allowed_origins=allowed_origins,
        max_request_body_bytes=max_body_bytes,
        rate_limit_enabled=_str_to_bool(env.get("SANGYAN_RATE_LIMIT_ENABLED"), default=True),
        auto_migrate=_str_to_bool(env.get("SANGYAN_AUTO_MIGRATE"), default=True),
        backup_dir=env.get("SANGYAN_BACKUP_DIR", "backups"),
        backup_encryption_key=env.get("SANGYAN_BACKUP_ENCRYPTION_KEY"),
        backup_retention_count=backup_retention,
        backup_storage_provider=env.get("SANGYAN_BACKUP_STORAGE_PROVIDER", "local"),
        backup_s3_bucket=env.get("SANGYAN_BACKUP_S3_BUCKET"),
        backup_s3_endpoint_url=env.get("SANGYAN_BACKUP_S3_ENDPOINT_URL"),
        backup_s3_region=env.get("SANGYAN_BACKUP_S3_REGION", "ap-south-1"),
        backup_s3_prefix=env.get("SANGYAN_BACKUP_S3_PREFIX", "backups"),
        redis_url=env.get("SANGYAN_REDIS_URL"),
        redis_failure_mode=env.get("SANGYAN_REDIS_FAILURE_MODE", "fail_closed_mutations"),
        checkpoint_backend=env.get("SANGYAN_CHECKPOINT_BACKEND"),
        tracing_enabled=_str_to_bool(env.get("SANGYAN_TRACING_ENABLED"), default=False),
        otel_exporter_endpoint=env.get("SANGYAN_OTEL_EXPORTER_ENDPOINT"),
        trace_sample_rate=trace_sample_rate,
        task_queue_type=task_queue_type,
        task_queue_stream=task_queue_stream,
        task_queue_group=task_queue_group,
        task_lease_duration_sec=task_lease_sec,
        task_max_retries=task_max_retries,
        task_dead_letter_stream=task_dl_stream,
        worker_concurrency=worker_concurrency,
        region_id=region_id,
        dr_cluster_epoch=dr_cluster_epoch,
        dr_role=dr_role,
        dr_fencing_enabled=dr_fencing_enabled,
        secondary_database_url=env.get("SANGYAN_SECONDARY_DATABASE_URL"),
        secondary_backup_s3_bucket=env.get("SANGYAN_SECONDARY_BACKUP_S3_BUCKET"),
        secondary_backup_s3_region=env.get("SANGYAN_SECONDARY_BACKUP_S3_REGION"),
        host=env.get("SANGYAN_HOST", "0.0.0.0"),
        port=port,
        log_level=env.get("SANGYAN_LOG_LEVEL", "INFO").upper(),
    )

    return cfg


def validate_production_config(config: SangyanConfig) -> None:
    """Validate that configuration satisfies strict production security invariants.

    Raises ConfigurationError if any insecure setting is detected when running in production.
    """
    if not config.is_production:
        return

    errors: list[str] = []

    # 1. Environment name
    if config.env not in VALID_ENVIRONMENTS:
        errors.append(f"Invalid environment '{config.env}'; must be one of {VALID_ENVIRONMENTS}")

    # 2. Database validation
    if not config.database_url or config.database_url.strip() in (":memory:", "sqlite:///:memory:"):
        errors.append("Production requires a durable database URL; in-memory SQLite ':memory:' is strictly forbidden.")

    # 3. Authentication requirement
    if not config.require_auth:
        errors.append("Production requires SANGYAN_REQUIRE_AUTH=true; unauthenticated access is forbidden.")

    # 4. JWT Secret & Key entropy validation
    has_asymmetric = bool(config.jwt_public_key)
    if not has_asymmetric:
        if not config.jwt_secret or config.jwt_secret == INSECURE_TEST_JWT_SECRET:
            errors.append(
                "Production cannot use the default test JWT secret. Set a secure SANGYAN_JWT_SECRET (min 32 bytes)."
            )
        elif len(config.jwt_secret) < 32:
            errors.append(
                f"SANGYAN_JWT_SECRET is too short ({len(config.jwt_secret)} bytes); minimum 32 bytes required in production."
            )
        elif config.jwt_secret.lower() in ("secret", "password", "changeme", "jwtsecret", "admin"):
            errors.append("SANGYAN_JWT_SECRET is trivially guessable; high-entropy secret required.")

    # 5. Permitted JWT algorithms
    from sangyan.security.jwt import ALLOWED_JWT_ALGORITHMS

    for alg in config.jwt_algorithms:
        if alg not in ALLOWED_JWT_ALGORITHMS:
            errors.append(f"Insecure JWT algorithm '{alg}' configured; permitted: {ALLOWED_JWT_ALGORITHMS}")

    # 6. CORS allowed origins
    if not config.allowed_origins:
        errors.append("Production requires explicit SANGYAN_ALLOWED_ORIGINS; empty origins forbidden.")
    elif "*" in config.allowed_origins:
        errors.append(
            "Production forbids wildcard CORS origin ('*') when authentication and credentials are enabled. "
            "Specify trusted origin domains."
        )

    # 7. Checkpoint durability
    if config.checkpoint_db_path and config.checkpoint_db_path.strip() == ":memory:":
        errors.append("Production forbids in-memory LangGraph checkpoint database ':memory:'.")

    if errors:
        msg = "Production Configuration Validation Failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ConfigurationError(msg)
