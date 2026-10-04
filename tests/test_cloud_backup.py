"""Tests for offsite cloud backup replication, pre-upload encryption enforcement, and restore."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sangyan.database.backup import BackupManager
from sangyan.database.cloud_backup import (
    LocalMockCloudStorage,
    S3BackupStorage,
    sha256_checksum,
)
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner


@pytest.fixture
def backup_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        db_path = tmp_path / "production.db"
        engine = SQLiteDatabaseEngine(db_path)
        MigrationRunner(engine).migrate()

        # Seed some data
        engine.execute(
            "INSERT INTO sangyan_organizations (id, name, status, created_at) VALUES (?, ?, ?, ?)",
            ("org_cloud_test", "Cloud Backup Org", "active", 1700000000.0),
        )

        manager = BackupManager(
            engine=engine,
            default_backup_dir=str(tmp_path / "local_backups"),
        )
        enc_key = "a" * 64

        yield {
            "tmpdir": tmp_path,
            "engine": engine,
            "manager": manager,
            "enc_key": enc_key,
        }
        engine.close()


def test_pre_upload_encryption_enforcement_rejects_plaintext(backup_env):
    """Scenario 9: Cloud storage MUST reject any unencrypted file upload."""
    tmpdir = backup_env["tmpdir"]
    storage = LocalMockCloudStorage(storage_dir=str(tmpdir / "cloud_bucket"))

    # Create unencrypted dummy archive
    plain_file = tmpdir / "unencrypted_backup.tar.gz"
    plain_file.write_bytes(b"Simulated plaintext SQLite and checkpoints")

    with pytest.raises(ValueError) as excinfo:
        storage.upload_backup(str(plain_file))
    assert "Plaintext backup upload strictly prohibited" in str(excinfo.value)


def test_cloud_backup_upload_verify_and_restore(backup_env):
    """Scenario 10: Encrypted backup creation, cloud replication, remote download, and isolated restore."""
    tmpdir = backup_env["tmpdir"]
    manager = backup_env["manager"]
    enc_key = backup_env["enc_key"]

    # 1. Create local encrypted backup
    local_archive = manager.create_backup(
        encrypt=True,
        encryption_key=enc_key,
        backup_dir=str(tmpdir / "local_backups"),
    )
    assert str(local_archive).endswith(".enc")
    local_hash = sha256_checksum(str(local_archive))

    # 2. Upload to mock cloud storage
    cloud_bucket_dir = tmpdir / "cloud_bucket"
    storage = LocalMockCloudStorage(storage_dir=str(cloud_bucket_dir))
    manifest = storage.upload_backup(str(local_archive))

    assert manifest.cloud_key.endswith(".enc")
    assert manifest.sha256 == local_hash
    assert manifest.encrypted is True

    # 3. Restore from cloud into isolated directory
    restore_target = tmpdir / "isolated_restored_artifacts"
    res = storage.restore_from_cloud(
        cloud_key=manifest.cloud_key,
        target_dir=str(restore_target),
        backup_manager=manager,
        encryption_key=enc_key,
    )

    assert res["target_dir"] == str(restore_target)
    assert res["restored_relational"] is not None
    assert res["table_count"] > 0

    # 4. Verify data integrity in restored database
    restored_db_path = Path(res["restored_relational"])
    restored_engine = SQLiteDatabaseEngine(restored_db_path)
    org_row = restored_engine.query_one(
        "SELECT name FROM sangyan_organizations WHERE id = ?",
        ("org_cloud_test",),
    )
    assert org_row is not None
    assert org_row["name"] == "Cloud Backup Org"
    restored_engine.close()


def test_cloud_backup_retention_pruning(backup_env):
    """Scenario 11: Cloud retention policy prunes oldest objects beyond keep count."""
    tmpdir = backup_env["tmpdir"]
    storage = LocalMockCloudStorage(storage_dir=str(tmpdir / "cloud_bucket"))

    # Upload 5 mock encrypted backups
    uploaded_keys = []
    for i in range(5):
        f = tmpdir / f"backup_2026100{i}.enc"
        f.write_bytes(f"Encrypted payload {i}".encode())
        m = storage.upload_backup(str(f))
        uploaded_keys.append(m.cloud_key)

    assert len(storage.list_backups()) == 5

    # Prune keeping only 3
    pruned = storage.prune_cloud_backups(keep_count=3)
    assert len(pruned) == 2
    assert len(storage.list_backups()) == 3

    remaining_keys = [b["key"] for b in storage.list_backups()]
    # The oldest 2 should be gone
    for p in pruned:
        assert p not in remaining_keys


def test_cloud_upload_retries_transient_failures(backup_env):
    tmpdir = backup_env["tmpdir"]
    f = tmpdir / "backup_retry_test.enc"
    f.write_bytes(b"Encrypted test content")

    mock_s3 = MagicMock()
    # Fail first 2 attempts, succeed on 3rd
    mock_s3.upload_file.side_effect = [
        Exception("Connection reset by peer"),
        Exception("503 Slow Down"),
        None,
    ]

    storage = S3BackupStorage(bucket="test-bucket", max_retries=3, base_retry_delay=0.01)
    storage._s3 = mock_s3

    manifest = storage.upload_backup(str(f))
    assert manifest.cloud_key.startswith("backups/")
    assert mock_s3.upload_file.call_count == 3
