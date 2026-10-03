"""Financial entity resolution and identifier extraction worker.

Extracts SEBI registration numbers, CINs, UPI VPAs, regulators, exchanges,
brokers, investment advisers, and suspicious social/app channels from text.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from sangyan.domain.models import ENTITY_TYPES, Entity


# ---------------------------------------------------------------------------
# Regulatory & Corporate Identifier Regexes
# ---------------------------------------------------------------------------

# SEBI Registration Numbers (Brokers, Advisers, Analysts, Merchant Bankers, Portfolio Managers)
SEBI_REG_PATTERNS = [
    (re.compile(r"\b(INZ[0-9]{9})\b", re.IGNORECASE), "BROKER", "Stock Broker"),
    (re.compile(r"\b(INA[0-9]{9})\b", re.IGNORECASE), "INVESTMENT_ADVISER", "Investment Adviser"),
    (re.compile(r"\b(INH[0-9]{9})\b", re.IGNORECASE), "RESEARCH_ANALYST", "Research Analyst"),
    (re.compile(r"\b(INP[0-9]{9})\b", re.IGNORECASE), "INVESTMENT_ADVISER", "Portfolio Manager"),
    (re.compile(r"\b(INM[0-9]{9})\b", re.IGNORECASE), "BROKER", "Merchant Banker"),
    (re.compile(r"\b(IN-DP-[0-9]{2,3}-[0-9]{4})\b", re.IGNORECASE), "DEPOSITORY", "Depository Participant"),
    (re.compile(r"\b(MF/[0-9]{3}/[0-9]{2}/[0-9]{2})\b", re.IGNORECASE), "SCHEME", "Mutual Fund"),
]

# Corporate Identity Number (CIN) (e.g. U74999MH2016PTC288123)
CIN_PATTERN = re.compile(
    r"\b([LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b", re.IGNORECASE
)

# Indian UPI Virtual Payment Address (VPA)
UPI_VPA_PATTERN = re.compile(
    r"\b([a-zA-Z0-9._\-]{2,50}@(okhdfcbank|okaxis|oksbi|okicici|paytm|ybl|ibl|apl|axl|postbank|upi|barodampay|federal|kotak|indus|airtel))\b",
    re.IGNORECASE,
)

# Telegram and WhatsApp Solicitations
TELEGRAM_PATTERN = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me)/(joinchat/[a-zA-Z0-9_\-]+|[a-zA-Z0-9_]{4,32})|(?:(?:^|\s)@([a-zA-Z0-9_]{5,32})(?=\s|$))",
    re.IGNORECASE,
)
WHATSAPP_PATTERN = re.compile(
    r"(?:https?://)?chat\.whatsapp\.com/([a-zA-Z0-9]{15,30})",
    re.IGNORECASE,
)

# Common Indian Financial Brands & Authorities
KNOWN_REGULATORS = {
    "sebi": ("Securities and Exchange Board of India", "REGULATOR", "https://www.sebi.gov.in"),
    "rbi": ("Reserve Bank of India", "REGULATOR", "https://www.rbi.org.in"),
    "irdai": ("Insurance Regulatory and Development Authority of India", "REGULATOR", "https://www.irdai.gov.in"),
    "mca": ("Ministry of Corporate Affairs", "REGULATOR", "https://www.mca.gov.in"),
    "pfrda": ("Pension Fund Regulatory and Development Authority", "REGULATOR", "https://www.pfrda.org.in"),
}

KNOWN_INFRASTRUCTURE = {
    "nse": ("National Stock Exchange of India", "EXCHANGE", "https://www.nseindia.com"),
    "bse": ("Bombay Stock Exchange", "EXCHANGE", "https://www.bseindia.com"),
    "mcx": ("Multi Commodity Exchange of India", "EXCHANGE", "https://www.mcxindia.com"),
    "nsdl": ("National Securities Depository Limited", "DEPOSITORY", "https://nsdl.co.in"),
    "cdsl": ("Central Depository Services Limited", "DEPOSITORY", "https://www.cdslindia.com"),
}

KNOWN_BROKERS = {
    "zerodha": ("Zerodha Broking Limited", "BROKER", "https://zerodha.com"),
    "groww": ("Groww (Nextbillion Technology)", "BROKER", "https://groww.in"),
    "angel one": ("Angel One Limited", "BROKER", "https://angelone.in"),
    "angelone": ("Angel One Limited", "BROKER", "https://angelone.in"),
    "upstox": ("Upstox (RKSV Securities)", "BROKER", "https://upstox.com"),
    "icici direct": ("ICICI Securities Limited", "BROKER", "https://icicidirect.com"),
    "hdfc sky": ("HDFC Securities Limited", "BROKER", "https://hdfcsky.com"),
    "kotak securities": ("Kotak Securities Limited", "BROKER", "https://kotaksecurities.com"),
    "motilal oswal": ("Motilal Oswal Financial Services", "BROKER", "https://motilaloswal.com"),
    "5paisa": ("5paisa Capital Limited", "BROKER", "https://5paisa.com"),
    "dhan": ("Dhan (Moneylicious Securities)", "BROKER", "https://dhan.co"),
    "paytm money": ("Paytm Money Limited", "BROKER", "https://paytmmoney.com"),
    "sharekhan": ("Sharekhan Limited", "BROKER", "https://sharekhan.com"),
}


class EntityResolver:
    """Extracts, normalizes, and classifies financial entities and identifiers."""

    def resolve_entities(self, text: str) -> list[Entity]:
        if not text:
            return []

        resolved: list[Entity] = []
        seen_keys: set[str] = set()

        # 1. Extract SEBI Registration Numbers
        for pattern, entity_type, subcategory in SEBI_REG_PATTERNS:
            for match in pattern.finditer(text):
                reg_no = match.group(1).upper()
                key = f"sebi:{reg_no}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                resolved.append(
                    Entity(
                        name=f"Entity claiming SEBI Registration {reg_no}",
                        entity_type=entity_type,
                        registration_number=reg_no,
                        metadata={
                            "identifier_type": "SEBI_REGISTRATION",
                            "subcategory": subcategory,
                            "raw_match": match.group(0),
                        },
                    )
                )

        # 2. Extract CINs
        for match in CIN_PATTERN.finditer(text):
            cin = match.group(1).upper()
            key = f"cin:{cin}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            resolved.append(
                Entity(
                    name=f"Company with CIN {cin}",
                    entity_type="COMPANY",
                    registration_number=cin,
                    metadata={"identifier_type": "CIN", "raw_match": match.group(0)},
                )
            )

        # 3. Extract UPI VPAs
        for match in UPI_VPA_PATTERN.finditer(text):
            vpa = match.group(1).lower()
            key = f"upi:{vpa}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            resolved.append(
                Entity(
                    name=vpa,
                    entity_type="UPI",
                    metadata={"identifier_type": "UPI_VPA", "handle": match.group(2).lower()},
                )
            )

        # 4. Extract Telegram Channels / Groups
        for match in TELEGRAM_PATTERN.finditer(text):
            tg_target = match.group(1) or match.group(2)
            if not tg_target:
                continue
            key = f"tg:{tg_target.lower()}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            resolved.append(
                Entity(
                    name=f"Telegram channel/handle @{tg_target}",
                    entity_type="APP",
                    official_url=f"https://t.me/{tg_target}",
                    metadata={"channel": "TELEGRAM", "handle": tg_target},
                )
            )

        # 5. Extract WhatsApp Groups
        for match in WHATSAPP_PATTERN.finditer(text):
            invite_code = match.group(1)
            key = f"wa:{invite_code}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            resolved.append(
                Entity(
                    name="WhatsApp Group Invite",
                    entity_type="APP",
                    official_url=f"https://chat.whatsapp.com/{invite_code}",
                    metadata={"channel": "WHATSAPP", "invite_code": invite_code},
                )
            )

        # 6. Recognize Regulators
        text_lower = text.lower()
        for alias, (full_name, etype, url) in KNOWN_REGULATORS.items():
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, text_lower):
                key = f"reg:{alias}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    resolved.append(
                        Entity(
                            name=full_name,
                            entity_type=etype,
                            aliases=[alias.upper()],
                            official_url=url,
                            metadata={"jurisdiction": "IN", "is_statutory_authority": True},
                        )
                    )

        # 7. Recognize Infrastructure (Exchanges / Depositories)
        for alias, (full_name, etype, url) in KNOWN_INFRASTRUCTURE.items():
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, text_lower):
                key = f"infra:{alias}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    resolved.append(
                        Entity(
                            name=full_name,
                            entity_type=etype,
                            aliases=[alias.upper()],
                            official_url=url,
                            metadata={"infrastructure_tier": "T1_INFRASTRUCTURE"},
                        )
                    )

        # 8. Recognize Known Registered Intermediaries
        for brand, (full_name, etype, url) in KNOWN_BROKERS.items():
            pattern = rf"\b{re.escape(brand)}\b"
            if re.search(pattern, text_lower):
                key = f"broker:{full_name}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    resolved.append(
                        Entity(
                            name=full_name,
                            entity_type=etype,
                            aliases=[brand.title()],
                            official_url=url,
                            metadata={"market_segment": "RETAIL_BROKER"},
                        )
                    )

        return resolved
