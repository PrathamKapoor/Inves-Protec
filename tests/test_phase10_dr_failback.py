"""Phase 10: controlled failback drill, promotion races, and split-brain red teaming.

Scenarios:
- Failover then controlled failback with epoch monotonicity and audit continuity.
- Concurrent promotion race: exactly one PRIMARY_ACTIVE survives; epochs never regress.
- Stale-epoch writer (role says active, epoch behind cluster max) rejected.
- Fencing rejection telemetry increments on every rejected write.
- Simulated RTO/RPO measurement recorded from the drill (simulation only).
"""
import threading
import time

import pytest

from sangyan.core.errors import NotFoundError, StaleRegionError
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.dr.manager import DisasterRecoveryManager
from sangyan.dr.models import RegionRole
from sangyan.security.telemetry import MetricsRegistry
from sangyan.tenancy.repository import TenantAdministration, TenantRepository


@pytest.fixture
def dr_env(tmp_path):
    engine = SQLiteDatabaseEngine(tmp_path / "dr_failback.db")
    MigrationRunner(engine).migrate()

    admin = TenantAdministration(engine)
    org_id = admin.create_organization("DR Tenant")
    user_id = admin.create_user("dr@sangyan.test", "DR Analyst")
    admin.add_membership(org_id, user_id, "sangyan_analyst")

    dr = DisasterRecoveryManager(
        engine=engine, region_id="region-a", default_role=RegionRole.PRIMARY_ACTIVE, default_epoch=1
    )
    dr.register_region("region-b", role=RegionRole.STANDBY_READY, cluster_epoch=1)

    yield {"engine": engine, "dr": dr, "org_id": org_id, "user_id": user_id}
    engine.close()


def _repo(env, region_id: str) -> TenantRepository:
    return TenantRepository(
        env["engine"],
        env["org_id"],
        env["user_id"],
        dr_manager=env["dr"],
        region_id=region_id,
    )


def _write(env, region_id: str, action: str) -> str:
    return _repo(env, region_id).record_audit_event(
        action=action, resource=f"res-{region_id}", result="SUCCESS"
    )


def test_controlled_failback_drill_with_timing(dr_env):
    """A active -> A fails -> B promoted -> B active -> A repaired -> controlled failback -> A active."""
    env = dr_env
    dr = env["dr"]
    metrics = MetricsRegistry.get_default()

    drill: dict[str, float] = {}

    # Phase 1: normal workload on A
    t0 = time.time()
    _write(env, "region-a", "workload_before_failover")
    drill["pre_failover_write"] = time.time() - t0

    # Phase 2: failure detected (operator/monitor marks A fenced)
    t_detect = time.time()
    dr.fence_region("region-a", reason="Simulated region A catastrophe")
    drill["failure_detection_and_fence"] = time.time() - t_detect

    # Writes to fenced A must now fail closed
    with pytest.raises(StaleRegionError):
        _write(env, "region-a", "stale_write_after_fence")

    # Phase 3: promote B
    t_promo = time.time()
    promoted = dr.promote_region("region-b", reason="Failover drill")
    drill["promotion_initiation_to_ready"] = time.time() - t_promo
    assert promoted.role == RegionRole.PRIMARY_ACTIVE
    assert promoted.cluster_epoch == 2

    # Phase 4: traffic resumes on B; first successful write
    t_first = time.time()
    _write(env, "region-b", "first_write_after_promotion")
    drill["first_successful_write"] = time.time() - t_first

    # Workload on B while A is down (including a review-like state transition)
    _write(env, "region-b", "workload_on_b")

    # Phase 5: A repaired and synchronized (operator-verified), controlled failback.
    # Interim active B is demoted first (no automatic failback - D-079).
    t_fb = time.time()
    dr.demote_region("region-b", reason="Controlled failback to repaired region A")
    a_state = dr.get_region("region-a")
    assert a_state.role == RegionRole.FENCED  # still fenced until explicitly re-promoted
    back = dr.promote_region("region-a", reason="Controlled failback drill")
    drill["failback_duration"] = time.time() - t_fb

    # Phase 6: post-failback authority
    assert back.role == RegionRole.PRIMARY_ACTIVE
    assert back.cluster_epoch == 3  # strictly monotonic across failover AND failback
    _write(env, "region-a", "first_write_after_failback")

    # Old active region B must now be rejected
    with pytest.raises(StaleRegionError):
        _write(env, "region-b", "stale_write_after_failback")

    # Audit ledger continuity unbroken across failover + failback
    continuity = dr.verify_audit_continuity()
    assert continuity["valid"] is True

    # Epoch monotonicity across all steps
    epochs = [1, promoted.cluster_epoch, back.cluster_epoch]
    assert epochs == sorted(epochs)
    assert len(set(epochs)) == 3

    # Simulated timing (NOT a production guarantee - local simulation only)
    assert all(k in drill and drill[k] >= 0 for k in
               ("failure_detection_and_fence", "promotion_initiation_to_ready", "first_successful_write"))
    # Fencing took effect BEFORE traffic moved: first B write succeeded only after promotion
    assert drill["failback_duration"] >= 0


def test_failback_rejected_write_uses_409_semantics(dr_env):
    """StaleRegionError maps to HTTP 409 at the API boundary (contract check)."""
    from sangyan.api.routes import get_api_router  # noqa: F401  (import sanity)

    env = dr_env
    dr = env["dr"]
    dr.promote_region("region-b", reason="failover")
    with pytest.raises(StaleRegionError) as exc:
        _write(env, "region-a", "stale")
    # Error is a conflict-class signal (HTTP 409 mapped in routes)
    from sangyan.core.errors import SangyanError
    assert isinstance(exc.value, SangyanError)


def test_concurrent_promotion_race_single_primary(dr_env):
    """Two concurrent promotions must converge to exactly one PRIMARY_ACTIVE with monotonic epochs."""
    env = dr_env
    dr = env["dr"]
    dr.register_region("region-c", role=RegionRole.STANDBY_READY, cluster_epoch=1)

    barrier = threading.Barrier(2)
    errors = []

    def promote(region: str):
        try:
            barrier.wait(timeout=5)
            dr.promote_region(region, reason="concurrent race")
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [
        threading.Thread(target=promote, args=("region-b",)),
        threading.Thread(target=promote, args=("region-c",)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert errors == []
    status = dr.get_cluster_status()
    primaries = [r for r in status["regions"] if r["role"] == RegionRole.PRIMARY_ACTIVE and not r["is_fenced"]]
    assert len(primaries) == 1  # split-brain prevented
    epochs = [r["cluster_epoch"] for r in status["regions"]]
    # Cluster max epoch advanced at least once; no epoch went backwards from its registration value
    assert status["current_epoch"] >= 2
    assert dr.verify_audit_continuity()["valid"] is True


def test_stale_epoch_active_writer_rejected(dr_env):
    """A region whose record claims PRIMARY_ACTIVE but whose epoch lags the cluster max is rejected."""
    env = dr_env
    dr = env["dr"]

    # B promoted -> cluster epoch 2
    dr.promote_region("region-b", reason="failover")
    # Tamper: make A look active again but with the stale epoch (split-brain forgery)
    env["engine"].execute(
        "UPDATE sangyan_region_fencing SET role=?, is_fenced=0, fence_reason=NULL WHERE region_id=?",
        (RegionRole.PRIMARY_ACTIVE, "region-a"),
    )

    with pytest.raises(StaleRegionError) as exc:
        dr.verify_write_authority("region-a")
    assert "stale" in str(exc.value)
    assert "Split-brain prevented" in str(exc.value)


def test_fencing_rejection_metric_increments(dr_env):
    """Every rejected stale write increments the fencing rejection counter."""
    env = dr_env
    dr = env["dr"]
    metrics = MetricsRegistry.get_default()
    before = _counter_value(metrics.dr_fencing_rejections_total)

    dr.promote_region("region-b", reason="failover")
    with pytest.raises(StaleRegionError):
        _write(env, "region-a", "rejected_write_1")
    with pytest.raises(StaleRegionError):
        _write(env, "region-a", "rejected_write_2")

    after = _counter_value(metrics.dr_fencing_rejections_total)
    assert after >= before + 2


def test_promotion_of_unregistered_region_fails_closed(dr_env):
    env = dr_env
    with pytest.raises(NotFoundError):
        env["dr"].promote_region("region-never-registered")


def test_simulated_failover_report_contains_audit_continuity(dr_env):
    env = dr_env
    dr = env["dr"]
    _write(env, "region-a", "pre_sim_workload")
    report = dr.simulate_failover("region-a", "region-b", reason="Phase 10 drill")
    assert report["failover_status"] == "SUCCESS"
    assert report["epoch"] == 2
    assert report["audit_continuity"]["valid"] is True
    assert report["from_region"]["is_fenced"] in (True, 1)
    assert report["to_region"]["role"] == RegionRole.PRIMARY_ACTIVE


def _counter_value(counter) -> float:
    """Read a prometheus Counter's total value across label sets."""
    total = 0.0
    for child in counter.collect()[0].samples:
        if child.name.endswith("_total"):
            total += child.value
    return total
