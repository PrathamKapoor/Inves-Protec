"""Claim decomposition worker converting compound messages into discrete, testable claims."""
from __future__ import annotations

import re
from typing import Any, Optional

from sangyan.domain.base import new_id
from sangyan.domain.models import CLAIM_TYPES, Claim, ConfidenceVector


# Regular expressions for identifying claim categories
REGULATORY_PATTERNS = re.compile(
    r"(?i)\b(sebi|rbi|irdai|mca|amfi|gov(?:t|ernment)?|registered|reg(?:istration)?\.?\s*(?:no|num)?|licensed|authorized|certified|intermediary|sub-broker)\b"
    r"|(?:सेबी|आरबीआई|लाइसेंस|पंजीकृत|नोंदणीकृत|प्रमाणित)"
)

RETURN_PATTERNS = re.compile(
    r"(?i)\b(?:guarantee[ds]?|100%|fixed\s+return|monthly\s+return|daily\s+profit|roi|doubl(?:e|ing)|zero\s+risk|risk[- ]free|loss\s+recovery|sure[- ]shot|pakka\s+profit|munafa|garanti)\b"
    r"|(?:\b\d+(?:\.\d+)?%\s*(?:daily|weekly|monthly|annual|return|profit|gain)\b)"
    r"|(?:ग्यारंटी|गारंटी|खात्रीशीर|परतावा|मुनाफा|फायदा|दुपट्ट|नफा)"
)

URGENCY_PATTERNS = re.compile(
    r"(?i)\b(?:hurry|urgent|last\s+chance|closing\s+soon|only\s+\d+\s+(?:slots?|seats?|spots?|members?)|valid\s+(?:today|only|now)|limited\s+time|offer\s+expires|jaldi|aaj\s+hi)\b"
    r"|(?:लवकर|त्वरा|फक्त\s+\d+|आजच|अंतिम\s+संधी|जल्दी|सीमित\s+समय)"
)

PAYMENT_PATTERNS = re.compile(
    r"(?i)\b(?:pay\b|deposit|transfer|fee|charges?|withdrawal\s+fee|processing\s+fee|tax|margin|upi|gpay|phonepe|paytm|bank\s+transfer|qr\s+code|send\s+₹|send\s+rs\.?)\b"
    r"|(?:[\w.\-]+@(?:okhdfcbank|okaxis|oksbi|paytm|apl|ybl|ibl))\b"
    r"|(?:पैसे\s+भरा|फी|चार्ज|जमा\s+करा|पाठवा|भुगतान|जमा)"
)

AFFILIATION_PATTERNS = re.compile(
    r"(?i)\b(?:partner(?:ship|ed)?\s+with|associated\s+with|backed\s+by|official\s+tie-up|tata|reliance|ambani|adani|infosys|hdfc|sbi|bse|nse|mcx)\b"
    r"|(?:सहकार्य|भागीदार|समर्थित)"
)

# Conjunctions and clause boundaries for splitting compound assertions
CLAUSE_SPLIT_REGEX = re.compile(
    r"(?:[\r\n]+|(?<=[.!?।|;])\s+|\b(?:and also|and\b|aur\b|ani\b|tatha\b|evam\b|lekin\b|par\b|pan\b|but\b|however\b)\s+)"
)



class ClaimExtractor:
    """Decomposes compound financial text into atomic, independently verifiable claims."""

    def extract_claims(self, text: str, content_item_id: str) -> list[Claim]:
        if not text or not text.strip():
            return []

        # 1. Split raw text into prospective candidate clauses
        raw_clauses = CLAUSE_SPLIT_REGEX.split(text)
        candidates: list[str] = []

        for raw in raw_clauses:
            cleaned = " ".join(raw.strip().split())
            # Skip very short fragments that don't constitute a substantive claim
            if len(cleaned) < 10 or len(cleaned.split()) < 3:
                continue
            candidates.append(cleaned)

        # If no clause split worked, use the full text if it's long enough
        if not candidates and len(text.strip()) >= 10:
            candidates.append(" ".join(text.strip().split()))

        claims: list[Claim] = []
        seen_statements: set[str] = set()

        for clause in candidates:
            claim_type = self._classify_claim_type(clause)
            normalized_stmt = self._normalize_statement(clause)

            if normalized_stmt.lower() in seen_statements:
                continue
            seen_statements.add(normalized_stmt.lower())

            # Find position in original text
            start_pos = text.find(clause)
            char_range = [start_pos, start_pos + len(clause)] if start_pos >= 0 else None

            # Initialize initial unverified confidence vector
            conf = ConfidenceVector(
                analytical_support=0.5,
                evidence_completeness=0.0,
                source_authority_weight=0.0,
            )

            claims.append(
                Claim(
                    content_item_id=content_item_id,
                    statement=normalized_stmt,
                    claim_type=claim_type,
                    status="UNVERIFIED",
                    confidence=conf,
                    metadata={
                        "context_pointers": {
                            "excerpt": clause,
                            "char_range": char_range,
                        },
                    },
                )
            )

        return claims

    def _classify_claim_type(self, clause: str) -> str:
        """Categorize claim into regulatory, return, urgency, payment, affiliation, or other."""
        # Check in priority order
        if RETURN_PATTERNS.search(clause):
            return "return"
        if REGULATORY_PATTERNS.search(clause):
            return "regulatory"
        if URGENCY_PATTERNS.search(clause):
            return "urgency"
        if PAYMENT_PATTERNS.search(clause):
            return "payment"
        if AFFILIATION_PATTERNS.search(clause):
            return "affiliation"
        return "other"

    def _normalize_statement(self, clause: str) -> str:
        """Produce a clean statement sentence starting with a capital letter."""
        clause = clause.strip(" ,;:-_")
        if not clause:
            return ""
        return clause[0].upper() + clause[1:]
