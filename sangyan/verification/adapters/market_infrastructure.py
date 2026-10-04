"""Authoritative Market Infrastructure (NSE, BSE, MCX, NSDL, CDSL) Verification Adapter."""
from __future__ import annotations

import re
import time
from typing import Any, Optional

from sangyan.domain.models import Claim, Entity
from sangyan.verification.adapters.base import AdapterResult, VerificationAdapter
from sangyan.verification.snapshots import SnapshotManager


class MarketInfrastructureVerificationAdapter(VerificationAdapter):
    """Verifies trading members, clearing members, and depository participants against market infrastructure records."""

    def __init__(self, snapshot_manager: Optional[SnapshotManager] = None) -> None:
        super().__init__(
            adapter_id="adapter_market_infrastructure",
            source_id="src_market_infrastructure",
            allowed_domains=["nseindia.com", "bseindia.com", "mcxindia.com", "nsdl.co.in", "cdslindia.com"],
        )
        self.snapshots = snapshot_manager or SnapshotManager()

    def supports(self, claim: Claim) -> bool:
        stmt = claim.statement.lower()
        return bool(
            re.search(
                r"\b(nse|bse|mcx|nsdl|cdsl|exchange\s+member|trading\s+member|clearing\s+member|depository\s+participant|dp\s*id)\b",
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

        # 1. Hard negative / Regulatory warning check
        if re.search(r"\b(nse|bse|mcx)\s+(?:warns|cautions|advises|alert)\b", stmt_lower):
            return AdapterResult(
                adapter_id=self.adapter_id,
                source_id=self.source_id,
                status="verified",
                stance="SUPPORTED",
                excerpt=stmt[:200],
                rationale="Statement reflects legitimate market infrastructure caution or warning advisory.",
                confidence_score=0.95,
                retrieved_at=now,
            )

        # 2. Identify target exchange/depository if mentioned
        exchange_hint: Optional[str] = None
        for ex in ["NSE", "BSE", "MCX", "NSDL", "CDSL"]:
            if re.search(r"\b" + ex.lower() + r"\b", stmt_lower):
                exchange_hint = ex
                break

        # 3. Extract member ID or DP ID if present
        member_id: Optional[str] = None
        # DP ID pattern (e.g. IN-DP-431-2019, IN-DP-CDSL-01-1999)
        dp_match = re.search(r"\b(IN[\s\-]?DP[\s\-]?[A-Z0-9\-]+)\b", stmt, re.I)
        if dp_match:
            member_id = re.sub(r"[\s]", "", dp_match.group(1)).upper()
        else:
            # Numeric member ID pattern with explicit keyword
            mem_match = re.search(r"\b(?:member\s*(?:id|no\.?)|id|code)\s*[:\-]?\s*([0-9]{3,6})\b", stmt, re.I)
            if mem_match:
                member_id = mem_match.group(1).strip()


        # 4. If explicit member/DP ID claimed, check authoritative record
        if member_id:
            rec = self.snapshots.lookup_market_infrastructure_member(member_id, exchange=exchange_hint)
            if rec:
                status = rec.get("status", "UNKNOWN").upper()
                ex_name = rec.get("exchange", "Exchange")
                valid_until = rec.get("valid_until")

                if status in {"EXPELLED", "EXPELLED_DEFAULTER", "DEFAULTER", "SUSPENDED"}:
                    reason = rec.get("expulsion_reason") or rec.get("suspension_reason", f"Status is {status}")
                    return AdapterResult(
                        adapter_id=self.adapter_id,
                        source_id=self.source_id,
                        status="verified",
                        stance="CONTRADICTED",
                        excerpt=f"{ex_name} member {member_id} is {status}. Details: {reason}.",
                        rationale=(
                            f"Authoritative {ex_name} records confirm that member {member_id} ('{rec.get('entity_name')}') "
                            f"is {status}. Action details: {reason}."
                        ),
                        structured_fact=rec,
                        confidence_score=0.99,
                        retrieved_at=now,
                        valid_until=valid_until,
                    )

                if valid_until and valid_until < now:
                    return AdapterResult(
                        adapter_id=self.adapter_id,
                        source_id=self.source_id,
                        status="verified",
                        stance="OUTDATED",
                        excerpt=f"{ex_name} membership {member_id} for '{rec.get('entity_name')}' expired on {time.strftime('%Y-%m-%d', time.gmtime(valid_until))}.",
                        rationale=(
                            f"The membership {member_id} is recorded in {ex_name} directories but expired on "
                            f"{time.strftime('%Y-%m-%d', time.gmtime(valid_until))}. It is no longer currently active."
                        ),
                        structured_fact=rec,
                        confidence_score=0.98,
                        retrieved_at=now,
                        valid_until=valid_until,
                    )

                if status == "ACTIVE":
                    return AdapterResult(
                        adapter_id=self.adapter_id,
                        source_id=self.source_id,
                        status="verified",
                        stance="SUPPORTED",
                        excerpt=f"Active {ex_name} member {member_id}: {rec.get('entity_name')} ({rec.get('category')}).",
                        rationale=(
                            f"Verified against {ex_name} directory: '{rec.get('entity_name')}' holds active "
                            f"membership {member_id} under category '{rec.get('category')}'."
                        ),
                        structured_fact=rec,
                        confidence_score=0.99,
                        retrieved_at=now,
                        valid_until=valid_until,
                    )


            # Claimed a member/DP ID that does not exist in authoritative records
            return AdapterResult(
                adapter_id=self.adapter_id,
                source_id=self.source_id,
                status="not_found",
                stance="CONTRADICTED",
                excerpt=f"Membership identifier '{member_id}' not found in market infrastructure directory.",
                rationale=(
                    f"Claim asserted {exchange_hint or 'exchange'} membership identifier '{member_id}', but no matching "
                    f"member or depository participant exists in authoritative infrastructure directories."
                ),
                structured_fact={"claimed_member_id": member_id, "exchange": exchange_hint},
                confidence_score=0.95,
                retrieved_at=now,
            )

        # 5. Lookup by legal / trade name if entity or known broker mentioned
        name_to_check = entity.name if entity else None
        if not name_to_check:
            for known in ["zerodha", "groww", "angel one", "karvy"]:
                if known in stmt_lower:
                    name_to_check = known
                    break

        if name_to_check:
            rec = self.snapshots.lookup_market_infrastructure_member(name_to_check, exchange=exchange_hint)
            if rec:
                status = rec.get("status", "UNKNOWN").upper()
                ex_name = rec.get("exchange", "Exchange")
                if status == "ACTIVE":
                    return AdapterResult(
                        adapter_id=self.adapter_id,
                        source_id=self.source_id,
                        status="verified",
                        stance="SUPPORTED",
                        excerpt=f"Found active {ex_name} member: {rec.get('entity_name')} (ID: {rec.get('member_id')}).",
                        rationale=f"Matched active member '{rec.get('entity_name')}' on {ex_name} with member ID {rec.get('member_id')}.",
                        structured_fact=rec,
                        confidence_score=0.90,
                        retrieved_at=now,
                        valid_until=rec.get("valid_until"),
                    )
                if status in {"EXPELLED", "EXPELLED_DEFAULTER", "SUSPENDED"}:
                    reason = rec.get("expulsion_reason") or rec.get("suspension_reason", f"Status is {status}")
                    return AdapterResult(
                        adapter_id=self.adapter_id,
                        source_id=self.source_id,
                        status="verified",
                        stance="CONTRADICTED",
                        excerpt=f"Entity '{rec.get('entity_name')}' is {status} on {ex_name}. Reason: {reason}.",
                        rationale=(
                            f"Authoritative {ex_name} records indicate that entity '{rec.get('entity_name')}' "
                            f"was {status} and is barred from market operations. Reason: {reason}."
                        ),
                        structured_fact=rec,
                        confidence_score=0.98,
                        retrieved_at=now,
                    )

        # 6. Insufficient evidence
        return AdapterResult(
            adapter_id=self.adapter_id,
            source_id=self.source_id,
            status="insufficient_evidence",
            stance="INSUFFICIENT_EVIDENCE",
            excerpt=stmt[:200],
            rationale="No verifiable exchange membership ID or recognized market participant was identified in the claim.",
            confidence_score=0.50,
            retrieved_at=now,
        )
