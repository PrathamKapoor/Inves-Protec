import { Link } from "react-router-dom";
import Reveal from "../../components/anim/Reveal";
import { ArrowRight, Terminal } from "lucide-react";
import "./FinalCta.css";

export default function FinalCta() {
  return (
    <section className="section" style={{ paddingBottom: "3rem" }}>
      <div className="container">
        <Reveal>
          <div className="final-cta-card">
            <h2 className="final-cta-title">
              Ready to verify financial claims with mathematical certainty?
            </h2>
            <p className="final-cta-desc">
              Deploy SANGYAN to deconstruct deceptive promotions, audit registration claims against official registries, and generate post-quantum sealed evidence dossiers.
            </p>
            <div className="final-cta-actions">
              <Link to="/console" className="btn-hero-launch">
                <Terminal size={17} />
                <span>Launch SANGYAN Console</span>
                <ArrowRight size={16} />
              </Link>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
