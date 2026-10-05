import type { ReactNode } from "react";
import "./anim.css";

export default function Marquee({
  items,
  speed = 35,
}: {
  items: ReactNode[];
  speed?: number;
}) {
  return (
    <div className="marquee" aria-hidden="true" style={{ "--marquee-speed": `${speed}s` } as React.CSSProperties}>
      <div className="marquee-track">
        <div className="marquee-group">
          {items.map((item, i) => (
            <span key={i} className="marquee-item">
              {item}
              <span className="marquee-sep">◆</span>
            </span>
          ))}
        </div>
        <div className="marquee-group">
          {items.map((item, i) => (
            <span key={`clone-${i}`} className="marquee-item">
              {item}
              <span className="marquee-sep">◆</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
