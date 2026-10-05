import { Link } from "react-router-dom";
import Logo from "./Logo";
import { ArrowRight, Terminal } from "lucide-react";
import "./Nav.css";

export default function Nav() {
  return (
    <header className="nav-wrapper">
      <nav className="nav-bar" aria-label="Primary navigation">
        <div className="nav-brand">
          <Link to="/" style={{ display: "flex", alignItems: "center" }}>
            <Logo size={28} showText={true} />
          </Link>
          <div className="nav-status-pill">
            <span className="nav-status-dot" />
            <span>PQC ML-DSA-65 · SEBI T0 CONNECTED</span>
          </div>
        </div>

        <ul className="nav-links">
          <li>
            <a href="#decomposition" className="nav-link">
              Deconstruction
            </a>
          </li>
          <li>
            <a href="#pipeline" className="nav-link">
              Pipeline
            </a>
          </li>
          <li>
            <a href="#signals" className="nav-link">
              Scam Signals
            </a>
          </li>
          <li>
            <a href="#evidence" className="nav-link">
              Evidence Graph
            </a>
          </li>
          <li>
            <a href="#post-quantum" className="nav-link">
              Post-Quantum Seal
            </a>
          </li>
          <li>
            <a href="#architecture" className="nav-link">
              Architecture
            </a>
          </li>
        </ul>

        <div className="nav-actions">
          <Link to="/console" className="btn-nav-console">
            <Terminal size={14} />
            <span>Launch Console</span>
            <ArrowRight size={13} />
          </Link>
        </div>
      </nav>
    </header>
  );
}
