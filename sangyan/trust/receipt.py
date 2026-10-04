"""TrustReceipt model representing post-quantum cryptographic verification receipts."""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field

from sangyan.domain.base import new_id


@dataclass(frozen=True)
class TrustReceipt:
    """Post-quantum signature receipt binding an investigation or finding to an immutable digest."""

    subject_type: str  # "investigation", "finding", "review"
    subject_id: str
    algorithm_id: str
    public_key: bytes
    content_digest: str
    signature: bytes
    id: str = field(default_factory=lambda: new_id("rcpt"))
    created_at: float = field(default_factory=time.time)
    signing_key_id: str = "default"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "algorithm_id": self.algorithm_id,
            "public_key_b64": base64.b64encode(self.public_key).decode("ascii"),
            "content_digest": self.content_digest,
            "signature_b64": base64.b64encode(self.signature).decode("ascii"),
            "created_at": self.created_at,
            "signing_key_id": self.signing_key_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TrustReceipt":
        return cls(
            id=d.get("id") or new_id("rcpt"),
            subject_type=d["subject_type"],
            subject_id=d["subject_id"],
            algorithm_id=d["algorithm_id"],
            public_key=base64.b64decode(d["public_key_b64"]),
            content_digest=d["content_digest"],
            signature=base64.b64decode(d["signature_b64"]),
            created_at=float(d.get("created_at", time.time())),
            signing_key_id=d.get("signing_key_id", "default"),
        )
