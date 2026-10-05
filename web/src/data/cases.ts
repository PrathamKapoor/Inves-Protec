export interface ClaimRecord {
  id: string;
  statement: string;
  claimType?: "return" | "regulatory" | "operational" | "payment";
  claim_type?: "return" | "regulatory" | "operational" | "payment";
  status: "CONTRADICTED" | "SUPPORTED" | "CONFLICTING" | "OUTDATED" | "UNVERIFIED";
  sourceName: string;
  authorityTier: string;
  excerpt: string;
  contentHash: string;
  rationale: string;
}

export interface SignalInstance {
  id: string;
  type: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM";
  label: string;
  detail: string;
  confidence: number;
}

export interface InvestigationCase {
  id: string;
  title: string;
  shortTitle: string;
  description: string;
  riskLevel: "CRITICAL_RISK" | "HIGH_RISK" | "ELEVATED_RISK" | "VERIFIED_SAFE";
  rawContent: string;
  sourceUrl: string;
  channelName: string;
  summary: string;
  signals: SignalInstance[];
  claims: ClaimRecord[];
  safeGuidance: {
    immediateAction: string;
    escalationChannel: string;
    filingUrl: string;
    preservationNotes: string;
  };
  receipt: {
    receiptId: string;
    algorithm: string;
    canonicalHash: string;
    signatureHex: string;
    publicKeyFingerprint: string;
    timestamp: string;
    signedBy: string;
  };
}

export const DEMO_CASES: Record<string, InvestigationCase> = {
  case_telegram_algo: {
    id: "inv_2026_algo_9481",
    title: "Telegram Guaranteed Yield Algo Scam",
    shortTitle: "Telegram 70% Monthly Yield",
    description: "Viral Telegram channel promising 70% monthly returns via automated algo-trading, routing victim funds to personal UPI VPAs.",
    riskLevel: "CRITICAL_RISK",
    rawContent: `🚀 EXCLUSIVE VIP ALGO-TRADING CLUB 🚀
Guaranteed 70% monthly returns on your capital using proprietary AI quantum algorithms with 0% drawdown risk!
SEBI Registered Research Analyst partner: AlphaQuant Advisors (Reg: INH000099999).
Minimum deposit: ₹25,000. Send funds immediately via UPI to fastprofit24@paytm to activate your terminal.
Warning: Only 3 slots left before group closes forever. Withdrawals processed within 15 minutes.`,
    sourceUrl: "https://t.me/AlphaQuantVIP_Official",
    channelName: "AlphaQuant VIP Official (Telegram)",
    summary: "High-risk financial deception detected: Promising guaranteed returns violates SEBI PFUTP regulations; claimed registration INH000099999 is non-existent; recipient UPI identifier is a personal mule account.",
    signals: [
      {
        id: "sig_01",
        type: "GUARANTEED_RETURN",
        severity: "CRITICAL",
        label: "Guaranteed Return Promise",
        detail: "Promised 70% monthly return with zero drawdown risk.",
        confidence: 0.99,
      },
      {
        id: "sig_02",
        type: "AUTHORITY_IMPERSONATION",
        severity: "CRITICAL",
        label: "Forged Regulatory Registration",
        detail: "Claimed SEBI RA number INH000099999 does not exist in official registry.",
        confidence: 0.98,
      },
      {
        id: "sig_03",
        type: "URGENCY",
        severity: "HIGH",
        label: "Artificial Urgency & Scarcity",
        detail: "'Only 3 slots left before group closes forever'.",
        confidence: 0.92,
      },
      {
        id: "sig_04",
        type: "THIRD_PARTY_PAYMENT",
        severity: "CRITICAL",
        label: "Mule UPI Payment Routing",
        detail: "Personal VPA fastprofit24@paytm requested instead of recognized broker escrow.",
        confidence: 0.96,
      },
    ],
    claims: [
      {
        id: "clm_01",
        statement: "Guaranteed 70% monthly returns on your capital using proprietary algorithms with 0% drawdown risk.",
        claim_type: "return",
        status: "CONTRADICTED",
        sourceName: "SEBI Master Circular on Investor Protection & PFUTP",
        authorityTier: "T0 (Regulator)",
        excerpt: "Under SEBI (Prohibition of Fraudulent and Unfair Trade Practices) Regulations, no person or intermediary shall promise or offer assured or guaranteed returns in securities markets.",
        contentHash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        rationale: "Direct violation of SEBI PFUTP statutory prohibitions. No registered entity is legally permitted to offer guaranteed yields.",
      },
      {
        id: "clm_02",
        statement: "SEBI Registered Research Analyst partner: AlphaQuant Advisors (Reg: INH000099999).",
        claim_type: "regulatory",
        status: "CONTRADICTED",
        sourceName: "SEBI Intermediaries Statutory Registry",
        authorityTier: "T0 (Regulator)",
        excerpt: "Registry query for registration identifier 'INH000099999' returned 0 records. Entity 'AlphaQuant Advisors' is not licensed as a Research Analyst.",
        contentHash: "8a4f2c9183b27e5d0b9826315cf3276189ef04d2e93b1853a47b85e0514197c3",
        rationale: "Statutory registry search confirms registration identifier is forged and entity is unlicenced.",
      },
      {
        id: "clm_03",
        statement: "Withdrawals processed within 15 minutes to bank account.",
        claim_type: "operational",
        status: "UNVERIFIED",
        sourceName: "Empirical Liquidity Model & Payment Telemetry",
        authorityTier: "T4 (Empirical)",
        excerpt: "No audited banking integration exists. Historical reports indicate withdrawal fees demanded upon capital release attempts.",
        contentHash: "1f8b4a2e5d9c7b6f3a0e8d1c4b7a2e5f8d9c6b3a0e7f4d1c8b5a2e9d6c3b0a7f",
        rationale: "Standard advance-fee trap pattern: withdrawals are blocked once funds are deposited.",
      },
    ],
    safeGuidance: {
      immediateAction: "DO NOT send funds to fastprofit24@paytm. Cease all communications immediately.",
      escalationChannel: "National Cyber Crime Reporting Portal (1930) & SEBI SCORES",
      filingUrl: "https://scores.sebi.gov.in",
      preservationNotes: "Take full-screen screenshots of the Telegram channel, profile info, and message history before leaving the group.",
    },
    receipt: {
      receiptId: "rcpt_mldsa65_948102b4",
      algorithm: "ML-DSA-65 (NIST FIPS 204)",
      canonicalHash: "4f9d8a1e2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e",
      signatureHex: "3f82a17cb49910d54a20b701c43d89ef...[3309 bytes lattice sig]...9a12c8b0",
      publicKeyFingerprint: "sha3-256:7b92f4410a881bc3d2e94711fa62b083c51239aa812f",
      timestamp: "2026-10-05T07:22:18Z",
      signedBy: "SANGYAN-AUTHORITY-NODE-01 (HSM-SLOT-04)",
    },
  },
  case_fake_sebi_advisor: {
    id: "inv_2026_sebi_advisor_3120",
    title: "Spoofed SEBI Research Analyst Certification",
    shortTitle: "Fake SEBI Certificate INH200001234",
    description: "WhatsApp broadcast circulating an embossed counterfeit SEBI certificate in the name of 'Sharma Capital Advisory' offering paid intraday calls.",
    riskLevel: "CRITICAL_RISK",
    rawContent: `OFFICIAL SEBI RESEARCH ANALYST ACCREDITATION
Entity: Sharma Capital Advisory LLP
SEBI Reg No: INH200001234 (Valid till 2030)
Join our Premium Nifty & BankNifty Jackpot Option Calls. 100% accuracy guaranteed.
Registration charges: ₹9,999/quarter. Transfer to Bank of Baroda A/C 918237192837 IFSC: BARB0KOTHAR.`,
    sourceUrl: "https://chat.whatsapp.com/inv_sharma_capital",
    channelName: "Sharma Capital VIP Calls (WhatsApp)",
    summary: "Counterfeit regulatory certificate: Registration format is spoofed; SEBI registry shows Sharma Capital Advisory LLP has never held an RA or RIA licence; claims of 100% options accuracy are fraudulent.",
    signals: [
      {
        id: "sig_11",
        type: "FORGED_CERTIFICATE",
        severity: "CRITICAL",
        label: "Counterfeit Government Document",
        detail: "Digital inspection reveals SEBI watermark and digital signature are digitally fabricated.",
        confidence: 0.99,
      },
      {
        id: "sig_12",
        type: "GUARANTEED_RETURN",
        severity: "CRITICAL",
        label: "100% Accuracy Claim in Derivatives",
        detail: "Promising guaranteed profits in F&O violates statutory market realities (SEBI study: 93% retail traders lose money).",
        confidence: 0.99,
      },
      {
        id: "sig_13",
        type: "UNREGISTERED_ADVISORY",
        severity: "CRITICAL",
        label: "Unregistered Investment Advice",
        detail: "No active SEBI intermediary record found under INH200001234.",
        confidence: 0.99,
      },
    ],
    claims: [
      {
        id: "clm_11",
        statement: "Entity Sharma Capital Advisory LLP holds SEBI Reg No INH200001234.",
        claim_type: "regulatory",
        status: "CONTRADICTED",
        sourceName: "SEBI Registered Intermediary Directory",
        authorityTier: "T0 (Regulator)",
        excerpt: "Official registry search for INH200001234 returned NO RESULTS. Identifier format does not match SEBI issued sequence.",
        contentHash: "c189b4f2a7102e3b8a9d6e4c2f1a0b5d8e7c4a1b2d3e4f5a6b7c8d9e0f1a2b3c",
        rationale: "Statutory registry confirms the registration number is completely fabricated.",
      },
      {
        id: "clm_12",
        statement: "100% accuracy guaranteed on Nifty & BankNifty Option Calls.",
        claim_type: "return",
        status: "CONTRADICTED",
        sourceName: "SEBI Derivative Study & Circular on Risk Disclosures",
        authorityTier: "T0 (Regulator)",
        excerpt: "9 out of 10 individual traders in equity F&O segment incurred net losses. Statutory prohibition exists on claims of guaranteed derivative success.",
        contentHash: "9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d",
        rationale: "Mathematical and legal impossibility in Indian listed markets.",
      },
    ],
    safeGuidance: {
      immediateAction: "Refuse payment. Do not trade on recommended option strikes.",
      escalationChannel: "SEBI Vigilance & SCORES Portal",
      filingUrl: "https://scores.sebi.gov.in",
      preservationNotes: "Export WhatsApp chat with media to preserve the fake certificate file with metadata.",
    },
    receipt: {
      receiptId: "rcpt_mldsa65_312019ab",
      algorithm: "ML-DSA-65 (NIST FIPS 204)",
      canonicalHash: "7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b",
      signatureHex: "2a149b01c7d833fa...[3309 bytes lattice sig]...88cf1092e",
      publicKeyFingerprint: "sha3-256:1289ab74e019c43d8a7b9012f45ea889102bc45129",
      timestamp: "2026-10-05T07:24:45Z",
      signedBy: "SANGYAN-AUTHORITY-NODE-02",
    },
  },
  case_offshore_escrow_trap: {
    id: "inv_2026_offshore_7712",
    title: "Offshore Pre-IPO Secondary Escrow Scam",
    shortTitle: "Offshore Pre-IPO Escrow Trap",
    description: "Invitation-only link offering unlisted shares of Indian unicorn startups through an unregistered Saint Vincent LLC escrow portal.",
    riskLevel: "HIGH_RISK",
    rawContent: `PRIVATE ALLOCATION: PRE-IPO UNICORN BASKET
Acquire unlisted shares of Swiggy & Zepto at 45% discount prior to public listing.
Transfers cleared via GlobalClear Capital Escrow (SVG IBC Reg: 918237).
Minimum allotment: ₹1,00,000. USDT TRC20 or Wire Transfer to Mauritius bank account accepted.
Guaranteed listing gains of minimum 250% on NSE listing day.`,
    sourceUrl: "https://globalclear-preipo-portal.io",
    channelName: "GlobalClear Allocations",
    summary: "Illegal offshore solicitation: Offers unlisted securities without SEBI RTA / Depository validation; offshore entity violates RBI LRS remittances for margin trading; promises guaranteed listing gains.",
    signals: [
      {
        id: "sig_21",
        type: "OFFSHORE_SOLICITATION",
        severity: "CRITICAL",
        label: "Unauthorized Offshore Intermediary",
        detail: "Entity operates outside SEBI/RBI jurisdiction, offering Indian securities with offshore USDT wire.",
        confidence: 0.97,
      },
      {
        id: "sig_22",
        type: "GUARANTEED_RETURN",
        severity: "CRITICAL",
        label: "Guaranteed Listing Gain Promise",
        detail: "Promise of 250% listing day gains violates securities laws.",
        confidence: 0.98,
      },
      {
        id: "sig_23",
        type: "DEPOSITORY_BYPASS",
        severity: "HIGH",
        label: "Bypasses NSDL / CDSL Demat Transfer",
        detail: "Legitimate Indian unlisted shares require off-market CDSL/NSDL DIS slips or validated escrow.",
        confidence: 0.95,
      },
    ],
    claims: [
      {
        id: "clm_21",
        statement: "GlobalClear Capital Escrow is authorized to escrow Indian pre-IPO securities.",
        claim_type: "regulatory",
        status: "CONTRADICTED",
        sourceName: "SEBI & RBI Alert List of Unauthorized Offshore Entities",
        authorityTier: "T0 (Regulator)",
        excerpt: "Offshore entities not registered with SEBI cannot act as custodians, depositories or intermediaries for Indian equity shares.",
        contentHash: "8b9a0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b",
        rationale: "Direct contravention of FEMA guidelines and SEBI Intermediary regulations.",
      },
    ],
    safeGuidance: {
      immediateAction: "Do not wire fiat or send USDT. Verify any unlisted shares through recognized SEBI RTAs.",
      escalationChannel: "RBI Sachet Portal & SEBI Investigation Cell",
      filingUrl: "https://sachet.rbi.org.in",
      preservationNotes: "Save domain WHOIS records, transaction wallet addresses, and email communications.",
    },
    receipt: {
      receiptId: "rcpt_mldsa65_771299ef",
      algorithm: "ML-DSA-65 (NIST FIPS 204)",
      canonicalHash: "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b",
      signatureHex: "9910d54a20b701c43...[3309 bytes lattice sig]...149b01c7d",
      publicKeyFingerprint: "sha3-256:45ea889102bc451291289ab74e019c43d8a7b9012f",
      timestamp: "2026-10-05T07:28:10Z",
      signedBy: "SANGYAN-AUTHORITY-NODE-03",
    },
  },
};
