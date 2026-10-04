"""Comprehensive tests for database backup, AES-256-GCM encryption, checksum verification, and isolated disaster recovery."""
from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from sangyan.database.backup import BackupIntegrityError, BackupManager
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.domain.base import new_id
from sangyan.domain.models import (
    Claim,
    ContentItem,
    Evidence,
    Finding,
    Investigation,
)
from sangyan.tenancy.repository import TenantAdministration, TenantRepository
from sangyan.trust.receipt import TrustReceipt
from sangyan.trust.service import TrustService
from sangyan.workflow.checkpointer import WorkflowCheckpointer


@pytest.fixture
def populated_env():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "prod.db"
        ckpt_path = tmp_path / "checkpoints.db"
        keys_path = tmp_path / "keys"
        backup_path = tmp_path / "backups"

        engine = SQLiteDatabaseEngine(db_path)
        MigrationRunner(engine).migrate()

        # Seed tenancy & identities
        admin = TenantAdministration(engine)
        org_id = admin.create_organization("DR Test Organization")
        user_id = admin.create_user("dr_analyst@sangyan.gov.in", "DR Analyst")
        admin.add_membership(org_id, user_id, "sangyan_analyst")

        repo = TenantRepository(engine, org_id, user_id)

        # Seed content, claims, evidence
        content = ContentItem(
            organization_id=org_id,
            content_type="text",
            raw_content="Guaranteed 200% returns in 10 days on WhatsApp",
            normalized_text="Guaranteed 200% returns in 10 days on WhatsApp",
        )
        repo.save_content_item(content)

        claim = Claim(
            content_item_id=content.id,
            statement="Guaranteed 200% returns in 10 days",
            claim_type="factual",
            status="UNVERIFIED",
        )
        repo.save_claim(claim)

        evid = Evidence(
            claim_id=claim.id,
            source_id="src_sebi_registry",
            excerpt="Unregistered entity offering speculative schemes",
            stance="CONTRADICTS",
        )
        repo.save_evidence(evid)

        finding = Finding(
            claim_id=claim.id,
            statement="Unregistered scheme violates regulations",
            status="CONTRADICTED",
            evidence_refs=[evid.id],
            rationale="Official SEBI registry does not authorize guaranteed return schemes.",
        )
        repo.save_finding(finding)

        # Seed investigation
        inv = Investigation(
            organization_id=org_id,
            user_id=user_id,
            content_item_id=content.id,
            claim_ids=[claim.id],
            finding_ids=[finding.id],
            status="COMPLETED",
        )
        repo.save_investigation(inv)

        # Trust service with keys
        keys_path.mkdir(parents=True, exist_ok=True)
        trust_service = TrustService(engine, key_dir=keys_path)
        receipt = trust_service.sign_document(
            subject_type="investigation",
            subject_id=inv.id,
            document={"claim": claim.id, "finding": finding.id, "evidence": evid.id},
        )

        # Workflow checkpoints
        checkpointer = WorkflowCheckpointer(db_path=ckpt_path)
        saver = checkpointer.get_saver()
        # Create a checkpoint entry
        conn = checkpointer._conn
        conn.execute("CREATE TABLE IF NOT EXISTS test_ckpt_table (id TEXT PRIMARY KEY, state TEXT)")
        conn.execute("INSERT INTO test_ckpt_table VALUES (?, ?)", ("ckpt_1", "interrupted_review"))
        conn.commit()

        manager = BackupManager(
            engine=engine,
            checkpoint_db_path=ckpt_path,
            key_dir=keys_path,
            default_backup_dir=backup_path,
        )

        try:
            yield {
                "manager": manager,
                "engine": engine,
                "org_id": org_id,
                "user_id": user_id,
                "content_id": content.id,
                "claim_id": claim.id,
                "evidence_id": evid.id,
                "finding_id": finding.id,
                "inv_id": inv.id,
                "receipt_id": receipt.id,
                "backup_dir": backup_path,
                "tmp_path": tmp_path,
            }
        finally:
            engine.close()
            checkpointer.close()
            import gc
            gc.collect()


def test_create_and_verify_unencrypted_backup(populated_env):
    mgr = populated_env["manager"]
    backup_file = mgr.create_backup(encrypt=False)
    assert backup_file.exists()
    assert backup_file.name.endswith(".tar.gz")

    # Checksum file exists
    sha_file = backup_file.parent / f"{backup_file.name}.sha256"
    assert sha_file.exists()

    # Metadata file exists
    meta_file = backup_file.parent / f"{backup_file.name}.meta.json"
    assert meta_file.exists()

    # Verify backup
    res = mgr.verify_backup(backup_file)
    assert res["valid"] is True
    assert res["checksum_verified"] is True
    assert res["integrity_check"] == "ok"
    assert "relational.db" in res["artifacts"]
    assert "checkpoints.db" in res["artifacts"]


def test_create_and_verify_aes256_gcm_encrypted_backup(populated_env):
    mgr = populated_env["manager"]
    key = "super-secret-backup-passphrase-32bytes-long!"
    backup_file = mgr.create_backup(encrypt=True, encryption_key=key)
    assert backup_file.exists()
    assert backup_file.name.endswith(".tar.gz.enc")

    # Verify with correct key
    res = mgr.verify_backup(backup_file, encryption_key=key)
    assert res["valid"] is True
    assert res["encrypted"] is True
    assert res["checksum_verified"] is True
    assert res["integrity_check"] == "ok"


def test_corrupted_backup_fails_verification(populated_env):
    mgr = populated_env["manager"]
    key = "super-secret-backup-passphrase-32bytes-long!"
    backup_file = mgr.create_backup(encrypt=True, encryption_key=key)

    # Tamper with the encrypted archive (flip bytes)
    with open(backup_file, "r+b") as f:
        f.seek(35)
        byte = f.read(1)
        f.seek(35)
        f.write(bytes([byte[0] ^ 0xFF]))

    # Checksum mismatch should be detected immediately
    with pytest.raises(BackupIntegrityError) as exc_info:
        mgr.verify_backup(backup_file, encryption_key=key)
    assert "Checksum verification failed" in str(exc_info.value)


def test_wrong_decryption_key_fails_verification(populated_env):
    mgr = populated_env["manager"]
    key = "super-secret-backup-passphrase-32bytes-long!"
    wrong_key = "completely-wrong-passphrase-attempting-decrypt"
    backup_file = mgr.create_backup(encrypt=True, encryption_key=key)

    with pytest.raises(BackupIntegrityError) as exc_info:
        mgr.verify_backup(backup_file, encryption_key=wrong_key)
    assert "Cryptographic decryption / tag verification failed" in str(exc_info.value)


def test_prune_backups_retains_keep_count(populated_env):
    mgr = populated_env["manager"]
    b_dir = populated_env["backup_dir"]

    # Create 5 backups with slight sleep to ensure distinct timestamps
    created = []
    for _ in range(5):
        time.sleep(0.05)
        created.append(mgr.create_backup(encrypt=False))

    assert len(list(b_dir.glob("*.tar.gz"))) == 5

    # Prune to keep 2
    pruned = mgr.prune_backups(b_dir, keep_count=2)
    assert len(pruned) == 3
    assert len(list(b_dir.glob("*.tar.gz"))) == 2


def test_full_isolated_restore_verification(populated_env):
    mgr = populated_env["manager"]
    key = "dr-restore-secret-key-32-bytes-long!!"
    backup_file = mgr.create_backup(encrypt=True, encryption_key=key)

    # Restore into an isolated clean directory
    restore_target = populated_env["tmp_path"] / "isolated_restore_target"
    res = mgr.restore_backup(backup_file, target_dir=restore_target, encryption_key=key)

    assert res["status"] == "restored"
    assert res["migrations_applied"] >= 4
    assert res["table_count"] >= 20

    # Verify data in restored database
    restored_db_path = Path(res["restored_relational"])
    restored_engine = SQLiteDatabaseEngine(restored_db_path)
    restored_repo = TenantRepository(
        restored_engine,
        organization_id=populated_env["org_id"],
        user_id=populated_env["user_id"],
    )

    # 1. Content item intact
    content = restored_repo.get_content_item(populated_env["content_id"])
    assert content is not None
    assert "Guaranteed 200% returns" in content.raw_content

    # 2. Claim intact
    claim = restored_repo.get_claim(populated_env["claim_id"])
    assert claim is not None
    assert claim.claim_type == "factual"

    # 3. Evidence intact
    evid = restored_repo.get_evidence(populated_env["evidence_id"])
    assert evid is not None
    assert evid.stance == "CONTRADICTS"

    # 4. Finding intact
    finding = restored_repo.get_finding(populated_env["finding_id"])
    assert finding is not None
    assert finding.status == "CONTRADICTED"

    # 5. Investigation intact
    restored_inv = restored_repo.get_investigation(populated_env["inv_id"])
    assert restored_inv is not None
    assert restored_inv.status == "COMPLETED"

    # 6. Trust receipt restored
    restored_receipt = restored_engine.query_one("SELECT * FROM sangyan_trust_receipts WHERE id=?", (populated_env["receipt_id"],))
    assert restored_receipt is not None
    assert restored_receipt["subject_id"] == populated_env["inv_id"]

    # 7. Checkpoint database restored
    restored_ckpt_path = Path(res["restored_checkpoints"])
    assert restored_ckpt_path.exists()
    import sqlite3
    conn = sqlite3.connect(str(restored_ckpt_path))
    cur = conn.execute("SELECT state FROM test_ckpt_table WHERE id='ckpt_1'")
    assert cur.fetchone()[0] == "interrupted_review"
    conn.close()

    restored_engine.close()
    import gc
    gc.collect()
