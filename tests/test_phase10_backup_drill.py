"""Phase 10: backup/restore drill negative paths.

Extends Phase 7 backup tests with:
- Truncated archive must fail verification and refuse restore.
- Restore of a corrupted archive must fail safely (no partial state written).
- Checkpoint and trust receipt integrity re-verified after an isolated restore.
- Wrong-generation restore (backup missing expected artifacts) rejected.
"""
import shutil
import tempfile
from pathlib import Path

import pytest

from sangyan.database.backup import BackupIntegrityError, BackupManager
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.domain.models import Claim, ContentItem, Investigation
from sangyan.tenancy.repository import TenantAdministration, TenantRepository
from sangyan.trust.service import TrustService
from sangyan.workflow.checkpointer import WorkflowCheckpointer


@pytest.fixture
def drill_env(tmp_path):
    db_path = tmp_path / "drill.db"
    ckpt_path = tmp_path / "checkpoints.db"
    keys_path = tmp_path / "keys"
    backup_path = tmp_path / "backups"

    engine = SQLiteDatabaseEngine(db_path)
    MigrationRunner(engine).migrate()

    admin = TenantAdministration(engine)
    org_id = admin.create_organization("Backup Drill Org")
    user_id = admin.create_user("drill@sangyan.test", "Drill Analyst")
    admin.add_membership(org_id, user_id, "sangyan_analyst")

    repo = TenantRepository(engine, org_id, user_id)
    content = ContentItem(
        organization_id=org_id,
        content_type="text",
        raw_content="Withdraw fee required to release guaranteed profits",
    )
    repo.save_content_item(content)
    claim = Claim(content_item_id=content.id, statement="Withdraw fee required", claim_type="payment")
    repo.save_claim(claim)
    inv = Investigation(
        organization_id=org_id,
        user_id=user_id,
        content_item_id=content.id,
        claim_ids=[claim.id],
        status="COMPLETED",
    )
    repo.save_investigation(inv)

    keys_path.mkdir(parents=True, exist_ok=True)
    trust_service = TrustService(engine, key_dir=keys_path)
    receipt = trust_service.sign_document(
        subject_type="investigation",
        subject_id=inv.id,
        document={"investigation": inv.id, "claim": claim.id},
    )

    checkpointer = WorkflowCheckpointer(db_path=ckpt_path)
    checkpointer.get_saver()  # initializes the underlying connection
    conn = checkpointer._conn
    conn.execute("CREATE TABLE IF NOT EXISTS test_ckpt_table (id TEXT PRIMARY KEY, state TEXT)")
    conn.execute("INSERT OR REPLACE INTO test_ckpt_table VALUES ('ckpt_1', 'awaiting_review')")
    conn.commit()

    manager = BackupManager(
        engine=engine,
        checkpoint_db_path=ckpt_path,
        key_dir=keys_path,
        default_backup_dir=backup_path,
    )

    yield {
        "manager": manager,
        "engine": engine,
        "org_id": org_id,
        "user_id": user_id,
        "inv_id": inv.id,
        "receipt_id": receipt.id,
        "content_id": content.id,
        "claim_id": claim.id,
        "backup_dir": backup_path,
        "tmp_path": tmp_path,
    }
    engine.close()
    checkpointer.close()


KEY = "drill-key-32-bytes-long-absolutely-ok!"


def test_truncated_archive_fails_verification_and_restore(drill_env):
    mgr = drill_env["manager"]
    backup_file = mgr.create_backup(encrypt=False)
    original_size = backup_file.stat().st_size

    # Truncate to half
    with open(backup_file, "r+b") as f:
        f.truncate(original_size // 2)

    with pytest.raises(BackupIntegrityError):
        mgr.verify_backup(backup_file)

    # Restore must also refuse (fails safely, never restores partial state)
    target = drill_env["tmp_path"] / "restore_truncated"
    with pytest.raises(BackupIntegrityError):
        mgr.restore_backup(backup_file, target_dir=target)
    assert not (target / "relational.db").exists() if target.exists() else True


def test_corrupted_archive_restore_rejected_no_partial_state(drill_env):
    mgr = drill_env["manager"]
    backup_file = mgr.create_backup(encrypt=False)

    # Corrupt the gzip payload mid-file
    size = backup_file.stat().st_size
    with open(backup_file, "r+b") as f:
        f.seek(size // 2)
        b = f.read(1)
        f.seek(size // 2)
        f.write(bytes([b[0] ^ 0xFF]))

    target = drill_env["tmp_path"] / "restore_corrupt"
    with pytest.raises(BackupIntegrityError):
        mgr.restore_backup(backup_file, target_dir=target)
    # No restored database materialized from a corrupt archive
    assert not (target / "relational.db").exists()


def test_isolated_restore_preserves_checkpoint_and_trust_receipt(drill_env):
    mgr = drill_env["manager"]
    backup_file = mgr.create_backup(encrypt=True, encryption_key=KEY)

    target = drill_env["tmp_path"] / "restore_full"
    res = mgr.restore_backup(backup_file, target_dir=target, encryption_key=KEY)
    assert res["status"] == "restored"

    # Relational integrity: trust receipt survives with matching subject
    restored_rel = Path(res["restored_relational"])
    restored_engine = SQLiteDatabaseEngine(restored_rel)
    try:
        receipt = restored_engine.query_one(
            "SELECT * FROM sangyan_trust_receipts WHERE id=?", (drill_env["receipt_id"],)
        )
        assert receipt is not None
        assert receipt["subject_id"] == drill_env["inv_id"]
        assert receipt["signature_b64"]

        # Audit continuity in the restored copy
        from sangyan.dr.manager import DisasterRecoveryManager

        dr = DisasterRecoveryManager(engine=restored_engine, region_id="restore-drill")
        assert dr.verify_audit_continuity()["valid"] is True
    finally:
        restored_engine.close()

    # Checkpoint artifact restored
    restored_ckpt = Path(res.get("restored_checkpoints") or (target / "checkpoints.db"))
    assert restored_ckpt.exists()
    ck = SQLiteDatabaseEngine(restored_ckpt)
    try:
        row = ck.query_one("SELECT state FROM test_ckpt_table WHERE id='ckpt_1'")
        assert row is not None
        assert row["state"] == "awaiting_review"
    finally:
        ck.close()


def test_wrong_generation_backup_missing_artifacts_rejected(drill_env):
    """A hand-assembled archive missing manifest/checksum artifacts is refused."""
    mgr = drill_env["manager"]
    fake = drill_env["tmp_path"] / "fake_generation.tar.gz"
    import gzip
    import io

    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(b"not a sangyan backup manifest")
    fake.write_bytes(buf.getvalue())

    with pytest.raises(BackupIntegrityError):
        mgr.verify_backup(fake)
