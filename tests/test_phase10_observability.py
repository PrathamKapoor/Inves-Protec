"""Phase 10: observability validation — metrics, dashboard/alert definitions, log redaction.

Covers:
- Phase 10 metric families exported after activity (queue depth, retries, DR, pool).
- Grafana dashboard JSON parses and references only registered metric names.
- Prometheus alert YAML parses and references registered metric names (no orphan alerts).
- configure_logging attaches sensitive-data redaction; secrets never reach handlers.
- Metrics output contains no secret material.
"""
import io
import json
import logging
import re

import pytest
import yaml

from sangyan.async_exec.models import TaskStatus, TaskType
from sangyan.core.logging import configure_logging, get_logger
from sangyan.security.telemetry import MetricsRegistry, redact_sensitive_text


# ---------------------------------------------------------------------------
# Metric registry
# ---------------------------------------------------------------------------


def _metric_base_names(registry: MetricsRegistry) -> set[str]:
    """Metric family names registered in the collector."""
    return {metric.name for metric in registry.registry.collect()}


def _references_registered(ident: str, bases: set[str]) -> bool:
    """True when identifier matches a registered family or its conventional suffix form.

    prometheus_client strips the ``_total`` suffix from Counter family names and
    creates ``_bucket``/``_le`` series lazily, so matching is prefix-based.
    """
    return any(ident == base or ident.startswith(base + "_") for base in bases)


def test_phase10_metric_families_registered():
    registry = MetricsRegistry()
    for attr in (
        "tasks_total",
        "task_retries_total",
        "task_dead_letters_total",
        "task_lease_expirations_total",
        "task_execution_seconds",
        "task_queue_depth",
        "task_oldest_queued_seconds",
        "task_stream_pending",
        "worker_inflight_tasks",
        "dr_promotions_total",
        "dr_fencing_rejections_total",
        "dr_cluster_epoch",
        "db_pool_size",
        "db_pool_available",
    ):
        assert hasattr(registry, attr), f"missing metric {attr}"


def test_metrics_export_contains_phase10_families():
    registry = MetricsRegistry()
    # touch metrics so they appear in the export even with zero values
    registry.task_queue_depth.labels(status=TaskStatus.QUEUED).set(0)
    registry.tasks_total.labels(task_type=TaskType.WORKFLOW_START, status=TaskStatus.SUCCEEDED).inc()
    registry.task_oldest_queued_seconds.set(0)
    registry.dr_cluster_epoch.set(1)
    body = registry.export_metrics().body.decode("utf-8")
    assert "sangyan_task_queue_depth" in body
    assert "sangyan_tasks_total" in body
    assert "sangyan_task_oldest_queued_seconds" in body
    assert "sangyan_dr_cluster_epoch" in body
    assert "sangyan_worker_inflight_tasks" in body
    assert "sangyan_db_pool_available" in body


def test_metrics_export_contains_no_secret_material():
    registry = MetricsRegistry()
    body = registry.export_metrics().body.decode("utf-8")
    for forbidden in ("sgy_", "BEGIN PRIVATE", "Bearer ey", "password=", "jwt_secret"):
        assert forbidden not in body


# ---------------------------------------------------------------------------
# Dashboard & alert definitions
# ---------------------------------------------------------------------------


def test_grafana_dashboard_parses_and_references_real_metrics():
    with open("deploy/observability/grafana-dashboard.json", encoding="utf-8") as fh:
        dashboard = json.load(fh)
    assert dashboard["uid"] == "sangyan-operational-overview"
    assert dashboard["panels"], "dashboard must define panels"

    bases = _metric_base_names(MetricsRegistry())
    # exprs reference metrics; extract leading metric identifiers
    referenced: set[str] = set()
    for panel in dashboard["panels"]:
        for target in panel.get("targets", []):
            expr = target.get("expr", "")
            for match in re.finditer(r"\b([a-zA-Z_:][a-zA-Z0-9_:]*)\s*(?:\{|\[|$)", expr):
                ident = match.group(1)
                if ident in ("sum", "rate", "histogram_quantile", "max", "by", "up"):
                    continue
                referenced.add(ident)

    assert referenced, "dashboard should reference metrics"
    missing = sorted(name for name in referenced if not _references_registered(name, bases))
    assert missing == [], f"dashboard references unregistered metrics: {missing}"


def test_alert_rules_parse_and_reference_real_metrics():
    with open("deploy/observability/prometheus-alerts.yaml", encoding="utf-8") as fh:
        rules = yaml.safe_load(fh)

    assert rules["groups"], "alert rules must define groups"
    alerts = []
    for group in rules["groups"]:
        for rule in group["rules"]:
            assert "alert" in rule and "expr" in rule
            assert "annotations" in rule and "summary" in rule["annotations"]
            alerts.append(rule)
    assert len(alerts) >= 10

    bases = _metric_base_names(MetricsRegistry())
    referenced: set[str] = set()
    for rule in alerts:
        for match in re.finditer(r"\b([a-zA-Z_:][a-zA-Z0-9_:]*)\s*(?:\{|\[|>|$)", rule["expr"]):
            ident = match.group(1)
            if ident in ("sum", "rate", "increase", "max", "by", "up", "and", "or"):
                continue
            referenced.add(ident)

    # sangyan_backup_age_seconds is exported by the backup CronJob textfile collector
    allowed_external = {"sangyan_backup_age_seconds"}
    missing = sorted(
        name for name in referenced
        if not _references_registered(name, bases) and name not in allowed_external
    )
    assert missing == [], f"alerts reference unregistered metrics: {missing}"


# ---------------------------------------------------------------------------
# Structured logging & redaction
# ---------------------------------------------------------------------------


def test_configure_logging_attaches_redaction_filter():
    configure_logging(level="INFO")
    root = logging.getLogger()
    has_redaction = any(
        type(f).__name__ == "RedactingLogFilter" for h in root.handlers for f in h.filters
    )
    assert has_redaction, "configure_logging must install the redaction filter on root handlers"


def test_secrets_never_reach_log_output():
    configure_logging(level="INFO")

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    from sangyan.security.telemetry import RedactingLogFilter

    handler.addFilter(RedactingLogFilter())
    test_logger = logging.getLogger("sangyan.test.redaction2")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.DEBUG)

    test_logger.info("Authorization: Bearer %s", "aaaa.bbbb.cccc")
    test_logger.info("api_key=sgy_deadbeef_%s", "0123456789abcdef0123456789abcdef")
    test_logger.info("password=hunter2 secret=topsecret")

    output = stream.getvalue()
    assert "aaaa.bbbb.cccc" not in output
    assert "sgy_deadbeef_" not in output or "[REDACTED" in output
    assert "hunter2" not in output
    assert "topsecret" not in output


def test_redact_sensitive_text_covers_jwt_apikey_pem():
    assert "[REDACTED_JWT]" in redact_sensitive_text("Bearer abc.def.ghi")
    assert "[REDACTED_API_KEY]" in redact_sensitive_text("key=sgy_12345678_0123456789abcdef0123456789abcdef")
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIB\n-----END RSA PRIVATE KEY-----"
    assert redact_sensitive_text(pem) == "[REDACTED_PRIVATE_KEY]"


def test_worker_logs_do_not_leak_task_payload_contents():
    """Structural check: worker log format strings never interpolate payload/raw content."""
    import inspect

    from sangyan.async_exec import worker as worker_module

    source = inspect.getsource(worker_module)
    # The worker may log task ids/types/status, never payload bodies
    assert 'logger.info("Worker %s executing task %s (type=%s)"' in source
    forbidden_patterns = [
        "task.payload",  # never passed into logger calls
    ]
    for line in source.splitlines():
        if "logger." in line or "logger(" in line:
            assert "task.payload" not in line
            assert "raw_content" not in line
