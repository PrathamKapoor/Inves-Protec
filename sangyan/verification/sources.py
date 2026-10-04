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
    source_type: str = "REGULATOR_REGISTRY"  # REGULATOR_REGISTRY, EXCHANGE_DIRECTORY, CORPORATE_REGISTRY, STATUTORY_CIRCULAR, OFFICIAL_DOMAINS, PAYMENT_DIRECTORY, DEPOSITORY_REGISTRY
    authority: str = "SEBI"  # SEBI, MCA, RBI, NSE, BSE, MCX, NSDL, CDSL, NPCI, IRDAI
    provenance_policy: str = "STATUTORY_MANDATE"  # STATUTORY_MANDATE, REGULATORY_FILING, CRYPTOGRAPHIC_SNAPSHOT, OFFICIAL_GAZETTE
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
                "source_type": self.source_type,
                "authority": self.authority,
                "provenance_policy": self.provenance_policy,
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
        source_type="REGULATOR_REGISTRY",
        authority="SEBI",
        provenance_policy="STATUTORY_MANDATE",
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
        source_type="STATUTORY_CIRCULAR",
        authority="SEBI",
        provenance_policy="OFFICIAL_GAZETTE",
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
        source_type="CORPORATE_REGISTRY",
        authority="MCA",
        provenance_policy="STATUTORY_MANDATE",
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
        source_type="EXCHANGE_DIRECTORY",
        authority="NSE",
        provenance_policy="REGULATORY_FILING",
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
        source_type="EXCHANGE_DIRECTORY",
        authority="BSE",
        provenance_policy="REGULATORY_FILING",
        freshness_policy_sec=86400,
        mode="SNAPSHOT",
        description="Recognized stock exchange member directory of active BSE brokers and participants.",
        version="2026.Q1",
    ),
    AuthoritativeSourceMetadata(
        source_id="src_mcx_members",
        name="Multi Commodity Exchange of India (MCX) Member Directory",
        authority_tier="T1_INFRASTRUCTURE",
        base_url="https://www.mcxindia.com/membership/membership-directory",
        allowed_domains=["mcxindia.com", "www.mcxindia.com"],
        supported_claim_types=["regulatory", "affiliation"],
        retrieval_method="SNAPSHOT",
        source_type="EXCHANGE_DIRECTORY",
        authority="MCX",
        provenance_policy="REGULATORY_FILING",
        freshness_policy_sec=86400,
        mode="SNAPSHOT",
        description="Statutory directory of active commodity derivatives trading and clearing members.",
        version="2026.Q1",
    ),
    AuthoritativeSourceMetadata(
        source_id="src_nsdl_depositories",
        name="National Securities Depository Limited (NSDL) Participants Directory",
        authority_tier="T1_INFRASTRUCTURE",
        base_url="https://nsdl.co.in/dplist/dplist.php",
        allowed_domains=["nsdl.co.in", "www.nsdl.co.in"],
        supported_claim_types=["regulatory", "affiliation"],
        retrieval_method="SNAPSHOT",
        source_type="DEPOSITORY_REGISTRY",
        authority="NSDL",
        provenance_policy="REGULATORY_FILING",
        freshness_policy_sec=86400,
        mode="SNAPSHOT",
        description="Statutory directory of registered Depository Participants holding client demat accounts.",
        version="2026.Q1",
    ),
    AuthoritativeSourceMetadata(
        source_id="src_cdsl_depositories",
        name="Central Depository Services (India) Limited (CDSL) Participants Directory",
        authority_tier="T1_INFRASTRUCTURE",
        base_url="https://www.cdslindia.com/DP/dplist.aspx",
        allowed_domains=["cdslindia.com", "www.cdslindia.com"],
        supported_claim_types=["regulatory", "affiliation"],
        retrieval_method="SNAPSHOT",
        source_type="DEPOSITORY_REGISTRY",
        authority="CDSL",
        provenance_policy="REGULATORY_FILING",
        freshness_policy_sec=86400,
        mode="SNAPSHOT",
        description="Statutory directory of registered CDSL Depository Participants holding electronic securities.",
        version="2026.Q1",
    ),
    AuthoritativeSourceMetadata(
        source_id="src_official_domains",
        name="Authoritative Financial Domain & Intermediary URL Registry",
        authority_tier="T0_REGULATOR",
        base_url="https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpi=yes&intmId=13",
        allowed_domains=["sebi.gov.in", "nseindia.com", "bseindia.com", "mcxindia.com", "rbi.org.in"],
        supported_claim_types=["regulatory", "affiliation", "payment", "other"],
        retrieval_method="SNAPSHOT",
        source_type="OFFICIAL_DOMAINS",
        authority="SEBI",
        provenance_policy="CRYPTOGRAPHIC_SNAPSHOT",
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
        source_type="REGULATOR_REGISTRY",
        authority="RBI",
        provenance_policy="STATUTORY_MANDATE",
        freshness_policy_sec=86400,
        mode="SNAPSHOT",
        description="Statutory register of RBI-licensed banks, NBFCs, and Sachet unauthorized deposit alerts.",
        version="2026.Q1",
    ),
    AuthoritativeSourceMetadata(
        source_id="src_upis_official",
        name="National Payments Corporation of India (NPCI) Verified Merchant VPA Directory",
        authority_tier="T0_REGULATOR",
        base_url="https://www.npci.org.in/what-we-do/upi/live-members",
        allowed_domains=["npci.org.in", "www.npci.org.in", "sebi.gov.in"],
        supported_claim_types=["payment", "regulatory", "affiliation"],
        retrieval_method="SNAPSHOT",
        source_type="PAYMENT_DIRECTORY",
        authority="NPCI",
        provenance_policy="REGULATORY_FILING",
        freshness_policy_sec=86400,
        mode="SNAPSHOT",
        description="Authoritative registry of verified corporate merchant VPAs for registered stock brokers and mutual funds.",
        version="2026.Q1",
    ),
    AuthoritativeSourceMetadata(
        source_id="src_irdai_insurers",
        name="Insurance Regulatory and Development Authority of India (IRDAI) Registry",
        authority_tier="T0_REGULATOR",
        base_url="https://irdai.gov.in/list-of-insurers",
        allowed_domains=["irdai.gov.in", "www.irdai.gov.in"],
        supported_claim_types=["regulatory", "affiliation"],
        retrieval_method="SNAPSHOT",
        source_type="REGULATOR_REGISTRY",
        authority="IRDAI",
        provenance_policy="STATUTORY_MANDATE",
        freshness_policy_sec=86400,
        mode="SNAPSHOT",
        description="Statutory registry of registered life, general, and health insurance companies in India.",
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
        source_type: Optional[str] = None,
        authority: Optional[str] = None,
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
            if source_type and src.source_type != source_type:
                continue
            if authority and src.authority != authority:
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
