"""Grievance Classification and Institutional Routing Subsystem for SANGYAN.

Categorizes investor disputes and fraud incidents into official grievance pathways
(SEBI SCORES, SMART ODR, Cybercrime 1930, RBI CMS, DoT Chakshu) without automated external submission.
"""
from __future__ import annotations

from typing import Any, Optional

from sangyan.domain.models import Finding, GrievanceRecord, Signal
from sangyan.tenancy.repository import TenantRepository


class GrievanceRouter:
    """Classifies grievance inquiries and maps them to authoritative institutional resolution channels."""

    def classify_and_route(
        self,
        organization_id: str,
        investigation_id: str,
        content_text: str,
        signals: list[Signal],
        findings: list[Finding],
        scam_patterns: list[str],
        repository: Optional[TenantRepository] = None,
    ) -> GrievanceRecord:
        """Determine grievance classification and produce official institutional routing steps."""
        text_lower = content_text.lower()
        signal_types = {s.signal_type for s in signals}
        has_fraud_patterns = len(scam_patterns) > 0
        has_contradictions = any(f.status == "CONTRADICTED" for f in findings)

        # 1. Cyber Fraud / Investment Scam by Unregistered Bad Actors
        if has_fraud_patterns or has_contradictions or "WITHDRAWAL_FEE" in signal_types:
            category = "INVESTMENT_SCAM" if "INVESTMENT_SCAM" in scam_patterns else "CYBER_FRAUD"
            record = GrievanceRecord(
                organization_id=organization_id,
                investigation_id=investigation_id,
                category=category,
                routing_channel="National Cybercrime Reporting Portal & Citizen Financial Cyber Fraud Reporting System",
                portal_url="https://cybercrime.gov.in",
                helpline="1930",
                guidance_steps=[
                    "Dial the National Cybercrime Financial Fraud Helpline at 1930 immediately to trigger an urgent freeze on the recipient bank account or UPI VPA.",
                    "File a formal cyber fraud complaint on the National Cybercrime Reporting Portal (https://cybercrime.gov.in) under 'Financial Fraud'.",
                    "Attach all preserved payment proofs: banking transaction receipts, UTR numbers, beneficiary UPI handles, chat transcripts, and screenshots.",
                    "Report the fraudulent telecom number, WhatsApp handle, or SMS sender on the Department of Telecommunications (DoT) Chakshu portal (https://sancharsaathi.gov.in/sfc/).",
                ],
                metadata={"source_classification": "fraud_pattern_detected", "scam_patterns": scam_patterns},
            )

        # 2. Broker Grievance (Dispute with registered broker)
        elif any(term in text_lower for term in ["broker", "trading account", "demat", "zerodha", "groww", "angelone", "upstox", "shares uncredited", "order execution"]):
            record = GrievanceRecord(
                organization_id=organization_id,
                investigation_id=investigation_id,
                category="BROKER_GRIEVANCE",
                routing_channel="SEBI SCORES & Stock Exchange Investor Grievance Redressal Committee (IGRC)",
                portal_url="https://scores.sebi.gov.in",
                helpline="1800-266-7575",
                guidance_steps=[
                    "Step 1: Lodge a written formal complaint with your broker's dedicated Grievance Redressal Officer (GRO) citing your Client ID and trade references.",
                    "Step 2: If the broker does not respond or resolve the issue within 30 days, lodge an online complaint on SEBI SCORES (https://scores.sebi.gov.in).",
                    "Step 3: Simultaneously submit an investor grievance to the Investor Service Centre (ISC) of the relevant exchange (NSE/BSE).",
                    "Step 4: If you remain aggrieved by the exchange recommendation, escalate to online dispute resolution via SMART ODR (https://smartodr.in).",
                ],
                metadata={"source_classification": "registered_broker_dispute"},
            )

        # 3. Adviser / Research Analyst Grievance
        elif any(term in text_lower for term in ["adviser", "advisor", "research analyst", "tips", "recommendation", "tipster"]):
            record = GrievanceRecord(
                organization_id=organization_id,
                investigation_id=investigation_id,
                category="ADVISER_GRIEVANCE",
                routing_channel="SEBI SCORES Intermediary Redressal",
                portal_url="https://scores.sebi.gov.in",
                helpline="1800-22-7575",
                guidance_steps=[
                    "Verify whether the adviser is SEBI-registered (INA / INH prefix). Unregistered tip services should be reported under Cyber Fraud.",
                    "For registered advisers, issue a written grievance to their designated compliance desk.",
                    "If unresolved within 30 days, register your grievance on SEBI SCORES with contract notes, fee invoices, and advisory agreements.",
                ],
                metadata={"source_classification": "adviser_dispute"},
            )

        # 4. Banking / Payment Dispute
        elif any(term in text_lower for term in ["bank", "upi debit", "unauthorized transaction", "chargeback", "atm", "card"]):
            record = GrievanceRecord(
                organization_id=organization_id,
                investigation_id=investigation_id,
                category="BANKING_PAYMENT_ISSUE",
                routing_channel="RBI Complaint Management System (CMS) & Bank Grievance Redressal",
                portal_url="https://cms.rbi.gov.in",
                helpline="14448",
                guidance_steps=[
                    "Notify your bank immediately (within 3 working days) to invoke zero/limited customer liability under RBI regulations on unauthorized electronic transactions.",
                    "Request a dispute form / chargeback claim and obtain a written complaint tracking number.",
                    "If the bank fails to resolve your grievance within 30 days or rejects your claim, escalate to the RBI Ombudsman via the CMS portal (https://cms.rbi.gov.in).",
                ],
                metadata={"source_classification": "banking_payment_dispute"},
            )

        # 5. Default / General Information Request
        else:
            record = GrievanceRecord(
                organization_id=organization_id,
                investigation_id=investigation_id,
                category="INFORMATION_REQUEST",
                routing_channel="SEBI Investor Awareness & Official Regulator Directory",
                portal_url="https://investor.sebi.gov.in",
                helpline="1800-22-7575",
                guidance_steps=[
                    "Check the regulatory standing of entities on the SEBI portal before engaging in transactions.",
                    "Review SEBI educational resources on investor rights, precautions against unverified tips, and dispute mechanisms at https://investor.sebi.gov.in.",
                    "Contact the SEBI Investor Toll-Free Helpline at 1800-22-7575 for guidance on registered market structures.",
                ],
                metadata={"source_classification": "general_inquiry"},
            )

        if repository is not None:
            repository.save_grievance_record(record)

        return record
