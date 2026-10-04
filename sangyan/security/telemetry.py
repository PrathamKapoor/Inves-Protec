"""Low-cardinality telemetry, Prometheus metrics exporter, and sensitive-data redaction."""
from __future__ import annotations

import logging
import re
import time
from typing import Callable, Optional

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Sensitive Data Redaction
# ---------------------------------------------------------------------------

PATTERNS_TO_REDACT: list[tuple[re.Pattern, str]] = [
    # JWT Bearer tokens
    (
        re.compile(r"Bearer\s+([A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_.+/=]*)", re.IGNORECASE),
        "Bearer [REDACTED_JWT]",
    ),
    # SANGYAN API keys: sgy_<8hex>_<32hex>
    (
        re.compile(r"sgy_[0-9a-fA-F]{8}_[0-9a-fA-F]{32}"),
        "sgy_[REDACTED_API_KEY]",
    ),
    # Private cryptographic keys (PEM format)
    (
        re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----.*?-----END [A-Z ]+ PRIVATE KEY-----", re.DOTALL),
        "[REDACTED_PRIVATE_KEY]",
    ),
    # Passwords, secrets, and OTPs in key-value format
    (
        re.compile(r"""(?i)(["']?(?:password|secret|api[_-]?key|otp|token|private[_-]?key)["']?\s*[:=]\s*["']?)([^"'\s,}{]+)(["']?)"""),
        r"\g<1>[REDACTED]\g<3>",
    ),
]


def redact_sensitive_text(text: str) -> str:
    """Sanitize secrets, JWTs, API keys, and OTPs from log lines or trace payloads."""
    if not isinstance(text, str):
        return text
    sanitized = text
    for pattern, replacement in PATTERNS_TO_REDACT:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class RedactingLogFilter(logging.Filter):
    """Logging filter that scrubs sensitive credentials from log records.

    Redaction runs on the fully formatted message so patterns that span the
    format string and its arguments (e.g. ``"Bearer %s"`` with a token arg)
    are caught; argument-wise redaction alone misses those because a bare
    token argument does not match the ``Bearer`` prefix pattern.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        record.msg = redact_sensitive_text(message)
        record.args = None
        return True


# ---------------------------------------------------------------------------
# Route Normalization (Prevent Cardinality Explosion)
# ---------------------------------------------------------------------------

UUID_OR_ID_REGEX = re.compile(
    r"\b(?:inv|clm|evid|find|fnd|key|usr|org|mem|sess|run|src|rec)_[0-9a-zA-Z\-_]+\b"
    r"|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"|\b\d+\b"
)


def normalize_route(path: str) -> str:
    """Normalize dynamic IDs to bounded route templates to enforce low label cardinality."""
    # Special-case well-known subroutes
    segments = path.strip("/").split("/")
    normalized: list[str] = []
    for i, seg in enumerate(segments):
        if UUID_OR_ID_REGEX.fullmatch(seg):
            # Inspect previous segment for context
            prev = segments[i - 1] if i > 0 else "item"
            if prev.endswith("s"):
                prev = prev[:-1]
            normalized.append(f"{{{prev}_id}}")
        else:
            normalized.append(seg)
    return "/" + "/".join(normalized) if normalized else "/"


# ---------------------------------------------------------------------------
# Prometheus Metrics Registry
# ---------------------------------------------------------------------------


class MetricsRegistry:
    """Low-cardinality Prometheus metrics collector for SANGYAN."""

    _instance: Optional[MetricsRegistry] = None

    def __init__(self, registry: Optional[CollectorRegistry] = None) -> None:
        self.registry = registry or CollectorRegistry(auto_describe=True)

        self.http_requests_total = Counter(
            "sangyan_http_requests_total",
            "Total HTTP requests partitioned by method, normalized route, and status code",
            ["method", "route", "status_code"],
            registry=self.registry,
        )

        self.http_request_duration_seconds = Histogram(
            "sangyan_http_request_duration_seconds",
            "HTTP request latency histogram in seconds",
            ["method", "route"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self.registry,
        )

        self.security_events_total = Counter(
            "sangyan_security_events_total",
            "Security events counter (auth_failure, rate_limit, tenant_mismatch, key_revocation)",
            ["event_type", "status"],
            registry=self.registry,
        )

        self.workflow_runs_total = Counter(
            "sangyan_workflow_runs_total",
            "Workflow execution transitions counter by terminal or paused status",
            ["status"],
            registry=self.registry,
        )

        self.rate_limit_exceeded_total = Counter(
            "sangyan_rate_limit_exceeded_total",
            "Rate limit violations counter by endpoint category",
            ["endpoint_class"],
            registry=self.registry,
        )

        self.pqc_trust_signatures_total = Counter(
            "sangyan_pqc_trust_signatures_total",
            "ML-DSA-65 post-quantum trust signature operations counter",
            ["status"],
            registry=self.registry,
        )

        # ------------------------------------------------------------------
        # Phase 10: Queue / Worker / DR / Database operational metrics
        # ------------------------------------------------------------------

        self.tasks_total = Counter(
            "sangyan_tasks_total",
            "Async task lifecycle transitions by task type and resulting status",
            ["task_type", "status"],
            registry=self.registry,
        )

        self.task_retries_total = Counter(
            "sangyan_task_retries_total",
            "Async task retry scheduling counter by task type",
            ["task_type"],
            registry=self.registry,
        )

        self.task_dead_letters_total = Counter(
            "sangyan_task_dead_letters_total",
            "Async tasks quarantined to dead-letter by task type",
            ["task_type"],
            registry=self.registry,
        )

        self.task_lease_expirations_total = Counter(
            "sangyan_task_lease_expirations_total",
            "Worker lease expirations recovered by lease reclamation",
            registry=self.registry,
        )

        self.task_execution_seconds = Histogram(
            "sangyan_task_execution_seconds",
            "Async task execution duration from lease acquisition to terminal transition",
            buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
            registry=self.registry,
        )

        self.task_queue_depth = Gauge(
            "sangyan_task_queue_depth",
            "Relational task ledger depth by lifecycle status (queue saturation telemetry)",
            ["status"],
            registry=self.registry,
        )

        self.task_oldest_queued_seconds = Gauge(
            "sangyan_task_oldest_queued_seconds",
            "Age of the oldest deliverable task (QUEUED or RETRY_WAIT) in seconds",
            registry=self.registry,
        )

        self.task_stream_pending = Gauge(
            "sangyan_task_stream_pending",
            "Broker pending-entries count for the task stream consumer group",
            registry=self.registry,
        )

        self.worker_inflight_tasks = Gauge(
            "sangyan_worker_inflight_tasks",
            "Tasks currently executing in this worker process (bounded utilization gauge)",
            registry=self.registry,
        )

        self.dr_promotions_total = Counter(
            "sangyan_dr_promotions_total",
            "Disaster recovery region promotion attempts by outcome",
            ["status"],
            registry=self.registry,
        )

        self.dr_fencing_rejections_total = Counter(
            "sangyan_dr_fencing_rejections_total",
            "Writes rejected by epoch/fencing authority checks (split-brain defense telemetry)",
            registry=self.registry,
        )

        self.dr_cluster_epoch = Gauge(
            "sangyan_dr_cluster_epoch",
            "Current authoritative cluster epoch observed by this region",
            registry=self.registry,
        )

        self.db_pool_size = Gauge(
            "sangyan_db_pool_size",
            "Database connection pool configured maximum size",
            registry=self.registry,
        )

        self.db_pool_available = Gauge(
            "sangyan_db_pool_available",
            "Database connection pool currently idle connections (pool exhaustion telemetry)",
            registry=self.registry,
        )

    @classmethod
    def get_default(cls) -> MetricsRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def export_metrics(self) -> Response:
        """Render Prometheus metrics payload in text format."""
        data = generate_latest(self.registry)
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------------------
# Telemetry Middleware
# ---------------------------------------------------------------------------


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """Records HTTP request counts and durations with strictly bounded label cardinality."""

    def __init__(self, app, metrics_registry: Optional[MetricsRegistry] = None) -> None:
        super().__init__(app)
        self.metrics = metrics_registry or MetricsRegistry.get_default()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Avoid recording metrics for the /metrics scraper itself
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        route = normalize_route(request.url.path)
        start_time = time.time()

        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = max(0.0, time.time() - start_time)
            try:
                self.metrics.http_requests_total.labels(
                    method=method,
                    route=route,
                    status_code=str(status_code),
                ).inc()
                self.metrics.http_request_duration_seconds.labels(
                    method=method,
                    route=route,
                ).observe(duration)
            except Exception:
                pass  # Telemetry fails open
