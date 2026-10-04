"""Safe Action Guidance Engine for SANGYAN.

Generates conditionally tailored, evidence-backed non-investment next steps
and incident preservation guidelines for investor safety.
"""
from __future__ import annotations

from typing import Any, Optional

from sangyan.domain.models import ActionGuidance, Finding, Signal
from sangyan.tenancy.repository import TenantRepository


class GuidanceEngine:
    """Produces conditional, non-investment safe action guidance based on observed evidence."""

    def generate_guidance(
        self,
        signals: list[Signal],
        findings: list[Finding],
        scam_patterns: list[str],
        repository: Optional[TenantRepository] = None,
    ) -> list[ActionGuidance]:
        """Generate deduplicated, prioritized action guidance items."""
        guidance_items: list[ActionGuidance] = []
        signal_types = {s.signal_type for s in signals}
        has_contradictions = any(f.status == "CONTRADICTED" for f in findings)
        is_high_risk = has_contradictions or len(scam_patterns) > 0 or len(signal_types) >= 2

        # 1. Credential Safety Guidance
        if "OTP_REQUEST" in signal_types or "CREDENTIAL_REQUEST" in signal_types or "OTP_THEFT" in scam_patterns:
            guidance_items.append(
                ActionGuidance(
                    category="CREDENTIAL_SAFETY",
                    title="Do Not Disclose OTPs, Passwords, or Trading PINs",
                    description=(
                        "Never share your OTP, trading account password, or Demat PIN. Regulated market "
                        "intermediaries, statutory authorities, and exchange officials will never request "
                        "one-time passwords or security credentials over phone, messaging apps, or email."
                    ),
                    priority=1,
                    urgency=True,
                    limitations="Guidance addresses credential security; does not assess account balance or trade status.",
                )
            )

        # 2. Withdrawal Safety Guidance
        if "WITHDRAWAL_FEE" in signal_types or "WITHDRAWAL_FEE_SCAM" in scam_patterns:
            guidance_items.append(
                ActionGuidance(
                    category="WITHDRAWAL_SAFETY",
                    title="Do Not Transfer Additional Funds to Release Investments",
                    description=(
                        "Refrain from sending additional money, taxes, or release charges to withdraw your funds. "
                        "Legitimate SEBI-registered brokers deduct statutory levies (such as STT and exchange fees) "
                        "directly from your trading ledger balance and never require upfront advance transfers."
                    ),
                    priority=1,
                    urgency=True,
                    limitations="Non-investment safety rule; does not resolve underlying account ledger disputes.",
                )
            )

        # 3. Official Verification Guidance
        if (
            "AUTHORITY_IMPERSONATION" in signal_types
            or "UNREGISTERED_ENTITY" in signal_types
            or "AUTHORITY_IMPERSONATION" in scam_patterns
            or "UNREGISTERED_INTERMEDIARY" in scam_patterns
            or has_contradictions
        ):
            guidance_items.append(
                ActionGuidance(
                    category="OFFICIAL_VERIFICATION",
                    title="Verify Registration on the Official SEBI Intermediaries Portal",
                    description=(
                        "Independently confirm whether the entity holds a valid, active registration directly "
                        "on the SEBI portal (https://www.sebi.gov.in) or recognized exchange member directories "
                        "(NSE, BSE, MCX) prior to transferring any capital."
                    ),
                    official_url="https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpi=yes",
                    priority=2,
                    urgency=False,
                    limitations="Verification confirms regulatory registration status; does not guarantee investment returns.",
                )
            )

        # 4. Banking & Payment Safety Guidance
        if "THIRD_PARTY_PAYMENT" in signal_types or "UPI_MISMATCH" in signal_types or "THIRD_PARTY_PAYMENT" in scam_patterns:
            guidance_items.append(
                ActionGuidance(
                    category="BANKING_PAYMENT_SAFETY",
                    title="Verify Payment Beneficiary Name and Corporate Account",
                    description=(
                        "Only deposit funds into bank accounts or UPI VPAs verified in the corporate name of your "
                        "registered broker. Never transfer investment funds to personal accounts, individual UPI IDs, "
                        "or unverified third-party intermediaries."
                    ),
                    priority=2,
                    urgency=True,
                    limitations="Safety measure against payment diversion; does not guarantee banking recovery.",
                )
            )

        # 5. Incident Preservation Guidance
        if is_high_risk:
            guidance_items.append(
                ActionGuidance(
                    category="PRESERVE_EVIDENCE",
                    title="Preserve Complete Transaction and Communication Evidence",
                    description=(
                        "Secure all forensic records immediately: save uncropped screenshots of promotional messages, "
                        "preserve banking transaction receipts and UTR/UPI reference numbers, record phone numbers and "
                        "Telegram/WhatsApp channel links, and export chat histories for legal and grievance reporting."
                    ),
                    priority=3,
                    urgency=False,
                    limitations="Evidence preservation aids reporting; does not constitute formal legal filing.",
                )
            )

        # 6. Cybercrime Reporting Guidance
        if "INVESTMENT_SCAM" in scam_patterns or "PHISHING_CREDENTIAL_THEFT" in scam_patterns or has_contradictions:
            guidance_items.append(
                ActionGuidance(
                    category="CYBERCRIME_1930",
                    title="Report Financial Cyber Fraud to 1930 / Cybercrime Portal",
                    description=(
                        "If you have transferred funds to an unverified or fraudulent scheme, immediately contact the "
                        "National Cybercrime Reporting helpline by dialing 1930 or submit a formal cyber incident "
                        "report at https://cybercrime.gov.in to initiate bank account debit freezing."
                    ),
                    official_url="https://cybercrime.gov.in",
                    priority=1,
                    urgency=True,
                    limitations="Helpline connects with state cyber police and participating banks.",
                )
            )

        # Optional persistence
        if repository is not None:
            for g in guidance_items:
                repository.save_guidance(g)

        return guidance_items
