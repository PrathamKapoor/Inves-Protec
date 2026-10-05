import Reveal from "../../components/anim/Reveal";
import { AUTHORITY_TIERS } from "../../data/system";
import { Database, Shield } from "lucide-react";
import "./RegistryVerify.css";

export default function RegistryVerify() {
  const getTierClass = (tier: string) => {
    if (tier === "T0") return "tier-tag-t0";
    if (tier === "T1") return "tier-tag-t1";
    if (tier === "T2") return "tier-tag-t2";
    return "tier-tag-other";
  };

  return (
    <section className="section" id="registry">
      <div className="container">
        <div className="section-head">
          <Reveal>
            <div className="section-eyebrow">
              <Database size={14} />
              <span>STATUTORY AUTHORITY HIERARCHY</span>
            </div>
            <h2 className="section-title">Evidence Weighted by Legal Reality</h2>
            <p className="section-desc">
              In retail financial fraud, claims cannot be treated equally. SANGYAN enforces a strict six-tier epistemic hierarchy where statutory regulators always supersede secondary and social sources.
            </p>
          </Reveal>
        </div>

        <div className="tiers-grid">
          {AUTHORITY_TIERS.map((item, idx) => (
            <Reveal key={item.tier} delay={idx * 60}>
              <div className="tier-card card-interactive">
                <div className="tier-card-head">
                  <span className={`tier-tag ${getTierClass(item.tier)}`}>{item.tier}</span>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-3)", fontWeight: 500 }}>
                    {item.weight}
                  </span>
                </div>
                <h3 className="tier-name">{item.name}</h3>
                <div className="tier-entities">{item.entities}</div>
                <p className="tier-role">{item.role}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
