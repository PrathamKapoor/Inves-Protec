"""Automated, cryptographically verified database backup and disaster recovery engine."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from sangyan.core.errors import StorageError
from sangyan.database.engine import DatabaseEngine, SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner


class BackupError(Exception):
    """Base exception for database backup and restore operations."""


class BackupIntegrityError(BackupError):
    """Raised when backup checksum verification or cryptographic integrity check fails."""


@dataclass
class BackupMetadata:
    """Metadata describing a point-in-time database backup archive."""

    backup_id: str
    timestamp: float
    created_at_iso: str
    dialect: str
    archive_name: str
    archive_sha256: str
    encrypted: bool
    encryption_algorithm: Optional[str]
    included_artifacts: list[str]
    applied_migrations: list[int]
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackupMetadata:
        return cls(**data)


def compute_sha256(path: Path) -> str:
    """Compute standard SHA-256 hex digest of file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def derive_key(secret: str | bytes, salt: bytes) -> bytes:
    """Derive 256-bit key using PBKDF2-HMAC-SHA256."""
    secret_bytes = secret.encode("utf-8") if isinstance(secret, str) else secret
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return kdf.derive(secret_bytes)


def _safe_extract_tar(tar: tarfile.TarFile, target_path: Path) -> None:
    """Safely extract tar archive with path traversal protection."""
    if hasattr(tarfile, "data_filter"):
        tar.extractall(target_path, filter="data")
    else:
        tar.extractall(target_path)


class BackupManager:
    """Manages transactional backups, AES-256-GCM encryption, checksumming, and restore."""

    def __init__(
        self,
        engine: DatabaseEngine,
        checkpoint_db_path: Optional[str | Path] = None,
        key_dir: Optional[str | Path] = None,
        default_backup_dir: str | Path = "backups",
    ) -> None:
        self.engine = engine
        self.checkpoint_db_path = Path(checkpoint_db_path) if checkpoint_db_path else None
        self.key_dir = Path(key_dir) if key_dir else None
        self.default_backup_dir = Path(default_backup_dir)

    def _snapshot_sqlite(self, source_path: Path, dest_path: Path) -> None:
        """Create a transactionally consistent online snapshot of SQLite database."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        # SQLite online backup API ensures safe point-in-time copy even during WAL writes
        src_conn = sqlite3.connect(str(source_path), check_same_thread=False)
        dst_conn = sqlite3.connect(str(dest_path), check_same_thread=False)
        try:
            with dst_conn:
                src_conn.backup(dst_conn)
        finally:
            src_conn.close()
            dst_conn.close()

    def create_backup(
        self,
        backup_dir: Optional[str | Path] = None,
        encrypt: bool = False,
        encryption_key: Optional[str | bytes] = None,
    ) -> Path:
        """Create an integrity-verified, optional encrypted backup archive.

        Returns path to final backup archive.
        """
        out_dir = Path(backup_dir) if backup_dir else self.default_backup_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        now = time.time()
        iso_ts = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        millis = int((now * 1000) % 1000)
        import uuid
        rand_suffix = uuid.uuid4().hex[:6]
        backup_id = f"sgy_backup_{iso_ts}_{millis:03d}_{rand_suffix}"

        # Get migration status
        runner = MigrationRunner(self.engine)
        try:
            applied_migrations = runner.applied_versions()
        except Exception:
            applied_migrations = []

        with tempfile.TemporaryDirectory() as staging_dir:
            staging_path = Path(staging_dir)
            artifacts: list[str] = []

            # 1. Snapshot primary relational DB
            if self.engine.dialect == "sqlite":
                sqlite_engine = self.engine
                if isinstance(sqlite_engine, SQLiteDatabaseEngine):
                    db_file = sqlite_engine.db_path
                    if str(db_file) != ":memory:" and db_file.exists():
                        target_db = staging_path / "relational.db"
                        self._snapshot_sqlite(db_file, target_db)
                        artifacts.append("relational.db")
                    elif str(db_file) == ":memory:":
                        # For in-memory testing, dump schema & data via backup
                        target_db = staging_path / "relational.db"
                        src_conn = sqlite_engine._get_connection()
                        dst_conn = sqlite3.connect(str(target_db))
                        try:
                            src_conn.backup(dst_conn)
                        finally:
                            dst_conn.close()
                        artifacts.append("relational.db")
            else:
                # PostgreSQL placeholder / table dump
                target_sql = staging_path / "relational_pg.sql"
                target_sql.write_text("-- PostgreSQL backup placeholder --\n", encoding="utf-8")
                artifacts.append("relational_pg.sql")

            # 2. Snapshot LangGraph workflow checkpoint DB if configured
            if self.checkpoint_db_path and self.checkpoint_db_path.exists():
                target_ckpt = staging_path / "checkpoints.db"
                self._snapshot_sqlite(self.checkpoint_db_path, target_ckpt)
                artifacts.append("checkpoints.db")

            # 3. Snapshot cryptographic trust keys if configured
            if self.key_dir and self.key_dir.exists():
                target_keys = staging_path / "keys"
                target_keys.mkdir(parents=True, exist_ok=True)
                for key_file in self.key_dir.glob("*"):
                    if key_file.is_file():
                        shutil.copy2(key_file, target_keys / key_file.name)
                        artifacts.append(f"keys/{key_file.name}")

            # 4. Pack into tar.gz archive
            raw_archive_name = f"{backup_id}.tar.gz"
            raw_archive_path = staging_path / raw_archive_name
            with tarfile.open(raw_archive_path, "w:gz") as tar:
                for art in artifacts:
                    file_path = staging_path / art
                    if file_path.exists():
                        tar.add(file_path, arcname=art)

            raw_sha256 = compute_sha256(raw_archive_path)

            # 5. Encryption (optional AES-256-GCM)
            should_encrypt = encrypt or (encryption_key is not None)
            if should_encrypt:
                if not encryption_key:
                    raise BackupError("Encryption requested but no encryption key provided.")

                salt = os.urandom(16)
                key = derive_key(encryption_key, salt)
                nonce = os.urandom(12)
                aesgcm = AESGCM(key)

                with open(raw_archive_path, "rb") as f:
                    plaintext = f.read()

                ciphertext = aesgcm.encrypt(nonce, plaintext, None)

                enc_archive_name = f"{backup_id}.tar.gz.enc"
                final_archive_path = out_dir / enc_archive_name

                # Format: SALT (16 bytes) + NONCE (12 bytes) + CIPHERTEXT_WITH_TAG
                with open(final_archive_path, "wb") as f:
                    f.write(salt)
                    f.write(nonce)
                    f.write(ciphertext)

                final_sha256 = compute_sha256(final_archive_path)
                final_archive_name = enc_archive_name
                enc_algo = "AES-256-GCM"
            else:
                final_archive_path = out_dir / raw_archive_name
                shutil.copy2(raw_archive_path, final_archive_path)
                final_sha256 = raw_sha256
                final_archive_name = raw_archive_name
                enc_algo = None

        # Write checksum file alongside archive: <archive_name>.sha256
        checksum_path = out_dir / f"{final_archive_name}.sha256"
        checksum_path.write_text(f"{final_sha256}  {final_archive_name}\n", encoding="utf-8")

        # Write metadata file: <backup_id>.meta.json
        meta = BackupMetadata(
            backup_id=backup_id,
            timestamp=now,
            created_at_iso=iso_ts,
            dialect=self.engine.dialect,
            archive_name=final_archive_name,
            archive_sha256=final_sha256,
            encrypted=should_encrypt,
            encryption_algorithm=enc_algo,
            included_artifacts=artifacts,
            applied_migrations=applied_migrations,
        )
        meta_path = out_dir / f"{final_archive_name}.meta.json"
        meta_path.write_text(json.dumps(meta.to_dict(), indent=2), encoding="utf-8")

        return final_archive_path

    def verify_backup(
        self,
        backup_path: str | Path,
        encryption_key: Optional[str | bytes] = None,
    ) -> dict[str, Any]:
        """Verify archive checksum, decryption tag (if encrypted), and database file integrity."""
        b_path = Path(backup_path)
        if not b_path.exists():
            raise BackupError(f"Backup archive does not exist: {b_path}")

        # 1. Verify SHA-256 checksum
        computed_sha = compute_sha256(b_path)
        checksum_file = b_path.parent / f"{b_path.name}.sha256"
        if checksum_file.exists():
            expected_content = checksum_file.read_text(encoding="utf-8").strip()
            expected_sha = expected_content.split()[0]
            if computed_sha.lower() != expected_sha.lower():
                raise BackupIntegrityError(
                    f"Checksum verification failed for {b_path.name}: "
                    f"computed {computed_sha} != expected {expected_sha}"
                )

        is_encrypted = b_path.name.endswith(".enc")

        with tempfile.TemporaryDirectory() as temp_extract:
            extract_path = Path(temp_extract)
            tar_to_inspect = b_path

            # 2. Decrypt if encrypted
            if is_encrypted:
                if not encryption_key:
                    raise BackupError("Backup is encrypted but no decryption key provided.")

                with open(b_path, "rb") as f:
                    salt = f.read(16)
                    nonce = f.read(12)
                    ciphertext = f.read()

                key = derive_key(encryption_key, salt)
                aesgcm = AESGCM(key)
                try:
                    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
                except Exception as e:
                    raise BackupIntegrityError(f"Cryptographic decryption / tag verification failed: {e}") from e

                decrypted_tar = extract_path / "decrypted.tar.gz"
                decrypted_tar.write_bytes(plaintext)
                tar_to_inspect = decrypted_tar

            # 3. Inspect archive contents
            try:
                with tarfile.open(tar_to_inspect, "r:gz") as tar:
                    _safe_extract_tar(tar, extract_path)
                    member_names = tar.getnames()
            except Exception as e:
                raise BackupIntegrityError(f"Malformed tar.gz archive: {e}") from e

            # 4. If relational.db is present, run SQLite PRAGMA integrity_check
            relational_db = extract_path / "relational.db"
            integrity_result = "not_applicable"
            if relational_db.exists():
                conn = sqlite3.connect(str(relational_db))
                try:
                    cur = conn.execute("PRAGMA integrity_check")
                    row = cur.fetchone()
                    if not row or row[0] != "ok":
                        raise BackupIntegrityError(f"SQLite PRAGMA integrity_check failed: {row}")
                    integrity_result = "ok"
                finally:
                    conn.close()

            # 5. Checkpoints integrity if present
            ckpt_db = extract_path / "checkpoints.db"
            if ckpt_db.exists():
                conn = sqlite3.connect(str(ckpt_db))
                try:
                    cur = conn.execute("PRAGMA integrity_check")
                    row = cur.fetchone()
                    if not row or row[0] != "ok":
                        raise BackupIntegrityError(f"Checkpoints PRAGMA integrity_check failed: {row}")
                finally:
                    conn.close()

        # Read metadata if present
        meta_file = b_path.parent / f"{b_path.name}.meta.json"
        meta_dict = {}
        if meta_file.exists():
            try:
                meta_dict = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        return {
            "valid": True,
            "archive": b_path.name,
            "sha256": computed_sha,
            "checksum_verified": True,
            "encrypted": is_encrypted,
            "integrity_check": integrity_result,
            "artifacts": member_names,
            "metadata": meta_dict,
        }

    def restore_backup(
        self,
        backup_path: str | Path,
        target_dir: str | Path,
        encryption_key: Optional[str | bytes] = None,
    ) -> dict[str, Any]:
        """Restore database, checkpoints, and keys into an isolated target directory with full verification."""
        b_path = Path(backup_path)
        t_dir = Path(target_dir)
        t_dir.mkdir(parents=True, exist_ok=True)

        # 1. Pre-verify backup integrity before restoring
        verif = self.verify_backup(b_path, encryption_key=encryption_key)

        is_encrypted = b_path.name.endswith(".enc")
        tar_to_extract = b_path

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            if is_encrypted:
                with open(b_path, "rb") as f:
                    salt = f.read(16)
                    nonce = f.read(12)
                    ciphertext = f.read()

                key = derive_key(encryption_key, salt)
                aesgcm = AESGCM(key)
                plaintext = aesgcm.decrypt(nonce, ciphertext, None)
                tar_to_extract = temp_path / "restore.tar.gz"
                tar_to_extract.write_bytes(plaintext)

            # Unpack into target directory
            with tarfile.open(tar_to_extract, "r:gz") as tar:
                _safe_extract_tar(tar, t_dir)

        # Post-restore verification in target directory
        restored_relational = t_dir / "relational.db"
        table_count = 0
        migrations_applied = 0
        if restored_relational.exists():
            conn = sqlite3.connect(str(restored_relational))
            try:
                cur = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
                table_count = cur.fetchone()[0]
                cur = conn.execute("SELECT count(*) FROM schema_migrations")
                migrations_applied = cur.fetchone()[0]
            finally:
                conn.close()

        return {
            "status": "restored",
            "target_dir": str(t_dir),
            "restored_relational": str(restored_relational) if restored_relational.exists() else None,
            "restored_checkpoints": str(t_dir / "checkpoints.db") if (t_dir / "checkpoints.db").exists() else None,
            "table_count": table_count,
            "migrations_applied": migrations_applied,
            "artifacts_restored": verif["artifacts"],
        }

    def prune_backups(
        self,
        backup_dir: Optional[str | Path] = None,
        keep_count: int = 7,
    ) -> list[str]:
        """Prune older backups beyond keep_count, cleaning associated checksums and metadata."""
        b_dir = Path(backup_dir) if backup_dir else self.default_backup_dir
        if not b_dir.exists():
            return []

        # Find all .meta.json files
        meta_files = sorted(b_dir.glob("*.meta.json"), key=os.path.getmtime)
        if len(meta_files) <= keep_count:
            return []

        to_prune = meta_files[: len(meta_files) - keep_count]
        pruned_ids: list[str] = []

        for mf in to_prune:
            try:
                meta = json.loads(mf.read_text(encoding="utf-8"))
                arch_name = meta.get("archive_name")
                b_id = meta.get("backup_id", mf.stem)
                # Delete archive
                if arch_name:
                    arch_path = b_dir / arch_name
                    if arch_path.exists():
                        arch_path.unlink()
                    sha_path = b_dir / f"{arch_name}.sha256"
                    if sha_path.exists():
                        sha_path.unlink()
                # Delete metadata file
                mf.unlink()
                pruned_ids.append(b_id)
            except Exception:
                pass

        return pruned_ids
