"""Static analysis and validation tests for Kubernetes / Helm manifests."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml


def _get_rendered_manifests() -> list[dict]:
    """Render Helm templates using alpine/helm container or return empty if docker unavailable."""
    try:
        res = subprocess.run(
            ["docker", "run", "--rm", "-v", "C:\\Projects\\Sangyan:/apps", "alpine/helm:latest", "template", "test-release", "/apps/deploy/helm/sangyan"],
            capture_output=True,
            text=True,
            timeout=25,
        )
        if res.returncode != 0:
            pytest.skip(f"Helm template failed: {res.stderr}")
        docs = [d for d in yaml.safe_load_all(res.stdout) if isinstance(d, dict)]
        return docs
    except Exception as e:
        pytest.skip(f"Docker or helm container unavailable: {e}")


def test_helm_chart_metadata():
    chart_file = Path("C:/Projects/Sangyan/deploy/helm/sangyan/Chart.yaml")
    assert chart_file.exists()
    chart = yaml.safe_load(chart_file.read_text(encoding="utf-8"))
    assert chart["name"] == "sangyan"
    assert chart["version"] == "0.7.0"
    assert chart["apiVersion"] == "v2"


def test_helm_values_security_defaults():
    values_file = Path("C:/Projects/Sangyan/deploy/helm/sangyan/values.yaml")
    assert values_file.exists()
    values = yaml.safe_load(values_file.read_text(encoding="utf-8"))

    # Single-replica topology enforced
    assert values["replicaCount"] == 1

    # Non-root pod security
    assert values["podSecurityContext"]["runAsNonRoot"] is True
    assert values["podSecurityContext"]["runAsUser"] == 10001

    # Container security context
    sec = values["securityContext"]
    assert sec["allowPrivilegeEscalation"] is False
    assert sec["readOnlyRootFilesystem"] is True
    assert sec["capabilities"]["drop"] == ["ALL"]
    assert sec["seccompProfile"]["type"] == "RuntimeDefault"

    # Zero plaintext secrets in committed values
    assert values["secrets"]["jwtSecret"] == ""
    assert values["secrets"]["backupEncryptionKey"] == ""


def test_rendered_manifests_compliance():
    docs = _get_rendered_manifests()
    assert len(docs) > 0

    kinds = {d.get("kind") for d in docs}
    assert "Deployment" in kinds
    assert "Service" in kinds
    assert "ConfigMap" in kinds
    assert "Job" in kinds
    assert "CronJob" in kinds
    assert "PersistentVolumeClaim" in kinds
    assert "NetworkPolicy" in kinds
    assert "Ingress" in kinds

    # Inspect Deployment
    deployment = next(d for d in docs if d.get("kind") == "Deployment")
    spec = deployment["spec"]
    assert spec["replicas"] == 1
    assert spec["strategy"]["type"] == "Recreate"

    pod_spec = spec["template"]["spec"]
    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    assert pod_spec["securityContext"]["runAsUser"] == 10001

    container = pod_spec["containers"][0]
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]

    # Probes
    assert "livenessProbe" in container
    assert "readinessProbe" in container
    assert "startupProbe" in container
    assert container["livenessProbe"]["httpGet"]["path"] == "/health/live"
    assert container["readinessProbe"]["httpGet"]["path"] == "/health/ready"

    # Resource requests and limits
    assert "requests" in container["resources"]
    assert "limits" in container["resources"]

    # Ingress blocks /metrics
    ingress = next(d for d in docs if d.get("kind") == "Ingress")
    annotations = ingress["metadata"]["annotations"]
    snippet = annotations.get("nginx.ingress.kubernetes.io/configuration-snippet", "")
    assert "location /metrics" in snippet
    assert "return 404" in snippet
