"""End-to-end verification of Phase 8 distributed production architecture scenarios."""
from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from sangyan.api.app import create_app
from sangyan.config import SangyanConfig
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.security.redis_limiter import RedisRateLimiter
from tests.test_redis_rate_limiting import MockRedisClient


@pytest.fixture
def distributed_env():
    import gc

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "cluster.db"
        engine = SQLiteDatabaseEngine(db_path)
        MigrationRunner(engine).migrate()

        shared_redis = MockRedisClient()

        # Custom small rate limit policies for quick exhaustion testing
        test_policies = {
            "auth": (3, 1),
            "investigation": (4, 1),
            "workflow_mutate": (3, 1),
            "read": (10, 1),
            "default": (5, 1),
        }

        # Pod A Rate Limiter
        limiter_a = RedisRateLimiter(
            redis_client=shared_redis,
            policies=test_policies,
            auth_failure_threshold=3,
        )
        # Pod B Rate Limiter
        limiter_b = RedisRateLimiter(
            redis_client=shared_redis,
            policies=test_policies,
            auth_failure_threshold=3,
        )

        now = time.time()
        engine.execute(
            "INSERT INTO sangyan_organizations (id, name, status, created_at) VALUES (?, ?, ?, ?)",
            ("org_test", "Test Org", "active", now),
        )
        engine.execute(
            "INSERT INTO sangyan_users (id, email, name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("user1", "user1@sangyan.local", "User One", "active", now),
        )
        engine.execute(
            "INSERT INTO sangyan_memberships (id, organization_id, user_id, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("mem_1", "org_test", "user1", "sangyan_analyst", "active", now),
        )

        key_dir = str(Path(tmpdir) / "keys")
        cfg_a = SangyanConfig(
            database_url=f"sqlite:///{db_path}",
            key_dir=key_dir,
            require_auth=False,
            auto_migrate=False,
        )
        cfg_b = SangyanConfig(
            database_url=f"sqlite:///{db_path}",
            key_dir=key_dir,
            require_auth=False,
            auto_migrate=False,
        )

        app_a = create_app(engine=engine, rate_limiter=limiter_a, config=cfg_a)
        app_b = create_app(engine=engine, rate_limiter=limiter_b, config=cfg_b)

        client_a = TestClient(app_a)
        client_b = TestClient(app_b)

        yield {
            "client_a": client_a,
            "client_b": client_b,
            "engine": engine,
            "shared_redis": shared_redis,
            "limiter_a": limiter_a,
            "limiter_b": limiter_b,
        }
        client_a.close()
        client_b.close()
        engine.close()
        gc.collect()


def test_scenario_1_readiness_probe_evaluates_database_and_redis(distributed_env):
    """Scenario 1: Readiness probe reports health of both database and Redis."""
    client_a = distributed_env["client_a"]
    res = client_a.get("/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert data["migrations"] == "current"
    assert data["redis"] == "connected"


def test_scenario_1_readiness_probe_fails_when_redis_down_strict_mode():
    """Scenario 1 & 13: Under fail_closed_mutations, Redis outage reports 503 not_ready."""
    broken_redis = MagicMock()
    broken_redis.ping.return_value = False
    broken_redis.register_script.side_effect = RuntimeError("Redis down")

    limiter = RedisRateLimiter(
        redis_client=broken_redis,
        failure_mode="fail_closed_mutations",
    )
    import gc

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        engine = SQLiteDatabaseEngine(db_path)
        MigrationRunner(engine).migrate()

        cfg = SangyanConfig(database_url=f"sqlite:///{db_path}", require_auth=False, auto_migrate=False)
        app = create_app(engine=engine, rate_limiter=limiter, config=cfg)
        client = TestClient(app)

        res = client.get("/health/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "not_ready"
        assert data["reason"] == "redis_unavailable"
        client.close()
        engine.close()
        gc.collect()


def test_scenario_2_cluster_wide_rate_limiting_across_replicas(distributed_env):
    """Scenario 2: Multi-pod shared rate limit exhaustion."""
    client_a = distributed_env["client_a"]
    client_b = distributed_env["client_b"]

    # Shared limit for 'investigation' endpoint is 4 tokens.
    # Pod A executes 2 claims
    for _ in range(2):
        res = client_a.post(
            "/api/v1/verify/claim?organization_id=org_test&user_id=user1",
            json={"statement": "Investigate ABC claim", "claim_type": "regulatory"},
        )
        assert res.status_code in (200, 201)

    # Pod B executes 2 claims -> Total 4 consumed
    for _ in range(2):
        res = client_b.post(
            "/api/v1/verify/claim?organization_id=org_test&user_id=user1",
            json={"statement": "Investigate XYZ claim", "claim_type": "regulatory"},
        )
        assert res.status_code in (200, 201)

    # 5th request to Pod A MUST be rate limited with 429
    res_a_rejected = client_a.post(
        "/api/v1/verify/claim?organization_id=org_test&user_id=user1",
        json={"statement": "Blocked claim", "claim_type": "regulatory"},
    )
    assert res_a_rejected.status_code == 429
    assert "Rate limit exceeded" in res_a_rejected.json()["detail"]

    # 6th request to Pod B MUST ALSO be rate limited with 429
    res_b_rejected = client_b.post(
        "/api/v1/verify/claim?organization_id=org_test&user_id=user1",
        json={"statement": "Blocked claim 2", "claim_type": "regulatory"},
    )
    assert res_b_rejected.status_code == 429
    assert "Rate limit exceeded" in res_b_rejected.json()["detail"]


def test_scenario_3_shared_failed_auth_lockout_across_replicas(distributed_env):
    """Scenario 3: Failed authentication on Pod A locks out user on Pod B across cluster."""
    client_a = distributed_env["client_a"]
    client_b = distributed_env["client_b"]
    shared_redis = distributed_env["shared_redis"]

    # Emulate 3 failed auth attempts from client IP
    tracker_a = distributed_env["limiter_a"].auth_tracker
    tracker_a.record_failure("testclient")
    tracker_a.record_failure("testclient")
    tracker_a.record_failure("testclient")

    # Now request sent to Pod B must be throttled with 429
    res_b = client_b.get("/api/v1/investigations")
    assert res_b.status_code == 429
    assert "Too many authentication failures" in res_b.json()["detail"]


def test_scenario_15_helm_manifest_distributed_scaling():
    """Scenario 15: Validate values-distributed.yaml allows multi-replica and HPA."""
    import yaml
    values_path = Path("C:/Projects/Sangyan/deploy/helm/sangyan/values-distributed.yaml")
    assert values_path.exists()
    vals = yaml.safe_load(values_path.read_text(encoding="utf-8"))

    assert vals["replicaCount"] >= 2
    assert vals["autoscaling"]["enabled"] is True
    assert vals["autoscaling"]["minReplicas"] == 2
    assert vals["autoscaling"]["maxReplicas"] == 10
    assert vals["config"]["databaseUrl"].startswith("postgresql://")
    assert vals["config"]["checkpointBackend"] == "postgres"
    assert vals["config"]["redisUrl"].startswith("redis://")
