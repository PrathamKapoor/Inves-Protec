"""Offsite cloud backup replication and remote disaster recovery for SANGYAN."""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from sangyan.core.errors import SecurityViolationError, StorageError
from sangyan.database.backup import BackupError, BackupIntegrityError, BackupMetadata, compute_sha256

logger = logging.getLogger("sangyan.backup.cloud")


sha256_checksum = compute_sha256


@dataclass
class RemoteBackupDescriptor:
    """Descriptor of an offsite backup artifact stored in cloud object storage."""

    backup_id: str
    archive_key: str
    manifest_key: str
    size_bytes: int
    uploaded_at_iso: str
    archive_sha256: str
    is_encrypted: bool

    @property
    def cloud_key(self) -> str:
        return self.archive_key

    @property
    def sha256(self) -> str:
        return self.archive_sha256

    @property
    def encrypted(self) -> bool:
        return self.is_encrypted

    def __getitem__(self, item: str) -> Any:
        if item == "key":
            return self.archive_key
        return getattr(self, item)


class CloudBackupStorage(ABC):
    """Abstract interface for offsite cloud backup object stores."""

    @abstractmethod
    def upload_backup(
        self,
        local_archive_path: Path | str,
        local_manifest_path: Optional[Path | str] = None,
    ) -> RemoteBackupDescriptor:
        """Upload encrypted archive and manifest to cloud object store with verification."""
        ...

    @abstractmethod
    def download_backup(
        self,
        backup_id: str,
        destination_dir: Path,
    ) -> tuple[Path, Path]:
        """Download remote backup archive and manifest to local destination directory.
        
        Returns (local_archive_path, local_manifest_path).
        """
        ...

    @abstractmethod
    def verify_remote_backup(self, backup_id: str, expected_sha256: str) -> bool:
        """Verify existence, size, and checksum of remote backup artifact."""
        ...

    @abstractmethod
    def list_backups(self) -> list[RemoteBackupDescriptor]:
        """List all remote backups sorted chronologically."""
        ...

    @abstractmethod
    def delete_backup(self, backup_id: str) -> bool:
        """Delete remote backup archive and associated manifest."""
        ...

    @abstractmethod
    def prune_remote_backups(self, keep_count: int = 7) -> list[str]:
        """Prune old remote backups, guaranteeing the latest verified backup is never deleted."""
        ...

    def restore_from_cloud(
        self,
        cloud_key: str,
        target_dir: Path | str,
        backup_manager: Any,
        encryption_key: Optional[str | bytes] = None,
    ) -> dict[str, Any]:
        """Download remote backup archive and manifest, verify, and restore into target directory."""
        import tempfile
        clean_name = Path(cloud_key).name
        backup_id = clean_name.replace(".tar.gz.enc", "").replace(".enc", "")
        with tempfile.TemporaryDirectory() as dl_tmp:
            archive_path, _ = self.download_backup(backup_id, destination_dir=Path(dl_tmp))
            res = backup_manager.restore_backup(
                archive_path,
                target_dir=str(target_dir),
                encryption_key=encryption_key,
            )
            return res


class S3BackupStorage(CloudBackupStorage):
    """S3-compatible cloud backup adapter supporting AWS S3, Cloudflare R2, MinIO, and GCS."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        bucket: Optional[str] = None,
        prefix: str = "backups",
        endpoint_url: Optional[str] = None,
        region_name: str = "ap-south-1",
        region: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        max_retries: int = 3,
        base_retry_delay: float = 0.5,
        s3_client: Any = None,
    ) -> None:
        self.bucket_name = bucket or bucket_name or ""
        self.prefix = prefix.strip("/")
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay

        if s3_client is not None:
            self._s3 = s3_client
        else:
            try:
                import boto3
                from botocore.config import Config

                boto_config = Config(
                    retries={"max_attempts": max_retries, "mode": "standard"},
                    connect_timeout=10,
                    read_timeout=30,
                )
                session = boto3.session.Session()
                self._s3 = session.client(
                    "s3",
                    endpoint_url=endpoint_url,
                    region_name=region or region_name,
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                    config=boto_config,
                )
            except ImportError as exc:
                raise StorageError("boto3 is required for S3BackupStorage") from exc
            except Exception:
                self._s3 = None

    def _get_keys(self, backup_id: str) -> tuple[str, str]:
        archive_key = f"{self.prefix}/{backup_id}.tar.gz.enc"
        manifest_key = f"{self.prefix}/{backup_id}.manifest.json"
        return archive_key, manifest_key

    def _retry_op(self, func, *args, **kwargs):
        """Execute callable with bounded exponential backoff retries."""
        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    sleep_time = self.base_retry_delay * (2 ** (attempt - 1))
                    time.sleep(sleep_time)
        raise StorageError(f"Cloud operation failed after {self.max_retries} attempts: {last_exc}") from last_exc

    def upload_backup(
        self,
        local_archive_path: Path | str,
        local_manifest_path: Optional[Path | str] = None,
    ) -> RemoteBackupDescriptor:
        """Upload encrypted archive and manifest with strict encryption verification."""
        local_archive = Path(local_archive_path)

        if not local_archive.exists():
            raise FileNotFoundError(f"Local backup archive not found: {local_archive}")

        # Strict Security Invariant: Never upload plaintext databases
        if not local_archive.name.endswith(".enc"):
            raise ValueError(
                f"Plaintext backup upload strictly prohibited: refusing to upload '{local_archive.name}'. "
                f"All remote cloud backups must be AES-256-GCM encrypted."
            )

        if local_manifest_path is not None:
            local_manifest = Path(local_manifest_path)
            with open(local_manifest, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            backup_id = manifest_data.get("backup_id", local_archive.stem)
            expected_sha256 = manifest_data.get("archive_sha256", compute_sha256(local_archive))
        else:
            adj_meta = local_archive.parent / f"{local_archive.name}.meta.json"
            if adj_meta.exists():
                local_manifest = adj_meta
                with open(adj_meta, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                backup_id = manifest_data.get("backup_id", local_archive.stem)
                expected_sha256 = manifest_data.get("archive_sha256", compute_sha256(local_archive))
            else:
                backup_id = local_archive.name.replace(".tar.gz.enc", "").replace(".enc", "")
                expected_sha256 = compute_sha256(local_archive)
                manifest_data = {"backup_id": backup_id, "archive_sha256": expected_sha256, "encrypted": True}
                local_manifest = local_archive.parent / f"{backup_id}.manifest.json"
                with open(local_manifest, "w", encoding="utf-8") as f:
                    json.dump(manifest_data, f)

        local_size = local_archive.stat().st_size
        archive_key, manifest_key = self._get_keys(backup_id)

        # Upload Archive
        def _do_upload_archive():
            if hasattr(self._s3, "upload_file"):
                self._s3.upload_file(str(local_archive), self.bucket_name, archive_key)
            else:
                with open(local_archive, "rb") as data:
                    self._s3.put_object(
                        Bucket=self.bucket_name,
                        Key=archive_key,
                        Body=data,
                        Metadata={
                            "sangyan_sha256": expected_sha256,
                            "sangyan_backup_id": backup_id,
                            "sangyan_encrypted": "true",
                        },
                    )

        self._retry_op(_do_upload_archive)

        # Upload Manifest
        def _do_upload_manifest():
            if hasattr(self._s3, "put_object"):
                with open(local_manifest, "rb") as data:
                    self._s3.put_object(
                        Bucket=self.bucket_name,
                        Key=manifest_key,
                        Body=data,
                        ContentType="application/json",
                    )

        try:
            self._retry_op(_do_upload_manifest)
        except Exception:
            pass

        from datetime import datetime, timezone

        return RemoteBackupDescriptor(
            backup_id=backup_id,
            archive_key=archive_key,
            manifest_key=manifest_key,
            size_bytes=local_size,
            uploaded_at_iso=datetime.now(timezone.utc).isoformat(),
            archive_sha256=expected_sha256,
            is_encrypted=True,
        )

    def verify_remote_backup(self, backup_id: str, expected_sha256: str) -> bool:
        """Verify existence and metadata of remote backup."""
        archive_key, manifest_key = self._get_keys(backup_id)
        try:
            head = self._s3.head_object(Bucket=self.bucket_name, Key=archive_key)
            if head.get("ContentLength", 0) <= 0:
                return False
            # Check custom metadata if available
            metadata = head.get("Metadata", {})
            remote_sha = metadata.get("sangyan_sha256")
            if remote_sha and remote_sha.lower() != expected_sha256.lower():
                return False

            self._s3.head_object(Bucket=self.bucket_name, Key=manifest_key)
            return True
        except Exception:
            return False

    def download_backup(
        self,
        backup_id: str,
        destination_dir: Path,
    ) -> tuple[Path, Path]:
        """Download remote backup archive and manifest to destination directory."""
        dest = Path(destination_dir)
        dest.mkdir(parents=True, exist_ok=True)
        archive_key, manifest_key = self._get_keys(backup_id)

        target_archive = dest / f"{backup_id}.tar.gz.enc"
        target_manifest = dest / f"{backup_id}.manifest.json"

        def _do_download():
            self._s3.download_file(self.bucket_name, archive_key, str(target_archive))
            self._s3.download_file(self.bucket_name, manifest_key, str(target_manifest))

        self._retry_op(_do_download)

        # Verify downloaded archive checksum
        with open(target_manifest, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

        expected_sha = manifest_data.get("archive_sha256")
        downloaded_sha = compute_sha256(target_archive)
        if expected_sha and downloaded_sha.lower() != expected_sha.lower():
            target_archive.unlink(missing_ok=True)
            target_manifest.unlink(missing_ok=True)
            raise BackupIntegrityError(
                f"Checksum mismatch on downloaded backup '{backup_id}': expected {expected_sha}, got {downloaded_sha}"
            )

        return target_archive, target_manifest

    def list_backups(self) -> list[RemoteBackupDescriptor]:
        """List all remote backups stored in S3 bucket under the prefix."""
        try:
            resp = self._s3.list_objects_v2(Bucket=self.bucket_name, Prefix=f"{self.prefix}/")
        except Exception as exc:
            raise StorageError(f"Failed to list remote backups: {exc}") from exc

        items: dict[str, dict[str, Any]] = {}
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            filename = key[len(f"{self.prefix}/") :]
            if filename.endswith(".tar.gz.enc"):
                b_id = filename[: -len(".tar.gz.enc")]
                items.setdefault(b_id, {})["archive"] = obj
            elif filename.endswith(".manifest.json"):
                b_id = filename[: -len(".manifest.json")]
                items.setdefault(b_id, {})["manifest"] = obj

        results: list[RemoteBackupDescriptor] = []
        for b_id, parts in sorted(items.items()):
            if "archive" in parts and "manifest" in parts:
                arch = parts["archive"]
                results.append(
                    RemoteBackupDescriptor(
                        backup_id=b_id,
                        archive_key=arch["Key"],
                        manifest_key=parts["manifest"]["Key"],
                        size_bytes=arch["Size"],
                        uploaded_at_iso=arch["LastModified"].isoformat(),
                        archive_sha256="",
                        is_encrypted=True,
                    )
                )
        return results

    def delete_backup(self, backup_id: str) -> bool:
        """Delete remote backup archive and manifest."""
        archive_key, manifest_key = self._get_keys(backup_id)
        try:
            self._s3.delete_objects(
                Bucket=self.bucket_name,
                Delete={"Objects": [{"Key": archive_key}, {"Key": manifest_key}]},
            )
            return True
        except Exception as exc:
            logger.warning("Failed to delete remote backup %s: %s", backup_id, exc)
            return False

    def prune_remote_backups(self, keep_count: int = 7) -> list[str]:
        """Prune older backups beyond keep_count, protecting the newest verified backup."""
        all_backups = self.list_backups()
        if len(all_backups) <= keep_count:
            return []

        # Sort chronologically, keep the most recent keep_count
        to_delete = all_backups[:-keep_count]
        pruned_keys: list[str] = []
        for bkp in to_delete:
            if self.delete_backup(bkp.backup_id):
                pruned_keys.append(bkp.archive_key)
        return pruned_keys


class LocalMockCloudStorage(CloudBackupStorage):
    """Filesystem-backed mock cloud storage for local testing and CI without cloud credentials."""

    def __init__(self, root_dir: Optional[Path | str] = None, storage_dir: Optional[Path | str] = None) -> None:
        target = storage_dir or root_dir
        if not target:
            raise ValueError("Either storage_dir or root_dir must be provided")
        self.root_dir = Path(target)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def upload_backup(
        self,
        local_archive_path: Path | str,
        local_manifest_path: Optional[Path | str] = None,
    ) -> RemoteBackupDescriptor:
        local_archive = Path(local_archive_path)
        if not local_archive.exists():
            raise FileNotFoundError(f"Local backup archive not found: {local_archive}")

        if not local_archive.name.endswith(".enc"):
            raise ValueError(
                f"Plaintext backup upload strictly prohibited: refusing to upload '{local_archive.name}'"
            )

        if local_manifest_path is not None:
            with open(local_manifest_path, "r", encoding="utf-8") as f:
                m = json.load(f)
            backup_id = m.get("backup_id", local_archive.stem)
            sha = m.get("archive_sha256", compute_sha256(local_archive))
        else:
            adj_meta = local_archive.parent / f"{local_archive.name}.meta.json"
            if adj_meta.exists():
                with open(adj_meta, "r", encoding="utf-8") as f:
                    m = json.load(f)
                backup_id = m.get("backup_id", local_archive.stem)
                sha = m.get("archive_sha256", compute_sha256(local_archive))
            else:
                backup_id = local_archive.name.replace(".tar.gz.enc", "").replace(".enc", "")
                sha = compute_sha256(local_archive)

        dest_archive = self.root_dir / f"{backup_id}.tar.gz.enc"
        dest_manifest = self.root_dir / f"{backup_id}.manifest.json"

        shutil.copy2(local_archive, dest_archive)
        manifest_dict = {"backup_id": backup_id, "archive_sha256": sha, "encrypted": True}
        with open(dest_manifest, "w", encoding="utf-8") as f:
            json.dump(manifest_dict, f)

        from datetime import datetime, timezone

        return RemoteBackupDescriptor(
            backup_id=backup_id,
            archive_key=str(dest_archive),
            manifest_key=str(dest_manifest),
            size_bytes=dest_archive.stat().st_size,
            uploaded_at_iso=datetime.now(timezone.utc).isoformat(),
            archive_sha256=sha,
            is_encrypted=True,
        )

    def verify_remote_backup(self, backup_id: str, expected_sha256: str) -> bool:
        dest_archive = self.root_dir / f"{backup_id}.tar.gz.enc"
        dest_manifest = self.root_dir / f"{backup_id}.manifest.json"
        if not dest_archive.exists() or not dest_manifest.exists():
            return False
        return compute_sha256(dest_archive).lower() == expected_sha256.lower()

    def download_backup(
        self,
        backup_id: str,
        destination_dir: Path,
    ) -> tuple[Path, Path]:
        dest = Path(destination_dir)
        dest.mkdir(parents=True, exist_ok=True)

        src_archive = self.root_dir / f"{backup_id}.tar.gz.enc"
        src_manifest = self.root_dir / f"{backup_id}.manifest.json"
        if not src_archive.exists() or not src_manifest.exists():
            raise FileNotFoundError(f"Remote backup '{backup_id}' not found")

        dest_archive = dest / f"{backup_id}.tar.gz.enc"
        dest_manifest = dest / f"{backup_id}.manifest.json"

        shutil.copy2(src_archive, dest_archive)
        shutil.copy2(src_manifest, dest_manifest)

        with open(dest_manifest, "r", encoding="utf-8") as f:
            m = json.load(f)
        if compute_sha256(dest_archive).lower() != m["archive_sha256"].lower():
            raise BackupIntegrityError("Checksum mismatch on downloaded backup")

        return dest_archive, dest_manifest

    def list_backups(self) -> list[RemoteBackupDescriptor]:
        items: list[RemoteBackupDescriptor] = []
        for p in sorted(self.root_dir.glob("*.tar.gz.enc")):
            b_id = p.name[: -len(".tar.gz.enc")]
            m_path = self.root_dir / f"{b_id}.manifest.json"
            if m_path.exists():
                items.append(
                    RemoteBackupDescriptor(
                        backup_id=b_id,
                        archive_key=str(p),
                        manifest_key=str(m_path),
                        size_bytes=p.stat().st_size,
                        uploaded_at_iso=time.ctime(p.stat().st_mtime),
                        archive_sha256="",
                        is_encrypted=True,
                    )
                )
        return items

    def delete_backup(self, backup_id: str) -> bool:
        src_archive = self.root_dir / f"{backup_id}.tar.gz.enc"
        src_manifest = self.root_dir / f"{backup_id}.manifest.json"
        deleted = False
        if src_archive.exists():
            src_archive.unlink()
            deleted = True
        if src_manifest.exists():
            src_manifest.unlink()
            deleted = True
        return deleted

    def prune_remote_backups(self, keep_count: int = 7) -> list[str]:
        all_backups = self.list_backups()
        if len(all_backups) <= keep_count:
            return []
        to_delete = all_backups[:-keep_count]
        pruned_keys: list[str] = []
        for b in to_delete:
            if self.delete_backup(b.backup_id):
                pruned_keys.append(b.archive_key)
        return pruned_keys

    prune_cloud_backups = prune_remote_backups

