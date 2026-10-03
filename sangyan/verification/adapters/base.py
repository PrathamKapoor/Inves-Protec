"""Base interface and data transfer models for authoritative verification adapters."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from sangyan.domain.models import CLAIM_STATUSES, Claim, Entity


ADAPTER_STATUSES = (
    "verified",
    "not_found",
    "source_unavailable",
    "rate_limited",
    "invalid_request",
    "not_supported",
    "insufficient_evidence",
    "error",
)


@dataclass
class AdapterResult:
    """Individual verification outcome produced by an authoritative adapter."""

    adapter_id: str
    source_id: str
    status: str  # verified, not_found, source_unavailable, rate_limited, invalid_request, etc.
    stance: str  # SUPPORTED, CONTRADICTED, CONFLICTING, OUTDATED, INSUFFICIENT_EVIDENCE
    excerpt: str
    rationale: str
    structured_fact: dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 1.0
    retrieved_at: float = field(default_factory=time.time)
    valid_until: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.stance not in CLAIM_STATUSES:
            raise ValueError(f"Invalid verification stance '{self.stance}'. Must be one of {CLAIM_STATUSES}")
        if self.status not in ADAPTER_STATUSES:
            raise ValueError(f"Invalid adapter status '{self.status}'. Must be one of {ADAPTER_STATUSES}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "source_id": self.source_id,
            "status": self.status,
            "stance": self.stance,
            "excerpt": self.excerpt,
            "rationale": self.rationale,
            "structured_fact": self.structured_fact,
            "confidence_score": round(self.confidence_score, 4),
            "retrieved_at": self.retrieved_at,
            "valid_until": self.valid_until,
            "metadata": self.metadata,
        }


class VerificationAdapter(ABC):
    """Abstract base class for all authoritative verification adapters."""

    def __init__(self, adapter_id: str, source_id: str, allowed_domains: Optional[list[str]] = None) -> None:
        self.adapter_id = adapter_id
        self.source_id = source_id
        self.allowed_domains = set(allowed_domains or [])

    @abstractmethod
    def supports(self, claim: Claim) -> bool:
        """Determine whether this adapter has authority to verify the given claim."""
        raise NotImplementedError

    @abstractmethod
    def verify(
        self,
        claim: Claim,
        entity: Optional[Entity] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> AdapterResult:
        """Verify the claim against this authoritative source and return structured result."""
        raise NotImplementedError
