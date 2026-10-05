import { useState } from "react";
import { Link } from "react-router-dom";
import Reveal from "../../components/anim/Reveal";
import { DEMO_CASES } from "../../data/cases";
import { ArrowUpRight, CheckCircle2, ShieldAlert, Terminal } from "lucide-react";
import "./ProductPreview.css";

export default function ProductPreview() {
  const [tab, setTab] = useState<"findings" | "signals" | "receipts">("findings");

  return (
    <section className="section" id="preview">
      <div className="container-wide">
        <div className="section-head">
          <Reveal>
            <div className="section-eyebrow">
              <Terminal size={14} />
              <span>THE OPERATIONAL WORKBENCH</span>
            </div>
            <h2 className="section-title">Built for Regulatory & Defense Workflows</h2>
            <p className="section-desc">
              Inspect suspicious claims, trace multi-tier evidence lineage, and review cryptographically sealed investigation dossiers in real time.
            </p>
          </Reveal>
        </div>

        <Reveal delay={120}>
          <div className="preview-container">
            <div className="preview-chrome-bar">
              <div className="preview-dots">
                <span className="preview-dot" style={{ background: "#ef4444" }} />
                <span className="preview-dot" style={{ background: "#f59e0b" }} />
                <span className="preview-dot" style={{ background: "#10b981" }} />
              </div>

              <div className="preview-tab-pills">
                <button
                  onClick={() => setTab("findings")}
                  className={`preview-tab-btn ${tab === "findings" ? "active" : ""}`}
                >
                  Active Findings
                </button>
                <button
                  onClick={() => setTab("signals")}
                  className={`preview-tab-btn ${tab === "signals" ? "active" : ""}`}
                >
                  Observed Signals
                </button>
                <button
                  onClick={() => setTab("receipts")}
                  className={`preview-tab-btn ${tab === "receipts" ? "active" : ""}`}
                >
                  PQC Trust Receipts
                </button>
              </div>

              <Link to="/console" className="btn btn-secondary" style={{ fontSize: "0.75rem", padding: "0.3rem 0.75rem" }}>
                <span>Expand Full Console</span>
                <ArrowUpRight size={13} />
              </Link>
            </div>

            <div className="preview-body">
              <div className="preview-grid-3">
                <div className="preview-card-stat">
                  <div style={{ fontSize: "0.75rem", color: "var(--text-3)", textTransform: "uppercase", marginBottom: "0.25rem" }}>
                    Active Ingest Queue
                  </div>
                  <div style={{ fontSize: "1.75rem", fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--text-1)" }}>
                    14 Payload Streams
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--ok)", marginTop: "0.25rem" }}>
                    ● Real-time SSE listening on port 8000
                  </div>
                </div>

                <div className="preview-card-stat">
                  <div style={{ fontSize: "0.75rem", color: "var(--text-3)", textTransform: "uppercase", marginBottom: "0.25rem" }}>
                    Critical Deceptions Flagged
                  </div>
                  <div style={{ fontSize: "1.75rem", fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--fail)" }}>
                    9 High-Risk Entities
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-3)", marginTop: "0.25rem" }}>
                    Statutory T0 violations detected
                  </div>
                </div>

                <div className="preview-card-stat">
                  <div style={{ fontSize: "0.75rem", color: "var(--text-3)", textTransform: "uppercase", marginBottom: "0.25rem" }}>
                    PQC Receipts Anchored
                  </div>
                  <div style={{ fontSize: "1.75rem", fontWeight: 700, fontFamily: "var(--font-mono)", color: "var(--brand-bright)" }}>
                    142 Sealed Dossiers
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--accent-cyan)", marginTop: "0.25rem" }}>
                    NIST FIPS 204 ML-DSA-65 Validated
                  </div>
                </div>
              </div>

              {tab === "findings" && (
                <div style={{ overflowX: "auto" }}>
                  <table className="preview-table">
                    <thead>
                      <tr>
                        <th>CLAIM IDENTIFIER</th>
                        <th>CLAIM STATEMENT</th>
                        <th>STATUTORY STATUS</th>
                        <th>PRIMARY CITATION</th>
                        <th>ACTION GUIDANCE</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td className="mono" style={{ color: "var(--brand-bright)" }}>CLM_ALGO_01</td>
                        <td>"Guaranteed 70% monthly returns with 0% drawdown"</td>
                        <td><span className="badge badge-fail">CONTRADICTED</span></td>
                        <td>SEBI PFUTP Reg 4(2)(k)</td>
                        <td>Freeze UPI fastprofit24@paytm</td>
                      </tr>
                      <tr>
                        <td className="mono" style={{ color: "var(--brand-bright)" }}>CLM_ALGO_02</td>
                        <td>"SEBI RA Reg: INH000099999 AlphaQuant Advisors"</td>
                        <td><span className="badge badge-fail">CONTRADICTED</span></td>
                        <td>SEBI Intermediaries Registry (0 records)</td>
                        <td>File SCORES 2.0 Complaint</td>
                      </tr>
                      <tr>
                        <td className="mono" style={{ color: "var(--brand-bright)" }}>CLM_SEBI_11</td>
                        <td>"Counterfeit SEBI RA Certificate INH200001234"</td>
                        <td><span className="badge badge-fail">CONTRADICTED</span></td>
                        <td>SEBI Public Enforcement Alert 2026</td>
                        <td>Escalate 1930 Cybercrime</td>
                      </tr>
                      <tr>
                        <td className="mono" style={{ color: "var(--brand-bright)" }}>CLM_PREIPO_21</td>
                        <td>"Saint Vincent LLC unlisted Swiggy equity escrow"</td>
                        <td><span className="badge badge-fail">CONTRADICTED</span></td>
                        <td>RBI / FEMA Foreign Exchange Alert List</td>
                        <td>Block Offshore Wire Transfer</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}

              {tab === "signals" && (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "1rem" }}>
                  {Object.values(DEMO_CASES).flatMap(c => c.signals).slice(0, 6).map((s, idx) => (
                    <div key={idx} style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: "1rem", borderRadius: "8px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                        <span className="mono" style={{ fontSize: "0.75rem", color: "var(--text-3)" }}>{s.type}</span>
                        <span className={s.severity === "CRITICAL" ? "badge badge-fail" : "badge badge-warn"}>{s.severity}</span>
                      </div>
                      <div style={{ fontWeight: 600, color: "var(--text-1)", fontSize: "0.9rem", marginBottom: "0.25rem" }}>{s.label}</div>
                      <div style={{ fontSize: "0.8rem", color: "var(--text-2)" }}>{s.detail}</div>
                    </div>
                  ))}
                </div>
              )}

              {tab === "receipts" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  {Object.values(DEMO_CASES).map(c => (
                    <div key={c.receipt.receiptId} style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: "1rem", borderRadius: "8px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                          <span className="mono" style={{ fontWeight: 600, color: "var(--accent-cyan)" }}>{c.receipt.receiptId}</span>
                          <span className="badge badge-brand">{c.receipt.algorithm}</span>
                        </div>
                        <div style={{ fontSize: "0.8rem", color: "var(--text-2)" }}>Case: {c.title}</div>
                      </div>
                      <div className="mono" style={{ fontSize: "0.75rem", color: "var(--text-3)", textAlign: "right" }}>
                        <div>Digest: {c.receipt.canonicalHash.substring(0, 24)}...</div>
                        <div style={{ color: "var(--ok)" }}>Signed by: {c.receipt.signedBy}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
