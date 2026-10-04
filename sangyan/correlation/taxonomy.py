"""Controlled Scam and Fraud Pattern Taxonomy Classifier for SANGYAN.

Maps observable signals, claims, and authoritative verification findings to a
controlled multi-label taxonomy of financial frauds without keyword-only triggering.
"""
from __future__ import annotations

from typing import Any

from sangyan.domain.models import Claim, Finding, Signal


class ScamTaxonomyClassifier:
    """Classifies content into supported financial fraud patterns with strict evidentiary basis."""

    def classify(
        self,
        signals: list[Signal],
        claims: list[Claim],
        findings: list[Finding],
    ) -> list[str]:
        """Classify into a deterministically sorted list of supported taxonomy patterns."""
        patterns: set[str] = set()
        signal_types = {s.signal_type for s in signals}
        finding_statements = [f.statement.lower() for f in findings if f.status == "CONTRADICTED"]

        # 1. GUARANTEED_RETURN
        if "GUARANTEED_RETURN" in signal_types or any("guaranteed return" in stmt for stmt in finding_statements):
            patterns.add("GUARANTEED_RETURN")

        # 2. AUTHORITY_IMPERSONATION
        if "AUTHORITY_IMPERSONATION" in signal_types or any(
            any(reg in stmt for reg in ["sebi", "rbi", "mca", "nse", "bse"]) for stmt in finding_statements
        ):
            patterns.add("AUTHORITY_IMPERSONATION")

        # 3. UNREGISTERED_INTERMEDIARY
        if "UNREGISTERED_ENTITY" in signal_types or any("not found in official registry" in stmt for stmt in finding_statements):
            patterns.add("UNREGISTERED_INTERMEDIARY")

        # 4. FAKE_TRADING_APP
        if "UNVERIFIED_APP" in signal_types or ("SUSPICIOUS_URL" in signal_types and "APK" in " ".join(s.excerpt for s in signals).upper()):
            patterns.add("FAKE_TRADING_APP")

        # 5. SOCIAL_MEDIA_SOLICITATION
        if "SOCIAL_MEDIA_SOLICITATION" in signal_types:
            patterns.add("SOCIAL_MEDIA_SOLICITATION")

        # 6. WITHDRAWAL_FEE_SCAM
        if "WITHDRAWAL_FEE" in signal_types:
            patterns.add("WITHDRAWAL_FEE_SCAM")

        # 7. THIRD_PARTY_PAYMENT
        if "THIRD_PARTY_PAYMENT" in signal_types:
            patterns.add("THIRD_PARTY_PAYMENT")

        # 8. UPI_IMPERSONATION
        if "UPI_MISMATCH" in signal_types or any("mismatch" in stmt and "upi" in stmt for stmt in finding_statements):
            patterns.add("UPI_IMPERSONATION")

        # 9. PHISHING_CREDENTIAL_THEFT
        if "CREDENTIAL_REQUEST" in signal_types:
            patterns.add("PHISHING_CREDENTIAL_THEFT")

        # 10. OTP_THEFT
        if "OTP_REQUEST" in signal_types:
            patterns.add("OTP_THEFT")

        # 11. FAKE_ADVISER
        if "SOCIAL_MEDIA_SOLICITATION" in signal_types and (
            "HIGH_RETURN_PROMISE" in signal_types or "GUARANTEED_RETURN" in signal_types
        ):
            patterns.add("FAKE_ADVISER")

        # 12. PONZI_PYRAMID
        if "GREED_APPEAL" in signal_types and "SOCIAL_PROOF" in signal_types and "HIGH_RETURN_PROMISE" in signal_types:
            patterns.add("PONZI_PYRAMID")

        # General Umbrella Category: INVESTMENT_SCAM
        # Triggered when multiple high-severity patterns co-occur
        if len(patterns) >= 2 or ("GUARANTEED_RETURN" in patterns and "WITHDRAWAL_FEE_SCAM" in patterns):
            patterns.add("INVESTMENT_SCAM")

        return sorted(patterns)
