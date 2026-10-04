"""High-fidelity demonstration fixtures for SANGYAN presentation and interactive walkthrough.

Provides realistic, authoritative cases modeled on pervasive financial deception funnels:
1. "Telegram 500% High-Yield Algo Scam" (Guaranteed returns, mule UPI routing)
2. "Counterfeit SEBI Research Analyst" (Spoofed registration number, fake certificate)
3. "Offshore Pre-IPO Escrow Trap" (Advance fee fraud, unauthorized offshore platform)
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional


def _sha3_256(text: str) -> str:
    return hashlib.sha3_256(text.encode("utf-8")).hexdigest()


DEMO_CASES: Dict[str, Dict[str, Any]] = {
    "case_telegram_algo": {
        "id": "inv_demo_telegram_algo_2026",
        "title": "Telegram Guaranteed Yield Algo Scam",
        "short_title": "Telegram 500% Algo Yield",
        "description": "Viral Telegram channel promising 70% monthly returns via automated algo-trading, routing victim funds to personal UPI VPAs.",
        "risk_level": "HIGH_RISK",
        "status": "COMPLETED",
        "created_at": 1775308800.0,
        "completed_at": 1775308808.5,
        "raw_content": (
            "🚀 EXCLUSIVE VIP ALGO-TRADING CLUB 🚀\n"
            "Guaranteed 70% monthly returns on your capital using proprietary AI quantum algorithms with 0% drawdown risk!\n"
            "SEBI Registered Research Analyst partner: AlphaQuant Advisors (Reg: INH000099999).\n"
            "Minimum deposit: ₹25,000. Send funds immediately via UPI to fastprofit24@paytm to activate your terminal.\n"
            "Warning: Only 3 slots left before group closes forever. Withdrawals processed within 15 minutes."
        ),
        "source_url": "https://t.me/AlphaQuantVIP_Official",
        "channel_name": "AlphaQuant VIP Official (Telegram)",
        "summary": "High-risk financial deception detected: Promising guaranteed returns violates SEBI PFUTP regulations; claimed registration INH000099999 is non-existent; recipient UPI identifier is a personal mule account.",
        "signals": [
            {
                "id": "sig_01",
                "type": "GUARANTEED_RETURN",
                "severity": "CRITICAL",
                "label": "Guaranteed Return Promise",
                "detail": "Promised 70% monthly return with zero drawdown risk.",
                "confidence": 0.99,
            },
            {
                "id": "sig_02",
                "type": "AUTHORITY_IMPERSONATION",
                "severity": "CRITICAL",
                "label": "Forged Regulatory Registration",
                "detail": "Claimed SEBI RA number INH000099999 does not exist in official registry.",
                "confidence": 0.98,
            },
            {
                "id": "sig_03",
                "type": "URGENCY",
                "severity": "HIGH",
                "label": "Artificial Urgency & Scarcity",
                "detail": "'Only 3 slots left before group closes forever'.",
                "confidence": 0.92,
            },
            {
                "id": "sig_04",
                "type": "THIRD_PARTY_PAYMENT",
                "severity": "CRITICAL",
                "label": "Mule UPI Payment Routing",
                "detail": "Personal VPA fastprofit24@paytm requested instead of recognized broker escrow.",
                "confidence": 0.96,
            },
        ],
        "claims": [
            {
                "id": "clm_01",
                "statement": "Guaranteed 70% monthly returns on your capital using proprietary algorithms with 0% drawdown risk.",
                "claim_type": "return",
                "status": "CONTRADICTED",
                "source_id": "src_sebi_circulars",
                "source_name": "SEBI Master Circular on Investor Protection & PFUTP",
                "authority_tier": "T0_REGULATOR",
                "excerpt": "Under SEBI (Prohibition of Fraudulent and Unfair Trade Practices) Regulations, no person or intermediary shall promise or offer assured or guaranteed returns in securities markets.",
                "content_hash": _sha3_256("SEBI PFUTP Reg 4(2)(k) Guaranteed Return Prohibition"),
                "rationale": "Direct violation of SEBI PFUTP statutory prohibitions. No registered entity is legally permitted to offer guaranteed yields.",
            },
            {
                "id": "clm_02",
                "statement": "SEBI Registered Research Analyst partner: AlphaQuant Advisors (Reg: INH000099999).",
                "claim_type": "regulatory",
                "status": "CONTRADICTED",
                "source_id": "src_sebi_intermediaries",
                "source_name": "SEBI Intermediaries Statutory Registry",
                "authority_tier": "T0_REGULATOR",
                "excerpt": "Registry query for registration identifier 'INH000099999' returned 0 records. Entity 'AlphaQuant Advisors' is not licensed as a Research Analyst.",
                "content_hash": _sha3_256("SEBI Query Result INH000099999 NOT FOUND"),
                "rationale": "Statutory registry search confirms registration identifier is forged and entity is unlicenced.",
            },
            {
                "id": "clm_03",
                "statement": "Withdrawals processed within 15 minutes to bank account.",
                "claim_type": "payment",
                "status": "INSUFFICIENT_EVIDENCE",
                "source_id": "src_rbi_caution",
                "source_name": "RBI Cautionary Database & Payment Oversight",
                "authority_tier": "T0_REGULATOR",
                "excerpt": "No institutional audit record exists for withdrawal SLA on unauthorized trading channels.",
                "content_hash": _sha3_256("RBI Withdrawal Audit Non-Existent"),
                "rationale": "No authoritative record substantiates the 15-minute withdrawal guarantee. Note: Insufficient evidence does not establish the claim is false.",
            },
        ],
        "scam_chain": [
            {"stage": 1, "name": "Social Hook / Bait", "status": "DETECTED", "evidence": "Public Telegram promo promising algorithmic trading profits."},
            {"stage": 2, "name": "Guaranteed Gain Lure", "status": "DETECTED", "evidence": "Explicit claim of 70% monthly return with zero drawdown."},
            {"stage": 3, "name": "Closed Group Transition", "status": "DETECTED", "evidence": "Channel directs users to private admin chat."},
            {"stage": 4, "name": "Authority Impersonation", "status": "DETECTED", "evidence": "Counterfeit SEBI RA registration number INH000099999."},
            {"stage": 5, "name": "Fabricated Social Proof", "status": "DETECTED", "evidence": "Screenshots of simulated MTM profits in group chat."},
            {"stage": 6, "name": "Test Deposit Trap", "status": "DETECTED", "evidence": "Initial request for ₹25,000 via UPI."},
            {"stage": 7, "name": "Simulated Dashboard Profit", "status": "SUSPECTED", "evidence": "Victim reported synthetic web dashboard showing 2x balance."},
            {"stage": 8, "name": "Coercive Upsell", "status": "SUSPECTED", "evidence": "Demand to upgrade to ₹1,00,000 tier for VIP trading pool."},
            {"stage": 9, "name": "Withdrawal Lock", "status": "DETECTED", "evidence": "Withdrawals blocked pending advance clearance."},
            {"stage": 10, "name": "Extortion / Release Fee", "status": "DETECTED", "evidence": "Demanding 18% GST deposit to unlock principal."},
            {"stage": 11, "name": "Loss Realization", "status": "DETECTED", "evidence": "Funds routed to mule accounts; victim blocked."},
            {"stage": 12, "name": "Identity Recycling", "status": "SUSPECTED", "evidence": "Admin accounts rotate under new handles every 14 days."},
        ],
        "graph": {
            "nodes": [
                {"id": "inv_01", "label": "Telegram Investigation", "type": "INVESTIGATION", "group": "root"},
                {"id": "c_return", "label": "Claim: 70% Monthly Yield", "type": "CLAIM", "status": "CONTRADICTED"},
                {"id": "c_sebi", "label": "Claim: SEBI INH000099999", "type": "CLAIM", "status": "CONTRADICTED"},
                {"id": "c_wdraw", "label": "Claim: 15-Min Withdrawal", "type": "CLAIM", "status": "INSUFFICIENT_EVIDENCE"},
                {"id": "ent_channel", "label": "t.me/AlphaQuantVIP", "type": "ENTITY", "category": "CHANNEL"},
                {"id": "ent_entity", "label": "AlphaQuant Advisors", "type": "ENTITY", "category": "IMPERSONATED_COMPANY"},
                {"id": "ent_vpa", "label": "fastprofit24@paytm", "type": "PAYMENT", "category": "UPI_MULE"},
                {"id": "src_sebi_reg", "label": "SEBI Intermediaries Registry", "type": "SOURCE", "tier": "T0"},
                {"id": "src_pfutp", "label": "SEBI PFUTP Master Circular", "type": "SOURCE", "tier": "T0"},
            ],
            "edges": [
                {"source": "inv_01", "target": "c_return", "relation": "EXTRACTED_FROM"},
                {"source": "inv_01", "target": "c_sebi", "relation": "EXTRACTED_FROM"},
                {"source": "inv_01", "target": "c_wdraw", "relation": "EXTRACTED_FROM"},
                {"source": "inv_01", "target": "ent_channel", "relation": "FOUND_IN"},
                {"source": "c_sebi", "target": "ent_entity", "relation": "REFERENCES"},
                {"source": "ent_channel", "target": "ent_vpa", "relation": "DIRECTS_PAYMENT"},
                {"source": "c_return", "target": "src_pfutp", "relation": "CONTRADICTED_BY"},
                {"source": "c_sebi", "target": "src_sebi_reg", "relation": "CONTRADICTED_BY"},
            ],
        },
        "trust_receipt": {
            "id": "rcpt_mldsa65_demo_01",
            "subject_type": "INVESTIGATION",
            "subject_id": "inv_demo_telegram_algo_2026",
            "algorithm_id": "ML-DSA-65",
            "standard": "FIPS 204 Post-Quantum Digital Signature Standard",
            "signing_key_id": "sangyan-hsm-pkcs11-slot0-key-mldsa65-2026",
            "public_key_fingerprint": "8b:42:f7:9e:1c:33:04:ad:65:21:bb:ee:90:3d:f1:aa:54:19:cc:02",
            "content_digest": _sha3_256("SANGYAN_CANONICAL_INV_TELEGRAM_ALGO_2026"),
            "signature_b64": "W7s2+a8Zc39kL89N2vV4p...[4,592 bytes post-quantum ML-DSA-65 signature]...==",
            "timestamp": 1775308808.5,
            "verification_status": "VERIFIED_AUTHENTIC",
        },
        "grievance": {
            "sebi_scores": {
                "portal_url": "https://scores.sebi.gov.in",
                "category": "Fraudulent / Unregistered Investment Advisory",
                "recommended_action": "File formal complaint against entity 'AlphaQuant Advisors' for offering guaranteed returns and forging registration identifier INH000099999.",
                "preservation_notes": "Preserve complete chat transcript, UPI transaction UTRs, and SANGYAN cryptographic dossier.",
            },
            "cybercrime_1930": {
                "portal_url": "https://cybercrime.gov.in",
                "helpline": "1930",
                "complaint_type": "Financial Cyber Fraud / Investment Mule Account",
                "suspect_vpa": "fastprofit24@paytm",
                "recommended_action": "Report suspect UPI VPA for immediate lien-marking under National Cybercrime Threat Analytics Unit (NCTAU).",
            },
        },
    },
    "case_fake_sebi_ra": {
        "id": "inv_demo_fake_sebi_ra_2026",
        "title": "Counterfeit SEBI Research Analyst Certificate",
        "short_title": "Forged SEBI Research Analyst",
        "description": "WhatsApp VIP advisory group operating under a forged SEBI Research Analyst registration certificate with spoofed corporate letterhead.",
        "risk_level": "HIGH_RISK",
        "status": "COMPLETED",
        "created_at": 1775312400.0,
        "completed_at": 1775312407.2,
        "raw_content": (
            "OFFICIAL NOTICE FROM SEBI REGISTERED RESEARCH ANALYST\n"
            "Name: Rajiv Sharma Capital Research\n"
            "SEBI Registration Number: INH200001844\n"
            "Registered Address: BKC, Bandra East, Mumbai 400051.\n"
            "We provide 100% verified intraday Nifty option calls with 1:5 risk-reward ratio.\n"
            "Monthly subscription fee: ₹15,000 paid to Axis Bank A/C 920020084920192 (IFSC: UTIB0000123).\n"
            "Certificate of registration verified by SEBI Western Regional Office."
        ),
        "source_url": "https://chat.whatsapp.com/inv/RajivSharmaResearchVIP",
        "channel_name": "Rajiv Sharma Research VIP (WhatsApp)",
        "summary": "Critical identity theft & fraud detected: Registration identifier INH200001844 belongs to a legitimate unrelated practitioner whose details were scraped and cloned; bank account beneficiary name does not match licensee.",
        "signals": [
            {
                "id": "sig_11",
                "type": "AUTHORITY_IMPERSONATION",
                "severity": "CRITICAL",
                "label": "Identity Spoofing of Licensed Intermediary",
                "detail": "License INH200001844 belongs to distinct registered individual with different registered contact details.",
                "confidence": 0.99,
            },
            {
                "id": "sig_12",
                "type": "HIGH_RETURN_PROMISE",
                "severity": "HIGH",
                "label": "Unrealistic Option Calls Promise",
                "detail": "Promising 100% verified intraday option calls.",
                "confidence": 0.94,
            },
            {
                "id": "sig_13",
                "type": "THIRD_PARTY_PAYMENT",
                "severity": "CRITICAL",
                "label": "Unregistered Bank Account Beneficiary",
                "detail": "Payment requested into personal bank account unlinked to official intermediary disclosures.",
                "confidence": 0.97,
            },
        ],
        "claims": [
            {
                "id": "clm_11",
                "statement": "SEBI Registration Number: INH200001844 associated with Rajiv Sharma Capital Research.",
                "claim_type": "regulatory",
                "status": "CONFLICTING",
                "source_id": "src_sebi_intermediaries",
                "source_name": "SEBI Intermediaries Statutory Registry",
                "authority_tier": "T0_REGULATOR",
                "excerpt": "Source A (SEBI Registry): INH200001844 is registered to 'Kunal Advisory Services' (Valid until 2027). Source B (Official Gazette): No entity named 'Rajiv Sharma Capital Research' exists under this registration code.",
                "content_hash": _sha3_256("SEBI Discrepancy Record INH200001844"),
                "rationale": "Conflicting authoritative determination: License code is active but assigned to an entirely different licensed entity. High probability of credentials cloning.",
            },
            {
                "id": "clm_12",
                "statement": "We provide 100% verified intraday Nifty option calls.",
                "claim_type": "return",
                "status": "CONTRADICTED",
                "source_id": "src_sebi_circulars",
                "source_name": "SEBI Study on Derivatives Trading & Retail Losses",
                "authority_tier": "T0_REGULATOR",
                "excerpt": "93% of individual traders in Equity F&O segment incurred net losses. Regulators forbid representation of options trading as guaranteed or assured income.",
                "content_hash": _sha3_256("SEBI F&O Retail Loss Circular"),
                "rationale": "Claims of '100% verified intraday option calls' mislead investors and contradict official empirical findings.",
            },
        ],
        "scam_chain": [
            {"stage": 1, "name": "Social Hook / Bait", "status": "DETECTED", "evidence": "Instagram reels promoting 100% accurate Nifty options."},
            {"stage": 2, "name": "Guaranteed Gain Lure", "status": "DETECTED", "evidence": "Promises of 1:5 daily risk-reward ratio."},
            {"stage": 3, "name": "Closed Group Transition", "status": "DETECTED", "evidence": "Moved to private WhatsApp VIP channel."},
            {"stage": 4, "name": "Authority Impersonation", "status": "DETECTED", "evidence": "Forged SEBI certificate displaying real licensee's number."},
            {"stage": 5, "name": "Fabricated Social Proof", "status": "DETECTED", "evidence": "Forged client profit screenshots."},
            {"stage": 6, "name": "Test Deposit Trap", "status": "DETECTED", "evidence": "₹15,000 monthly advisory subscription fee."},
            {"stage": 7, "name": "Simulated Dashboard Profit", "status": "SUSPECTED", "evidence": "Private tips delivered via WhatsApp."},
            {"stage": 8, "name": "Coercive Upsell", "status": "SUSPECTED", "evidence": "Push to enroll in ₹50,000 'HNI Portfolio Management' tier."},
            {"stage": 9, "name": "Withdrawal Lock", "status": "UNVERIFIED", "evidence": "Advisory model; loss occurs directly via market tips."},
            {"stage": 10, "name": "Extortion / Release Fee", "status": "UNVERIFIED", "evidence": "N/A for direct advisory scams."},
            {"stage": 11, "name": "Loss Realization", "status": "DETECTED", "evidence": "Subscribers suffer rapid capital depletion via unhedged options."},
            {"stage": 12, "name": "Identity Recycling", "status": "DETECTED", "evidence": "Operators change WhatsApp phone numbers once complaints surface."},
        ],
        "graph": {
            "nodes": [
                {"id": "inv_02", "label": "WhatsApp Impersonation", "type": "INVESTIGATION", "group": "root"},
                {"id": "c_license", "label": "Claim: INH200001844", "type": "CLAIM", "status": "CONFLICTING"},
                {"id": "c_options", "label": "Claim: 100% Win Rate", "type": "CLAIM", "status": "CONTRADICTED"},
                {"id": "ent_wa", "label": "WhatsApp VIP Group", "type": "ENTITY", "category": "CHANNEL"},
                {"id": "ent_spoofed", "label": "Rajiv Sharma Research", "type": "ENTITY", "category": "SPOOFED_ENTITY"},
                {"id": "ent_real_licensee", "label": "Kunal Advisory Services", "type": "ENTITY", "category": "LEGITIMATE_LICENSEE"},
                {"id": "ent_bank", "label": "Axis Bank 920020084920192", "type": "PAYMENT", "category": "SUSPECT_BANK_ACCOUNT"},
                {"id": "src_sebi_db", "label": "SEBI Intermediaries Registry", "type": "SOURCE", "tier": "T0"},
            ],
            "edges": [
                {"source": "inv_02", "target": "c_license", "relation": "EXTRACTED_FROM"},
                {"source": "inv_02", "target": "c_options", "relation": "EXTRACTED_FROM"},
                {"source": "c_license", "target": "ent_spoofed", "relation": "CLAIMED_BY"},
                {"source": "c_license", "target": "ent_real_licensee", "relation": "ACTUAL_OWNER"},
                {"source": "ent_wa", "target": "ent_bank", "relation": "COLLECTS_FEES"},
                {"source": "c_license", "target": "src_sebi_db", "relation": "CONFLICTING_WITH"},
            ],
        },
        "trust_receipt": {
            "id": "rcpt_mldsa65_demo_02",
            "subject_type": "INVESTIGATION",
            "subject_id": "inv_demo_fake_sebi_ra_2026",
            "algorithm_id": "ML-DSA-65",
            "standard": "FIPS 204 Post-Quantum Digital Signature Standard",
            "signing_key_id": "sangyan-hsm-pkcs11-slot0-key-mldsa65-2026",
            "public_key_fingerprint": "8b:42:f7:9e:1c:33:04:ad:65:21:bb:ee:90:3d:f1:aa:54:19:cc:02",
            "content_digest": _sha3_256("SANGYAN_CANONICAL_INV_FAKE_SEBI_RA_2026"),
            "signature_b64": "G6t7+x11K99zM22vV4p...[4,592 bytes post-quantum ML-DSA-65 signature]...==",
            "timestamp": 1775312407.2,
            "verification_status": "VERIFIED_AUTHENTIC",
        },
        "grievance": {
            "sebi_scores": {
                "portal_url": "https://scores.sebi.gov.in",
                "category": "Impersonation of Registered Research Analyst",
                "recommended_action": "Submit grievance under Intermediary Impersonation; inform real licensee Kunal Advisory Services for dual-filing.",
                "preservation_notes": "Preserve WhatsApp phone numbers, bank account IFSC, and forged PDF certificate.",
            },
            "cybercrime_1930": {
                "portal_url": "https://cybercrime.gov.in",
                "helpline": "1930",
                "complaint_type": "Impersonation / Cheating by Personation under IT Act Sec 66D",
                "suspect_bank": "Axis Bank A/C 920020084920192 (IFSC: UTIB0000123)",
                "recommended_action": "Request bank account freeze via 1930 NCRP quick-reporting pipeline.",
            },
        },
    },
    "case_offshore_escrow": {
        "id": "inv_demo_offshore_escrow_2026",
        "title": "Unregulated Offshore Pre-IPO Escrow Trap",
        "short_title": "Pre-IPO Offshore Escrow Trap",
        "description": "Fraudulent offshore platform soliciting Indian retail investors for unlisted unicorn shares with mandatory advance 'foreign exchange release tax'.",
        "risk_level": "HIGH_RISK",
        "status": "COMPLETED",
        "created_at": 1775316000.0,
        "completed_at": 1775316009.8,
        "raw_content": (
            "EXCLUSIVE PRE-IPO ALLOCATION PORTAL: ApexEquityGlobal.cc\n"
            "Direct allocation of Swiggy and Reliance Retail pre-IPO unlisted shares at 40% discount.\n"
            "Platform regulated under Cyprus Securities & Exchange Commission (CySEC license #88921).\n"
            "Funds settled via international escrow. Deposit via USDT TRC20 or UPI to apex.escrow@icici.\n"
            "Note: In accordance with FEMA regulations, an advance release tax of 20% is required before share allotment transfer."
        ),
        "source_url": "https://apexequityglobal.cc/pre-ipo/india",
        "channel_name": "Apex Equity Global (Web / Offshore)",
        "summary": "Severe cross-border fraud & FEMA violation: Domain registered 18 days ago on privacy proxy; entity appears on RBI Caution List; demanding 20% advance tax is textbook advance-fee fraud.",
        "signals": [
            {
                "id": "sig_21",
                "type": "UNREGISTERED_ENTITY",
                "severity": "CRITICAL",
                "label": "Unauthorized Foreign Trading Entity",
                "detail": "Platform operates without SEBI or RBI authorization for Indian residents.",
                "confidence": 0.99,
            },
            {
                "id": "sig_22",
                "type": "WITHDRAWAL_FEE",
                "severity": "CRITICAL",
                "label": "Advance-Fee Fraud Pattern",
                "detail": "Demanding 20% advance tax before allotment transfer.",
                "confidence": 0.99,
            },
            {
                "id": "sig_23",
                "type": "SUSPICIOUS_URL",
                "severity": "HIGH",
                "label": "Newly Registered Disposable Domain",
                "detail": "Domain apexequityglobal.cc created < 30 days ago with hidden WHOIS.",
                "confidence": 0.95,
            },
        ],
        "claims": [
            {
                "id": "clm_21",
                "statement": "Regulated under Cyprus Securities & Exchange Commission (CySEC license #88921).",
                "claim_type": "regulatory",
                "status": "CONTRADICTED",
                "source_id": "src_rbi_caution",
                "source_name": "RBI Caution List of Unauthorized Forex/Trading Platforms",
                "authority_tier": "T0_REGULATOR",
                "excerpt": "Entity 'ApexEquityGlobal' listed on RBI Alert List of entities unauthorized to deal in forex or securities solicitations for Indian residents.",
                "content_hash": _sha3_256("RBI Alert List Record ApexEquityGlobal"),
                "rationale": "Appears on official RBI Caution List. Dealing with unauthorized offshore platforms violates FEMA guidelines.",
            },
            {
                "id": "clm_22",
                "statement": "Advance release tax of 20% required under FEMA regulations.",
                "claim_type": "regulatory",
                "status": "CONTRADICTED",
                "source_id": "src_sebi_circulars",
                "source_name": "Reserve Bank of India FEMA Statutory Master Direction",
                "authority_tier": "T0_REGULATOR",
                "excerpt": "Indian tax and regulatory statutes do not require advance cash deposits into private merchant accounts to release share allotments.",
                "content_hash": _sha3_256("FEMA Advance Tax Misrepresentation"),
                "rationale": "Statutory provisions do not authorize private offshore entities to collect advance release taxes via UPI.",
            },
        ],
        "scam_chain": [
            {"stage": 1, "name": "Social Hook / Bait", "status": "DETECTED", "evidence": "Sponsored Google search ads targeting pre-IPO investors."},
            {"stage": 2, "name": "Guaranteed Gain Lure", "status": "DETECTED", "evidence": "Promising 40% pre-IPO discount."},
            {"stage": 3, "name": "Closed Group Transition", "status": "DETECTED", "evidence": "Portal redirects to dedicated 'account manager'."},
            {"stage": 4, "name": "Authority Impersonation", "status": "DETECTED", "evidence": "Fabricated CySEC license number."},
            {"stage": 5, "name": "Fabricated Social Proof", "status": "DETECTED", "evidence": "Fake trust pilot reviews on cloned site."},
            {"stage": 6, "name": "Test Deposit Trap", "status": "DETECTED", "evidence": "Initial share purchase payment via UPI."},
            {"stage": 7, "name": "Simulated Dashboard Profit", "status": "DETECTED", "evidence": "Fake depository allotment certificate generated."},
            {"stage": 8, "name": "Coercive Upsell", "status": "DETECTED", "evidence": "Encouraged to buy additional IPO tranches."},
            {"stage": 9, "name": "Withdrawal Lock", "status": "DETECTED", "evidence": "Shares locked in 'international escrow'."},
            {"stage": 10, "name": "Extortion / Release Fee", "status": "DETECTED", "evidence": "Demanding 20% advance tax before transfer."},
            {"stage": 11, "name": "Loss Realization", "status": "DETECTED", "evidence": "Total capital loss if release fee is paid."},
            {"stage": 12, "name": "Identity Recycling", "status": "DETECTED", "evidence": "Domain scheduled for takedown; mirror domain registered."},
        ],
        "graph": {
            "nodes": [
                {"id": "inv_03", "label": "Offshore Pre-IPO Investigation", "type": "INVESTIGATION", "group": "root"},
                {"id": "c_cysec", "label": "Claim: CySEC #88921", "type": "CLAIM", "status": "CONTRADICTED"},
                {"id": "c_fema", "label": "Claim: 20% FEMA Tax", "type": "CLAIM", "status": "CONTRADICTED"},
                {"id": "ent_dom", "label": "apexequityglobal.cc", "type": "ENTITY", "category": "FRAUD_DOMAIN"},
                {"id": "ent_upi", "label": "apex.escrow@icici", "type": "PAYMENT", "category": "MULE_UPI"},
                {"id": "src_rbi", "label": "RBI Caution List", "type": "SOURCE", "tier": "T0"},
                {"id": "src_fema", "label": "RBI FEMA Master Direction", "type": "SOURCE", "tier": "T0"},
            ],
            "edges": [
                {"source": "inv_03", "target": "c_cysec", "relation": "EXTRACTED_FROM"},
                {"source": "inv_03", "target": "c_fema", "relation": "EXTRACTED_FROM"},
                {"source": "inv_03", "target": "ent_dom", "relation": "HOSTED_AT"},
                {"source": "ent_dom", "target": "ent_upi", "relation": "DIRECTS_FUNDS_TO"},
                {"source": "c_cysec", "target": "src_rbi", "relation": "CONTRADICTED_BY"},
                {"source": "c_fema", "target": "src_fema", "relation": "CONTRADICTED_BY"},
            ],
        },
        "trust_receipt": {
            "id": "rcpt_mldsa65_demo_03",
            "subject_type": "INVESTIGATION",
            "subject_id": "inv_demo_offshore_escrow_2026",
            "algorithm_id": "ML-DSA-65",
            "standard": "FIPS 204 Post-Quantum Digital Signature Standard",
            "signing_key_id": "sangyan-hsm-pkcs11-slot0-key-mldsa65-2026",
            "public_key_fingerprint": "8b:42:f7:9e:1c:33:04:ad:65:21:bb:ee:90:3d:f1:aa:54:19:cc:02",
            "content_digest": _sha3_256("SANGYAN_CANONICAL_INV_OFFSHORE_ESCROW_2026"),
            "signature_b64": "H9v8+b33L77zM44vV4p...[4,592 bytes post-quantum ML-DSA-65 signature]...==",
            "timestamp": 1775316009.8,
            "verification_status": "VERIFIED_AUTHENTIC",
        },
        "grievance": {
            "sebi_scores": {
                "portal_url": "https://scores.sebi.gov.in",
                "category": "Fraudulent Unlisted Securities Solicitation",
                "recommended_action": "Submit information to SEBI Market Surveillance regarding unauthorized public solicitation of unlisted shares.",
                "preservation_notes": "Preserve domain WHOIS records, SSL certificate issuer, and payment transaction receipts.",
            },
            "cybercrime_1930": {
                "portal_url": "https://cybercrime.gov.in",
                "helpline": "1930",
                "complaint_type": "Cross-Border Investment Scam / FEMA Advance-Fee Fraud",
                "suspect_vpa": "apex.escrow@icici",
                "recommended_action": "Report mule UPI account and register domain takedown request via Indian Cyber Crime Coordination Centre (I4C).",
            },
        },
    },
}


def get_demo_cases() -> List[Dict[str, Any]]:
    """Return summary metadata for all demo cases."""
    return [
        {
            "id": k,
            "title": v["title"],
            "short_title": v["short_title"],
            "description": v["description"],
            "risk_level": v["risk_level"],
            "channel_name": v["channel_name"],
            "claims_count": len(v["claims"]),
            "signals_count": len(v["signals"]),
        }
        for k, v in DEMO_CASES.items()
    ]


def get_demo_case(case_id: str) -> Optional[Dict[str, Any]]:
    """Return full investigation fixture for the specified demo case."""
    return DEMO_CASES.get(case_id)
