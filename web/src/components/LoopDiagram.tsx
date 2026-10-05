import { useState } from "react";
import Reveal from "./anim/Reveal";
import "./LoopDiagram.css";

export interface PipelineStage {
  key: string;
  step: string;
  label: string;
  subsystem: string;
  description: string;
  specs: [string, string][];
}

const STAGES: PipelineStage[] = [
  {
    key: "intake",
    step: "01",
    label: "Intake & SSRF Guard",
    subsystem: "sangyan.ingest",
    description:
      "Captures suspicious input payloads across raw text, forwarded messages, documents, or URLs with strict anti-SSRF IP pinning and zero outbound network poisoning.",
    specs: [
      ["Input Types", "Text · Telegram · WhatsApp · PDF · Screenshots"],
      ["Network Security", "Strict SSRF IP validation · Non-routable subnet rejection"],
      ["Size Envelope", "Bounded 10 MB maximum payload streaming"],
    ],
  },
  {
    key: "deconstruct",
    step: "02",
    label: "Semantic Decomposition",
    subsystem: "sangyan.intelligence.claims",
    description:
      "Breaks compound messages into atomic, independently auditable sub-claims. Separates financial promises, regulatory assertions, and payment instructions.",
    specs: [
      ["Segmentation", "Atomic claim graph generation"],
      ["Entity Resolution", "NER for SEBI registration, CIN, broker names, VPAs"],
      ["Language Support", "English, Hindi, Hinglish, regional scripts"],
    ],
  },
  {
    key: "signals",
    step: "03",
    label: "Observable Signal Scan",
    subsystem: "sangyan.intelligence.signals",
    description:
      "Scans for 20+ concrete, observable persuasion and fraud indicators. Never outputs vague vibes; every signal links to explicit rule tokens.",
    specs: [
      ["Detector Count", "20+ active financial fraud rules"],
      ["High-Priority Patterns", "Guaranteed yield · Forged certificates · Mule UPIs"],
      ["Explainability", "Observable quote extraction & confidence weight"],
    ],
  },
  {
    key: "registry",
    step: "04",
    label: "Authoritative T0 Query",
    subsystem: "sangyan.verification.engine",
    description:
      "Cross-references extracted entities against authoritative regulatory registries (SEBI Registered Intermediaries, NSE/BSE member lists, MCA CIN portal).",
    specs: [
      ["Statutory Sources", "SEBI Intermediaries · NSE/BSE Exchanges · MCA"],
      ["Cache Strategy", "Durable SQLite / Redis with TTL and SHA-256 snapshots"],
      ["Ground Truth", "Zero hallucinated registration status"],
    ],
  },
  {
    key: "stance",
    step: "05",
    label: "Multi-Valued Stance",
    subsystem: "sangyan.correlation.engine",
    description:
      "Evaluates evidence hierarchy (T0 Regulator to T5 Social Media) to assign deterministic stances: SUPPORTED, CONTRADICTED, CONFLICTING, or OUTDATED.",
    specs: [
      ["Stance Classes", "SUPPORTED · CONTRADICTED · CONFLICTING · OUTDATED"],
      ["Conflict Resolution", "Statutory T0 supremacy over lower-tier claims"],
      ["Explainability", "'Why Flagged' plain-language reasoning generation"],
    ],
  },
  {
    key: "seal",
    step: "06",
    label: "Post-Quantum Seal",
    subsystem: "sangyan.trust.service",
    description:
      "Constructs canonical RFC-8785 JSON digest (SHA3-256) of the investigation bundle and signs with NIST FIPS 204 ML-DSA-65 (Dilithium) lattice cryptography.",
    specs: [
      ["Cryptographic Standard", "NIST FIPS 204 ML-DSA-65"],
      ["Digest Method", "RFC-8785 Canonical JSON + SHA3-256"],
      ["HSM Interface", "PKCS#11 / HSM slot hardware integration"],
    ],
  },
];

export default function LoopDiagram() {
  const [activeStage, setActiveStage] = useState<PipelineStage>(STAGES[1]!);

  return (
    <div className="loop-container">
      <Reveal>
        <ol className="loop-rail" aria-label="Investigation execution pipeline stages">
          {STAGES.map((s, i) => {
            const isActive = s.key === activeStage.key;
            return (
              <li className="loop-node-wrap" key={s.key}>
                <button
                  className={`loop-node ${isActive ? "is-active" : ""}`}
                  onClick={() => setActiveStage(s)}
                  aria-pressed={isActive}
                >
                  <span className="loop-node-index">{s.step}</span>
                  <span>{s.label}</span>
                </button>
                {i < STAGES.length - 1 && (
                  <span className="loop-arrow" aria-hidden="true">
                    <svg width="14" height="10" viewBox="0 0 14 10" fill="none">
                      <path d="M1 5h10.4M8.6 1.4 12.2 5 8.6 8.6" stroke="currentColor" strokeWidth="1.3" />
                    </svg>
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      </Reveal>

      <Reveal delay={120}>
        <div className="loop-detail-panel" aria-live="polite">
          <div className="loop-detail-head">
            <div className="loop-detail-title-wrap">
              <span className="loop-detail-step">{activeStage.step} / {STAGES.length}</span>
              <h3 className="loop-detail-title">{activeStage.label}</h3>
            </div>
            <span className="badge badge-brand">
              <span className="mono">{activeStage.subsystem}</span>
            </span>
          </div>

          <p className="loop-detail-body">{activeStage.description}</p>

          <div className="loop-detail-spec-grid">
            {activeStage.specs.map(([k, v], idx) => (
              <div key={idx} className="loop-detail-spec-item">
                <span className="loop-spec-k">{k}</span>
                <span className="loop-spec-v">{v}</span>
              </div>
            ))}
          </div>
        </div>
      </Reveal>
    </div>
  );
}
