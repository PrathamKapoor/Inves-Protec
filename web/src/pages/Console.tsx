import { useState } from "react";
import { Link } from "react-router-dom";
import Logo from "../components/Logo";
import { DEMO_CASES, type ClaimRecord, type InvestigationCase } from "../data/cases";
import { SIGNAL_CATALOG } from "../data/signals";
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  ArrowLeft,
  CheckCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Cpu,
  Database,
  Download,
  ExternalLink,
  Eye,
  FileCheck,
  FileCode,
  FileText,
  Filter,
  Flame,
  KeyRound,
  Layers,
  Play,
  Radio,
  Search,
  Send,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Terminal,
  UserCheck,
  XCircle,
} from "lucide-react";
import "./Console.css";

type ConsoleTab = "overview" | "intake" | "findings" | "review" | "entities" | "trust" | "system";

export default function Console() {
  const [activeTab, setActiveTab] = useState<ConsoleTab>("overview");
  const [searchQuery, setSearchQuery] = useState("");

  // Sandbox State
  const [inputContent, setInputContent] = useState(DEMO_CASES["case_telegram_algo"]!.rawContent);
  const [selectedCaseKey, setSelectedCaseKey] = useState("case_telegram_algo");
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [analysisResult, setAnalysisResult] = useState<InvestigationCase | null>(DEMO_CASES["case_telegram_algo"]!);

  // Findings Explorer State
  const [findingFamily, setFindingFamily] = useState<string>("all");
  const [findingSeverity, setFindingSeverity] = useState<string>("all");
  const [findingStatus, setFindingStatus] = useState<string>("all");
  const [expandedClaimId, setExpandedClaimId] = useState<string | null>("clm_01");

  // Review Queue State
  const [reviewDecisions, setReviewDecisions] = useState<Record<string, { status: string; note: string; timestamp: string }>>({
    clm_01: { status: "CONFIRMED_VIOLATION", note: "Violates SEBI PFUTP Reg 4(2)(k). Escalate to Cybercrime 1930.", timestamp: "2026-10-05 07:23:10 UTC" },
  });

  // Receipts Verification State
  const [verifiedReceipts, setVerifiedReceipts] = useState<Record<string, boolean>>({});

  const allClaims: (ClaimRecord & { caseTitle: string; caseId: string })[] = Object.values(DEMO_CASES).flatMap((c) =>
    c.claims.map((claim) => ({
      ...claim,
      caseTitle: c.title,
      caseId: c.id,
    }))
  );

  const filteredClaims = allClaims.filter((clm) => {
    const matchesSearch =
      clm.statement.toLowerCase().includes(searchQuery.toLowerCase()) ||
      clm.sourceName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      clm.id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSeverity = findingSeverity === "all" || (findingSeverity === "CRITICAL" && clm.status === "CONTRADICTED");
    const matchesStatus = findingStatus === "all" || clm.status === findingStatus;
    const matchesFamily =
      findingFamily === "all" ||
      clm.claimType === findingFamily ||
      clm.claim_type === findingFamily;
    return matchesSearch && matchesSeverity && matchesStatus && matchesFamily;
  });

  const handleRunPipeline = () => {
    setPipelineRunning(true);
    setCurrentStep(1);

    const stepInterval = setInterval(() => {
      setCurrentStep((prev) => {
        if (prev >= 6) {
          clearInterval(stepInterval);
          setPipelineRunning(false);
          setAnalysisResult(DEMO_CASES[selectedCaseKey] || DEMO_CASES["case_telegram_algo"]!);
          return 6;
        }
        return prev + 1;
      });
    }, 450);
  };

  const handleLoadPreset = (key: string) => {
    setSelectedCaseKey(key);
    const chosen = DEMO_CASES[key];
    if (chosen) {
      setInputContent(chosen.rawContent);
      setAnalysisResult(chosen);
      setCurrentStep(6);
    }
  };

  const handleDecision = (claimId: string, status: string, note: string) => {
    setReviewDecisions((prev) => ({
      ...prev,
      [claimId]: {
        status,
        note,
        timestamp: new Date().toISOString().replace("T", " ").substring(0, 19) + " UTC",
      },
    }));
  };

  const handleVerifyReceipt = (receiptId: string) => {
    setVerifiedReceipts((prev) => ({ ...prev, [receiptId]: true }));
  };

  const handleExportDossier = () => {
    const dossierData = {
      investigator: "Dr. Arvind Rao (Senior Regulatory Investigator)",
      authority: "SANGYAN Investor Safety Platform",
      generatedAt: new Date().toISOString(),
      activeDecisions: reviewDecisions,
      verifiedCases: Object.values(DEMO_CASES).map((c) => ({
        id: c.id,
        title: c.title,
        risk: c.riskLevel,
        receipt: c.receipt,
        claims: c.claims,
      })),
    };
    const blob = new Blob([JSON.stringify(dossierData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `SANGYAN-Dossier-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="console-shell">
      {/* Sidebar */}
      <aside className="console-sidebar">
        <div>
          <div className="console-sidebar-header">
            <Link to="/" style={{ display: "flex", alignItems: "center" }}>
              <Logo size={24} showText={true} />
            </Link>
          </div>

          <div className="console-investigator-card">
            <div className="investigator-avatar">AR</div>
            <div className="investigator-details">
              <span className="investigator-name">Dr. Arvind Rao</span>
              <span className="investigator-role">SEBI ENFORCEMENT CELL</span>
            </div>
          </div>

          <div className="console-nav-scroll">
            <div>
              <div className="console-nav-group-title">Operations</div>
              <ul className="console-nav-list">
                <li>
                  <button
                    onClick={() => setActiveTab("overview")}
                    className={`console-nav-item ${activeTab === "overview" ? "active" : ""}`}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <Activity size={15} />
                      <span>Overview</span>
                    </div>
                    <span className="console-nav-badge">LIVE</span>
                  </button>
                </li>
                <li>
                  <button
                    onClick={() => setActiveTab("intake")}
                    className={`console-nav-item ${activeTab === "intake" ? "active" : ""}`}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <Terminal size={15} />
                      <span>Intake & Pipeline</span>
                    </div>
                    <span className="console-nav-badge" style={{ color: "var(--brand-bright)" }}>RUN</span>
                  </button>
                </li>
              </ul>
            </div>

            <div>
              <div className="console-nav-group-title">Investigation</div>
              <ul className="console-nav-list">
                <li>
                  <button
                    onClick={() => setActiveTab("findings")}
                    className={`console-nav-item ${activeTab === "findings" ? "active" : ""}`}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <ShieldAlert size={15} />
                      <span>Findings Explorer</span>
                    </div>
                    <span className="console-nav-badge">{allClaims.length}</span>
                  </button>
                </li>
                <li>
                  <button
                    onClick={() => setActiveTab("review")}
                    className={`console-nav-item ${activeTab === "review" ? "active" : ""}`}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <UserCheck size={15} />
                      <span>Review Queue</span>
                    </div>
                    <span className="console-nav-badge" style={{ color: "var(--warn)" }}>3 Pending</span>
                  </button>
                </li>
                <li>
                  <button
                    onClick={() => setActiveTab("entities")}
                    className={`console-nav-item ${activeTab === "entities" ? "active" : ""}`}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <Database size={15} />
                      <span>Entities Registry</span>
                    </div>
                    <span className="console-nav-badge">5 Tracked</span>
                  </button>
                </li>
              </ul>
            </div>

            <div>
              <div className="console-nav-group-title">Cryptographic Trust</div>
              <ul className="console-nav-list">
                <li>
                  <button
                    onClick={() => setActiveTab("trust")}
                    className={`console-nav-item ${activeTab === "trust" ? "active" : ""}`}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <KeyRound size={15} />
                      <span>PQC ML-DSA-65</span>
                    </div>
                    <span className="console-nav-badge" style={{ color: "var(--accent-cyan)" }}>FIPS 204</span>
                  </button>
                </li>
                <li>
                  <button
                    onClick={() => setActiveTab("system")}
                    className={`console-nav-item ${activeTab === "system" ? "active" : ""}`}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <Layers size={15} />
                      <span>Telemetry & Rules</span>
                    </div>
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div className="console-sidebar-footer">
          <Link to="/" style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", color: "var(--text-2)" }}>
            <ArrowLeft size={13} />
            <span>Return to Public Landing</span>
          </Link>
          <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.68rem" }}>
            NODE: GOV-MUMBAI-01 (ML-DSA-65)
          </div>
        </div>
      </aside>

      {/* Main Container */}
      <main className="console-main">
        {/* Topbar */}
        <header className="console-topbar">
          <div className="console-breadcrumb">
            <span style={{ color: "var(--text-3)" }}>Workbench</span>
            <span style={{ color: "var(--text-3)" }}>/</span>
            <span style={{ textTransform: "capitalize" }}>{activeTab}</span>
          </div>

          <div className="console-topbar-actions">
            <div className="console-search-bar">
              <Search
                size={13}
                style={{ position: "absolute", top: "50%", left: "0.75rem", transform: "translateY(-50%)", color: "var(--text-3)" }}
              />
              <input
                type="text"
                placeholder="Search claims, entities, VPAs..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="console-search-input"
              />
            </div>

            <div className="nav-status-pill" style={{ fontSize: "0.7rem", padding: "0.2rem 0.5rem" }}>
              <span className="nav-status-dot" />
              <span>LIVE REGISTRY CONNECTED</span>
            </div>

            <button onClick={handleExportDossier} className="btn btn-secondary" style={{ fontSize: "0.75rem", padding: "0.35rem 0.75rem" }}>
              <Download size={13} />
              <span>Export Dossier</span>
            </button>
          </div>
        </header>

        {/* Content Body */}
        <div className="console-content-body">
          {/* TAB 1: OVERVIEW */}
          {activeTab === "overview" && (
            <div>
              {/* Metric Tiles Grid (6 Tiles matching SIH26 style) */}
              <div className="console-tiles-grid">
                <div className="console-tile">
                  <div>
                    <div className="console-tile-title">Ingested Payloads</div>
                    <div className="console-tile-val">14</div>
                  </div>
                  <div className="console-tile-footer" style={{ color: "var(--ok)" }}>
                    <CheckCircle2 size={12} />
                    <span>SSRF Validated</span>
                  </div>
                </div>

                <div className="console-tile">
                  <div>
                    <div className="console-tile-title">Flagged Scam Claims</div>
                    <div className="console-tile-val" style={{ color: "var(--fail)" }}>
                      9
                    </div>
                  </div>
                  <div className="console-tile-footer" style={{ color: "var(--fail)" }}>
                    <AlertTriangle size={12} />
                    <span>Statutory Contradictions</span>
                  </div>
                </div>

                <div className="console-tile">
                  <div>
                    <div className="console-tile-title">High-Risk Entities</div>
                    <div className="console-tile-val" style={{ color: "var(--warn)" }}>
                      3
                    </div>
                  </div>
                  <div className="console-tile-footer" style={{ color: "var(--warn)" }}>
                    <ShieldAlert size={12} />
                    <span>Unregistered / Forged</span>
                  </div>
                </div>

                <div className="console-tile">
                  <div>
                    <div className="console-tile-title">Awaiting Review</div>
                    <div className="console-tile-val" style={{ color: "var(--brand-bright)" }}>
                      3
                    </div>
                  </div>
                  <div className="console-tile-footer" style={{ color: "var(--text-3)" }}>
                    <span>Supervisory Decision Gate</span>
                  </div>
                </div>

                <div className="console-tile">
                  <div>
                    <div className="console-tile-title">PQC Sealed Receipts</div>
                    <div className="console-tile-val" style={{ color: "var(--accent-cyan)" }}>
                      142
                    </div>
                  </div>
                  <div className="console-tile-footer" style={{ color: "var(--accent-cyan)" }}>
                    <Cpu size={12} />
                    <span>ML-DSA-65 Validated</span>
                  </div>
                </div>

                <div className="console-tile">
                  <div>
                    <div className="console-tile-title">Pipeline Latency</div>
                    <div className="console-tile-val">412ms</div>
                  </div>
                  <div className="console-tile-footer" style={{ color: "var(--ok)" }}>
                    <span>P99 &lt; 850ms</span>
                  </div>
                </div>
              </div>

              {/* Priority Attention Queue */}
              <div className="console-panel">
                <div className="console-panel-header">
                  <div className="console-panel-title">
                    <Flame size={16} style={{ color: "var(--fail)" }} />
                    <span>Priority Attention Queue — Immediate Regulatory Intervention</span>
                  </div>
                  <span className="badge badge-fail">3 High-Priority Funnels</span>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1rem" }}>
                  {Object.entries(DEMO_CASES).map(([key, c]) => (
                    <div key={key} style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: "1.25rem", borderRadius: "8px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                      <div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                          <span className="mono" style={{ fontSize: "0.72rem", color: "var(--text-3)" }}>{c.id}</span>
                          <span className="badge badge-fail">{c.riskLevel}</span>
                        </div>
                        <h4 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-1)", marginBottom: "0.35rem" }}>{c.title}</h4>
                        <p style={{ fontSize: "0.8rem", color: "var(--text-2)", marginBottom: "1rem", lineHeight: 1.5 }}>{c.description}</p>
                      </div>

                      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
                        <button
                          onClick={() => {
                            setSelectedCaseKey(key);
                            setInputContent(c.rawContent);
                            setAnalysisResult(c);
                            setActiveTab("intake");
                          }}
                          className="btn btn-secondary"
                          style={{ flex: 1, fontSize: "0.75rem", padding: "0.35rem 0.5rem" }}
                        >
                          <Play size={12} />
                          <span>Re-Analyze</span>
                        </button>
                        <button
                          onClick={() => {
                            setExpandedClaimId(c.claims[0]?.id || null);
                            setActiveTab("findings");
                          }}
                          className="btn btn-primary"
                          style={{ flex: 1, fontSize: "0.75rem", padding: "0.35rem 0.5rem" }}
                        >
                          <Eye size={12} />
                          <span>Inspect Claims</span>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Real-time Event Stream / System Log */}
              <div className="console-panel">
                <div className="console-panel-header">
                  <div className="console-panel-title">
                    <Radio size={16} style={{ color: "var(--ok)" }} />
                    <span>Live Verification Stream (SSE Events)</span>
                  </div>
                  <span className="mono" style={{ fontSize: "0.75rem", color: "var(--text-3)" }}>
                    sse://localhost:8000/api/v1/investigations/stream
                  </span>
                </div>

                <div style={{ background: "var(--bg-0)", padding: "1rem", borderRadius: "6px", fontFamily: "var(--font-mono)", fontSize: "0.75rem", display: "flex", flexDirection: "column", gap: "0.45rem", maxHeight: "200px", overflowY: "auto" }}>
                  <div style={{ color: "var(--text-3)" }}>[07:22:15.102] [SSE] Connected to event broker. Tenant: sebi_enforcement_cell</div>
                  <div style={{ color: "var(--ok)" }}>[07:22:16.420] [INGEST] Received Telegram payload: AlphaQuant VIP Official. Cleaned 248 chars.</div>
                  <div style={{ color: "var(--accent-cyan)" }}>[07:22:16.890] [DECOMPOSITION] Extracted 3 discrete claims (return, regulatory, operational).</div>
                  <div style={{ color: "var(--fail)" }}>[07:22:17.310] [T0_REGISTRY] Query INH000099999 against SEBI Intermediaries: 0 records found. Status: CONTRADICTED.</div>
                  <div style={{ color: "var(--brand-bright)" }}>[07:22:18.491] [PQC_TRUST] Minted receipt rcpt_mldsa65_948102b4 via NIST FIPS 204. Canonical digest: 4f9d8a1e2b...</div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: INTAKE & PIPELINE SANDBOX */}
          {activeTab === "intake" && (
            <div>
              <div className="console-panel">
                <div className="console-panel-header">
                  <div className="console-panel-title">
                    <Terminal size={16} style={{ color: "var(--brand-bright)" }} />
                    <span>Suspicious Payload Intake & Live Execution Sandbox</span>
                  </div>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button
                      onClick={() => handleLoadPreset("case_telegram_algo")}
                      className={`btn btn-secondary ${selectedCaseKey === "case_telegram_algo" ? "btn-primary" : ""}`}
                      style={{ fontSize: "0.75rem", padding: "0.3rem 0.65rem" }}
                    >
                      Telegram Algo Scam
                    </button>
                    <button
                      onClick={() => handleLoadPreset("case_fake_sebi_advisor")}
                      className={`btn btn-secondary ${selectedCaseKey === "case_fake_sebi_advisor" ? "btn-primary" : ""}`}
                      style={{ fontSize: "0.75rem", padding: "0.3rem 0.65rem" }}
                    >
                      Fake SEBI Certificate
                    </button>
                    <button
                      onClick={() => handleLoadPreset("case_offshore_escrow_trap")}
                      className={`btn btn-secondary ${selectedCaseKey === "case_offshore_escrow_trap" ? "btn-primary" : ""}`}
                      style={{ fontSize: "0.75rem", padding: "0.3rem 0.65rem" }}
                    >
                      Offshore Pre-IPO Trap
                    </button>
                  </div>
                </div>

                <div style={{ marginBottom: "1rem" }}>
                  <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-3)", marginBottom: "0.4rem", fontFamily: "var(--font-mono)" }}>
                    UNSTRUCTURED FINANCIAL PROMOTION TEXT / MESSAGE / TRANSCRIPT
                  </label>
                  <textarea
                    rows={5}
                    value={inputContent}
                    onChange={(e) => setInputContent(e.target.value)}
                    style={{ width: "100%", background: "var(--bg-0)", border: "1px solid var(--line)", borderRadius: "6px", padding: "0.75rem", fontSize: "0.85rem", color: "var(--text-1)", fontFamily: "var(--font-mono)", lineHeight: 1.5, resize: "vertical" }}
                  />
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-3)" }}>
                    Strict anti-SSRF IP pinning active · Bounded payload streaming max 10MB
                  </div>
                  <button
                    onClick={handleRunPipeline}
                    disabled={pipelineRunning}
                    className="btn btn-primary"
                    style={{ padding: "0.55rem 1.25rem", fontSize: "0.85rem" }}
                  >
                    {pipelineRunning ? (
                      <>
                        <Activity size={14} className="pulse-dot" />
                        <span>Executing Pipeline Stage {currentStep}/6...</span>
                      </>
                    ) : (
                      <>
                        <Play size={14} />
                        <span>Run Full Verification Pipeline</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Progress Stepper Rail */}
              <div className="stepper-rail">
                <div className={`stepper-step ${currentStep >= 1 ? "completed" : ""} ${currentStep === 1 ? "active" : ""}`}>
                  <span>01. Ingest Normalizer</span>
                </div>
                <ChevronRight size={12} style={{ color: "var(--text-3)" }} />
                <div className={`stepper-step ${currentStep >= 2 ? "completed" : ""} ${currentStep === 2 ? "active" : ""}`}>
                  <span>02. Claim Decomposition</span>
                </div>
                <ChevronRight size={12} style={{ color: "var(--text-3)" }} />
                <div className={`stepper-step ${currentStep >= 3 ? "completed" : ""} ${currentStep === 3 ? "active" : ""}`}>
                  <span>03. Signal Scan (20+)</span>
                </div>
                <ChevronRight size={12} style={{ color: "var(--text-3)" }} />
                <div className={`stepper-step ${currentStep >= 4 ? "completed" : ""} ${currentStep === 4 ? "active" : ""}`}>
                  <span>04. SEBI T0 Lookup</span>
                </div>
                <ChevronRight size={12} style={{ color: "var(--text-3)" }} />
                <div className={`stepper-step ${currentStep >= 5 ? "completed" : ""} ${currentStep === 5 ? "active" : ""}`}>
                  <span>05. Stance Triangulation</span>
                </div>
                <ChevronRight size={12} style={{ color: "var(--text-3)" }} />
                <div className={`stepper-step ${currentStep >= 6 ? "completed" : ""} ${currentStep === 6 ? "active" : ""}`}>
                  <span>06. ML-DSA-65 Seal</span>
                </div>
              </div>

              {/* Analysis Result Display */}
              {analysisResult && (
                <div>
                  <div className="console-panel" style={{ borderLeft: "3px solid var(--fail)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem", flexWrap: "wrap", gap: "0.5rem" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <ShieldAlert size={18} style={{ color: "var(--fail)" }} />
                        <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--text-1)" }}>{analysisResult.title}</h3>
                      </div>
                      <div style={{ display: "flex", gap: "0.5rem" }}>
                        <span className="badge badge-fail">{analysisResult.riskLevel}</span>
                        <span className="badge badge-cyan">{analysisResult.receipt.algorithm}</span>
                      </div>
                    </div>
                    <p style={{ fontSize: "0.875rem", color: "var(--text-2)", marginBottom: "1rem" }}>
                      {analysisResult.summary}
                    </p>

                    {/* Extracted Atomic Claims */}
                    <div style={{ marginTop: "1rem" }}>
                      <h4 style={{ fontSize: "0.8125rem", color: "var(--text-3)", textTransform: "uppercase", marginBottom: "0.5rem" }}>
                        Atomic Claim Deconstruction & Statutory Stances
                      </h4>
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                        {analysisResult.claims.map((clm) => (
                          <div key={clm.id} style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: "1rem", borderRadius: "6px" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.35rem" }}>
                              <span className="mono" style={{ fontSize: "0.75rem", color: "var(--brand-bright)" }}>
                                {clm.id} · {(clm.claimType || clm.claim_type || "").toUpperCase()}
                              </span>
                              <span className={clm.status === "CONTRADICTED" ? "badge badge-fail" : "badge badge-ok"}>
                                {clm.status}
                              </span>
                            </div>
                            <div style={{ color: "var(--text-1)", fontWeight: 500, fontSize: "0.875rem", marginBottom: "0.35rem" }}>
                              "{clm.statement}"
                            </div>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-3)" }}>
                              <strong>Statutory Citation:</strong> {clm.sourceName} ({clm.authorityTier})
                            </div>
                            <div style={{ fontSize: "0.75rem", color: "var(--fail)", marginTop: "0.25rem" }}>
                              <strong>Finding:</strong> {clm.rationale}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Safe Guidance */}
                    <div style={{ marginTop: "1.25rem", padding: "1rem", background: "rgba(56, 189, 248, 0.05)", border: "1px solid rgba(56, 189, 248, 0.2)", borderRadius: "6px" }}>
                      <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--accent-cyan)", marginBottom: "0.35rem" }}>
                        Recommended Non-Advisory Safe Guidance
                      </div>
                      <div style={{ fontSize: "0.8125rem", color: "var(--text-2)", marginBottom: "0.25rem" }}>
                        <strong>Action:</strong> {analysisResult.safeGuidance.immediateAction}
                      </div>
                      <div style={{ fontSize: "0.8125rem", color: "var(--text-2)" }}>
                        <strong>Escalation:</strong> {analysisResult.safeGuidance.escalationChannel} (
                        <a href={analysisResult.safeGuidance.filingUrl} target="_blank" rel="noreferrer" style={{ color: "var(--accent-cyan)", textDecoration: "underline" }}>
                          Filing Portal
                        </a>
                        )
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: FINDINGS & CLAIMS EXPLORER */}
          {activeTab === "findings" && (
            <div>
              <div className="console-panel">
                <div className="console-panel-header">
                  <div className="console-panel-title">
                    <ShieldAlert size={16} style={{ color: "var(--fail)" }} />
                    <span>Evidence-Backed Findings Explorer</span>
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-3)" }}>
                    Showing {filteredClaims.length} of {allClaims.length} claims
                  </div>
                </div>

                {/* Filter Tabstrip */}
                <div className="console-filter-tabs">
                  <button
                    onClick={() => setFindingFamily("all")}
                    className={`console-filter-tab ${findingFamily === "all" ? "active" : ""}`}
                  >
                    All Families ({allClaims.length})
                  </button>
                  <button
                    onClick={() => setFindingFamily("return")}
                    className={`console-filter-tab ${findingFamily === "return" ? "active" : ""}`}
                  >
                    Guaranteed Returns
                  </button>
                  <button
                    onClick={() => setFindingFamily("regulatory")}
                    className={`console-filter-tab ${findingFamily === "regulatory" ? "active" : ""}`}
                  >
                    Regulatory Credentials
                  </button>
                  <button
                    onClick={() => setFindingFamily("payment")}
                    className={`console-filter-tab ${findingFamily === "payment" ? "active" : ""}`}
                  >
                    Payment Routing
                  </button>
                  <button
                    onClick={() => setFindingFamily("operational")}
                    className={`console-filter-tab ${findingFamily === "operational" ? "active" : ""}`}
                  >
                    Operational Liquidity
                  </button>
                </div>

                <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem", flexWrap: "wrap" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-3)" }}>Status:</span>
                    <select
                      value={findingStatus}
                      onChange={(e) => setFindingStatus(e.target.value)}
                      style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: "0.25rem 0.5rem", borderRadius: "4px", fontSize: "0.75rem", color: "var(--text-1)" }}
                    >
                      <option value="all">All Stances</option>
                      <option value="CONTRADICTED">CONTRADICTED</option>
                      <option value="SUPPORTED">SUPPORTED</option>
                      <option value="UNVERIFIED">UNVERIFIED</option>
                    </select>
                  </div>
                </div>

                {/* Dense Table */}
                <div style={{ overflowX: "auto" }}>
                  <table className="console-data-table">
                    <thead>
                      <tr>
                        <th style={{ width: "40px" }}></th>
                        <th>CLAIM ID</th>
                        <th>ASSERTION STATEMENT</th>
                        <th>SOURCE / AUTHORITY</th>
                        <th>STANCE</th>
                        <th>INVESTIGATION DOSSIER</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredClaims.map((clm) => {
                        const isExpanded = expandedClaimId === clm.id;
                        return (
                          <>
                            <tr
                              key={clm.id}
                              onClick={() => setExpandedClaimId(isExpanded ? null : clm.id)}
                              style={{ cursor: "pointer" }}
                            >
                              <td>
                                {isExpanded ? (
                                  <ChevronDown size={14} style={{ color: "var(--brand-bright)" }} />
                                ) : (
                                  <ChevronRight size={14} style={{ color: "var(--text-3)" }} />
                                )}
                              </td>
                              <td className="mono" style={{ color: "var(--brand-bright)" }}>
                                {clm.id}
                              </td>
                              <td style={{ fontWeight: 500, color: "var(--text-1)", maxWidth: "340px" }}>
                                "{clm.statement}"
                              </td>
                              <td>
                                <div>{clm.sourceName}</div>
                                <span className="mono" style={{ fontSize: "0.7rem", color: "var(--text-3)" }}>
                                  {clm.authorityTier}
                                </span>
                              </td>
                              <td>
                                <span className={clm.status === "CONTRADICTED" ? "badge badge-fail" : "badge badge-ok"}>
                                  {clm.status}
                                </span>
                              </td>
                              <td style={{ fontSize: "0.75rem", color: "var(--text-3)" }}>
                                {clm.caseTitle}
                              </td>
                            </tr>
                            {isExpanded && (
                              <tr key={`${clm.id}-drawer`}>
                                <td colSpan={6} style={{ padding: 0 }}>
                                  <div className="drawer-content">
                                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
                                      <div>
                                        <h4 style={{ fontSize: "0.8125rem", color: "var(--fail)", textTransform: "uppercase", marginBottom: "0.4rem" }}>
                                          Why Flagged (Observed Ground Truth)
                                        </h4>
                                        <p style={{ fontSize: "0.85rem", color: "var(--text-1)", lineHeight: 1.5 }}>
                                          {clm.rationale}
                                        </p>
                                        <div style={{ marginTop: "0.75rem", fontSize: "0.75rem", color: "var(--text-3)" }}>
                                          <strong>Statutory Source Excerpt:</strong> {clm.excerpt}
                                        </div>
                                      </div>
                                      <div>
                                        <h4 style={{ fontSize: "0.8125rem", color: "var(--accent-cyan)", textTransform: "uppercase", marginBottom: "0.4rem" }}>
                                          Cryptographic Content Hash (SHA3-256)
                                        </h4>
                                        <div className="mono" style={{ fontSize: "0.75rem", color: "var(--accent-cyan)", background: "var(--bg-2)", padding: "0.5rem", borderRadius: "4px", wordBreak: "break-all" }}>
                                          {clm.contentHash}
                                        </div>
                                        <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem" }}>
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              handleDecision(clm.id, "CONFIRMED_VIOLATION", "Confirmed against statutory registry.");
                                            }}
                                            className="btn btn-secondary"
                                            style={{ fontSize: "0.75rem", padding: "0.3rem 0.65rem" }}
                                          >
                                            Confirm Violation
                                          </button>
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              handleDecision(clm.id, "ESCALATED_1930", "Escalated to Cybercrime Portal 1930.");
                                            }}
                                            className="btn btn-primary"
                                            style={{ fontSize: "0.75rem", padding: "0.3rem 0.65rem" }}
                                          >
                                            Escalate 1930
                                          </button>
                                        </div>
                                      </div>
                                    </div>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: REVIEW QUEUE */}
          {activeTab === "review" && (
            <div>
              <div className="console-panel">
                <div className="console-panel-header">
                  <div className="console-panel-title">
                    <UserCheck size={16} style={{ color: "var(--brand-bright)" }} />
                    <span>Supervisory Review Queue & Decision Ledger</span>
                  </div>
                  <span className="badge badge-brand">Human-in-the-Loop Gate</span>
                </div>

                <p style={{ fontSize: "0.875rem", color: "var(--text-2)", marginBottom: "1.5rem" }}>
                  In accordance with regulatory audit standards, all findings with statutory enforcement implications must receive explicit investigator confirmation before sealing.
                </p>

                <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  {allClaims.slice(0, 3).map((clm) => {
                    const dec = reviewDecisions[clm.id];
                    return (
                      <div key={clm.id} style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: "1.25rem", borderRadius: "8px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                          <span className="mono" style={{ fontSize: "0.75rem", color: "var(--brand-bright)" }}>
                            CLAIM {clm.id} · {clm.authorityTier}
                          </span>
                          {dec ? (
                            <span className="badge badge-ok">
                              <CheckCircle size={12} />
                              <span>{dec.status}</span>
                            </span>
                          ) : (
                            <span className="badge badge-warn">Awaiting Supervisory Decision</span>
                          )}
                        </div>

                        <div style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--text-1)", marginBottom: "0.4rem" }}>
                          "{clm.statement}"
                        </div>
                        <div style={{ fontSize: "0.8rem", color: "var(--text-3)", marginBottom: "0.75rem" }}>
                          {clm.sourceName} — {clm.rationale}
                        </div>

                        {dec && (
                          <div style={{ background: "var(--bg-0)", padding: "0.6rem 0.85rem", borderRadius: "4px", fontSize: "0.75rem", marginBottom: "0.75rem" }}>
                            <span style={{ color: "var(--brand-bright)" }}>Investigator Note:</span> {dec.note} ·{" "}
                            <span style={{ color: "var(--text-3)" }}>{dec.timestamp}</span>
                          </div>
                        )}

                        <div style={{ display: "flex", gap: "0.5rem" }}>
                          <button
                            onClick={() => handleDecision(clm.id, "CONFIRMED_VIOLATION", "Verified against SEBI statutory registry. High fraud severity.")}
                            className="btn btn-secondary"
                            style={{ fontSize: "0.75rem", padding: "0.35rem 0.75rem" }}
                          >
                            Confirm Violation
                          </button>
                          <button
                            onClick={() => handleDecision(clm.id, "ESCALATE_TO_REGULATOR", "Transmitted to SEBI Enforcement Cell for formal cease-and-desist.")}
                            className="btn btn-primary"
                            style={{ fontSize: "0.75rem", padding: "0.35rem 0.75rem" }}
                          >
                            Escalate to SEBI / 1930
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: ENTITIES REGISTRY */}
          {activeTab === "entities" && (
            <div>
              <div className="console-panel">
                <div className="console-panel-header">
                  <div className="console-panel-title">
                    <Database size={16} style={{ color: "var(--brand-bright)" }} />
                    <span>Investigated Entities Registry & Regulatory Standing</span>
                  </div>
                  <span className="badge badge-neutral">SEBI / MCA Directory</span>
                </div>

                <table className="console-data-table">
                  <thead>
                    <tr>
                      <th>ENTITY NAME</th>
                      <th>CLAIMED REGISTRATION</th>
                      <th>OFFICIAL REGISTRY STATUS</th>
                      <th>SECTOR COHORT</th>
                      <th>FLAGGED FINDINGS</th>
                      <th>RISK TIER</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td style={{ fontWeight: 600, color: "var(--text-1)" }}>AlphaQuant Advisors</td>
                      <td className="mono" style={{ color: "var(--fail)" }}>INH000099999</td>
                      <td><span className="badge badge-fail">FORGED IDENTIFIER</span></td>
                      <td>Research Analyst (Unregistered)</td>
                      <td className="mono" style={{ color: "var(--fail)" }}>3 Violations</td>
                      <td><span className="badge badge-fail">CRITICAL</span></td>
                    </tr>
                    <tr>
                      <td style={{ fontWeight: 600, color: "var(--text-1)" }}>Sharma Capital Advisory LLP</td>
                      <td className="mono" style={{ color: "var(--fail)" }}>INH200001234</td>
                      <td><span className="badge badge-fail">COUNTERFEIT CERT</span></td>
                      <td>F&O Tipster Channel</td>
                      <td className="mono" style={{ color: "var(--fail)" }}>2 Violations</td>
                      <td><span className="badge badge-fail">CRITICAL</span></td>
                    </tr>
                    <tr>
                      <td style={{ fontWeight: 600, color: "var(--text-1)" }}>GlobalClear Capital LLC</td>
                      <td className="mono">SVG-IBC-918237</td>
                      <td><span className="badge badge-warn">UNAUTHORIZED OFFSHORE</span></td>
                      <td>Pre-IPO Secondary Escrow</td>
                      <td className="mono" style={{ color: "var(--warn)" }}>1 Violation</td>
                      <td><span className="badge badge-warn">HIGH</span></td>
                    </tr>
                    <tr>
                      <td style={{ fontWeight: 600, color: "var(--text-1)" }}>Zerodha Broking Limited</td>
                      <td className="mono" style={{ color: "var(--ok)" }}>INZ000031633</td>
                      <td><span className="badge badge-ok">ACTIVE &amp; LICENSED</span></td>
                      <td>Stock Broker (NSE/BSE/MCX)</td>
                      <td className="mono" style={{ color: "var(--ok)" }}>0 Violations</td>
                      <td><span className="badge badge-ok">SAFE T2</span></td>
                    </tr>
                    <tr>
                      <td style={{ fontWeight: 600, color: "var(--text-1)" }}>HDFC Securities Limited</td>
                      <td className="mono" style={{ color: "var(--ok)" }}>INZ000186937</td>
                      <td><span className="badge badge-ok">ACTIVE &amp; LICENSED</span></td>
                      <td>Stock Broker &amp; Depository Participant</td>
                      <td className="mono" style={{ color: "var(--ok)" }}>0 Violations</td>
                      <td><span className="badge badge-ok">SAFE T2</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 6: POST-QUANTUM TRUST & RECEIPTS */}
          {activeTab === "trust" && (
            <div>
              <div className="console-panel">
                <div className="console-panel-header">
                  <div className="console-panel-title">
                    <KeyRound size={16} style={{ color: "var(--accent-cyan)" }} />
                    <span>Post-Quantum Cryptographic Trust Receipts (NIST FIPS 204)</span>
                  </div>
                  <span className="badge badge-cyan">ML-DSA-65 LATTICE</span>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                  {Object.values(DEMO_CASES).map((c) => {
                    const isVal = verifiedReceipts[c.receipt.receiptId];
                    return (
                      <div key={c.receipt.receiptId} style={{ background: "var(--bg-2)", border: "1px solid var(--line-accent)", padding: "1.5rem", borderRadius: "8px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
                          <div>
                            <span className="mono" style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--accent-cyan)" }}>
                              {c.receipt.receiptId}
                            </span>
                            <div style={{ fontSize: "0.8rem", color: "var(--text-2)" }}>Investigation: {c.title}</div>
                          </div>
                          <span className="badge badge-brand">{c.receipt.algorithm}</span>
                        </div>

                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "1rem", marginBottom: "1rem", fontSize: "0.8rem" }}>
                          <div>
                            <span style={{ color: "var(--text-3)", display: "block" }}>CANONICAL DIGEST (SHA3-256)</span>
                            <span className="mono" style={{ color: "var(--text-1)", wordBreak: "break-all" }}>
                              {c.receipt.canonicalHash}
                            </span>
                          </div>
                          <div>
                            <span style={{ color: "var(--text-3)", display: "block" }}>SIGNING NODE AUTHORITY</span>
                            <span className="mono" style={{ color: "var(--ok)" }}>
                              {c.receipt.signedBy}
                            </span>
                          </div>
                          <div>
                            <span style={{ color: "var(--text-3)", display: "block" }}>PUBLIC KEY FINGERPRINT</span>
                            <span className="mono" style={{ color: "var(--text-2)", wordBreak: "break-all" }}>
                              {c.receipt.publicKeyFingerprint}
                            </span>
                          </div>
                          <div>
                            <span style={{ color: "var(--text-3)", display: "block" }}>TIMESTAMP (UTC)</span>
                            <span className="mono" style={{ color: "var(--text-2)" }}>
                              {c.receipt.timestamp}
                            </span>
                          </div>
                        </div>

                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: "0.75rem", borderTop: "1px solid var(--line)", flexWrap: "wrap", gap: "0.5rem" }}>
                          <span style={{ fontSize: "0.75rem", color: "var(--text-3)", fontFamily: "var(--font-mono)" }}>
                            Signature Length: 3,309 bytes · Category 3 Security
                          </span>
                          <button
                            onClick={() => handleVerifyReceipt(c.receipt.receiptId)}
                            className="btn btn-secondary"
                            style={{ fontSize: "0.75rem", padding: "0.3rem 0.75rem" }}
                          >
                            {isVal ? (
                              <>
                                <CheckCircle size={13} style={{ color: "var(--ok)" }} />
                                <span style={{ color: "var(--ok)" }}>Lattice Verified Valid</span>
                              </>
                            ) : (
                              <>
                                <Cpu size={13} />
                                <span>Verify Mathematical Validity</span>
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* TAB 7: SYSTEM & TELEMETRY */}
          {activeTab === "system" && (
            <div>
              <div className="console-panel">
                <div className="console-panel-header">
                  <div className="console-panel-title">
                    <Layers size={16} style={{ color: "var(--brand-bright)" }} />
                    <span>System Subsystems & Active Regulatory Guardrails</span>
                  </div>
                  <span className="badge badge-ok">All Systems Nominal</span>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem", marginBottom: "2rem" }}>
                  <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: "1.25rem", borderRadius: "8px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                      <span style={{ fontWeight: 600, color: "var(--text-1)" }}>FastAPI ASGI Core</span>
                      <span className="badge badge-ok">Healthy</span>
                    </div>
                    <p style={{ fontSize: "0.8rem", color: "var(--text-2)" }}>Port 8000 listening · JWT + RBAC gateway active · Redis rate limiter 60 req/min.</p>
                  </div>

                  <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: "1.25rem", borderRadius: "8px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                      <span style={{ fontWeight: 600, color: "var(--text-1)" }}>LangGraph StateGraph</span>
                      <span className="badge badge-ok">Durable</span>
                    </div>
                    <p style={{ fontSize: "0.8rem", color: "var(--text-2)" }}>SQLite durable checkpointer epoch #88 · Zero state corruption on hard stop.</p>
                  </div>

                  <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: "1.25rem", borderRadius: "8px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                      <span style={{ fontWeight: 600, color: "var(--text-1)" }}>SEBI T0 Registry Sync</span>
                      <span className="badge badge-ok">Synced</span>
                    </div>
                    <p style={{ fontSize: "0.8rem", color: "var(--text-2)" }}>1,492 licensed RAs/RIAs indexed · Cache TTL 3600s with persistent snapshots.</p>
                  </div>

                  <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: "1.25rem", borderRadius: "8px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                      <span style={{ fontWeight: 600, color: "var(--text-1)" }}>Post-Quantum HSM</span>
                      <span className="badge badge-cyan">Active</span>
                    </div>
                    <p style={{ fontSize: "0.8rem", color: "var(--text-2)" }}>ML-DSA-65 hardware slot 4 · Zero key exfiltration · FIPS 204 compliant.</p>
                  </div>
                </div>

                <div style={{ padding: "1rem", background: "var(--bg-2)", border: "1px solid var(--line)", borderRadius: "8px" }}>
                  <h4 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--brand-bright)", marginBottom: "0.5rem" }}>
                    Strict Architectural Invariants (Non-Negotiable)
                  </h4>
                  <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "0.45rem", fontSize: "0.8125rem", color: "var(--text-2)" }}>
                    <li>✓ <strong>NO INVESTMENT ADVICE:</strong> System never suggests buying, holding, or selling securities.</li>
                    <li>✓ <strong>NO BLACK-BOX PROBABILITIES:</strong> Never emits arbitrary scam percentages without citeable statutory grounding.</li>
                    <li>✓ <strong>NO REGULATORY HALLUCINATIONS:</strong> Always cross-references live T0 SEBI / MCA databases.</li>
                    <li>✓ <strong>ANTI-SSRF PINNING:</strong> Outbound fetcher disallows localhost, 169.254, 10.0.0.0/8, 172.16.0.0/12, and 192.168.0.0/16.</li>
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
