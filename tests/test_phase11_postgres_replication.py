"""Tests for Phase 11 PostgreSQL physical WAL streaming replication tooling, health validation, and CLI commands."""

import time
import pytest
from click.testing import CliRunner

from sangyan.cli import cli
from sangyan.core.errors import DomainValidationError
from sangyan.database.engine import create_engine
from sangyan.database.migrations import MigrationRunner
from sangyan.database.replication import PostgresReplicationManager
from sangyan.dr.manager import DisasterRecoveryManager
from sangyan.dr.models import RegionRole


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "sangyan_repl_test.db"
    engine = create_engine(f"sqlite:///{db_file}")
    runner = MigrationRunner(engine)
    runner.migrate()
    yield engine
    engine.close()


def test_simulated_replication_status_primary(test_db):
    mgr = PostgresReplicationManager(engine=test_db)
    status = mgr.get_replication_status()

    assert status["role"] == "PRIMARY"
    assert status["in_recovery"] is False
    assert status["simulated"] is True
    assert status["node_id"] == "primary-south-1"
    assert status["lag_bytes"] == 0
    assert status["lag_seconds"] == 0.0


def test_simulated_replication_status_standby(test_db):
    now = time.time()
    test_db.execute(
        """
        INSERT INTO sangyan_replication_state (
            node_id, role, cluster_epoch, wal_lsn, replay_lsn,
            lag_bytes, lag_seconds, last_heartbeat_at, is_healthy, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("standby-node-2", "STANDBY", 1, "0/16B2D80", "0/16B2C00", 384, 1.25, now, 1, "{}"),
    )

    mgr = PostgresReplicationManager(engine=test_db)
    status = mgr.get_replication_status()

    assert status["role"] == "STANDBY"
    assert status["in_recovery"] is True
    assert status["node_id"] == "standby-node-2"
    assert status["lag_bytes"] == 384
    assert status["lag_seconds"] == 1.25


def test_replication_slots(test_db):
    mgr = PostgresReplicationManager(engine=test_db, primary_slot="test_slot_01")
    slots = mgr.get_replication_slots()

    assert len(slots) >= 1
    assert slots[0]["slot_name"] == "test_slot_01"
    assert slots[0]["slot_type"] == "physical"
    assert slots[0]["active"] is True


def test_validate_standby_health_bounds(test_db):
    mgr = PostgresReplicationManager(engine=test_db, max_lag_sec=5.0, max_lag_bytes=1000)

    # Healthy state
    health = mgr.validate_standby_health()
    assert health["healthy"] is True

    # Breach lag threshold
    now = time.time()
    test_db.execute(
        """
        UPDATE sangyan_replication_state
        SET lag_seconds = 12.5, last_heartbeat_at = ?
        WHERE 1=1
        """,
        (now,),
    )
    unhealthy = mgr.validate_standby_health()
    assert unhealthy["healthy"] is False
    assert unhealthy["lag_seconds"] == 12.5


def test_promote_standby(test_db):
    dr_mgr = DisasterRecoveryManager(
        engine=test_db,
        region_id="mumbai-primary",
        default_role=RegionRole.PRIMARY_ACTIVE,
        default_epoch=1,
    )

    mgr = PostgresReplicationManager(engine=test_db)
    result = mgr.promote_standby(
        dr_manager=dr_mgr,
        target_region="delhi-standby",
        reason="Manual operator failover test",
    )

    assert result["status"] == "PROMOTED"
    assert result["role"] == "PRIMARY"
    assert result["reason"] == "Manual operator failover test"
    assert "dr" in result

    # Verify database state was updated
    status = mgr.get_replication_status()
    assert status["role"] == "PRIMARY"
    assert status["lag_bytes"] == 0
    assert status["lag_seconds"] == 0.0


def test_controlled_switchover_success(test_db):
    dr_mgr = DisasterRecoveryManager(
        engine=test_db,
        region_id="mumbai-primary",
        default_role=RegionRole.PRIMARY_ACTIVE,
        default_epoch=1,
    )
    dr_mgr.register_region("chennai-standby", role=RegionRole.STANDBY_READY)

    mgr = PostgresReplicationManager(engine=test_db)
    result = mgr.controlled_switchover(
        dr_manager=dr_mgr,
        primary_region="mumbai-primary",
        standby_region="chennai-standby",
        reason="Scheduled maintenance switchover",
    )

    assert result["status"] == "SWITCHOVER_COMPLETED"
    assert result["old_primary"] == "mumbai-primary"
    assert result["new_primary"] == "chennai-standby"
    assert result["new_epoch"] == 2

    # Verify DB state
    status = mgr.get_replication_status()
    assert status["node_id"] == "chennai-standby"
    assert status["cluster_epoch"] == 2


def test_controlled_switchover_rejected_if_unhealthy(test_db):
    dr_mgr = DisasterRecoveryManager(
        engine=test_db,
        region_id="mumbai-primary",
        default_role=RegionRole.PRIMARY_ACTIVE,
        default_epoch=1,
    )
    dr_mgr.register_region("chennai-standby", role=RegionRole.STANDBY_READY)

    # Set excessive lag
    mgr = PostgresReplicationManager(engine=test_db, max_lag_sec=2.0)
    mgr.get_replication_status()
    test_db.execute("UPDATE sangyan_replication_state SET lag_seconds = 100.0 WHERE 1=1")

    with pytest.raises(DomainValidationError, match="Controlled switchover refused"):
        mgr.controlled_switchover(
            dr_manager=dr_mgr,
            primary_region="mumbai-primary",
            standby_region="chennai-standby",
        )


def test_cli_db_commands(tmp_path, monkeypatch):
    db_file = tmp_path / "cli_repl.db"
    monkeypatch.setenv("SANGYAN_DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("SANGYAN_AUTO_MIGRATE", "true")

    runner = CliRunner()

    # 1. replication-status
    res = runner.invoke(cli, ["db", "replication-status"])
    assert res.exit_code == 0
    assert "PostgreSQL Physical Replication Status" in res.output
    assert "Role:" in res.output
    assert "Standby Health:" in res.output

    # 2. promote without confirm fails
    res_no_conf = runner.invoke(cli, ["db", "promote", "--region", "ap-south-2"])
    assert res_no_conf.exit_code == 1
    assert "--confirm required" in res_no_conf.output

    # 3. promote with confirm succeeds
    res_conf = runner.invoke(cli, ["db", "promote", "--region", "ap-south-2", "--confirm"])
    assert res_conf.exit_code == 0
    assert "promoted successfully" in res_conf.output

    # 4. switchover without confirm fails
    res_sw_no = runner.invoke(cli, ["db", "switchover", "--primary", "ap-south-1", "--standby", "ap-south-2"])
    assert res_sw_no.exit_code == 1
    assert "--confirm required" in res_sw_no.output

    # 5. switchover with confirm succeeds
    res_sw = runner.invoke(cli, ["db", "switchover", "--primary", "ap-south-1", "--standby", "ap-south-2", "--confirm"])
    assert res_sw.exit_code == 0
    assert "Controlled switchover completed successfully" in res_sw.output
    assert "New Primary:  ap-south-2" in res_sw.output
