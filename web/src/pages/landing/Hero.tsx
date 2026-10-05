import { useState } from "react";
import { Link } from "react-router-dom";
import Grainient from "../../components/Grainient";
import Reveal from "../../components/anim/Reveal";
import { DEMO_CASES } from "../../data/cases";
import { ArrowRight, CheckCircle2, ShieldAlert, Sparkles, Terminal } from "lucide-react";
import "./Hero.css";

export default function Hero() {
  const caseKeys = Object.keys(DEMO_CASES);
  const [activeCaseKey, setActiveCaseKey] = useState<string>(caseKeys[0] || "case_telegram_algo");
  const activeCase = DEMO_CASES[activeCaseKey] || DEMO_CASES["case_telegram_algo"]!;

  return (
    <section className="hero-section" id="hero">
      {/* Background WebGL Grainient Component from React Bits */}
      <div className="hero-grainient-bg">
        <Grainient
          color1="#FF9FFC"
          color2="#5227FF"
          color3="#B497CF"
          timeSpeed={0.25}
          colorBalance={0.0}
          warpStrength={1.0}
          warpFrequency={5.0}
          warpSpeed={2.0}
          warpAmplitude={50.0}
          blendAngle={0.0}
          blendSoftness={0.05}
          rotationAmount={500.0}
          noiseScale={2.0}
          grainAmount={0.1}
          grainScale={2.0}
          grainAnimated={false}
          contrast={1.5}
          gamma={1.0}
          saturation={1.0}
          centerX={0.0}
          centerY={0.0}
          zoom={0.9}
        />
      </div>

      <div className="container">
        <div className="hero-content">
          <Reveal delay={0}>
            <div className="hero-eyebrow">
              <Sparkles size={13} style={{ color: "#38bdf8" }} />
              <span>POST-QUANTUM INVESTOR SAFETY · NIST FIPS 204</span>
            </div>
          </Reveal>

          <Reveal delay={80}>
            <h1 className="hero-title">
              Investor Safety Driven by <span className="hero-title-gradient">Ground Truth</span>, Not AI Hallucinations.
            </h1>
          </Reveal>

          <Reveal delay={140}>
            <p className="hero-subtitle">
              SANGYAN deconstructs compound financial promotions into discrete claims, verifies them against live statutory SEBI and Exchange registries, and seals findings with post-quantum ML-DSA-65 cryptography.
            </p>
          </Reveal>

          <Reveal delay={200}>
            <div className="hero-cta-group">
              <Link to="/console" className="btn-hero-launch">
                <Terminal size={17} />
                <span>Launch Interactive Console</span>
                <ArrowRight size={16} />
              </Link>
              <a href="#pipeline" className="btn-hero-secondary">
                <span>Explore Verification Pipeline</span>
              </a>
            </div>
          </Reveal>

          {/* Interactive Live Teaser Box */}
          <Reveal delay={260}>
            <div className="hero-sandbox-card">
              <div className="hero-sandbox-head">
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <ShieldAlert size={16} style={{ color: "var(--fail)" }} />
                  <span style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--text-1)" }}>
                    Live Deconstruction & Stance Verification Preview
                  </span>
                </div>
                <div className="hero-sandbox-presets">
                  {caseKeys.map((k) => (
                    <button
                      key={k}
                      onClick={() => setActiveCaseKey(k)}
                      className={`preset-chip ${activeCaseKey === k ? "active" : ""}`}
                    >
                      {DEMO_CASES[k]?.shortTitle}
                    </button>
                  ))}
                </div>
              </div>

              <div className="hero-sample-prompt">
                {activeCase.rawContent}
              </div>

              <div className="hero-claims-grid">
                {activeCase.claims.map((claim) => (
                  <div key={claim.id} className="hero-claim-pill">
                    <div className="hero-claim-status-row">
                      <span className="mono" style={{ fontSize: "0.7rem", color: "var(--text-3)" }}>
                        {claim.id.toUpperCase()} · {claim.authorityTier}
                      </span>
                      <span className={claim.status === "CONTRADICTED" ? "badge badge-fail" : "badge badge-ok"}>
                        {claim.status}
                      </span>
                    </div>
                    <div style={{ color: "var(--text-1)", fontWeight: 500, lineHeight: 1.4 }}>
                      "{claim.statement}"
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-3)" }}>
                      Source: {claim.sourceName}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>

          <Reveal delay={320}>
            <div className="hero-stats-row">
              <div className="hero-stat-card">
                <div className="hero-stat-val" style={{ color: "var(--ok)" }}>100%</div>
                <div className="hero-stat-lbl">Statutory Registry Grounding</div>
              </div>
              <div className="hero-stat-card">
                <div className="hero-stat-val" style={{ color: "var(--brand-bright)" }}>20+</div>
                <div className="hero-stat-lbl">Observable Scam Signal Detectors</div>
              </div>
              <div className="hero-stat-card">
                <div className="hero-stat-val" style={{ color: "var(--accent-cyan)" }}>ML-DSA-65</div>
                <div className="hero-stat-lbl">Post-Quantum Dilithium Seals</div>
              </div>
              <div className="hero-stat-card">
                <div className="hero-stat-val" style={{ color: "var(--text-1)" }}>0</div>
                <div className="hero-stat-lbl">Investment Advice Hallucinations</div>
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
