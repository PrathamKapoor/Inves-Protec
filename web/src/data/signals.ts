export interface SignalDefinition {
  id: string;
  name: string;
  category: "guarantee" | "impersonation" | "pressure" | "payment" | "platform";
  severity: "CRITICAL" | "HIGH" | "MEDIUM";
  description: string;
  legalBasis: string;
}

export const SIGNAL_CATALOG: SignalDefinition[] = [
  {
    id: "SIG_GUARANTEED_RETURN",
    name: "Guaranteed Return Promise",
    category: "guarantee",
    severity: "CRITICAL",
    description: "Promises fixed daily, weekly, or monthly percentage yield on securities investments.",
    legalBasis: "SEBI PFUTP Regulations 2003, Reg 4(2)(k)",
  },
  {
    id: "SIG_AUTHORITY_IMPERSONATION",
    name: "SEBI / Exchange Impersonation",
    category: "impersonation",
    severity: "CRITICAL",
    description: "Display of forged SEBI certificates, spoofed registration numbers, or NSE/BSE logos.",
    legalBasis: "IPC Sec 465 / 468 (Forgery), IT Act Sec 66D",
  },
  {
    id: "SIG_MULE_PAYMENT",
    name: "Mule Account / Personal UPI Routing",
    category: "payment",
    severity: "CRITICAL",
    description: "Requests investor funds transferred to individual savings accounts or personal VPAs rather than recognized broker client accounts.",
    legalBasis: "SEBI Master Circular on Handling of Client Funds",
  },
  {
    id: "SIG_ADVANCE_WITHDRAWAL_FEE",
    name: "Advance Fee / Tax for Withdrawal",
    category: "payment",
    severity: "CRITICAL",
    description: "Demands upfront payment of 'GST', 'SEBI release tax', or 'processing fee' before locked funds can be withdrawn.",
    legalBasis: "BNS / IPC Sec 420 (Criminal Cheating)",
  },
  {
    id: "SIG_ARTIFICIAL_URGENCY",
    name: "Artificial Urgency & Scarcity",
    category: "pressure",
    severity: "HIGH",
    description: "Statements like 'Only 2 seats left', 'Closing in 10 minutes', or 'One-time insider offer'.",
    legalBasis: "Consumer Protection (E-Commerce) Rules 2020",
  },
  {
    id: "SIG_UNREGISTERED_ADVISORY",
    name: "Unregistered Investment Advice",
    category: "platform",
    severity: "HIGH",
    description: "Offering specific stock buy/sell calls or portfolio management without SEBI RIA/RA license.",
    legalBasis: "SEBI (Investment Advisers) Regulations 2013",
  },
  {
    id: "SIG_OFFSHORE_FOREX_BINARY",
    name: "Unauthorized Offshore Forex / Binary",
    category: "platform",
    severity: "HIGH",
    description: "Promoting offshore platforms offering leveraged FX or binary options forbidden for resident Indians.",
    legalBasis: "RBI Alert List of Unauthorized Forex Trading Platforms",
  },
  {
    id: "SIG_RECOVERY_FEE_SCAM",
    name: "Phantom Asset Recovery Trap",
    category: "payment",
    severity: "HIGH",
    description: "Impersonating cybercrime officers or ethical hackers promising to recover lost funds for an upfront fee.",
    legalBasis: "MHA Cybercrime Advisory & IT Act Sec 66D",
  },
];
