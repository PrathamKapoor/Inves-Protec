"""Controlled Authoritative Source Registry for Indian financial investor safety."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from sangyan.domain.models import AUTHORITY_TIERS, Source


@dataclass
class AuthoritativeSourceMetadata:
    """Detailed operational and governance metadata for an authoritative source."""

    source_id: str
    name: str
    authority_tier: str  # T0_REGULATOR, T1_INFRASTRUCTURE, T2_REGISTERED_ENTITY, etc.
    base_url: str
    allowed_domains: list[str]
    supported_claim_types: list[str]
    retrieval_method: str  # "SNAPSHOT", "LIVE_API", "HTTP_SCRAPE"
    freshness_policy_sec: int = 86400  # Default 24 hours
    mode: str = "SNAPSHOT"  # "LIVE", "SNAPSHOT", "TEST", "UNAVAILABLE"
    enabled: bool = True
    description: str = ""
    version: str = "2026.1"
    content_hash: str = ""
    record_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_domain_source(self) -> Source:
        """Convert to canonical domain Source entity."""
        return Source(
            id=self.source_id,
            name=self.name,
            authority_tier=self.authority_tier,
            url=self.base_url,
            publisher=self.name,
            published_at=time.time(),
            retrieved_at=time.time(),
            valid_until=time.time() + self.freshness_policy_sec,
            metadata={
                "allowed_domains": self.allowed_domains,
                "supported_claim_types": self.supported_claim_types,
                "retrieval_method": self.retrieval_method,
                "mode": self.mode,
                "version": self.version,
                "content_hash": self.content_hash,
                "record_count": self.record_count,
            },
        )


# Seed authoritative sources for Indian capital markets & retail protection
SEED_AUTHORITATIVE_SOURCES: list[AuthoritativeSourceMetadata] = [
    AuthoritativeSourceMetadata(
        source_id="src_sebi_intermediaries",
        name="Securities and Exchange Board of India (SEBI) Intermediaries Registry",
        authority_tier="T0_REGULATOR",
        base_url="https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpi=yes&intmId=13",
        allowed_domains=["sebi.gov.in", "www.sebi.gov.in"],
        supported_claim_types=["regulatory", "affiliation"],
        retrieval_method="SNAPSHOT",
        freshness_policy_sec=86400,
        mode="SNAPSHOT",
        description="Official statutory registry of SEBI-registered stock brokers, investment advisers, and research analysts.",
        version="2026.Q1",
    ),
    AuthoritativeSourceMetadata(
        source_id="src_sebi_circulars",
        name="SEBI Master Circulars and Cautionary Investor Advisories",
        authority_tier="T0_REGULATOR",
        base_url="https://www.sebi.gov.in/legal/master-circulars.html",
        allowed_domains=["sebi.gov.in", "www.sebi.gov.in"],
        supported_claim_types=["return", "regulatory", "urgency", "payment"],
        retrieval_method="SNAPSHOT",
        freshness_policy_sec=604800,  # 7 days
        mode="SNAPSHOT",
        description="Official circulars prohibiting guaranteed returns, unauthorized advisory, and fraudulent schemes.",
        version="2026.Q1",
    ),
    AuthoritativeSourceMetadata(
        source_id="src_mca_registry",
        name="Ministry of Corporate Affairs (MCA) Company Master Data",
        authority_tier="T0_REGULATOR",
        base_url="https://www.mca.gov.in/mcafoportal/viewCompanyMasterData.do",
        allowed_domains=["mca.gov.in", "www.mca.gov.in"],
        supported_claim_types=["regulatory", "affiliation"],
        retrieval_method="SNAPSHOT",
        freshness_policy_sec=86400,
        mode="SNAPSHOT",
        description="Statutory register of incorporated companies, CINs, and registration statuses in India.",
        version="2026.Q1",
    ),
    AuthoritativeSourceMetadata(
        source_id="src_nse_members",
        name="National Stock Exchange of India (NSE) Member Directory",
        authority_tier="T1_INFRASTRUCTURE",
        base_url="https://www.nseindia.com/invest/find-a-broker",
        allowed_domains=["nseindia.com", "www.nseindia.com"],
        supported_claim_types=["regulatory", "affiliation"],
        retrieval_method="SNAPSHOT",
        freshness_policy_sec=86400,
        mode="SNAPSHOT",
        description="Recognized stock exchange member directory of active trading and clearing members.",
        version="2026.Q1",
    ),
    AuthoritativeSourceMetadata(
        source_id="src_bse_members",
        name="Bombay Stock Exchange (BSE) Member Directory",
        authority_tier="T1_INFRASTRUCTURE",
        base_url="https://www.bseindia.com/members/MembershipDirectory.aspx",
        allowed_domains=["bseindia.com", "www.bseindia.com"],
        supported_claim_types=["regulatory", "affiliation"],
        retrieval_method="SNAPSHOT",
        freshness_policy_sec=86400,
        mode="SNAPSHOT",
        description="Recognized stock exchange member directory of active BSE brokers and participants.",
        version="2026.Q1",
    ),
    AuthoritativeSourceMetadata(
        source_id="src_official_domains",
        name="Authoritative Financial Domain & Intermediary URL Registry",
        authority_tier="T0_REGULATOR",
        base_url="https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpi=yes&intmId=13",
        allowed_domains=["sebi.gov.in", "nseindia.com", "bseindia.com", "rbi.org.in"],
        supported_claim_types=["regulatory", "affiliation", "payment", "other"],
        retrieval_method="SNAPSHOT",
        freshness_policy_sec=86400,
        mode="SNAPSHOT",
        description="Authoritative directory of authentic web portals, domains, and apps for registered entities.",
        version="2026.Q1",
    ),
    AuthoritativeSourceMetadata(
        source_id="src_rbi_entities",
        name="Reserve Bank of India (RBI) Sachet & Regulated Entities Registry",
        authority_tier="T0_REGULATOR",
        base_url="https://sachet.rbi.org.in",
        allowed_domains=["rbi.org.in", "sachet.rbi.org.in"],
        supported_claim_types=["regulatory", "payment", "other"],
        retrieval_method="SNAPSHOT",
        freshness_policy_sec=86400,
        mode="SNAPSHOT",
        description="Statutory register of RBI-licensed banks, NBFCs, and Sachet unauthorized deposit alerts.",
        version="2026.Q1",
    ),
]


class AuthoritativeSourceRegistry:
    """Registry maintaining approved, controlled authoritative sources."""

    def __init__(self, sources: Optional[list[AuthoritativeSourceMetadata]] = None) -> None:
        self._sources: dict[str, AuthoritativeSourceMetadata] = {}
        initial_sources = sources if sources is not None else SEED_AUTHORITATIVE_SOURCES
        for src in initial_sources:
            self.register(src)

    def register(self, source_meta: AuthoritativeSourceMetadata) -> None:
        """Register or update an authoritative source."""
        self._sources[source_meta.source_id] = source_meta

    def get_source(self, source_id: str) -> Optional[AuthoritativeSourceMetadata]:
        """Retrieve authoritative source metadata by ID."""
        return self._sources.get(source_id)

    def list_sources(
        self,
        claim_type: Optional[str] = None,
        authority_tier: Optional[str] = None,
        enabled_only: bool = True,
    ) -> list[AuthoritativeSourceMetadata]:
        """Query authoritative sources matching criteria."""
        results = []
        for src in self._sources.values():
            if enabled_only and not src.enabled:
                continue
            if claim_type and claim_type not in src.supported_claim_types:
                continue
            if authority_tier and src.authority_tier != authority_tier:
                continue
            results.append(src)
        return results

    def is_domain_allowed(self, source_id: str, domain: str) -> bool:
        """Verify whether a target domain is explicitly allowlisted for this authoritative source."""
        src = self.get_source(source_id)
        if not src:
            return False
        domain_clean = domain.lower().strip()
        for allowed in src.allowed_domains:
            if domain_clean == allowed or domain_clean.endswith("." + allowed):
                return True
        return False
