"""Disaster Recovery Manager providing region authority epoch tracking, split-brain fencing, and audit continuity."""
from __future__ import annotations

import time
from typing import Any, Optional

from sangyan.core.errors import NotFoundError, StaleRegionError
from sangyan.core.logging import get_logger
from sangyan.crypto.hashing import sha3_hex
from sangyan.database.engine import DatabaseEngine
from sangyan.dr.models import RegionFencingRecord, RegionRole

logger = get_logger("sangyan.dr")


class DisasterRecoveryManager:
    """Manages active-passive region authority, epoch progression, and immutable audit verification."""

    def __init__(
        self,
        engine: DatabaseEngine,
        region_id: str = "primary-south-1",
        default_role: str = RegionRole.PRIMARY_ACTIVE,
        default_epoch: int = 1,
    ) -> None:
        self._db = engine
        self.region_id = region_id
        self.default_role = default_role
        self.default_epoch = default_epoch
        self.ensure_registered()

    def ensure_registered(self) -> None:
        """Register region in sangyan_region_fencing if not already present."""
        now = time.time()
        try:
            with self._db.transaction():
                row = self._db.query_one(
                    "SELECT * FROM sangyan_region_fencing WHERE region_id=?",
                    (self.region_id,),
                )
                if row is None:
                    self._db.execute(
                        """
                        INSERT INTO sangyan_region_fencing
                        (region_id, cluster_epoch, role, is_fenced, fence_reason, last_heartbeat_at, promoted_at, updated_at)
                        VALUES (?,?,?,?,?,?,?,?)
                        """,
                        (
                            self.region_id,
                            self.default_epoch,
                            self.default_role,
                            0,
                            None,
                            now,
                            now if self.default_role == RegionRole.PRIMARY_ACTIVE else None,
                            now,
                        ),
                    )
        except Exception as exc:
            logger.warning("Could not ensure region registration in database: %s", exc)

    def register_region(
        self,
        region_id: str,
        role: str = RegionRole.STANDBY_READY,
        cluster_epoch: int = 1,
    ) -> RegionFencingRecord:
        """Explicitly register an additional region (e.g. secondary standby)."""
        now = time.time()
        with self._db.transaction():
            existing = self._db.query_one("SELECT * FROM sangyan_region_fencing WHERE region_id=?", (region_id,))
            if existing is None:
                self._db.execute(
                    """
                    INSERT INTO sangyan_region_fencing
                    (region_id, cluster_epoch, role, is_fenced, fence_reason, last_heartbeat_at, promoted_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        region_id,
                        cluster_epoch,
                        role,
                        0,
                        None,
                        now,
                        now if role == RegionRole.PRIMARY_ACTIVE else None,
                        now,
                    ),
                )
            return self.get_region(region_id)

    def get_region(self, region_id: Optional[str] = None) -> RegionFencingRecord:
        target = region_id or self.region_id
        row = self._db.query_one("SELECT * FROM sangyan_region_fencing WHERE region_id=?", (target,))
        if row is None:
            raise NotFoundError(f"Region '{target}' not registered in fencing table")
        return RegionFencingRecord.from_dict(row)

    def verify_write_authority(self, region_id: Optional[str] = None) -> None:
        """Assert that the specified (or local) region possesses active primary write authority.

        Raises StaleRegionError if fenced, standby, or behind the latest cluster epoch.
        """
        target = region_id or self.region_id
        row = self._db.query_one("SELECT * FROM sangyan_region_fencing WHERE region_id=?", (target,))
        if row is None:
            raise StaleRegionError(f"Region '{target}' is not registered; write rejected.")

        rec = RegionFencingRecord.from_dict(row)
        if rec.is_fenced:
            reason = f" (reason: {rec.fence_reason})" if rec.fence_reason else ""
            raise StaleRegionError(f"Region '{target}' is fenced{reason}. Pre-write validation failed.")

        if rec.role != RegionRole.PRIMARY_ACTIVE:
            raise StaleRegionError(
                f"Region '{target}' has role '{rec.role}', not '{RegionRole.PRIMARY_ACTIVE}'. Writes rejected."
            )

        # Check maximum global epoch
        max_row = self._db.query_one("SELECT MAX(cluster_epoch) AS max_epoch FROM sangyan_region_fencing")
        max_epoch = int(max_row["max_epoch"]) if max_row and max_row.get("max_epoch") is not None else rec.cluster_epoch

        if rec.cluster_epoch < max_epoch:
            raise StaleRegionError(
                f"Region '{target}' epoch ({rec.cluster_epoch}) is stale; current cluster epoch is {max_epoch}. Split-brain prevented."
            )

    def heartbeat(self, region_id: Optional[str] = None) -> None:
        target = region_id or self.region_id
        now = time.time()
        self._db.execute(
            "UPDATE sangyan_region_fencing SET last_heartbeat_at=?, updated_at=? WHERE region_id=?",
            (now, now, target),
        )

    def fence_region(self, region_id: str, reason: str = "") -> RegionFencingRecord:
        """Demote and fence a region, revoking its write authority immediately."""
        now = time.time()
        with self._db.transaction():
            self._db.execute(
                """
                UPDATE sangyan_region_fencing
                SET is_fenced=1, role=?, fence_reason=?, updated_at=?
                WHERE region_id=?
                """,
                (RegionRole.FENCED, reason or "Fenced by administrator", now, region_id),
            )
        logger.warning("Fenced region %s: %s", region_id, reason)
        return self.get_region(region_id)

    def promote_region(self, region_id: str, reason: str = "") -> RegionFencingRecord:
        """Idempotently promote a standby region to PRIMARY_ACTIVE with epoch increment."""
        now = time.time()
        with self._db.transaction():
            target_row = self._db.query_one("SELECT * FROM sangyan_region_fencing WHERE region_id=?", (region_id,))
            if target_row is None:
                raise NotFoundError(f"Cannot promote unregistered region '{region_id}'")

            target_rec = RegionFencingRecord.from_dict(target_row)
            if target_rec.role == RegionRole.PRIMARY_ACTIVE and not target_rec.is_fenced:
                # Already active primary
                return target_rec

            max_row = self._db.query_one("SELECT MAX(cluster_epoch) AS max_epoch FROM sangyan_region_fencing")
            current_max = int(max_row["max_epoch"]) if max_row and max_row.get("max_epoch") is not None else 1
            new_epoch = current_max + 1

            # 1. Demote and fence any currently active primary regions
            self._db.execute(
                """
                UPDATE sangyan_region_fencing
                SET role=?, is_fenced=1, fence_reason=?, updated_at=?
                WHERE role=? AND region_id != ?
                """,
                (
                    RegionRole.DEMOTED,
                    f"Demoted by failover promotion of {region_id}",
                    now,
                    RegionRole.PRIMARY_ACTIVE,
                    region_id,
                ),
            )

            # 2. Promote target region
            self._db.execute(
                """
                UPDATE sangyan_region_fencing
                SET role=?, cluster_epoch=?, is_fenced=0, fence_reason=NULL, promoted_at=?, updated_at=?
                WHERE region_id=?
                """,
                (RegionRole.PRIMARY_ACTIVE, new_epoch, now, now, region_id),
            )

        logger.info("Promoted region %s to PRIMARY_ACTIVE (epoch %d): %s", region_id, new_epoch, reason)
        return self.get_region(region_id)

    def simulate_failover(
        self,
        from_region: str,
        to_region: str,
        reason: str = "Automated disaster recovery simulation",
    ) -> dict[str, Any]:
        """Perform end-to-end failover simulation: demote primary, promote standby, and verify ledger continuity."""
        start_time = time.time()
        # 1. Verify source and destination exist
        source = self.get_region(from_region)
        dest = self.get_region(to_region)

        # 2. Promote target region (which automatically fences and demotes source)
        promoted = self.promote_region(to_region, reason=reason)
        fenced_source = self.get_region(from_region)

        # 3. Verify audit ledger continuity across the failover boundary
        audit_res = self.verify_audit_continuity()

        duration = time.time() - start_time
        return {
            "failover_status": "SUCCESS",
            "from_region": fenced_source.to_dict(),
            "to_region": promoted.to_dict(),
            "epoch": promoted.cluster_epoch,
            "duration_seconds": round(duration, 4),
            "audit_continuity": audit_res,
        }

    def verify_audit_continuity(self) -> dict[str, Any]:
        """Verify the unbroken linear cryptographic hash chain in sangyan_audit_events."""
        rows = self._db.query_all(
            "SELECT * FROM sangyan_audit_events ORDER BY timestamp ASC, id ASC"
        )
        if not rows:
            return {"valid": True, "event_count": 0, "head_hash": "0" * 64}

        prev_hash = "0" * 64
        for idx, row in enumerate(rows):
            event_id = row["event_id"]
            actor = row["actor"]
            action = row["action"]
            resource = row["resource"]
            result = row["result"]
            timestamp = row["timestamp"]
            expected_stored_hash = row["ledger_hash"]

            raw_ledger = f"{prev_hash}:{event_id}:{actor}:{action}:{resource}:{result}:{timestamp}"
            calculated_hash = sha3_hex(raw_ledger.encode("utf-8"))

            if calculated_hash != expected_stored_hash:
                return {
                    "valid": False,
                    "event_count": len(rows),
                    "broken_at_index": idx,
                    "event_id": event_id,
                    "expected_hash": calculated_hash,
                    "stored_hash": expected_stored_hash,
                }
            prev_hash = calculated_hash

        return {
            "valid": True,
            "event_count": len(rows),
            "head_hash": prev_hash,
        }

    def get_cluster_status(self) -> dict[str, Any]:
        rows = self._db.query_all("SELECT * FROM sangyan_region_fencing ORDER BY cluster_epoch DESC, region_id ASC")
        records = [RegionFencingRecord.from_dict(r).to_dict() for r in rows]
        primary = next((r for r in records if r["role"] == RegionRole.PRIMARY_ACTIVE and not r["is_fenced"]), None)
        return {
            "local_region": self.region_id,
            "active_primary": primary["region_id"] if primary else None,
            "current_epoch": primary["cluster_epoch"] if primary else 0,
            "regions": records,
        }
