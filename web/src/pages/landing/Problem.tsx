import Reveal from "../../components/anim/Reveal";
import { AlertTriangle, CheckCircle, ShieldAlert, ShieldCheck, XCircle } from "lucide-react";
import "./Problem.css";

export default function Problem() {
  return (
    <section className="section" id="decomposition">
      <div className="container">
        <div className="section-head">
          <Reveal>
            <div className="section-eyebrow">
              <AlertTriangle size={14} />
              <span>THE ARCHITECTURAL PROBLEM</span>
            </div>
            <h2 className="section-title">Why Black-Box AI Fails Retail Investors</h2>
            <p className="section-desc">
              Unstructured financial schemes rely on compound messages that blend truth with deception. Generic LLMs hallucinate compliance and produce unverifiable probability scores.
            </p>
          </Reveal>
        </div>

        <div className="problem-grid">
          <Reveal delay={100}>
            <div className="problem-card problem-card-negative">
              <div>
                <div className="problem-card-header">
                  <ShieldAlert size={24} style={{ color: "var(--fail)" }} />
                  <div>
                    <h3 style={{ fontSize: "1.25rem", color: "var(--fail)" }}>Generic LLM Black Boxes</h3>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-3)" }}>Unreliable for fraud investigation</span>
                  </div>
                </div>

                <ul className="problem-points">
                  <li className="problem-point-item">
                    <XCircle size={18} style={{ color: "var(--fail)", flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      <h4>Arbitrary Scam Probabilities</h4>
                      <p>Outputs ungrounded numbers like "87% scam likelihood" without legal basis or citeable statutory facts.</p>
                    </div>
                  </li>
                  <li className="problem-point-item">
                    <XCircle size={18} style={{ color: "var(--fail)", flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      <h4>Regulatory Hallucinations</h4>
                      <p>Fabricates SEBI registration statuses or accepts forged certificate images without querying live databases.</p>
                    </div>
                  </li>
                  <li className="problem-point-item">
                    <XCircle size={18} style={{ color: "var(--fail)", flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      <h4>Advisory Guardrail Failure</h4>
                      <p>Accidentally offers trading tips or validates high-risk penny stocks under clever user prompt phrasing.</p>
                    </div>
                  </li>
                  <li className="problem-point-item">
                    <XCircle size={18} style={{ color: "var(--fail)", flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      <h4>Zero Legal Chain of Custody</h4>
                      <p>No cryptographic tamper-proofing or verifiable evidence bundle admissible for regulatory enforcement.</p>
                    </div>
                  </li>
                </ul>
              </div>
            </div>
          </Reveal>

          <Reveal delay={200}>
            <div className="problem-card problem-card-positive">
              <div>
                <div className="problem-card-header">
                  <ShieldCheck size={24} style={{ color: "var(--ok)" }} />
                  <div>
                    <h3 style={{ fontSize: "1.25rem", color: "var(--ok)" }}>SANGYAN Evidence Grounding</h3>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-3)" }}>Cryptographic statutory audit</span>
                  </div>
                </div>

                <ul className="problem-points">
                  <li className="problem-point-item">
                    <CheckCircle size={18} style={{ color: "var(--ok)", flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      <h4>Atomic Claim Decomposition</h4>
                      <p>Deconstructs compound messages into independently verifiable sub-claims (return promise, licensing, payment method).</p>
                    </div>
                  </li>
                  <li className="problem-point-item">
                    <CheckCircle size={18} style={{ color: "var(--ok)", flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      <h4>Live Statutory Registry Queries</h4>
                      <p>Directly queries SEBI intermediary registries, NSE/BSE member databases, and MCA CIN records.</p>
                    </div>
                  </li>
                  <li className="problem-point-item">
                    <CheckCircle size={18} style={{ color: "var(--ok)", flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      <h4>Explicit Multi-Valued Stances</h4>
                      <p>Classifies claims as CONTRADICTED, SUPPORTED, CONFLICTING, or OUTDATED with statutory citations.</p>
                    </div>
                  </li>
                  <li className="problem-point-item">
                    <CheckCircle size={18} style={{ color: "var(--ok)", flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      <h4>Post-Quantum ML-DSA-65 Receipts</h4>
                      <p>Signs SHA3-256 canonical investigation bundles with NIST FIPS 204 lattice cryptography for judicial custody.</p>
                    </div>
                  </li>
                </ul>
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
