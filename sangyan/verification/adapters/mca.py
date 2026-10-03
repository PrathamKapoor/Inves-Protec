"""Authoritative Ministry of Corporate Affairs (MCA) CIN Verification Adapter."""
from __future__ import annotations

import re
import time
from typing import Any, Optional

from sangyan.domain.models import Claim, Entity
from sangyan.verification.adapters.base import AdapterResult, VerificationAdapter
from sangyan.verification.snapshots import SnapshotManager


class MCAVerificationAdapter(VerificationAdapter):
    """Verifies corporate identity numbers (CIN) and legal status against MCA records."""

    def __init__(self, snapshot_manager: Optional[SnapshotManager] = None) -> None:
        super().__init__(
            adapter_id="adapter_mca_registry",
            source_id="src_mca_registry",
            allowed_domains=["mca.gov.in", "www.mca.gov.in"],
        )
        self.snapshots = snapshot_manager or SnapshotManager()

    def supports(self, claim: Claim) -> bool:
        stmt = claim.statement.lower()
        return bool(
            re.search(r"\b(cin|mca|incorporated|pvt\.?\s*ltd|limited|llp|[lu][0-9]{5}[a-z]{2}[0-9]{4}[a-z]{3}[0-9]{6})\b", stmt)
        )

    def verify(
        self,
        claim: Claim,
        entity: Optional[Entity] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> AdapterResult:
        now = time.time()
        stmt = claim.statement

        # Extract CIN
        cin: Optional[str] = None
        if entity and entity.registration_number and re.match(r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$", entity.registration_number, re.I):
            cin = entity.registration_number.upper()
        else:
            match = re.search(r"\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b", stmt, re.I)
            if match:
                cin = match.group(1).upper()

        if cin:
            record = self.snapshots.lookup_mca_cin(cin)
            if record:
                status = record.get("status", "UNKNOWN").upper()
                if status == "ACTIVE":
                    return AdapterResult(
                        adapter_id=self.adapter_id,
                        source_id=self.source_id,
                        status="verified",
                        stance="SUPPORTED",
                        excerpt=f"Active company {cin}: {record.get('company_name')} ({record.get('class')}).",
                        rationale=(
                            f"Verified against MCA Company Master Data: '{record.get('company_name')}' holds active "
                            f"registration under CIN {cin} in state of {record.get('registered_state')}."
                        ),
                        structured_fact=record,
                        confidence_score=0.98,
                        retrieved_at=now,
                    )
                if status in {"STRUCK_OFF", "DORMANT", "UNDER_LIQUIDATION"}:
                    return AdapterResult(
                        adapter_id=self.adapter_id,
                        source_id=self.source_id,
                        status="verified",
                        stance="OUTDATED",
                        excerpt=f"Company with CIN {cin} is {status}.",
                        rationale=(
                            f"Authoritative MCA records show company '{record.get('company_name')}' under CIN {cin} "
                            f"is currently {status} and not authorized for active commercial operations."
                        ),
                        structured_fact=record,
                        confidence_score=0.98,
                        retrieved_at=now,
                    )

            return AdapterResult(
                adapter_id=self.adapter_id,
                source_id=self.source_id,
                status="not_found",
                stance="CONTRADICTED",
                excerpt=f"CIN '{cin}' not found in MCA company master data.",
                rationale=f"Claim asserted corporate CIN '{cin}', but no matching company is registered with the Ministry of Corporate Affairs.",
                structured_fact={"claimed_cin": cin},
                confidence_score=0.95,
                retrieved_at=now,
            )

        return AdapterResult(
            adapter_id=self.adapter_id,
            source_id=self.source_id,
            status="insufficient_evidence",
            stance="INSUFFICIENT_EVIDENCE",
            excerpt=stmt[:200],
            rationale="No verifiable Corporate Identity Number (CIN) was provided to confirm MCA registration.",
            confidence_score=0.50,
            retrieved_at=now,
        )
