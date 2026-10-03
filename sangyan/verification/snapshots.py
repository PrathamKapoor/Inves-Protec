"""Versioned, reproducible authoritative registry snapshots with cryptographic integrity."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from sangyan.crypto.hashing import canonical_json, digest_document, sha3_hex


@dataclass
class RegistrySnapshot:
    """An immutable, versioned authoritative data snapshot with verifiable SHA3-256 hash."""

    source_id: str
    version: str
    retrieved_at: float
    effective_from: float
    effective_until: float
    content_hash: str
    record_count: int
    records: list[dict[str, Any]]
    mode: str = "SNAPSHOT"  # "SNAPSHOT", "TEST", "LIVE"
    metadata: dict[str, Any] = field(default_factory=dict)

    def verify_integrity(self) -> bool:
        """Verify that the records match the recorded canonical SHA3-256 content_hash."""
        calculated_hash = digest_document(self.records)
        return calculated_hash == self.content_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "version": self.version,
            "retrieved_at": self.retrieved_at,
            "effective_from": self.effective_from,
            "effective_until": self.effective_until,
            "content_hash": self.content_hash,
            "record_count": self.record_count,
            "mode": self.mode,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Authoritative Seed Snapshot Records
# ---------------------------------------------------------------------------

_SEBI_INTERMEDIARIES_RECORDS: list[dict[str, Any]] = [
    {
        "registration_number": "INZ000031633",
        "entity_name": "Zerodha Broking Limited",
        "category": "STOCK_BROKER",
        "status": "ACTIVE",
        "exchanges": ["NSE", "BSE", "MCX"],
        "official_domain": "zerodha.com",
        "official_email": "compliance@zerodha.com",
        "effective_from": 1420070400.0,  # 2015-01-01
        "valid_until": 1956441600.0,    # 2032-01-01
        "registered_address": "153/154, 4th Cross, Dollars Colony, JP Nagar 4th Phase, Bengaluru, Karnataka 560078",
    },
    {
        "registration_number": "INZ000301838",
        "entity_name": "Nextbillion Technology Private Limited",
        "trade_name": "Groww",
        "category": "STOCK_BROKER",
        "status": "ACTIVE",
        "exchanges": ["NSE", "BSE"],
        "official_domain": "groww.in",
        "official_email": "compliance@groww.in",
        "effective_from": 1577836800.0,  # 2020-01-01
        "valid_until": 1956441600.0,
        "registered_address": "Vaishnavi Tech Park, South Tower, Bellandur, Bengaluru, Karnataka 560103",
    },
    {
        "registration_number": "INZ000161534",
        "entity_name": "Angel One Limited",
        "category": "STOCK_BROKER",
        "status": "ACTIVE",
        "exchanges": ["NSE", "BSE", "MCX"],
        "official_domain": "angelone.in",
        "official_email": "compliance@angelone.in",
        "effective_from": 1483228800.0,  # 2017-01-01
        "valid_until": 1956441600.0,
        "registered_address": "G-1, Ackruti Trade Centre, MIDC, Andheri East, Mumbai, Maharashtra 400093",
    },
    {
        "registration_number": "INZ000183631",
        "entity_name": "ICICI Securities Limited",
        "trade_name": "ICICI Direct",
        "category": "STOCK_BROKER",
        "status": "ACTIVE",
        "exchanges": ["NSE", "BSE", "MCX"],
        "official_domain": "icicidirect.com",
        "official_email": "compliance@icicisecurities.com",
        "effective_from": 1420070400.0,
        "valid_until": 1956441600.0,
        "registered_address": "ICICI Venture House, Appasaheb Marathe Marg, Prabhadevi, Mumbai 400025",
    },
    {
        "registration_number": "INZ000185137",
        "entity_name": "RKSV Securities India Private Limited",
        "trade_name": "Upstox",
        "category": "STOCK_BROKER",
        "status": "ACTIVE",
        "exchanges": ["NSE", "BSE", "MCX"],
        "official_domain": "upstox.com",
        "official_email": "compliance@rksv.in",
        "effective_from": 1483228800.0,
        "valid_until": 1956441600.0,
        "registered_address": "30th Floor, Sunshine Tower, Senapati Bapat Marg, Dadar West, Mumbai 400013",
    },
    {
        "registration_number": "INA000001234",
        "entity_name": "Bharat Wealth Advisory LLP",
        "category": "INVESTMENT_ADVISER",
        "status": "ACTIVE",
        "official_domain": "bharatadvisory.in",
        "effective_from": 1546300800.0,
        "valid_until": 1956441600.0,
        "registered_address": "Nariman Point, Mumbai 400021",
    },
    {
        "registration_number": "INH000005678",
        "entity_name": "Research Alpha Capital",
        "category": "RESEARCH_ANALYST",
        "status": "ACTIVE",
        "official_domain": "researchalpha.in",
        "effective_from": 1577836800.0,
        "valid_until": 1956441600.0,
        "registered_address": "Bandra Kurla Complex, Mumbai 400051",
    },
    # Cancelled / Expired record for temporal verification testing
    {
        "registration_number": "INZ000999999",
        "entity_name": "Fraudulent Wealth Management LLP",
        "category": "STOCK_BROKER",
        "status": "CANCELLED",
        "cancellation_reason": "Order of SEBI Adjudicating Officer for unauthorized assured return schemes",
        "effective_from": 1514764800.0,  # 2018-01-01
        "valid_until": 1719705600.0,    # Expired 2024-06-30
    },
    # Suspended entity record
    {
        "registration_number": "INZ000888888",
        "entity_name": "Shady Trades India Limited",
        "category": "STOCK_BROKER",
        "status": "SUSPENDED",
        "cancellation_reason": "Interim suspension order under enquiry for client fund misappropriation",
        "effective_from": 1546300800.0,
        "valid_until": 1798761600.0,
    },
]

_MCA_COMPANIES_RECORDS: list[dict[str, Any]] = [
    {
        "cin": "U65929KA2018PLC116815",
        "company_name": "ZERODHA BROKING LIMITED",
        "status": "ACTIVE",
        "class": "Public",
        "incorporation_date": "2018-09-26",
        "registered_state": "Karnataka",
        "authorized_capital": 500000000,
    },
    {
        "cin": "U65100KA2016PTC092976",
        "company_name": "NEXTBILLION TECHNOLOGY PRIVATE LIMITED",
        "status": "ACTIVE",
        "class": "Private",
        "incorporation_date": "2016-05-09",
        "registered_state": "Karnataka",
        "authorized_capital": 100000000,
    },
    {
        "cin": "L67120MH1996PLC101709",
        "company_name": "ANGEL ONE LIMITED",
        "status": "ACTIVE",
        "class": "Public Listed",
        "incorporation_date": "1996-08-08",
        "registered_state": "Maharashtra",
        "authorized_capital": 1000000000,
    },
    {
        "cin": "U74999MH2016PTC288123",
        "company_name": "APEX CAPITAL SECURITIES PRIVATE LIMITED",
        "status": "ACTIVE",
        "class": "Private",
        "incorporation_date": "2016-11-20",
        "registered_state": "Maharashtra",
        "authorized_capital": 25000000,
    },
    # Struck off company for temporal and corporate verification testing
    {
        "cin": "U12345DL2010PTC999999",
        "company_name": "BOGUS MULTI TRADING PRIVATE LIMITED",
        "status": "STRUCK_OFF",
        "class": "Private",
        "incorporation_date": "2010-02-14",
        "registered_state": "Delhi",
        "authorized_capital": 100000,
    },
]

_REGULATORY_CIRCULARS_RECORDS: list[dict[str, Any]] = [
    {
        "circular_no": "SEBI/HO/MIRSD/MIRSD-PoD-1/P/CIR/2023/24",
        "title": "Advisory against associating with entities offering guaranteed or assured returns",
        "issue_date": "2023-02-14",
        "issuing_authority": "SEBI",
        "summary": "Intermediaries and retail investors are cautioned that offering or assuring fixed/guaranteed returns in the securities market is illegal and prohibited under SEBI regulations.",
        "prohibited_actions": [
            "guaranteed return promise",
            "assured monthly income",
            "fixed percentage daily profit",
            "loss recovery agreement",
        ],
    },
    {
        "circular_no": "SEBI/PR/2024/18",
        "title": "Caution against unauthorized trading platforms, WhatsApp/Telegram groups, and fake mobile apps",
        "issue_date": "2024-04-10",
        "issuing_authority": "SEBI",
        "summary": "Investors are warned against investing through unauthorized apps or transferring money to personal bank accounts/UPI IDs of individuals impersonating registered brokers or foreign FPIs.",
        "prohibited_actions": [
            "sideloaded apk download",
            "vip telegram trading group",
            "personal upi payment",
            "withdrawal fee demand",
        ],
    },
    {
        "circular_no": "SEBI/HO/ISD/ISD/CIR/P/2020/0001",
        "title": "Prohibition on collection of client trading credentials, passwords, and OTPs",
        "issue_date": "2020-03-30",
        "issuing_authority": "SEBI",
        "summary": "Registered intermediaries and any third party are strictly prohibited from soliciting client trading passwords, MPINs, or one-time passwords under any circumstances.",
        "prohibited_actions": [
            "otp sharing request",
            "trading password request",
            "demat credentials request",
            "remote screen share",
        ],
    },
]

_OFFICIAL_DOMAINS_RECORDS: list[dict[str, Any]] = [
    {
        "domain": "sebi.gov.in",
        "canonical_name": "Securities and Exchange Board of India",
        "category": "REGULATOR",
        "reputation": "OFFICIAL",
    },
    {
        "domain": "rbi.org.in",
        "canonical_name": "Reserve Bank of India",
        "category": "REGULATOR",
        "reputation": "OFFICIAL",
    },
    {
        "domain": "mca.gov.in",
        "canonical_name": "Ministry of Corporate Affairs",
        "category": "REGULATOR",
        "reputation": "OFFICIAL",
    },
    {
        "domain": "nseindia.com",
        "canonical_name": "National Stock Exchange of India",
        "category": "EXCHANGE",
        "reputation": "OFFICIAL",
    },
    {
        "domain": "bseindia.com",
        "canonical_name": "Bombay Stock Exchange",
        "category": "EXCHANGE",
        "reputation": "OFFICIAL",
    },
    {
        "domain": "zerodha.com",
        "canonical_name": "Zerodha Broking Limited",
        "category": "BROKER",
        "reputation": "OFFICIAL",
    },
    {
        "domain": "groww.in",
        "canonical_name": "Nextbillion Technology Private Limited",
        "category": "BROKER",
        "reputation": "OFFICIAL",
    },
    {
        "domain": "angelone.in",
        "canonical_name": "Angel One Limited",
        "category": "BROKER",
        "reputation": "OFFICIAL",
    },
    {
        "domain": "upstox.com",
        "canonical_name": "RKSV Securities India Private Limited",
        "category": "BROKER",
        "reputation": "OFFICIAL",
    },
    # Known phishing / typosquatting lookalike blacklist
    {
        "domain": "zerodha-profit.cc",
        "canonical_name": "Impersonation of Zerodha",
        "category": "PHISHING_LOOKALIKE",
        "reputation": "MALICIOUS",
        "impersonated_domain": "zerodha.com",
    },
    {
        "domain": "groww-vip-invest.top",
        "canonical_name": "Impersonation of Groww",
        "category": "PHISHING_LOOKALIKE",
        "reputation": "MALICIOUS",
        "impersonated_domain": "groww.in",
    },
    {
        "domain": "sebi-approval.xyz",
        "canonical_name": "Impersonation of SEBI",
        "category": "PHISHING_LOOKALIKE",
        "reputation": "MALICIOUS",
        "impersonated_domain": "sebi.gov.in",
    },
]


def create_snapshot(
    source_id: str,
    version: str,
    records: list[dict[str, Any]],
    retrieved_at: Optional[float] = None,
    effective_from: Optional[float] = None,
    effective_until: Optional[float] = None,
    mode: str = "SNAPSHOT",
) -> RegistrySnapshot:
    """Build a RegistrySnapshot with deterministic canonical SHA3-256 hash."""
    now = retrieved_at or time.time()
    eff_from = effective_from or (now - 86400 * 30)
    eff_until = effective_until or (now + 86400 * 365)
    content_hash = digest_document(records)

    return RegistrySnapshot(
        source_id=source_id,
        version=version,
        retrieved_at=now,
        effective_from=eff_from,
        effective_until=eff_until,
        content_hash=content_hash,
        record_count=len(records),
        records=records,
        mode=mode,
    )


class SnapshotManager:
    """Provides validated, tamper-checked access to versioned authoritative snapshots."""

    def __init__(self) -> None:
        self._snapshots: dict[str, RegistrySnapshot] = {}
        self._load_seed_snapshots()

    def _load_seed_snapshots(self) -> None:
        # 1. SEBI Intermediaries
        self.register_snapshot(
            create_snapshot(
                source_id="src_sebi_intermediaries",
                version="2026.Q1",
                records=_SEBI_INTERMEDIARIES_RECORDS,
            )
        )
        # 2. MCA Companies
        self.register_snapshot(
            create_snapshot(
                source_id="src_mca_registry",
                version="2026.Q1",
                records=_MCA_COMPANIES_RECORDS,
            )
        )
        # 3. Regulatory Circulars
        self.register_snapshot(
            create_snapshot(
                source_id="src_sebi_circulars",
                version="2026.Q1",
                records=_REGULATORY_CIRCULARS_RECORDS,
            )
        )
        # 4. Official Domains & Lookalikes
        self.register_snapshot(
            create_snapshot(
                source_id="src_official_domains",
                version="2026.Q1",
                records=_OFFICIAL_DOMAINS_RECORDS,
            )
        )

    def register_snapshot(self, snapshot: RegistrySnapshot) -> None:
        if not snapshot.verify_integrity():
            raise ValueError(f"Snapshot integrity failure for source '{snapshot.source_id}'")
        self._snapshots[snapshot.source_id] = snapshot

    def get_snapshot(self, source_id: str) -> Optional[RegistrySnapshot]:
        return self._snapshots.get(source_id)

    # -----------------------------------------------------------------------
    # Direct Lookup Helpers
    # -----------------------------------------------------------------------

    def lookup_sebi_registration(self, reg_no: str) -> Optional[dict[str, Any]]:
        """Lookup SEBI registration by exact or normalized registration identifier (case-insensitive)."""
        snap = self.get_snapshot("src_sebi_intermediaries")
        if not snap:
            return None
        import re
        target = re.sub(r"[\s\-]", "", reg_no).upper()
        for rec in snap.records:
            rec_reg = re.sub(r"[\s\-]", "", rec.get("registration_number", "")).upper()
            if rec_reg == target:
                return dict(rec)
        return None

    def lookup_sebi_entity_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Lookup SEBI entity by exact or normalized legal/trade name."""
        snap = self.get_snapshot("src_sebi_intermediaries")
        if not snap:
            return None
        name_clean = " ".join(name.lower().split())
        for rec in snap.records:
            legal = " ".join(rec.get("entity_name", "").lower().split())
            trade = " ".join(rec.get("trade_name", "").lower().split())
            if name_clean == legal or (trade and name_clean == trade):
                return dict(rec)
        return None

    def lookup_mca_cin(self, cin: str) -> Optional[dict[str, Any]]:
        """Lookup MCA Corporate Identity Number by exact or normalized CIN (case-insensitive)."""
        snap = self.get_snapshot("src_mca_registry")
        if not snap:
            return None
        import re
        target = re.sub(r"[\s\-]", "", cin).upper()
        for rec in snap.records:
            rec_cin = re.sub(r"[\s\-]", "", rec.get("cin", "")).upper()
            if rec_cin == target:
                return dict(rec)
        return None

    def lookup_official_domain(self, domain_or_url: str) -> Optional[dict[str, Any]]:
        """Lookup domain in official directory and phishing blacklist with www and dot normalization."""
        snap = self.get_snapshot("src_official_domains")
        if not snap:
            return None
        # Extract host if full URL passed
        host = domain_or_url.lower().strip().rstrip(".")
        if "://" in host:
            from urllib.parse import urlparse
            try:
                host = urlparse(host).hostname or host
            except Exception:
                pass
        elif "/" in host:
            host = host.split("/")[0]

        # Strip port if present
        if ":" in host:
            host = host.split(":")[0]

        host = host.strip().rstrip(".")
        host_no_www = host[4:] if host.startswith("www.") else host

        for rec in snap.records:
            rec_domain = rec.get("domain", "").lower().strip().rstrip(".")
            rec_no_www = rec_domain[4:] if rec_domain.startswith("www.") else rec_domain
            if host == rec_domain or host_no_www == rec_no_www:
                return dict(rec)
        return None

    def lookup_prohibited_practice(self, claim_statement: str) -> list[dict[str, Any]]:
        """Check if statement asserts practices prohibited by official circulars."""
        snap = self.get_snapshot("src_sebi_circulars")
        if not snap:
            return []
        matched_circulars = []
        stmt_lower = claim_statement.lower()
        for rec in snap.records:
            for prohibited in rec.get("prohibited_actions", []):
                # Check for prohibited practice keywords
                if prohibited in stmt_lower or any(word in stmt_lower for word in prohibited.split()):
                    matched_circulars.append(dict(rec))
                    break
        return matched_circulars
