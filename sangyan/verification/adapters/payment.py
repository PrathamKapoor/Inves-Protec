"""Authoritative UPI and Payment Identifier Verification Adapter."""
from __future__ import annotations

import re
import time
from typing import Any, Optional

from sangyan.domain.models import Claim, Entity
from sangyan.verification.adapters.base import AdapterResult, VerificationAdapter
from sangyan.verification.snapshots import SnapshotManager


class UPIPaymentVerificationAdapter(VerificationAdapter):
    """Verifies UPI Virtual Payment Addresses (VPAs) and corporate payment destination compliance."""

    def __init__(self, snapshot_manager: Optional[SnapshotManager] = None) -> None:
        super().__init__(
            adapter_id="adapter_upi_payment",
            source_id="src_upis_official",
            allowed_domains=["npci.org.in", "sebi.gov.in"],
        )
        self.snapshots = snapshot_manager or SnapshotManager()

    def supports(self, claim: Claim) -> bool:
        if claim.claim_type == "payment":
            return True
        stmt = claim.statement.lower()
        return bool(
            re.search(
                r"(?:[a-zA-Z0-9.\-_]{2,64}@[a-zA-Z]{2,32}|\b(?:upi|vpa|gpay|phonepe|paytm|deposit\s+money|send\s+payment|account\s+transfer)\b)",
                stmt,
            )
        )

    def verify(
        self,
        claim: Claim,
        entity: Optional[Entity] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> AdapterResult:
        now = time.time()
        stmt = claim.statement
        stmt_lower = stmt.lower()

        # 1. Collect candidate VPAs from entity and statement
        candidates: list[str] = []
        if entity and entity.entity_type == "upi_vpa" and entity.registration_number:
            candidates.append(entity.registration_number.strip().lower())

        for vpa_match in re.finditer(r"\b([a-zA-Z0-9.\-_]{2,64}@[a-zA-Z]{2,32})\b", stmt):
            v = vpa_match.group(1).strip().lower()
            if v not in candidates:
                candidates.append(v)

        if not candidates:
            return AdapterResult(
                adapter_id=self.adapter_id,
                source_id=self.source_id,
                status="insufficient_evidence",
                stance="INSUFFICIENT_EVIDENCE",
                excerpt=stmt[:200],
                rationale="No verifiable UPI Virtual Payment Address (VPA) was identified in the claim.",
                confidence_score=0.50,
                retrieved_at=now,
            )

        # 2. Check each candidate VPA
        for vpa in candidates:
            rec = self.snapshots.lookup_upi_vpa(vpa)

            # Check 2a: Flagged fraudulent or scam VPA
            if rec and rec.get("status") == "FLAGGED_FRAUDULENT":
                warning = rec.get("warning", "Reported fraudulent payment handle")
                return AdapterResult(
                    adapter_id=self.adapter_id,
                    source_id=self.source_id,
                    status="verified",
                    stance="CONTRADICTED",
                    excerpt=f"Flagged fraudulent payment destination: {vpa}. Warning: {warning}.",
                    rationale=(
                        f"The payment identifier '{vpa}' is listed in official fraud alerts as an unauthorized or "
                        f"deceptive collection handle. Warning: {warning}."
                    ),
                    structured_fact=rec,
                    confidence_score=0.99,
                    retrieved_at=now,
                )

            # Check 2b: Verified official corporate VPA
            if rec and rec.get("status") == "ACTIVE" and rec.get("vpa_type") == "OFFICIAL_CORPORATE":
                canonical = rec.get("canonical_name", "Registered Intermediary")
                return AdapterResult(
                    adapter_id=self.adapter_id,
                    source_id=self.source_id,
                    status="verified",
                    stance="SUPPORTED",
                    excerpt=f"Verified corporate payment destination: {vpa} belonging to {canonical}.",
                    rationale=(
                        f"The payment destination '{vpa}' matches the verified official corporate account of "
                        f"statutory registered intermediary '{canonical}'."
                    ),
                    structured_fact=rec,
                    confidence_score=0.99,
                    retrieved_at=now,
                )

            # Check 2c: Corporate Mismatch Detection (Claim asserts registered broker, but payment is to a personal VPA)
            claimed_broker_present = any(
                broker in stmt_lower
                for broker in ["zerodha", "groww", "angel one", "angelone", "upstox", "icici direct", "sebi"]
            )
            is_personal = self.snapshots.is_personal_vpa_pattern(vpa)
            if claimed_broker_present and (is_personal or (rec is None and "@" in vpa)):
                # If content mentions a registered broker/authority but asks to pay to an unverified or personal VPA
                matched_broker = next(
                    b for b in ["zerodha", "groww", "angel one", "angelone", "upstox", "icici direct", "sebi"] if b in stmt_lower
                )
                return AdapterResult(
                    adapter_id=self.adapter_id,
                    source_id=self.source_id,
                    status="verified",
                    stance="CONTRADICTED",
                    excerpt=f"Payment destination mismatch: Content mentions {matched_broker.title()} but directs payment to '{vpa}'.",
                    rationale=(
                        f"Payment destination mismatch: Claim mentions recognized financial entity '{matched_broker.title()}', but instructs payment to "
                        f"unverified personal handle '{vpa}'. SEBI regulations strictly prohibit registered intermediaries "
                        f"from collecting client funds through personal third-party accounts or unauthorized VPAs."
                    ),

                    structured_fact={"claimed_entity": matched_broker, "destination_vpa": vpa, "mismatch": True},
                    confidence_score=0.95,
                    retrieved_at=now,
                )

        # 3. Unverified VPA with no contradiction: INSUFFICIENT_EVIDENCE
        # As mandated by Section 34 of the prompt:
        # "Do not declare fraud solely because a payment identifier cannot be verified. Use INSUFFICIENT_EVIDENCE where appropriate."
        return AdapterResult(
            adapter_id=self.adapter_id,
            source_id=self.source_id,
            status="insufficient_evidence",
            stance="INSUFFICIENT_EVIDENCE",
            excerpt=f"Unregistered payment handle: {candidates[0]}.",
            rationale=(
                f"The payment handle '{candidates[0]}' could not be corroborated against authoritative merchant registers. "
                f"Absence of an institutional directory record is insufficient to establish fraud or regulatory compliance."
            ),
            structured_fact={"candidate_vpas": candidates},
            confidence_score=0.50,
            retrieved_at=now,
        )
