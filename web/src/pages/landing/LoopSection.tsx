import LoopDiagram from "../../components/LoopDiagram";
import Reveal from "../../components/anim/Reveal";
import { GitBranch } from "lucide-react";

export default function LoopSection() {
  return (
    <section className="section" id="pipeline" style={{ background: "var(--bg-1)", borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)" }}>
      <div className="container">
        <div className="section-head">
          <Reveal>
            <div className="section-eyebrow">
              <GitBranch size={14} />
              <span>THE VERIFICATION LOOP</span>
            </div>
            <h2 className="section-title">End-to-End Investigation Architecture</h2>
            <p className="section-desc">
              Every suspicious claim traverses an immutable, six-stage deterministic pipeline. No black-box guesses — only verifiable statutory lookups, evidence grounding, and cryptographic receipts.
            </p>
          </Reveal>
        </div>

        <LoopDiagram />
      </div>
    </section>
  );
}
