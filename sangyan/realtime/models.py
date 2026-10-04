"""Domain models for real-time investigation event streaming."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class InvestigationEventType(str, Enum):
    """Lifecycle event types emitted during investigation processing."""

    INVESTIGATION_STARTED = "INVESTIGATION_STARTED"
    INTAKE_STARTED = "INTAKE_STARTED"
    INTAKE_COMPLETED = "INTAKE_COMPLETED"
    INTELLIGENCE_STARTED = "INTELLIGENCE_STARTED"
    INTELLIGENCE_COMPLETED = "INTELLIGENCE_COMPLETED"
    VERIFICATION_STARTED = "VERIFICATION_STARTED"
    VERIFICATION_COMPLETED = "VERIFICATION_COMPLETED"
    CORRELATION_STARTED = "CORRELATION_STARTED"
    CORRELATION_COMPLETED = "CORRELATION_COMPLETED"
    SCAM_CHAIN_STARTED = "SCAM_CHAIN_STARTED"
    SCAM_CHAIN_COMPLETED = "SCAM_CHAIN_COMPLETED"
    GUIDANCE_STARTED = "GUIDANCE_STARTED"
    GUIDANCE_COMPLETED = "GUIDANCE_COMPLETED"
    EXPLANATION_STARTED = "EXPLANATION_STARTED"
    EXPLANATION_COMPLETED = "EXPLANATION_COMPLETED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REVIEW_SUBMITTED = "REVIEW_SUBMITTED"
    REVIEW_RESUMED = "REVIEW_RESUMED"
    TRUST_FINALIZATION_STARTED = "TRUST_FINALIZATION_STARTED"
    TRUST_FINALIZATION_COMPLETED = "TRUST_FINALIZATION_COMPLETED"
    INVESTIGATION_COMPLETED = "INVESTIGATION_COMPLETED"
    INVESTIGATION_FAILED = "INVESTIGATION_FAILED"
    HEARTBEAT = "HEARTBEAT"


@dataclass(frozen=True)
class InvestigationEvent:
    """An immutable, sequenced event representing progress in an investigation."""

    event_id: str
    investigation_id: str
    organization_id: str
    event_type: str
    sequence: int
    timestamp: float = field(default_factory=time.time)
    node_name: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "event_id": self.event_id,
            "investigation_id": self.investigation_id,
            "organization_id": self.organization_id,
            "event_type": str(self.event_type),
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "node_name": self.node_name,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> InvestigationEvent:
        """Construct event from dictionary."""
        payload = data.get("payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        return cls(
            event_id=str(data["event_id"]),
            investigation_id=str(data["investigation_id"]),
            organization_id=str(data["organization_id"]),
            event_type=str(data["event_type"]),
            sequence=int(data["sequence"]),
            timestamp=float(data.get("timestamp", time.time())),
            node_name=data.get("node_name"),
            payload=payload,
        )

    def to_sse_message(self) -> str:
        """Format event as standard Server-Sent Events (SSE) wire protocol packet."""
        data_json = json.dumps(self.to_dict(), separators=(",", ":"))
        return f"id: {self.event_id}\nevent: {self.event_type}\ndata: {data_json}\n\n"
