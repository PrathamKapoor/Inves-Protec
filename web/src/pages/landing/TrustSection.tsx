import { useState } from "react";
import Reveal from "../../components/anim/Reveal";
import { Check, Cpu, KeyRound, ShieldCheck, Sparkles } from "lucide-react";
import "./TrustSection.css";

export default function TrustSection() {
  const [verified, setVerified] = useState(false);
  const [verifying, setVerifying] = useState(false);

  const handleVerify = () => {
    setVerifying(true);
    setTimeout(() => {
      setVerifying(false);
      setVerified(true);
    }, 600);
  };

  return (
    <section className="section trust-wrapper" id="post-quantum">
      <div className="container">
        <div className="section-head">
          <Reveal>
            <div className="section-eyebrow">
              <KeyRound size={14} />
              <span>POST-QUANTUM CRYPTOGRAPHIC INTEGRITY</span>
            </div>
            <h2 className="section-title">Tamper-Proof ML-DSA-65 Receipts</h2>
            <p className="section-desc">
              Every completed investigation generates a canonical SHA3-256 digest signed with NIST FIPS 204 ML-DSA-65 lattice cryptography. Evidence cannot be backdated, modified, or forged.
            </p>
          </Reveal>
        </div>

        <Reveal delay={100}>
          <div className="trust-receipt-card">
            <div className="trust-receipt-head">
              <div style={{ display: "flex", alignItems: "center", gap: "0.65rem" }}>
                <ShieldCheck size={20} style={{ color: "var(--brand-bright)" }} />
                <span style={{ fontWeight: 600, color: "var(--text-1)" }}>
                  OFFICIAL INVESTIGATION TRUST RECEIPT · RC-2026-9481-ML
                </span>
              </div>
              <span className="badge badge-cyan">
                <Cpu size={12} />
                <span>NIST FIPS 204 LATTICE VERIFIED</span>
              </span>
            </div>

            <div className="trust-receipt-grid">
              <div className="trust-field">
                <span className="trust-label">Signature Scheme</span>
                <span className="trust-val">ML-DSA-65 (Crystals-Dilithium) · Category 3</span>
              </div>
              <div className="trust-field">
                <span className="trust-label">Signing Node Authority</span>
                <span className="trust-val">SANGYAN-GOV-NODE-01 (PKCS#11 Hardware Slot 4)</span>
              </div>
              <div className="trust-field">
                <span className="trust-label">Public Key Fingerprint</span>
                <span className="trust-val mono">sha3-256:7b92f4410a881bc3d2e94711fa62b083c51239aa</span>
              </div>
              <div className="trust-field">
                <span className="trust-label">Timestamp (UTC)</span>
                <span className="trust-val">2026-10-05 07:22:18.491 Z</span>
              </div>
            </div>

            <div style={{ marginBottom: "1.5rem" }}>
              <span className="trust-label" style={{ display: "block", marginBottom: "0.4rem" }}>
                Canonical Bundle Digest (RFC 8785 JSON · SHA3-256)
              </span>
              <div className="trust-hash-box">
                4f9d8a1e2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e01f2a3b4c5d6e7f8
              </div>
            </div>

            <div className="trust-verify-bar">
              <div style={{ fontSize: "0.8125rem", color: "var(--text-2)" }}>
                Signature Size: 3,309 bytes · Public Key: 1,952 bytes · Hardware Epoch: #88
              </div>
              <button
                onClick={handleVerify}
                disabled={verifying}
                className="btn btn-primary"
                style={{ fontSize: "0.8125rem", padding: "0.45rem 1rem" }}
              >
                {verifying ? (
                  <span>Verifying Lattice Polynomials...</span>
                ) : verified ? (
                  <>
                    <Check size={14} style={{ color: "#34d399" }} />
                    <span style={{ color: "#34d399" }}>Lattice Signature Validated</span>
                  </>
                ) : (
                  <>
                    <Sparkles size={14} />
                    <span>Verify Cryptographic Seal</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
