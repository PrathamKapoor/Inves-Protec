import Reveal from "../../components/anim/Reveal";
import { HelpCircle } from "lucide-react";
import "./Uncertainty.css";

const STANCES = [
  {
    name: "CONTRADICTED",
    tone: "fail",
    badge: "badge-fail",
    meaning: "Directly falsified by authoritative T0/T1 statutory data.",
    example: "SEBI search for INH000099999 yields zero records.",
  },
  {
    name: "SUPPORTED",
    tone: "ok",
    badge: "badge-ok",
    meaning: "Affirmed by official registry, exchange filing, or gazette.",
    example: "HDFC Securities SEBI registration INZ000186937 confirmed active.",
  },
  {
    name: "CONFLICTING",
    tone: "warn",
    badge: "badge-warn",
    meaning: "Independent sources disagree; flagged for human investigator review.",
    example: "Entity claimed active broker status, but exchange circular noted suspension.",
  },
  {
    name: "OUTDATED",
    tone: "warn",
    badge: "badge-neutral",
    meaning: "Registration or disclosure was valid historically but has expired or lapsed.",
    example: "Advisor registration expired in 2023 with no renewal record.",
  },
  {
    name: "UNVERIFIED",
    tone: "cyan",
    badge: "badge-cyan",
    meaning: "No authoritative source confirms or refutes; marked as unverifiable claim.",
    example: "Promotional statement: 'Our founder has 15 years experience'.",
  },
];

export default function Uncertainty() {
  return (
    <section className="section" id="evidence">
      <div className="container">
        <div className="section-head">
          <Reveal>
            <div className="section-eyebrow">
              <HelpCircle size={14} />
              <span>EVIDENCE CALIBRATION</span>
            </div>
            <h2 className="section-title">Explicit Multi-Valued Stance Resolution</h2>
            <p className="section-desc">
              SANGYAN refuses to mask epistemic uncertainty behind a single statistical confidence number. Every claim receives a distinct statutory stance with primary citations.
            </p>
          </Reveal>
        </div>

        <div className="uncertainty-grid">
          {STANCES.map((stance, idx) => (
            <Reveal key={stance.name} delay={idx * 60}>
              <div className="stance-card card-interactive">
                <div className="stance-title">
                  <span className={`badge ${stance.badge}`}>{stance.name}</span>
                </div>
                <p className="stance-desc">{stance.meaning}</p>
                <div className="stance-example">
                  <strong>Example:</strong> {stance.example}
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
