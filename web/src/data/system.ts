export interface SystemStat {
  label: string;
  value: string;
  change?: string;
  tone?: "brand" | "ok" | "warn" | "fail" | "cyan";
  detail?: string;
}

export const SYSTEM_STATS: SystemStat[] = [
  {
    label: "Registry Ingestion",
    value: "100%",
    tone: "ok",
    detail: "SEBI, NSE, BSE & MCA statutory sync active",
  },
  {
    label: "Cryptographic Seal",
    value: "ML-DSA-65",
    tone: "cyan",
    detail: "NIST FIPS 204 post-quantum signature lattice",
  },
  {
    label: "Canonical Digest",
    value: "SHA3-256",
    tone: "brand",
    detail: "Strict RFC-8785 JSON canonical hashing",
  },
  {
    label: "Observable Signals",
    value: "20+",
    tone: "warn",
    detail: "Zero hallucination rule-grounded detectors",
  },
  {
    label: "Mean Latency",
    value: "412 ms",
    tone: "brand",
    detail: "Claim deconstruction to verified seal",
  },
];

export const AUTHORITY_TIERS = [
  {
    tier: "T0",
    name: "Statutory Regulators",
    entities: "SEBI, RBI, MCA, 1930 Cybercrime Portal",
    weight: "Absolute Authority",
    role: "Definitive registration state, circular bans, disciplinary actions.",
  },
  {
    tier: "T1",
    name: "Market Infrastructure",
    entities: "NSE, BSE, NSDL, CDSL, Clearing Corps",
    weight: "Authoritative Operational",
    role: "Listed scrip status, corporate actions, member broker terminals.",
  },
  {
    tier: "T2",
    name: "Primary Intermediaries",
    entities: "SEBI Registered Brokers, Custodians, RAs, RIAs",
    weight: "Primary Entity",
    role: "Verified disclosures, formal research reports, official portals.",
  },
  {
    tier: "T3",
    name: "Established Financial Press",
    entities: "Mint, Business Standard, Economic Times, Reuters",
    weight: "Corroborative",
    role: "Secondary corroboration; cannot override T0/T1 statutory registries.",
  },
  {
    tier: "T4",
    name: "General Web Media",
    entities: "Independent blogs, forums, domain whois records",
    weight: "Contextual",
    role: "Domain age verification, certificate telemetry, phishing infrastructure.",
  },
  {
    tier: "T5",
    name: "User Generated Content",
    entities: "Telegram VIP channels, WhatsApp groups, Instagram Reels",
    weight: "Subject of Investigation",
    role: "Treated exclusively as evidence to investigate, never authoritative truth.",
  },
];

export const STRICT_GUARDRAILS = [
  {
    title: "Zero Investment Advice",
    description:
      "SANGYAN strictly evaluates deceptive patterns and regulatory standing. It never provides stock tips, price targets, or trading recommendations.",
  },
  {
    title: "Zero Black-Box Probabilities",
    description:
      "Rejects arbitrary percentages like '94.2% scam likelihood'. Every finding is explicitly linked to statutory rules, falsified claims, or observable signals.",
  },
  {
    title: "Zero Hallucinated Registrations",
    description:
      "Queries live official registries. If an intermediary registration number is missing or revoked, SANGYAN states verifiable facts with official timestamps.",
  },
  {
    title: "Safe Action Escrow Guidance",
    description:
      "Directs harmed users to official statutory grievance channels (SEBI SCORES, National Cybercrime Portal 1930, Bank Ombudsman) rather than fee-charging 'recovery agents'.",
  },
];
