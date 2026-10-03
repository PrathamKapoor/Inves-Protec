"""Authoritative Official Financial Domain and Lookalike Verification Adapter."""
from __future__ import annotations

import re
import time
from typing import Any, Optional
from urllib.parse import urlparse

from sangyan.domain.models import Claim, Entity
from sangyan.verification.adapters.base import AdapterResult, VerificationAdapter
from sangyan.verification.snapshots import SnapshotManager


class OfficialDomainsVerificationAdapter(VerificationAdapter):
    """Verifies claimed web domains and URLs against official directories and known lookalike registries."""

    def __init__(self, snapshot_manager: Optional[SnapshotManager] = None) -> None:
        super().__init__(
            adapter_id="adapter_official_domains",
            source_id="src_official_domains",
            allowed_domains=["sebi.gov.in", "nseindia.com", "bseindia.com", "rbi.org.in"],
        )
        self.snapshots = snapshot_manager or SnapshotManager()

    def supports(self, claim: Claim) -> bool:
        stmt = claim.statement.lower()
        return bool(
            re.search(r"(?:https?://|\b[a-zA-Z0-9_\-]+\.(?:com|in|org|gov\.in|cc|top|vip|xyz|live|net|io|link)\b)", stmt)
        )

    def verify(
        self,
        claim: Claim,
        entity: Optional[Entity] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> AdapterResult:
        now = time.time()
        stmt = claim.statement

        # Collect all domain candidates from entity and statement
        candidates: list[str] = []
        if entity and entity.official_url:
            h = self._extract_hostname(entity.official_url)
            if h and h not in candidates:
                candidates.append(h)

        # Match all URLs in statement
        for url_match in re.finditer(r"https?://([^\s/$.?#][^\s/]*)", stmt):
            h = self._extract_hostname(url_match.group(0))
            if h and h not in candidates:
                candidates.append(h)

        # Match all bare domains in statement
        for domain_match in re.finditer(r"\b([a-zA-Z0-9\-]+\.(?:com|in|org|gov\.in|cc|top|vip|xyz|live|net|io|link|fit|work|click))\b", stmt, re.I):
            d = domain_match.group(1).lower().strip().rstrip(".")
            if d and d not in candidates:
                candidates.append(d)

        if not candidates:
            return AdapterResult(
                adapter_id=self.adapter_id,
                source_id=self.source_id,
                status="insufficient_evidence",
                stance="INSUFFICIENT_EVIDENCE",
                excerpt=stmt[:200],
                rationale="No verifiable financial domain or URL was identified in the claim.",
                confidence_score=0.50,
                retrieved_at=now,
            )

        # 1. Adversarial / Malicious Check: Look for phishing lookalikes or suspicious TLDs across ALL candidates
        for dom in candidates:
            rec = self.snapshots.lookup_official_domain(dom)
            if rec:
                rep = rec.get("reputation", "").upper()
                if rep == "MALICIOUS" or rec.get("category") == "PHISHING_LOOKALIKE":
                    impersonated = rec.get("impersonated_domain", "registered entity")
                    return AdapterResult(
                        adapter_id=self.adapter_id,
                        source_id=self.source_id,
                        status="verified",
                        stance="CONTRADICTED",
                        excerpt=f"Malicious lookalike domain: {dom} impersonating {impersonated}.",
                        rationale=(
                            f"Domain '{dom}' is an identified deceptive lookalike domain engaged in "
                            f"unauthorized impersonation of '{impersonated}'."
                        ),
                        structured_fact=rec,
                        confidence_score=0.98,
                        retrieved_at=now,
                    )

            # Heuristic check for high-risk suspicious TLDs
            if re.search(r"\.(?:top|vip|cc|xyz|click|work|link)$", dom):
                return AdapterResult(
                    adapter_id=self.adapter_id,
                    source_id=self.source_id,
                    status="verified",
                    stance="CONTRADICTED",
                    excerpt=f"Unregistered high-risk infrastructure domain: {dom}.",
                    rationale=(
                        f"Domain '{dom}' utilizes a high-risk non-standard TLD not recognized as official "
                        f"infrastructure by statutory regulators or recognized market intermediaries."
                    ),
                    structured_fact={"domain": dom, "reputation": "SUSPICIOUS_TLD"},
                    confidence_score=0.85,
                    retrieved_at=now,
                )

        # 2. Official Domain Verification: Check if all candidates are verified official
        official_records = []
        for dom in candidates:
            rec = self.snapshots.lookup_official_domain(dom)
            if rec and rec.get("reputation", "").upper() == "OFFICIAL":
                official_records.append((dom, rec))

        if official_records and len(official_records) == len(candidates):
            dom, rec = official_records[0]
            return AdapterResult(
                adapter_id=self.adapter_id,
                source_id=self.source_id,
                status="verified",
                stance="SUPPORTED",
                excerpt=f"Verified official domain: {dom} ({rec.get('canonical_name')}).",
                rationale=(
                    f"Domain '{dom}' is registered in authoritative directories as the official "
                    f"web portal of '{rec.get('canonical_name')}'."
                ),
                structured_fact=rec,
                confidence_score=0.99,
                retrieved_at=now,
            )

        return AdapterResult(
            adapter_id=self.adapter_id,
            source_id=self.source_id,
            status="insufficient_evidence",
            stance="INSUFFICIENT_EVIDENCE",
            excerpt=stmt[:200],
            rationale="Domain could not be definitively matched against official directory or lookalike blacklists.",
            confidence_score=0.50,
            retrieved_at=now,
        )

    def _extract_hostname(self, url_or_host: str) -> str:
        url_or_host = url_or_host.strip().lower().rstrip(".")
        if "://" not in url_or_host:
            url_or_host = "https://" + url_or_host
        try:
            parsed = urlparse(url_or_host)
            host = parsed.hostname or url_or_host
            if ":" in host:
                host = host.split(":")[0]
            return host.rstrip(".")
        except Exception:
            return url_or_host.rstrip(".")
