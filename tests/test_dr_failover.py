"""Tests for Multi-Region Disaster Recovery, split-brain fencing, and cryptographic audit continuity."""
import pytest

from sangyan.core.errors import NotFoundError, StaleRegionError
from sangyan.database.engine import create_engine
from sangyan.database.migrations import MigrationRunner
from sangyan.dr.manager import DisasterRecoveryManager
from sangyan.dr.models import RegionFencingRecord, RegionRole
from sangyan.tenancy.repository import TenantAdministration, TenantRepository


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    MigrationRunner(engine).migrate()
    yield engine
    engine.close()


@pytest.fixture
def seeded_tenancy(test_db):
    admin = TenantAdministration(test_db)
    org_id = admin.create_organization("SEBI Watchdog Organization")
    user_id = admin.create_user("analyst@sebi.gov.in", "Lead Analyst")
    admin.add_membership(org_id, user_id, "sangyan_analyst")
    return {"engine": test_db, "org_id": org_id, "user_id": user_id}


def test_dr_registration_and_status(test_db):
    dr = DisasterRecoveryManager(
        engine=test_db,
        region_id="primary-mumbai",
        default_role=RegionRole.PRIMARY_ACTIVE,
        default_epoch=1,
    )

    status = dr.get_cluster_status()
    assert status["local_region"] == "primary-mumbai"
    assert status["active_primary"] == "primary-mumbai"
    assert status["current_epoch"] == 1
    assert len(status["regions"]) == 1

    # Register standby region
    standby = dr.register_region("standby-hyderabad", role=RegionRole.STANDBY_READY, cluster_epoch=1)
    assert standby.region_id == "standby-hyderabad"
    assert standby.role == RegionRole.STANDBY_READY
    assert standby.is_fenced is False

    updated_status = dr.get_cluster_status()
    assert len(updated_status["regions"]) == 2


def test_standby_region_write_rejection(seeded_tenancy):
    engine = seeded_tenancy["engine"]
    org_id = seeded_tenancy["org_id"]
    user_id = seeded_tenancy["user_id"]

    dr = DisasterRecoveryManager(
        engine=engine,
        region_id="standby-delhi",
        default_role=RegionRole.STANDBY_READY,
        default_epoch=1,
    )

    with pytest.raises(StaleRegionError) as exc:
        dr.verify_write_authority("standby-delhi")
    assert "Writes rejected" in str(exc.value)

    # Attempting to write through TenantRepository with standby region must raise StaleRegionError
    repo = TenantRepository(
        engine,
        organization_id=org_id,
        user_id=user_id,
        dr_manager=dr,
        region_id="standby-delhi",
    )

    with pytest.raises(StaleRegionError):
        repo.record_audit_event(
            action="INVESTIGATION_CREATED",
            resource="inv-001",
            result="SUCCESS",
        )


def test_fencing_and_demotion_blocks_writes(test_db):
    dr = DisasterRecoveryManager(
        engine=test_db,
        region_id="primary-mumbai",
        default_role=RegionRole.PRIMARY_ACTIVE,
        default_epoch=1,
    )

    # Initially primary has write authority
    dr.verify_write_authority("primary-mumbai")

    # Manually fence primary
    dr.fence_region("primary-mumbai", reason="Operator network isolation drill")
    fenced = dr.get_region("primary-mumbai")
    assert fenced.is_fenced is True
    assert fenced.role == RegionRole.FENCED

    with pytest.raises(StaleRegionError) as exc:
        dr.verify_write_authority("primary-mumbai")
    assert "is fenced" in str(exc.value)
    assert "Operator network isolation drill" in str(exc.value)


def test_promotion_and_split_brain_prevention(test_db):
    # Setup Primary in Mumbai (Epoch 1) and Standby in Bangalore (Epoch 1)
    dr_primary = DisasterRecoveryManager(
        engine=test_db,
        region_id="primary-mumbai",
        default_role=RegionRole.PRIMARY_ACTIVE,
        default_epoch=1,
    )
    dr_primary.register_region("standby-bangalore", role=RegionRole.STANDBY_READY, cluster_epoch=1)

    # Verify primary can write
    dr_primary.verify_write_authority("primary-mumbai")

    # Perform failover: promote standby-bangalore
    promoted = dr_primary.promote_region("standby-bangalore", reason="Mumbai power failure")
    assert promoted.role == RegionRole.PRIMARY_ACTIVE
    assert promoted.cluster_epoch == 2
    assert promoted.is_fenced is False

    # Old primary must now be DEMOTED and FENCED
    old_primary = dr_primary.get_region("primary-mumbai")
    assert old_primary.role == RegionRole.DEMOTED
    assert old_primary.is_fenced is True

    # Standby promoted to primary now has write authority
    dr_primary.verify_write_authority("standby-bangalore")

    # Old primary attempting to write must be REJECTED (Split-Brain Prevention)
    with pytest.raises(StaleRegionError) as exc:
        dr_primary.verify_write_authority("primary-mumbai")
    assert "is fenced" in str(exc.value)

    # Idempotent promotion: promoting bangalore again should return current state without incrementing epoch
    re_promoted = dr_primary.promote_region("standby-bangalore")
    assert re_promoted.cluster_epoch == 2


def test_audit_ledger_continuity_and_tamper_detection(seeded_tenancy):
    engine = seeded_tenancy["engine"]
    org_id = seeded_tenancy["org_id"]
    user_id = seeded_tenancy["user_id"]

    dr = DisasterRecoveryManager(
        engine=engine,
        region_id="primary-mumbai",
        default_role=RegionRole.PRIMARY_ACTIVE,
        default_epoch=1,
    )
    repo = TenantRepository(
        engine,
        organization_id=org_id,
        user_id=user_id,
        dr_manager=dr,
        region_id="primary-mumbai",
    )

    # Empty audit ledger is valid
    res_empty = dr.verify_audit_continuity()
    assert res_empty["valid"] is True
    assert res_empty["event_count"] == 0

    # Write sequence of audit events
    event_ids = []
    for i in range(5):
        eid = repo.record_audit_event(
            action=f"ACTION_EXECUTE_{i}",
            resource=f"res-{i}",
            result="SUCCESS",
        )
        event_ids.append(eid)

    # Verify unbroken hash chain
    res_valid = dr.verify_audit_continuity()
    assert res_valid["valid"] is True
    assert res_valid["event_count"] == 5

    # Tamper with an audit event's ledger_hash in the database
    tamper_id = event_ids[2]
    engine.execute(
        "UPDATE sangyan_audit_events SET ledger_hash='0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' WHERE id=?",
        (tamper_id,),
    )

    # Verification must detect tampering
    res_tampered = dr.verify_audit_continuity()
    assert res_tampered["valid"] is False
    assert res_tampered["broken_at_index"] == 2


def test_simulate_failover_end_to_end(seeded_tenancy):
    engine = seeded_tenancy["engine"]
    org_id = seeded_tenancy["org_id"]
    user_id = seeded_tenancy["user_id"]

    dr = DisasterRecoveryManager(
        engine=engine,
        region_id="primary-south",
        default_role=RegionRole.PRIMARY_ACTIVE,
        default_epoch=1,
    )
    dr.register_region("standby-north", role=RegionRole.STANDBY_READY, cluster_epoch=1)

    repo = TenantRepository(
        engine,
        organization_id=org_id,
        user_id=user_id,
        dr_manager=dr,
        region_id="primary-south",
    )
    repo.record_audit_event(
        action="SYSTEM_INIT",
        resource="cluster",
        result="SUCCESS",
    )

    report = dr.simulate_failover("primary-south", "standby-north", reason="Drill 2026-Q4")
    assert report["failover_status"] == "SUCCESS"
    assert report["from_region"]["role"] == RegionRole.DEMOTED
    assert report["from_region"]["is_fenced"] is True
    assert report["to_region"]["role"] == RegionRole.PRIMARY_ACTIVE
    assert report["to_region"]["is_fenced"] is False
    assert report["epoch"] == 2
    assert report["audit_continuity"]["valid"] is True
    assert report["audit_continuity"]["event_count"] == 1
