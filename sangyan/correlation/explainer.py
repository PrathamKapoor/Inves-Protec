"""Investigation Explainability Subsystem for SANGYAN.

Produces evidence-grounded factual explanations answering "Why was this flagged?"
while explicitly defining "What we don't know" to prevent unjustified certainty.
"""
from __future__ import annotations

from typing import Any

from sangyan.domain.models import (
    Claim,
    Entity,
    Finding,
    InvestigationExplanation,
    InvestigationStage,
    Signal,
)


class InvestigationExplainer:
    """Constructs explainability reports separating grounded observations from explicit epistemic limits."""

    def explain(
        self,
        signals: list[Signal],
        claims: list[Claim],
        entities: list[Entity],
        findings: list[Finding],
        stages: list[InvestigationStage],
        scam_patterns: list[str],
        overall_status: str,
    ) -> InvestigationExplanation:
        """Synthesize explainability points grounded directly in observable signals and findings."""
        why_flagged: list[str] = []
        what_we_do_not_know: list[str] = []
        limitations: list[str] = []

        # -------------------------------------------------------------------
        # 1. Why Was This Flagged? (Evidence-grounded observations)
        # -------------------------------------------------------------------
        # Authoritative contradictions
        for fnd in findings:
            if fnd.status == "CONTRADICTED":
                why_flagged.append(f"Authoritative Contradiction: {fnd.statement}")
            elif fnd.status == "OUTDATED":
                why_flagged.append(f"Outdated Regulatory Standing: {fnd.statement}")
            elif fnd.status == "CONFLICTING":
                why_flagged.append(f"Conflicting Institutional Evidence: {fnd.statement}")

        # High-severity signals
        for sig in signals:
            if sig.signal_type == "GUARANTEED_RETURN":
                why_flagged.append("The content promises guaranteed or fixed returns, prohibited under SEBI circular SEBI/HO/MIRSD/DOS3/CIR/P/2018/140.")
            elif sig.signal_type == "WITHDRAWAL_FEE":
                why_flagged.append(f"Advance withdrawal fee or tax demanded before releasing funds: '{sig.excerpt[:90]}'.")
            elif sig.signal_type == "OTP_REQUEST":
                why_flagged.append("Content solicits one-time passwords (OTPs) under guise of verification or trade authorization.")
            elif sig.signal_type == "CREDENTIAL_REQUEST":
                why_flagged.append("Content requests account passwords, trading PINs, or Demat login credentials.")
            elif sig.signal_type == "AUTHORITY_IMPERSONATION":
                why_flagged.append(f"Purported institutional authority or registration assertion: '{sig.excerpt[:90]}'.")
            elif sig.signal_type == "THIRD_PARTY_PAYMENT" or sig.signal_type == "UPI_MISMATCH":
                why_flagged.append(f"Payment destination mismatch: funds directed to personal or third-party handle '{sig.excerpt[:80]}'.")
            elif sig.signal_type == "UNVERIFIED_APP":
                why_flagged.append("Direct promotion of unverified APK download link or unofficial trading client.")
            elif sig.signal_type == "SUSPICIOUS_URL":
                why_flagged.append(f"High-risk, unofficial, or lookalike domain observed: '{sig.excerpt[:90]}'.")

        # Deduplicate why_flagged deterministically
        why_flagged = sorted(list(dict.fromkeys(why_flagged)))

        if not why_flagged:
            if overall_status == "SAFE":
                why_flagged.append("All extracted claims were corroborated by active authoritative institutional records with zero high-risk signals.")
            else:
                why_flagged.append("No specific high-severity signals were detected; status reflects unverified assertions lacking registry records.")

        # -------------------------------------------------------------------
        # 2. What We Don't Know (Explicit epistemic abstentions)
        # -------------------------------------------------------------------
        unverified_entities = [
            e for e in entities
            if not e.registration_number and e.entity_type not in {"REGULATOR", "EXCHANGE", "DEPOSITORY"}
        ]
        for ue in unverified_entities:
            what_we_do_not_know.append(
                f"The legal real-world identity of entity/handle '{ue.name}' could not be independently authenticated."
            )

        for claim in claims:
            if claim.status == "INSUFFICIENT_EVIDENCE":
                what_we_do_not_know.append(
                    f"No authoritative regulatory records were found to verify or refute claim: '{claim.statement[:80]}'."
                )

        unobserved_stages = [stg for stg in stages if stg.status in {"NOT_OBSERVED", "UNKNOWN"}]
        if unobserved_stages:
            stage_names = ", ".join(s.stage for s in unobserved_stages[:3])
            what_we_do_not_know.append(
                f"Scam lifecycle stages ({stage_names}) were not observed in the submitted content and are not assumed."
            )

        what_we_do_not_know.append(
            "Offline interactions, private direct messages, and banking transactions occurring outside the submitted artifacts remain unknown."
        )

        what_we_do_not_know = sorted(list(dict.fromkeys(what_we_do_not_know)))

        # -------------------------------------------------------------------
        # 3. System Limitations & Non-Advisory Notice
        # -------------------------------------------------------------------
        limitations.append(
            "This analysis is based strictly on submitted digital artifacts, pattern detection, and snapshot registries."
        )
        limitations.append(
            "SANGYAN provides investor-safety analysis and regulatory verification only; it does NOT provide investment advice, buy/sell recommendations, or legal counsel."
        )

        return InvestigationExplanation(
            why_flagged=why_flagged,
            what_we_do_not_know=what_we_do_not_know,
            limitations=limitations,
        )
