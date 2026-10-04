"""Scam-Chain Reconstruction Subsystem for SANGYAN.

Maps observed signals, claims, and authoritative verification findings to known
stages of financial scams with strict evidentiary provenance and hard-negative suppression.
"""
from __future__ import annotations

from typing import Any, Optional

from sangyan.domain.models import (
    SCAM_CHAIN_STAGES,
    Claim,
    Evidence,
    Finding,
    InvestigationStage,
    Signal,
)
from sangyan.tenancy.repository import TenantRepository


class ScamChainReconstructor:
    """Reconstructs the lifecycle stages of an investment scam based strictly on evidence."""

    # Ordered scam chain sequence
    STAGE_ORDER: list[str] = list(SCAM_CHAIN_STAGES)

    def reconstruct(
        self,
        organization_id: str,
        investigation_id: str,
        signals: list[Signal],
        claims: list[Claim],
        findings: list[Finding],
        evidence_items: list[Evidence],
        is_educational_or_warning: bool = False,
        repository: Optional[TenantRepository] = None,
    ) -> list[InvestigationStage]:
        """Reconstruct each stage of the scam chain with strict status determination."""
        stages: list[InvestigationStage] = []

        # Hard-negative safeguard: If content is identified as an educational warning,
        # circular, or official advice, do NOT reconstruct an active scam chain.
        if is_educational_or_warning:
            for idx, stage_name in enumerate(self.STAGE_ORDER):
                stg = InvestigationStage(
                    organization_id=organization_id,
                    investigation_id=investigation_id,
                    stage=stage_name,
                    status="NOT_OBSERVED",
                    details="Stage not observed: content is identified as legitimate regulatory warning or educational advisory.",
                    sequence_order=idx + 1,
                )
                stages.append(stg)
            return stages

        signal_types = {s.signal_type: s for s in signals}
        contradicted_findings = [f for f in findings if f.status == "CONTRADICTED"]

        for idx, stage_name in enumerate(self.STAGE_ORDER):
            status = "NOT_OBSERVED"
            details = ""
            sig_refs: list[str] = []
            evid_refs: list[str] = []

            if stage_name == "INITIAL_CONTACT":
                if "SOCIAL_MEDIA_SOLICITATION" in signal_types:
                    sig = signal_types["SOCIAL_MEDIA_SOLICITATION"]
                    status = "OBSERVED"
                    sig_refs.append(sig.id)
                    details = f"Unsolicited contact observed: '{sig.excerpt[:100]}'"

            elif stage_name == "AUTHORITY_IMPERSONATION":
                if "AUTHORITY_IMPERSONATION" in signal_types or "UNREGISTERED_ENTITY" in signal_types:
                    status = "OBSERVED"
                    if "AUTHORITY_IMPERSONATION" in signal_types:
                        sig_refs.append(signal_types["AUTHORITY_IMPERSONATION"].id)
                    if "UNREGISTERED_ENTITY" in signal_types:
                        sig_refs.append(signal_types["UNREGISTERED_ENTITY"].id)
                    details = "Claims of statutory authority or regulatory registration observed."

                # If authoritative verification contradicted the authority claim, escalate to SUPPORTED contradiction
                if contradicted_findings:
                    for cf in contradicted_findings:
                        if any(term in cf.statement.lower() for term in ["sebi", "cin", "registration", "exchange"]):
                            status = "SUPPORTED"
                            evid_refs.extend(cf.evidence_refs)
                            details = f"Authoritatively refuted registration: {cf.statement}"
                            break

            elif stage_name == "TRUST_BUILDING":
                if "SOCIAL_PROOF" in signal_types or "SECRECY_REQUEST" in signal_types:
                    status = "OBSERVED"
                    details = "Fabricated testimonials, social proof, or exclusivity tactics observed."

            elif stage_name == "INVESTMENT_PROMISE":
                if "GUARANTEED_RETURN" in signal_types or "HIGH_RETURN_PROMISE" in signal_types or "GREED_APPEAL" in signal_types:
                    status = "OBSERVED"
                    if "GUARANTEED_RETURN" in signal_types:
                        sig_refs.append(signal_types["GUARANTEED_RETURN"].id)
                    if "HIGH_RETURN_PROMISE" in signal_types:
                        sig_refs.append(signal_types["HIGH_RETURN_PROMISE"].id)
                    details = "Promise of guaranteed, fixed, or extraordinarily high returns observed."

                # Check if circulars contradicted guaranteed return
                for cf in contradicted_findings:
                    if "guaranteed return" in cf.statement.lower() or "circular" in cf.statement.lower():
                        status = "SUPPORTED"
                        evid_refs.extend(cf.evidence_refs)
                        details = f"Prohibited guaranteed returns corroborated by regulatory circular: {cf.statement}"

            elif stage_name == "DEPOSIT_REQUEST":
                if "THIRD_PARTY_PAYMENT" in signal_types or "UPI_MISMATCH" in signal_types:
                    status = "OBSERVED"
                    if "THIRD_PARTY_PAYMENT" in signal_types:
                        sig_refs.append(signal_types["THIRD_PARTY_PAYMENT"].id)
                    if "UPI_MISMATCH" in signal_types:
                        sig_refs.append(signal_types["UPI_MISMATCH"].id)
                    details = "Direct fund transfer requested to third-party or personal account."

            elif stage_name == "FAKE_PLATFORM":
                if "UNVERIFIED_APP" in signal_types or "SUSPICIOUS_URL" in signal_types:
                    status = "OBSERVED"
                    if "UNVERIFIED_APP" in signal_types:
                        sig_refs.append(signal_types["UNVERIFIED_APP"].id)
                    if "SUSPICIOUS_URL" in signal_types:
                        sig_refs.append(signal_types["SUSPICIOUS_URL"].id)
                    details = "Direct link to unverified APK, clone trading portal, or suspicious TLD."

            elif stage_name == "FAKE_PROFIT":
                if "FAKE_PROFIT" in signal_types:
                    status = "OBSERVED"
                    sig_refs.append(signal_types["FAKE_PROFIT"].id)
                    details = "Synthetic profit claims or fabricated portfolio returns presented."

            elif stage_name == "WITHDRAWAL_BLOCK":
                # If WITHDRAWAL_FEE is observed, withdrawal block is strongly INFERRED
                if "WITHDRAWAL_FEE" in signal_types:
                    status = "INFERRED"
                    details = "Withdrawal restriction inferred from requirement of upfront release fee."

            elif stage_name == "ADDITIONAL_PAYMENT":
                if "WITHDRAWAL_FEE" in signal_types:
                    status = "OBSERVED"
                    sig_refs.append(signal_types["WITHDRAWAL_FEE"].id)
                    details = "Demand for advance fee, tax, or deposit prior to releasing investor funds."

            elif stage_name == "CREDENTIAL_REQUEST":
                if "CREDENTIAL_REQUEST" in signal_types:
                    status = "OBSERVED"
                    sig_refs.append(signal_types["CREDENTIAL_REQUEST"].id)
                    details = "Solicitation of account passwords, trading PINs, or Demat credentials."

            elif stage_name == "OTP_REQUEST":
                if "OTP_REQUEST" in signal_types:
                    status = "OBSERVED"
                    sig_refs.append(signal_types["OTP_REQUEST"].id)
                    details = "Solicitation of one-time password (OTP) under guise of verification."

            elif stage_name == "DISAPPEARANCE":
                status = "UNKNOWN"
                details = "Channel status or perpetrator availability cannot be determined from static content."

            stage_obj = InvestigationStage(
                organization_id=organization_id,
                investigation_id=investigation_id,
                stage=stage_name,
                status=status,
                evidence_refs=evid_refs,
                signal_refs=sig_refs,
                details=details,
                sequence_order=idx + 1,
            )
            stages.append(stage_obj)

            if repository is not None:
                repository.save_scam_chain_stage(stage_obj)

        return stages
