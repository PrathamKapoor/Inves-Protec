"""Static and dynamic security tests for Docker container packaging and hardening."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest


def test_dockerignore_rules():
    dockerignore_path = Path("C:/Projects/Sangyan/.dockerignore")
    assert dockerignore_path.exists(), ".dockerignore must exist"
    content = dockerignore_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

    # Mandatory exclusions
    assert ".git" in lines
    assert "tests/" in lines
    assert "paper/" in lines
    assert "research/" in lines
    assert ".env" in lines
    assert "*.db" in lines
    assert "*.sqlite" in lines


def test_dockerfile_security_standards():
    dockerfile_path = Path("C:/Projects/Sangyan/Dockerfile")
    assert dockerfile_path.exists(), "Dockerfile must exist"
    content = dockerfile_path.read_text(encoding="utf-8")

    # 1. Multi-stage build
    assert "FROM python:3.13-slim AS builder" in content
    assert "FROM python:3.13-slim AS runtime" in content

    # 2. Non-root user with UID 10001
    assert "groupadd -g 10001" in content
    assert "useradd -u 10001" in content
    assert "USER 10001:10001" in content

    # 3. Read-only application source code
    assert "chmod -R 0555 /app/sangyan" in content

    # 4. Explicit writable directories with strict permissions
    assert "mkdir -p /app/data /app/checkpoints /app/keys /app/backups /tmp" in content
    assert "chmod 0750 /app/data /app/checkpoints /app/backups" in content
    assert "chmod 0700 /app/keys" in content

    # 5. Exec-form entrypoint
    assert 'ENTRYPOINT ["python", "-m", "sangyan.cli"]' in content

    # 6. Healthcheck probe
    assert "HEALTHCHECK" in content
    assert "/health/live" in content


def test_container_runtime_non_root_and_permissions():
    """Verify non-root execution and filesystem boundaries using Docker if available."""
    try:
        # Check if docker is responsive
        res = subprocess.run(["docker", "image", "inspect", "sangyan:0.7.0"], capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            pytest.skip("sangyan:0.7.0 image not found locally")
    except Exception:
        pytest.skip("Docker daemon not available")

    # 1. Verify effective UID is 10001
    id_res = subprocess.run(["docker", "run", "--rm", "--entrypoint", "id", "sangyan:0.7.0"], capture_output=True, text=True, timeout=15)
    assert id_res.returncode == 0
    assert "uid=10001(sangyan)" in id_res.stdout
    assert "gid=10001(sangyan)" in id_res.stdout

    # 2. Verify write to /app root is forbidden (read-only root)
    write_app = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "sh", "sangyan:0.7.0", "-c", "touch /app/forbidden.txt"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert write_app.returncode != 0
    assert "permission denied" in write_app.stderr.lower()

    # 3. Verify write to /app/data is allowed
    write_data = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "sh", "sangyan:0.7.0", "-c", "touch /app/data/ok.txt && rm /app/data/ok.txt"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert write_data.returncode == 0
