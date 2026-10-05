/**
 * SANGYAN Cryptographic Investor Safety Logo Mark:
 * An origami-precise hexagonal post-quantum lattice shield
 * enclosing the central Ocular Iris of Vigilance (संज्ञान)
 * with a luminous evidence core.
 */
export default function Logo({ size = 24, showText = false }: { size?: number; showText?: boolean }) {
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: "0.65rem" }}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        focusable="false"
      >
        <defs>
          <linearGradient id="sangyan-grad" x1="2" y1="4" x2="30" y2="28" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#38BDF8" />
            <stop offset="50%" stopColor="#8B5CF6" />
            <stop offset="100%" stopColor="#5227FF" />
          </linearGradient>
          <linearGradient id="sangyan-core" x1="12" y1="12" x2="20" y2="20" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#F8FAFC" />
            <stop offset="60%" stopColor="#A78BFA" />
            <stop offset="100%" stopColor="#8B5CF6" />
          </linearGradient>
          <filter id="sangyan-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Outer Cryptographic Lattice Hex-Shield */}
        <path
          d="M16 3L27 9V23L16 29L5 23V9L16 3Z"
          stroke="url(#sangyan-grad)"
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="rgba(139, 92, 246, 0.06)"
        />

        {/* Inner Lattice Nodes & Triangulation */}
        <path
          d="M16 3V9M27 9L21.5 12M27 23L21.5 20M16 29V23M5 23L10.5 20M5 9L10.5 12"
          stroke="url(#sangyan-grad)"
          strokeWidth="1.2"
          strokeOpacity="0.5"
          strokeLinecap="round"
        />

        {/* Cognitive Iris & Aperture of Vigilance */}
        <path
          d="M8.5 16C10.5 11.5 21.5 11.5 23.5 16C21.5 20.5 10.5 20.5 8.5 16Z"
          stroke="#38BDF8"
          strokeWidth="1.5"
          strokeOpacity="0.85"
        />

        {/* Luminous Evidence Core Pupil */}
        <circle
          cx="16"
          cy="16"
          r="3.2"
          fill="url(#sangyan-core)"
          filter="url(#sangyan-glow)"
        />

        {/* Center Post-Quantum Calibration Point */}
        <circle cx="16" cy="16" r="1.1" fill="#06080E" />
      </svg>
      {showText && (
        <span
          style={{
            fontFamily: "var(--font-ui)",
            fontWeight: 700,
            fontSize: "1.1rem",
            letterSpacing: "0.08em",
            color: "var(--text-1)",
            display: "inline-flex",
            alignItems: "center",
            gap: "0.35rem",
          }}
        >
          SANGYAN
          <span
            style={{
              fontSize: "0.75rem",
              fontFamily: "var(--font-mono)",
              fontWeight: 500,
              padding: "0.1rem 0.4rem",
              borderRadius: "4px",
              background: "rgba(139, 92, 246, 0.15)",
              color: "#A78BFA",
              border: "1px solid rgba(139, 92, 246, 0.3)",
              letterSpacing: "0.04em"
            }}
          >
            PQC
          </span>
        </span>
      )}
    </div>
  );
}
