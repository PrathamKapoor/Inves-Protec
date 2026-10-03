"""Cryptographic trust binding tying Claims, Evidence, and Findings to ML-DSA-65 receipts."""
from __future__ import annotations

from typing import Any, Optional

from sangyan.crypto.hashing import digest_document
from sangyan.domain.models import Claim, Evidence, Finding
from sangyan.trust.receipt import TrustReceipt
from sangyan.trust.service import TrustService


class TrustBindingService:
    """Binds verification conclusions and evidence graphs to immutable ML-DSA-65 post-quantum receipts."""

    def __init__(self, trust_service: TrustService) -> None:
        self.trust_service = trust_service

    def build_verification_payload(
        self,
        finding: Finding,
        claim: Claim,
        evidence_items: list[Evidence],
    ) -> dict[str, Any]:
        """Construct deterministic canonical document representing the complete verification chain."""
        return {
            "finding_id": finding.id,
            "finding_statement": finding.statement,
            "claim_id": claim.id,
            "claim_statement": claim.statement,
            "status": finding.status,
            "rationale": finding.rationale,
            "evidence": [
                {
                    "evidence_id": e.id,
                    "source_id": e.source_id,
                    "content_hash": e.content_hash,
                    "stance": e.stance,
                }
                for e in sorted(evidence_items, key=lambda x: x.id)
            ],
            "verification_version": finding.verification_version,
            "generated_at": finding.generated_at,
        }

    def bind_finding(
        self,
        finding: Finding,
        claim: Claim,
        evidence_items: list[Evidence],
    ) -> TrustReceipt:
        """Sign canonical verification payload with ML-DSA-65 and persist TrustReceipt."""
        payload = self.build_verification_payload(finding, claim, evidence_items)
        receipt = self.trust_service.sign_document(
            subject_type="finding",
            subject_id=finding.id,
            document=payload,
        )
        return receipt

    def verify_finding_integrity(
        self,
        receipt: TrustReceipt,
        finding: Finding,
        claim: Claim,
        evidence_items: list[Evidence],
    ) -> bool:
        """Verify that the recorded receipt matches the finding and evidence without tampering."""
        payload = self.build_verification_payload(finding, claim, evidence_items)
        return self.trust_service.verify_document(receipt, payload)
