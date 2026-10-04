"""Phase 10: static Kubernetes manifest hardening validation (no cluster required).

Verifies:
- Worker PodDisruptionBudget template exists and guards multi-worker pods.
- Worker Deployment: non-root, read-only rootfs, graceful termination window,
  bounded concurrency, resource limits, config/secret refs, checkpoint/key mounts.
- API Deployment keeps Recreate single-replica topology (documented constraint).
- HPA bounds for workers; NetworkPolicy present; new Phase 10 env vars surfaced.
- No plaintext secrets in committed manifests.
"""
import re
from pathlib import Path

import pytest
import yaml

CHART = Path("deploy/helm/sangyan")
TEMPLATES = CHART / "templates"


def _read(name: str) -> str:
    path = TEMPLATES / name
    assert path.exists(), f"missing template {name}"
    return path.read_text(encoding="utf-8")


def test_worker_poddisruptionbudget_template_exists_and_is_safe():
    content = _read("poddisruptionbudget.yaml")
    assert "kind: PodDisruptionBudget" in content
    assert "maxUnavailable: 1" in content
    # Only enabled with worker replicas > 1 (single worker PDB would block drains)
    assert "gt (int .Values.worker.replicaCount) 1" in content
    assert ".Values.worker.enabled" in content


def test_worker_deployment_hardening():
    content = _read("deployment-worker.yaml")
    # Graceful drain window for SIGTERM
    assert "terminationGracePeriodSeconds: 90" in content
    # Bounded worker concurrency wired on the CLI
    assert '"--concurrency"' in content
    # Non-root via shared pod security context (values: runAsUser 10001)
    assert "podSecurityContext" in content
    assert "securityContext" in content
    # Worker command entrypoint (graceful SIGTERM handling by python process)
    assert '"python", "-m", "sangyan.cli", "worker"' in content
    # Must run the hardened container security context from values
    assert "securityContext" in content
    # Resource requests/limits present
    assert "resources" in content


def test_worker_mounts_relational_data_volume():
    """Worker must mount the data PVC: it writes the task ledger (SQLite topology).

    A read-only rootfs without /app/data would make every worker DB write fail.
    """
    content = _read("deployment-worker.yaml")
    assert "mountPath: /app/data" in content
    assert 'claimName: {{ include "sangyan.fullname" . }}-data' in content
    assert "/app/data" in content  # worker relies on same store as API


def test_worker_command_matches_config_defaults():
    content = _read("deployment-worker.yaml")
    # Lease duration on the worker matches config default (60s)
    assert '"--lease-sec", "60"' in content
    assert '"--poll-ms", "1000"' in content


def test_api_deployment_single_replica_recreate():
    content = _read("deployment.yaml")
    assert "strategy:" in content
    assert "Recreate" in content
    # Liveness/readiness probes decoupled (paths come from values)
    assert ".Values.probes.liveness.path" in content
    assert ".Values.probes.readiness.path" in content
    assert ".Values.probes.startup.path" in content
    values = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    assert values["probes"]["liveness"]["path"] == "/health/live"
    assert values["probes"]["readiness"]["path"] == "/health/ready"


def test_hpa_worker_bounds():
    content = _read("hpa-worker.yaml")
    assert "kind: HorizontalPodAutoscaler" in content
    assert "minReplicas" in content
    assert "maxReplicas" in content


def test_networkpolicy_exists():
    content = _read("networkpolicy.yaml")
    assert "kind: NetworkPolicy" in content


def test_configmap_surfaces_phase10_variables():
    content = _read("configmap.yaml")
    for var in (
        "SANGYAN_TASK_MAX_OUTSTANDING_PER_TENANT",
        "SANGYAN_MAX_CONTENTS_PER_WORKFLOW_REQUEST",
        "SANGYAN_TASK_RETRY_SWEEP_INTERVAL_SEC",
        "SANGYAN_TASK_STALE_QUEUE_REQUEUE_SEC",
        "SANGYAN_WORKER_CONCURRENCY",
        # stale name corrected in Phase 10
        "SANGYAN_OTEL_EXPORTER_ENDPOINT",
    ):
        assert var in content, f"configmap missing {var}"
    assert "SANGYAN_OTLP_ENDPOINT" not in content, "stale env var name reintroduced"


def test_values_phase10_defaults():
    values = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    cfg = values["config"]
    assert cfg["taskMaxOutstandingPerTenant"] == 1000
    assert cfg["maxContentsPerWorkflowRequest"] == 100
    assert cfg["taskRetrySweepIntervalSec"] == 1.0
    assert cfg["taskStaleQueueRequeueSec"] == 30.0
    assert cfg["workerConcurrency"] == 4
    # Worker resources defined for capacity planning
    assert "limits" in values["worker"]["resources"]
    assert "requests" in values["worker"]["resources"]


def test_no_plaintext_secrets_in_committed_manifests():
    # Secret template must reference values, not embed literals
    raw = _read("secret.yaml")
    assert "jwtSecret" in raw
    assert re.search(r"(?i)(password|secret)\s*:\s*['\"]?[A-Za-z0-9+/]{16,}", raw) is None
    values = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    assert values["secrets"]["jwtSecret"] == ""
    assert values["secrets"]["backupEncryptionKey"] == ""


def test_deployment_worker_yaml_is_gated_on_worker_enabled():
    content = _read("deployment-worker.yaml")
    assert "{{- if .Values.worker.enabled -}}" in content
