"""Authoritative SEBI Intermediary Registry Verification Adapter."""
from __future__ import annotations

import re
import time
from typing import Any, Optional

from sangyan.domain.models import Claim, Entity
from sangyan.verification.adapters.base import AdapterResult, VerificationAdapter
from sangyan.verification.snapshots import SnapshotManager


class SEBIVerificationAdapter(VerificationAdapter):
    """Verifies intermediary registrations, brokers, and advisers against SEBI authoritative records."""

    def __init__(self, snapshot_manager: Optional[SnapshotManager] = None) -> None:
        super().__init__(
            adapter_id="adapter_sebi_intermediaries",
            source_id="src_sebi_intermediaries",
            allowed_domains=["sebi.gov.in", "www.sebi.gov.in"],
        )
        self.snapshots = snapshot_manager or SnapshotManager()

    def supports(self, claim: Claim) -> bool:
        """Supports claims touching regulatory registrations, licensed status, or SEBI authority."""
        if claim.claim_type == "regulatory":
            return True
        stmt = claim.statement.lower()
        return bool(
            re.search(r"\b(sebi|registered|registration|reg\.?\s*no|broker|adviser|analyst|inz|ina|inh)\b", stmt)
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

        # 1. Hard Negative Check: Is this a regulatory warning report?
        # e.g., "SEBI warns that ABC Wealth is not registered"
        if "sebi warns" in stmt_lower or "sebi caution" in stmt_lower or "sebi alert" in stmt_lower:
            return AdapterResult(
                adapter_id=self.adapter_id,
                source_id=self.source_id,
                status="verified",
                stance="SUPPORTED",
                excerpt=stmt[:200],
                rationale="Statement reflects legitimate regulatory caution/warning published by statutory authority.",
                confidence_score=0.95,
                retrieved_at=now,
            )

        # 2. Extract candidate SEBI registration number from statement or entity
        reg_no: Optional[str] = None
        stmt_match = re.search(r"\b(IN[ZAHPM][\s\-]?[0-9]{8,10})\b", stmt, re.IGNORECASE)
        if stmt_match:
            reg_no = re.sub(r"[\s\-]", "", stmt_match.group(1)).upper()
        elif entity and entity.registration_number:
            reg_no = re.sub(r"[\s\-]", "", entity.registration_number).upper()

        # 3. Lookup by registration number if available
        if reg_no:
            record = self.snapshots.lookup_sebi_registration(reg_no)
            if record:
                rec_status = record.get("status", "UNKNOWN").upper()
                valid_until = record.get("valid_until")

                # Temporal check: Has the registration expired?
                if valid_until and valid_until < now:
                    return AdapterResult(
                        adapter_id=self.adapter_id,
                        source_id=self.source_id,
                        status="verified",
                        stance="OUTDATED",
                        excerpt=f"Registration {reg_no} for '{record.get('entity_name')}' expired on {time.strftime('%Y-%m-%d', time.gmtime(valid_until))}.",
                        rationale=(
                            f"The registration {reg_no} exists in SEBI records but expired on "
                            f"{time.strftime('%Y-%m-%d', time.gmtime(valid_until))}. It is no longer currently active."
                        ),
                        structured_fact=record,
                        confidence_score=0.98,
                        retrieved_at=now,
                        valid_until=valid_until,
                    )

                if rec_status == "ACTIVE":
                    return AdapterResult(
                        adapter_id=self.adapter_id,
                        source_id=self.source_id,
                        status="verified",
                        stance="SUPPORTED",
                        excerpt=f"Active registration {reg_no}: {record.get('entity_name')} ({record.get('category')}).",
                        rationale=(
                            f"Verified against SEBI authoritative registry: '{record.get('entity_name')}' holds active "
                            f"registration {reg_no} in category '{record.get('category')}'."
                        ),
                        structured_fact=record,
                        confidence_score=0.99,
                        retrieved_at=now,
                        valid_until=valid_until,
                    )

                if rec_status in {"CANCELLED", "SUSPENDED", "EXPIRED"}:
                    reason = record.get("cancellation_reason", f"Registration is {rec_status}")
                    return AdapterResult(
                        adapter_id=self.adapter_id,
                        source_id=self.source_id,
                        status="verified",
                        stance="CONTRADICTED",
                        excerpt=f"Registration {reg_no} is {rec_status}. Reason: {reason}.",
                        rationale=(
                            f"Authoritative SEBI records indicate that registration {reg_no} is currently {rec_status}. "
                            f"Details: {reason}."
                        ),
                        structured_fact=record,
                        confidence_score=0.98,
                        retrieved_at=now,
                        valid_until=valid_until,
                    )

            # Registration number explicitly claimed, but NOT found in authoritative registry
            return AdapterResult(
                adapter_id=self.adapter_id,
                source_id=self.source_id,
                status="not_found",
                stance="CONTRADICTED",
                excerpt=f"Registration number '{reg_no}' not found in SEBI registry.",
                rationale=(
                    f"Claim asserted SEBI registration number '{reg_no}', but no matching record exists in the "
                    f"authoritative SEBI Intermediaries Registry."
                ),
                structured_fact={"claimed_registration_number": reg_no},
                confidence_score=0.95,
                retrieved_at=now,
            )

        # 4. Lookup by entity name if entity name is provided or extractable
        name_to_check = entity.name if entity else None
        if not name_to_check:
            # Try to see if known broker names appear in the statement
            for known in ["zerodha", "groww", "angel one", "icici direct", "upstox"]:
                if known in stmt_lower:
                    name_to_check = known
                    break

        if name_to_check:
            record = self.snapshots.lookup_sebi_entity_by_name(name_to_check)
            if record:
                return AdapterResult(
                    adapter_id=self.adapter_id,
                    source_id=self.source_id,
                    status="verified",
                    stance="SUPPORTED",
                    excerpt=f"Found SEBI registered entity: {record.get('entity_name')} ({record.get('registration_number')}).",
                    rationale=(
                        f"Matched legal entity '{record.get('entity_name')}' with valid SEBI registration "
                        f"{record.get('registration_number')}."
                    ),
                    structured_fact=record,
                    confidence_score=0.90,
                    retrieved_at=now,
                    valid_until=record.get("valid_until"),
                )

        # 5. No specific identifier found; lack of evidence does not mean contradicted
        return AdapterResult(
            adapter_id=self.adapter_id,
            source_id=self.source_id,
            status="insufficient_evidence",
            stance="INSUFFICIENT_EVIDENCE",
            excerpt=stmt[:200],
            rationale=(
                "No verifiable SEBI registration number or recognized registered intermediary was identified. "
                "Authoritative evidence is insufficient to verify or refute regulatory status."
            ),
            confidence_score=0.50,
            retrieved_at=now,
        )
