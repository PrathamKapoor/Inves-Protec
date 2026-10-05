import Reveal from "../../components/anim/Reveal";
import { SIGNAL_CATALOG } from "../../data/signals";
import { Radio } from "lucide-react";
import "./SignalsSection.css";

export default function SignalsSection() {
  return (
    <section className="section" id="signals" style={{ background: "var(--bg-1)", borderTop: "1px solid var(--line)" }}>
      <div className="container">
        <div className="section-head">
          <Reveal>
            <div className="section-eyebrow">
              <Radio size={14} />
              <span>OBSERVABLE SIGNAL DETECTORS</span>
            </div>
            <h2 className="section-title">20+ Concrete Deception Signatures</h2>
            <p className="section-desc">
              SANGYAN detects concrete linguistic and operational scam artifacts rather than relying on black-box sentiment. Every triggered signal is linked to its statutory regulatory violation.
            </p>
          </Reveal>
        </div>

        <div className="signals-grid">
          {SIGNAL_CATALOG.map((sig, idx) => (
            <Reveal key={sig.id} delay={idx * 50}>
              <div className="signal-card card-interactive">
                <div>
                  <div className="signal-card-head" style={{ marginBottom: "0.75rem" }}>
                    <span className="mono" style={{ fontSize: "0.72rem", color: "var(--text-3)" }}>
                      {sig.id}
                    </span>
                    <span className={sig.severity === "CRITICAL" ? "badge badge-fail" : "badge badge-warn"}>
                      {sig.severity}
                    </span>
                  </div>
                  <h3 className="signal-name">{sig.name}</h3>
                  <p className="signal-desc" style={{ marginTop: "0.5rem" }}>{sig.description}</p>
                </div>
                <div className="signal-legal-basis">
                  <strong>Statute:</strong> {sig.legalBasis}
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
