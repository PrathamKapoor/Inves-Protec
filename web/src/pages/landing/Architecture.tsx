import Reveal from "../../components/anim/Reveal";
import { Layers } from "lucide-react";
import "./Architecture.css";

const LAYERS = [
  {
    num: "LAYER 01",
    title: "Ingest & Security Gateway",
    module: "sangyan.ingest · sangyan.security",
    desc: "FastAPI ASGI layer with tenant partitioning, JWT & API Key authentication, rate limiting, and strict anti-SSRF IP pinning.",
    tech: "FastAPI · Redis Limiter · IP Pinning",
  },
  {
    num: "LAYER 02",
    title: "Intelligence & NLP",
    module: "sangyan.intelligence",
    desc: "Decomposes compound messages into atomic claims. Runs 20+ observable signal detectors across English, Hindi, and Hinglish.",
    tech: "spaCy · Regex Matrix · Transformer Embeddings",
  },
  {
    num: "LAYER 03",
    title: "Verification & Registry Sync",
    module: "sangyan.verification",
    desc: "Authoritative adapters querying SEBI, NSE, BSE, and MCA registries with persistent SQLite and Redis snapshot caching.",
    tech: "SEBI T0 Adapter · NSE/BSE API · MCA Sync",
  },
  {
    num: "LAYER 04",
    title: "StateGraph & Workflow Checkpointer",
    module: "sangyan.workflow",
    desc: "Durable LangGraph StateGraph engine with interruptible review gates, allowing human supervisory audit before final issuance.",
    tech: "LangGraph · SQLite Checkpointer · Human Gate",
  },
  {
    num: "LAYER 05",
    title: "Post-Quantum Cryptographic Trust",
    module: "sangyan.crypto · sangyan.trust",
    desc: "Produces RFC-8785 canonical JSON digests (SHA3-256) and signs with NIST FIPS 204 ML-DSA-65 (Dilithium) lattice cryptography.",
    tech: "ML-DSA-65 · SHA3-256 · PKCS#11 HSM",
  },
  {
    num: "LAYER 06",
    title: "Real-time Telemetry & SSE Streaming",
    module: "sangyan.realtime · sangyan.api.sse",
    desc: "Event-driven Server-Sent Events broker streaming live investigation progress to regulatory dashboards with zero polling lag.",
    tech: "SSE Broker · Redis Streams · Prometheus Metrics",
  },
];

export default function Architecture() {
  return (
    <section className="section" id="architecture">
      <div className="container">
        <div className="section-head">
          <Reveal>
            <div className="section-eyebrow">
              <Layers size={14} />
              <span>SYSTEM BLUEPRINT</span>
            </div>
            <h2 className="section-title">Production Modular Architecture</h2>
            <p className="section-desc">
              SANGYAN is engineered as an enterprise-grade defense infrastructure with strict separation of concerns, zero circular dependencies, and post-quantum trust anchoring.
            </p>
          </Reveal>
        </div>

        <div className="arch-grid">
          {LAYERS.map((layer, idx) => (
            <Reveal key={layer.num} delay={idx * 60}>
              <div className="arch-layer-card card-interactive">
                <div>
                  <div className="arch-layer-header">
                    <span className="arch-layer-num">{layer.num}</span>
                    <span className="badge badge-brand mono" style={{ fontSize: "0.7rem" }}>
                      {layer.module}
                    </span>
                  </div>
                  <h3 className="arch-layer-title">{layer.title}</h3>
                  <p className="arch-layer-desc" style={{ marginTop: "0.5rem" }}>{layer.desc}</p>
                </div>
                <div className="arch-layer-footer">
                  <span>STACK:</span>
                  <span style={{ color: "var(--brand-bright)" }}>{layer.tech}</span>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
