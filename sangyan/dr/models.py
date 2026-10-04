"""Domain models and role definitions for multi-region disaster recovery and split-brain fencing."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


class RegionRole:
    PRIMARY_ACTIVE = "PRIMARY_ACTIVE"
    STANDBY_READY = "STANDBY_READY"
    DEMOTED = "DEMOTED"
    FENCED = "FENCED"

    ALL = (PRIMARY_ACTIVE, STANDBY_READY, DEMOTED, FENCED)


@dataclass
class RegionFencingRecord:
    """Relational record capturing cluster epoch, operational role, and fencing state for a region."""

    region_id: str
    cluster_epoch: int = 1
    role: str = RegionRole.STANDBY_READY
    is_fenced: bool = False
    fence_reason: Optional[str] = None
    last_heartbeat_at: float = field(default_factory=time.time)
    promoted_at: Optional[float] = None
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "cluster_epoch": self.cluster_epoch,
            "role": self.role,
            "is_fenced": self.is_fenced,
            "fence_reason": self.fence_reason,
            "last_heartbeat_at": self.last_heartbeat_at,
            "promoted_at": self.promoted_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> RegionFencingRecord:
        return cls(
            region_id=d["region_id"],
            cluster_epoch=int(d.get("cluster_epoch", 1)),
            role=d.get("role", RegionRole.STANDBY_READY),
            is_fenced=bool(d.get("is_fenced", 0)),
            fence_reason=d.get("fence_reason"),
            last_heartbeat_at=float(d.get("last_heartbeat_at", time.time())),
            promoted_at=float(d["promoted_at"]) if d.get("promoted_at") is not None else None,
            updated_at=float(d.get("updated_at", time.time())),
        )
