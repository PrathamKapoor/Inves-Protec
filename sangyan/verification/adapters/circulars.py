"""Authoritative Regulatory Circulars & Prohibited Practices Verification Adapter."""
from __future__ import annotations

import re
import time
from typing import Any, Optional

from sangyan.domain.models import Claim, Entity
from sangyan.verification.adapters.base import AdapterResult, VerificationAdapter
from sangyan.verification.snapshots import SnapshotManager


class CircularsVerificationAdapter(VerificationAdapter):
    """Verifies return promises, credential solicitations, and payment practices against statutory prohibitions."""

    def __init__(self, snapshot_manager: Optional[SnapshotManager] = None) -> None:
        super().__init__(
            adapter_id="adapter_sebi_circulars",
            source_id="src_sebi_circulars",
            allowed_domains=["sebi.gov.in", "www.sebi.gov.in"],
        )
        self.snapshots = snapshot_manager or SnapshotManager()

    def supports(self, claim: Claim) -> bool:
        if claim.claim_type in {"return", "payment", "urgency"}:
            return True
        stmt = claim.statement.lower()
        return bool(
            re.search(
                r"\b(guarantee|guaranteed|fixed\s+return|100%|risk[- ]free|loss\s+recovery|otp|password|withdrawal\s+fee|tax\s+to\s+withdraw)\b",
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

        # Hard negative check: Is this an advisory or educational disclaimer?
        # e.g., "Investments are subject to market risks; past performance does not guarantee future results."
        if "subject to market risks" in stmt_lower or "past performance is not" in stmt_lower or "not guaranteed" in stmt_lower:
            return AdapterResult(
                adapter_id=self.adapter_id,
                source_id=self.source_id,
                status="verified",
                stance="SUPPORTED",
                excerpt=stmt[:200],
                rationale="Statement conforms to standard statutory risk disclosures mandated by SEBI regulations.",
                confidence_score=0.98,
                retrieved_at=now,
            )

        # Prohibited Practice 1: Guaranteed / Fixed / Assured returns
        if re.search(r"\b(guarantee[ds]?|100%\s+guarantee|fixed\s+return|assured\s+return|zero\s+risk|loss[- ]proof|pakka\s+profit)\b", stmt_lower):
            circular = self.snapshots.lookup_prohibited_practice("guaranteed return promise")
            circular_info = circular[0] if circular else {
                "circular_no": "SEBI/HO/MIRSD/MIRSD-PoD-1/P/CIR/2023/24",
                "title": "Advisory against entities offering guaranteed or assured returns",
            }
            return AdapterResult(
                adapter_id=self.adapter_id,
                source_id=self.source_id,
                status="verified",
                stance="CONTRADICTED",
                excerpt=f"Prohibited under {circular_info.get('circular_no')}: Offering guaranteed/fixed returns is unlawful.",
                rationale=(
                    f"Claim promises guaranteed or fixed investment returns, which directly violates SEBI Circular "
                    f"'{circular_info.get('circular_no')}'. Statutory regulations strictly prohibit any entity "
                    f"from offering assured returns or capital guarantees in the securities market."
                ),
                structured_fact=circular_info,
                confidence_score=0.99,
                retrieved_at=now,
            )

        # Prohibited Practice 2: Demanding OTP or private credentials
        if re.search(r"\b(otp|share\s+password|demat\s+login|trading\s+pin|anydesk|teamviewer)\b", stmt_lower):
            circular = self.snapshots.lookup_prohibited_practice("otp sharing request")
            circular_info = circular[0] if circular else {
                "circular_no": "SEBI/HO/ISD/ISD/CIR/P/2020/0001",
                "title": "Prohibition on collection of client trading credentials and OTPs",
            }
            return AdapterResult(
                adapter_id=self.adapter_id,
                source_id=self.source_id,
                status="verified",
                stance="CONTRADICTED",
                excerpt=f"Prohibited under {circular_info.get('circular_no')}: Intermediaries may never solicit OTPs or credentials.",
                rationale=(
                    f"Soliciting OTPs, client trading passwords, or remote desktop control violates SEBI Circular "
                    f"'{circular_info.get('circular_no')}'. Registered brokers are legally barred from seeking credentials."
                ),
                structured_fact=circular_info,
                confidence_score=0.99,
                retrieved_at=now,
            )

        # Prohibited Practice 3: Demanding advance fee or tax to release funds
        if re.search(r"\b(withdrawal\s+fee|pay\s+tax\s+to\s+withdraw|unlock\s+profit|gas\s+fee)\b", stmt_lower):
            circular = self.snapshots.lookup_prohibited_practice("withdrawal fee demand")
            circular_info = circular[0] if circular else {
                "circular_no": "SEBI/PR/2024/18",
                "title": "Caution against unauthorized trading platforms and fee demands",
            }
            return AdapterResult(
                adapter_id=self.adapter_id,
                source_id=self.source_id,
                status="verified",
                stance="CONTRADICTED",
                excerpt=f"Identified as unauthorized fee demand under {circular_info.get('circular_no')}.",
                rationale=(
                    f"Demanding advance taxes or processing fees to release profits is a recognized fraudulent pattern "
                    f"cautioned against by SEBI advisory '{circular_info.get('circular_no')}'. Legitimate brokers settle "
                    f"taxes via standard automated withholding and never require upfront deposits to release client funds."
                ),
                structured_fact=circular_info,
                confidence_score=0.98,
                retrieved_at=now,
            )

        return AdapterResult(
            adapter_id=self.adapter_id,
            source_id=self.source_id,
            status="insufficient_evidence",
            stance="INSUFFICIENT_EVIDENCE",
            excerpt=stmt[:200],
            rationale="No relevant statutory circular or prohibition was matched for this claim.",
            confidence_score=0.50,
            retrieved_at=now,
        )
