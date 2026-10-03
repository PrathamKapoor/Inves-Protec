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

        # Extract domain candidate
        candidate_domain: Optional[str] = None
        if entity and entity.official_url:
            candidate_domain = self._extract_hostname(entity.official_url)
        if not candidate_domain:
            # Match URL or domain in statement
            match = re.search(r"https?://([^\s/$.?#].[^\s/]*)", stmt)
            if match:
                candidate_domain = self._extract_hostname(match.group(0))
            else:
                domain_match = re.search(r"\b([a-zA-Z0-9\-]+\.(?:com|in|org|gov\.in|cc|top|vip|xyz|net|io))\b", stmt, re.I)
                if domain_match:
                    candidate_domain = domain_match.group(1).lower()

        if candidate_domain:
            record = self.snapshots.lookup_official_domain(candidate_domain)
            if record:
                rep = record.get("reputation", "").upper()
                if rep == "OFFICIAL":
                    return AdapterResult(
                        adapter_id=self.adapter_id,
                        source_id=self.source_id,
                        status="verified",
                        stance="SUPPORTED",
                        excerpt=f"Verified official domain: {candidate_domain} ({record.get('canonical_name')}).",
                        rationale=(
                            f"Domain '{candidate_domain}' is registered in authoritative directories as the official "
                            f"web portal of '{record.get('canonical_name')}'."
                        ),
                        structured_fact=record,
                        confidence_score=0.99,
                        retrieved_at=now,
                    )
                if rep == "MALICIOUS" or record.get("category") == "PHISHING_LOOKALIKE":
                    impersonated = record.get("impersonated_domain", "registered entity")
                    return AdapterResult(
                        adapter_id=self.adapter_id,
                        source_id=self.source_id,
                        status="verified",
                        stance="CONTRADICTED",
                        excerpt=f"Malicious lookalike domain: {candidate_domain} impersonating {impersonated}.",
                        rationale=(
                            f"Domain '{candidate_domain}' is an identified deceptive lookalike domain engaged in "
                            f"unauthorized impersonation of '{impersonated}'."
                        ),
                        structured_fact=record,
                        confidence_score=0.98,
                        retrieved_at=now,
                    )

            # Heuristic check for high-risk suspicious TLDs
            if re.search(r"\.(?:top|vip|cc|xyz|click|work|link)$", candidate_domain):
                return AdapterResult(
                    adapter_id=self.adapter_id,
                    source_id=self.source_id,
                    status="verified",
                    stance="CONTRADICTED",
                    excerpt=f"Unregistered high-risk infrastructure domain: {candidate_domain}.",
                    rationale=(
                        f"Domain '{candidate_domain}' utilizes a high-risk non-standard TLD not recognized as official "
                        f"infrastructure by statutory regulators or recognized market intermediaries."
                    ),
                    structured_fact={"domain": candidate_domain, "reputation": "SUSPICIOUS_TLD"},
                    confidence_score=0.85,
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
        url_or_host = url_or_host.strip().lower()
        if "://" not in url_or_host:
            url_or_host = "https://" + url_or_host
        try:
            return urlparse(url_or_host).hostname or url_or_host
        except Exception:
            return url_or_host
