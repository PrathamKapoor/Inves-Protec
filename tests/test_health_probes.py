"""Unit and integration tests for operational health probes (live, ready, startup)."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from sangyan.api.app import create_app
from sangyan.config import SangyanConfig
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.trust.service import TrustService
from sangyan.verification.engine import ClaimVerificationEngine


@pytest.fixture
def api_client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "health_test.db"
        engine = SQLiteDatabaseEngine(db_path)
        MigrationRunner(engine).migrate()

        trust = TrustService(engine)
        verif_engine = ClaimVerificationEngine()

        cfg = SangyanConfig(
            database_url=f"sqlite:///{db_path}",
            require_auth=False,
        )

        app = create_app(
            engine=engine,
            trust_service=trust,
            verification_engine=verif_engine,
            config=cfg,
        )
        client = TestClient(app)
        yield client, engine
        engine.close()


def test_liveness_probe(api_client):
    client, _ = api_client
    res = client.get("/health/live")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "live"
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0


def test_readiness_probe_healthy(api_client):
    client, _ = api_client
    res = client.get("/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert data["migrations"] == "current"


def test_readiness_probe_degraded_when_database_fails(api_client):
    client, engine = api_client
    # Simulate database failure by closing engine and pointing to a broken mock
    engine.close()
    broken_engine = MagicMock()
    broken_engine.connect.side_effect = RuntimeError("Database connection refused")
    broken_engine.query_one.side_effect = RuntimeError("Database connection refused")

    cfg = SangyanConfig(auto_migrate=False, require_auth=False)
    app = create_app(engine=broken_engine, config=cfg)
    broken_client = TestClient(app)

    res = broken_client.get("/health/ready")
    assert res.status_code == 503
    data = res.json()
    assert data["status"] == "not_ready"
    assert data["reason"] == "database_unavailable"


def test_health_summary_backwards_compatible(api_client):
    client, _ = api_client
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "sangyan-verification-engine"
    assert data["version"] == "0.7.0"
    assert data["sources_registered"] >= 7
    assert data["ready"] is True
    assert data["live"] is True


def test_health_endpoints_zero_information_disclosure(api_client):
    client, _ = api_client
    for path in ("/health", "/health/live", "/health/ready"):
        res = client.get(path)
        content = res.text.lower()
        # Verify no sensitive keywords or internal paths are leaked
        assert "password" not in content
        assert "secret" not in content
        assert "private_key" not in content
        assert "token" not in content
        assert "sqlite:///" not in content
        assert "traceback" not in content
