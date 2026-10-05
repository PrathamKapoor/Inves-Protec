import { Link } from "react-router-dom";
import Logo from "./Logo";
import "./Footer.css";

export default function Footer() {
  return (
    <footer className="footer-wrapper">
      <div className="container-wide">
        <div className="footer-grid">
          <div className="footer-brand">
            <Logo size={26} showText={true} />
            <p>
              Autonomous, evidence-grounded intelligence protecting retail investors from financial fraud, fake regulatory registrations, and predatory schemes.
            </p>
          </div>

          <div>
            <h4 className="footer-col-title">Platform</h4>
            <ul className="footer-links">
              <li><Link to="/console" className="footer-link">Interactive Console</Link></li>
              <li><a href="#pipeline" className="footer-link">Verification Loop</a></li>
              <li><a href="#signals" className="footer-link">Observable Signals</a></li>
              <li><a href="#post-quantum" className="footer-link">ML-DSA-65 Receipts</a></li>
            </ul>
          </div>

          <div>
            <h4 className="footer-col-title">Statutory Sources</h4>
            <ul className="footer-links">
              <li><a href="https://www.sebi.gov.in" target="_blank" rel="noreferrer" className="footer-link">SEBI Intermediary Registry</a></li>
              <li><a href="https://scores.sebi.gov.in" target="_blank" rel="noreferrer" className="footer-link">SCORES 2.0 Grievance</a></li>
              <li><a href="https://cybercrime.gov.in" target="_blank" rel="noreferrer" className="footer-link">National Cybercrime (1930)</a></li>
              <li><a href="https://sachet.rbi.org.in" target="_blank" rel="noreferrer" className="footer-link">RBI Sachet Portal</a></li>
            </ul>
          </div>

          <div>
            <h4 className="footer-col-title">Verification Spec</h4>
            <div className="footer-spec-box">
              <div className="footer-spec-row">
                <span className="footer-spec-label">Crypto Standard</span>
                <span className="footer-spec-val">NIST FIPS 204</span>
              </div>
              <div className="footer-spec-row">
                <span className="footer-spec-label">Algorithm</span>
                <span className="footer-spec-val">ML-DSA-65</span>
              </div>
              <div className="footer-spec-row">
                <span className="footer-spec-label">Canonical Hash</span>
                <span className="footer-spec-val">RFC-8785 SHA3-256</span>
              </div>
              <div className="footer-spec-row">
                <span className="footer-spec-label">Security Parameter</span>
                <span className="footer-spec-val">Category 3 (192-bit)</span>
              </div>
            </div>
          </div>
        </div>

        <div className="footer-bottom">
          <div className="footer-disclaimer">
            <strong>STATUTORY NON-ADVISORY GUARDRAIL:</strong> SANGYAN operates strictly as an evidence-grounded fraud and claim verification system. It does not offer financial advice, price forecasts, or investment recommendations. All verification records are backed by official public registry queries and cryptographic receipts.
          </div>
          <div>
            © 2026 SANGYAN (संज्ञान) · Open Source Defense Infrastructure
          </div>
        </div>
      </div>
    </footer>
  );
}
