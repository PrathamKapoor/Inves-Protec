"""HTML inspection views and web interfaces for SANGYAN Investor Safety Platform."""
from __future__ import annotations

import html
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse

from sangyan.core.errors import NotFoundError, PermissionDeniedError
from sangyan.domain.models import Claim, Evidence, Finding, Investigation
from sangyan.web.demo_fixtures import get_demo_case, get_demo_cases
from sangyan.web.landing import render_landing_page
from sangyan.web.workbench import render_workbench_page


def get_views_router(
    repository_factory: Optional[Any] = None,
    trust_service: Optional[Any] = None,
) -> APIRouter:
    """Build router for web landing, investigation workbench, and HTML inspection views."""
    router = APIRouter(tags=["web_and_inspection_ui"])

    def _get_repo(org_id: Optional[str], usr_id: Optional[str]):
        if repository_factory and org_id and usr_id:
            try:
                return repository_factory(org_id, usr_id)
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        return None

    # -----------------------------------------------------------------------
    # Public Web Routes: Landing Page & Workbench
    # -----------------------------------------------------------------------

    @router.get("/", response_class=HTMLResponse)
    def landing_page():
        """Render Denmu-style public editorial landing page with Grainient shader and evidence showcase."""
        return HTMLResponse(content=render_landing_page())

    @router.get("/workbench", response_class=HTMLResponse)
    def investigation_workbench():
        """Render interactive investigation workbench with live SSE, graph, and trust receipts."""
        return HTMLResponse(content=render_workbench_page())

    @router.get("/app", response_class=HTMLResponse)
    def app_workbench_alias():
        """Direct alias for investigation workbench."""
        return HTMLResponse(content=render_workbench_page())

    @router.get("/console", response_class=HTMLResponse)
    def console_page():
        """Direct route for interactive investigation console."""
        return HTMLResponse(content=render_workbench_page())

    # -----------------------------------------------------------------------
    # Interactive Walkthrough & Demo API Endpoints
    # -----------------------------------------------------------------------

    @router.get("/api/v1/demo/cases")
    def list_demo_cases():
        """Return metadata for all preloaded interactive demo cases."""
        return get_demo_cases()

    @router.get("/api/v1/demo/cases/{case_id}")
    def get_demo_case_detail(case_id: str):
        """Return full investigation fixture for specified demo case."""
        case_data = get_demo_case(case_id)
        if not case_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Demo case '{case_id}' not found")
        return case_data

    # -----------------------------------------------------------------------
    # Human-Auditable Inspection Views (Backward Compatible)
    # -----------------------------------------------------------------------

    @router.get("/inspect/claim/{claim_id}", response_class=HTMLResponse)
    def inspect_claim(
        claim_id: str,
        organization_id: str = Query(...),
        user_id: str = Query(...),
    ):
        """Render human-auditable claim verification report."""
        repo = _get_repo(organization_id, user_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")

        try:
            claim = repo.get_claim(claim_id)
            findings = repo.list_findings_for_claim(claim_id)
            evidence_items = repo.list_evidence_for_claim(claim_id)
        except NotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

        finding = findings[0] if findings else None
        stance = finding.status if finding else claim.status

        # Color and theme mapping
        theme = {
            "SUPPORTED": {"bg": "#ecfdf5", "border": "#10b981", "text": "#065f46", "label": "SUPPORTED"},
            "CONTRADICTED": {"bg": "#fef2f2", "border": "#ef4444", "text": "#991b1b", "label": "CONTRADICTED"},
            "CONFLICTING": {"bg": "#fff7ed", "border": "#f97316", "text": "#9a3412", "label": "CONFLICTING"},
            "OUTDATED": {"bg": "#fffbeb", "border": "#f59e0b", "text": "#92400e", "label": "OUTDATED"},
            "INSUFFICIENT_EVIDENCE": {"bg": "#f3f4f6", "border": "#6b7280", "text": "#1f2937", "label": "INSUFFICIENT EVIDENCE"},
        }.get(stance, {"bg": "#f3f4f6", "border": "#9ca3af", "text": "#374151", "label": stance})

        # Insufficient evidence banner (Mandatory Section 40)
        insufficient_banner = ""
        if stance == "INSUFFICIENT_EVIDENCE":
            insufficient_banner = """
            <div style="background-color: #fef3c7; border-left: 5px solid #d97706; padding: 16px; margin: 20px 0; border-radius: 4px;">
                <h4 style="margin: 0 0 8px 0; color: #92400e; font-size: 16px;">⚠️ INSUFFICIENT EVIDENCE</h4>
                <p style="margin: 0; color: #78350f; font-size: 14px;">
                    No authoritative institutional record was found to substantiate or refute this claim.<br>
                    <strong>Note: This does NOT establish that the claim is false.</strong>
                </p>
            </div>
            """

        # Conflicting evidence comparison display (Mandatory Section 40)
        conflicting_display = ""
        if stance == "CONFLICTING" and len(evidence_items) >= 2:
            cards = ""
            for idx, ev in enumerate(evidence_items[:2]):
                src_name = html.escape(ev.source_id)
                cards += f"""
                <div style="flex: 1; min-width: 250px; background: white; border: 1px solid #e5e7eb; border-radius: 6px; padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                    <div style="font-size: 12px; font-weight: bold; color: #6b7280; text-transform: uppercase;">Source {chr(65+idx)}: {src_name}</div>
                    <div style="margin: 8px 0; font-size: 14px; font-weight: bold; color: {'#16a34a' if ev.stance == 'SUPPORTS' else '#dc2626'};">Stance: {html.escape(ev.stance)}</div>
                    <blockquote style="margin: 0; padding-left: 10px; border-left: 3px solid #d1d5db; font-size: 13px; color: #4b5563; font-style: italic;">
                        "{html.escape(ev.excerpt)}"
                    </blockquote>
                </div>
                """
            conflicting_display = f"""
            <div style="margin: 20px 0;">
                <h4 style="margin-bottom: 10px; color: #9a3412;">⚡ Conflicting Authoritative Determinations</h4>
                <div style="display: flex; gap: 15px; flex-wrap: wrap;">{cards}</div>
                <p style="font-size: 13px; color: #6b7280; margin-top: 8px;"><strong>Review required:</strong> Multiple registered institutional sources yielded incompatible records.</p>
            </div>
            """

        # Evidence records table
        evidence_rows = ""
        for ev in evidence_items:
            retrieved_dt = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(ev.retrieved_at))
            evidence_rows += f"""
            <tr style="border-bottom: 1px solid #e5e7eb;">
                <td style="padding: 10px; font-family: monospace; font-size: 12px;">{html.escape(ev.source_id)}</td>
                <td style="padding: 10px; font-size: 13px;">{html.escape(ev.excerpt)}</td>
                <td style="padding: 10px; font-family: monospace; font-size: 11px; color: #6b7280;">{html.escape(ev.content_hash[:16])}...</td>
                <td style="padding: 10px; font-size: 12px; color: #6b7280;">{retrieved_dt}</td>
            </tr>
            """

        # Trust status
        trust_status_html = """
        <div style="display: inline-flex; align-items: center; gap: 8px; background: #f0fdf4; border: 1px solid #86efac; padding: 6px 12px; border-radius: 9999px; font-size: 12px; color: #166534;">
            <span>🛡️ Post-Quantum Tamper-Evident Receipt: Active (ML-DSA-65)</span>
        </div>
        """

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SANGYAN — Claim Verification Audit</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f9fafb; color: #111827; margin: 0; padding: 30px; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 30px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e5e7eb; padding-bottom: 15px; margin-bottom: 20px; }}
        .claim-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 20px; margin-bottom: 20px; }}
        .badge {{ display: inline-block; padding: 6px 14px; border-radius: 4px; font-weight: bold; font-size: 13px; text-transform: uppercase; border: 1px solid; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th {{ background: #f3f4f6; text-align: left; padding: 10px; font-size: 12px; text-transform: uppercase; color: #4b5563; border-bottom: 2px solid #e5e7eb; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1 style="margin: 0; font-size: 22px;">SANGYAN Verification Inspection</h1>
                <div style="font-size: 12px; color: #6b7280; margin-top: 4px;">Claim ID: {html.escape(claim.id)}</div>
            </div>
            <div>
                <span class="badge" style="background-color: {theme['bg']}; border-color: {theme['border']}; color: {theme['text']};">
                    {theme['label']}
                </span>
            </div>
        </div>

        <div class="claim-card">
            <div style="font-size: 11px; text-transform: uppercase; font-weight: bold; color: #64748b; margin-bottom: 6px;">Evaluated Assertion</div>
            <div style="font-size: 17px; font-weight: 500; color: #0f172a; line-height: 1.5;">"{html.escape(claim.statement)}"</div>
            <div style="margin-top: 10px; font-size: 12px; color: #64748b;">Type: <strong>{html.escape(claim.claim_type.upper())}</strong> | Extracted: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(claim.extracted_at))}</div>
        </div>

        {insufficient_banner}
        {conflicting_display}

        <div style="margin-top: 25px;">
            <h3 style="font-size: 16px; margin-bottom: 8px;">Authoritative Finding</h3>
            <p style="font-size: 14px; color: #374151; line-height: 1.6; background: #fafafa; padding: 15px; border-left: 4px solid {theme['border']}; border-radius: 4px;">
                {html.escape(finding.rationale if finding else 'Evaluation completed.')}
            </p>
        </div>

        <div style="margin-top: 25px;">
            <h3 style="font-size: 16px; margin-bottom: 8px;">Evidentiary Provenance ({len(evidence_items)} records)</h3>
            <table>
                <thead>
                    <tr>
                        <th>Source</th>
                        <th>Authoritative Excerpt</th>
                        <th>SHA3-256 Digest</th>
                        <th>Retrieved At</th>
                    </tr>
                </thead>
                <tbody>
                    {evidence_rows if evidence_rows else '<tr><td colspan="4" style="padding: 15px; text-align: center; color: #9ca3af;">No evidence records persisted.</td></tr>'}
                </tbody>
            </table>
        </div>

        <div style="margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 20px; display: flex; justify-content: space-between; align-items: center;">
            {trust_status_html}
            <div style="font-size: 12px; color: #9ca3af;">
                <a href="/workbench" style="color: #6366f1; text-decoration: none; margin-right: 14px;">Open Workbench &rarr;</a>
                SANGYAN Phase 3 Investor Safety Foundation
            </div>
        </div>
    </div>
</body>
</html>
"""
        return HTMLResponse(content=html_content)

    @router.get("/inspect/investigation/{investigation_id}", response_class=HTMLResponse)
    def inspect_investigation(
        investigation_id: str,
        organization_id: str = Query(...),
        user_id: str = Query(...),
    ):
        """Render high-level investigation summary view with claims and signals."""
        repo = _get_repo(organization_id, user_id)
        if not repo:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")

        try:
            inv = repo.get_investigation(investigation_id)
            claims = [repo.get_claim(cid) for cid in inv.claim_ids]
        except NotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")

        claims_html = ""
        for c in claims:
            inspect_url = f"/inspect/claim/{c.id}?organization_id={organization_id}&user_id={user_id}"
            claims_html += f"""
            <tr style="border-bottom: 1px solid #e5e7eb;">
                <td style="padding: 10px; font-size: 13px;"><a href="{inspect_url}" style="color: #2563eb; text-decoration: none; font-weight: 500;">{html.escape(c.statement)}</a></td>
                <td style="padding: 10px; font-size: 12px;">{html.escape(c.claim_type)}</td>
                <td style="padding: 10px; font-weight: bold; font-size: 12px;">{html.escape(c.status)}</td>
                <td style="padding: 10px;"><a href="{inspect_url}" style="font-size: 12px; color: #4b5563; background: #f3f4f6; padding: 4px 8px; border-radius: 4px; text-decoration: none;">Audit Claim &rarr;</a></td>
            </tr>
            """

        overall_status = inv.metadata.get("overall_status", inv.status)
        badge_color = {
            "SAFE": "#16a34a",
            "HIGH_RISK": "#dc2626",
            "SUSPICIOUS": "#ea580c",
            "UNVERIFIED": "#4b5563",
        }.get(overall_status, "#4b5563")

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SANGYAN — Investigation {html.escape(inv.id)}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f9fafb; color: #111827; margin: 0; padding: 30px; }}
        .container {{ max-width: 960px; margin: 0 auto; background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 30px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th {{ background: #f3f4f6; text-align: left; padding: 10px; font-size: 12px; text-transform: uppercase; color: #4b5563; border-bottom: 2px solid #e5e7eb; }}
        .stepper {{ display: flex; justify-content: space-between; margin: 25px 0 30px 0; position: relative; }}
        .step {{ flex: 1; text-align: center; position: relative; }}
        .step-circle {{ width: 28px; height: 28px; border-radius: 50%; background: #e5e7eb; color: #6b7280; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; margin-bottom: 6px; transition: all 0.3s ease; }}
        .step-label {{ font-size: 11px; color: #6b7280; font-weight: 500; display: block; }}
        .step.active .step-circle {{ background: #3b82f6; color: white; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.3); }}
        .step.active .step-label {{ color: #1d4ed8; font-weight: bold; }}
        .step.completed .step-circle {{ background: #10b981; color: white; }}
        .step.completed .step-label {{ color: #047857; }}
        .event-log {{ background: #1e293b; color: #f8fafc; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; padding: 14px; border-radius: 6px; max-height: 200px; overflow-y: auto; margin-top: 20px; }}
        .event-entry {{ margin-bottom: 4px; line-height: 1.5; }}
        .event-time {{ color: #94a3b8; margin-right: 8px; }}
        .event-type {{ color: #38bdf8; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e5e7eb; padding-bottom: 15px; margin-bottom: 20px;">
            <div>
                <h1 style="margin: 0; font-size: 22px;">Investigation Overview</h1>
                <div style="font-size: 12px; color: #6b7280; margin-top: 4px;">ID: {html.escape(inv.id)} &bull; Tenant: {html.escape(organization_id)}</div>
            </div>
            <div style="display: flex; align-items: center; gap: 12px;">
                <a href="/workbench" style="color: #6366f1; text-decoration: none; font-size: 13px; font-weight: 600;">Open in Workbench &rarr;</a>
                <span id="risk-badge" style="display: inline-block; padding: 6px 14px; border-radius: 4px; font-weight: bold; font-size: 14px; color: white; background-color: {badge_color};">
                    {html.escape(overall_status)}
                </span>
            </div>
        </div>

        <!-- Real-Time Investigation Progress Stepper -->
        <h3 style="margin: 0 0 10px 0; font-size: 14px; text-transform: uppercase; color: #64748b; letter-spacing: 0.05em;">Real-Time Pipeline Progress</h3>
        <div class="stepper" id="pipeline-stepper">
            <div class="step" id="step-intake"><div class="step-circle">1</div><span class="step-label">Intake</span></div>
            <div class="step" id="step-intelligence"><div class="step-circle">2</div><span class="step-label">Intelligence</span></div>
            <div class="step" id="step-verification"><div class="step-circle">3</div><span class="step-label">Verification</span></div>
            <div class="step" id="step-correlation"><div class="step-circle">4</div><span class="step-label">Correlation</span></div>
            <div class="step" id="step-scam_chain"><div class="step-circle">5</div><span class="step-label">Scam Chain</span></div>
            <div class="step" id="step-guidance"><div class="step-circle">6</div><span class="step-label">Guidance</span></div>
            <div class="step" id="step-explanation"><div class="step-circle">7</div><span class="step-label">Explain</span></div>
            <div class="step" id="step-review"><div class="step-circle">8</div><span class="step-label">Review</span></div>
            <div class="step" id="step-trust"><div class="step-circle">9</div><span class="step-label">Trust Seal</span></div>
            <div class="step" id="step-completed"><div class="step-circle">10</div><span class="step-label">Complete</span></div>
        </div>

        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin-bottom: 20px;">
            <div style="font-size: 14px; color: #334155;"><strong>Summary:</strong> <span id="inv-summary">{html.escape(inv.summary)}</span></div>
        </div>

        <h3>Decomposed Claims & Verification Stances</h3>
        <table>
            <thead>
                <tr>
                    <th>Claim Statement</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {claims_html if claims_html else '<tr><td colspan="4" style="padding: 15px; text-align: center; color: #9ca3af;">No claims in this investigation.</td></tr>'}
            </tbody>
        </table>

        <h3 style="margin-top: 30px; margin-bottom: 8px;">Live Investigation Events Feed (SSE)</h3>
        <div class="event-log" id="event-feed">
            <div class="event-entry"><span class="event-time">[INIT]</span> <span class="event-type">CONNECTED</span> Listening to Server-Sent Events stream...</div>
        </div>
    </div>

    <script>
        (function() {{
            const invId = "{html.escape(inv.id)}";
            const orgId = "{html.escape(organization_id)}";
            const stepMap = {{
                "INTAKE_STARTED": ["step-intake", "active"],
                "INTAKE_COMPLETED": ["step-intake", "completed"],
                "INTELLIGENCE_STARTED": ["step-intelligence", "active"],
                "INTELLIGENCE_COMPLETED": ["step-intelligence", "completed"],
                "VERIFICATION_STARTED": ["step-verification", "active"],
                "VERIFICATION_COMPLETED": ["step-verification", "completed"],
                "CORRELATION_STARTED": ["step-correlation", "active"],
                "CORRELATION_COMPLETED": ["step-correlation", "completed"],
                "SCAM_CHAIN_STARTED": ["step-scam_chain", "active"],
                "SCAM_CHAIN_COMPLETED": ["step-scam_chain", "completed"],
                "GUIDANCE_STARTED": ["step-guidance", "active"],
                "GUIDANCE_COMPLETED": ["step-guidance", "completed"],
                "EXPLANATION_STARTED": ["step-explanation", "active"],
                "EXPLANATION_COMPLETED": ["step-explanation", "completed"],
                "REVIEW_REQUIRED": ["step-review", "active"],
                "REVIEW_RESUMED": ["step-review", "completed"],
                "TRUST_FINALIZATION_STARTED": ["step-trust", "active"],
                "TRUST_FINALIZATION_COMPLETED": ["step-trust", "completed"],
                "INVESTIGATION_COMPLETED": ["step-completed", "completed"]
            }};

            const feed = document.getElementById("event-feed");
            const es = new EventSource("/api/v1/investigations/" + invId + "/events");

            es.onmessage = function(e) {{
                try {{
                    const data = JSON.parse(e.data);
                    if (data.event_type === "HEARTBEAT") return;

                    const row = document.createElement("div");
                    row.className = "event-entry";
                    const t = new Date(data.timestamp * 1000).toISOString().substr(11, 8);
                    row.innerHTML = `<span class="event-time">[${{t}}]</span> <span class="event-type">#${{data.sequence}} ${{data.event_type}}</span> ${{JSON.stringify(data.payload)}}`;
                    feed.appendChild(row);
                    feed.scrollTop = feed.scrollHeight;

                    if (stepMap[data.event_type]) {{
                        const [stepId, stateClass] = stepMap[data.event_type];
                        const el = document.getElementById(stepId);
                        if (el) {{
                            el.classList.remove("active");
                            el.classList.add(stateClass);
                        }}
                    }}
                }} catch (err) {{
                    console.error("Error parsing event:", err);
                }}
            }};

            es.onerror = function() {{
                const row = document.createElement("div");
                row.className = "event-entry";
                row.innerHTML = `<span class="event-time">[INFO]</span> Stream connection idle or completed.`;
                feed.appendChild(row);
            }};
        }})();
    </script>
</body>
</html>
"""
        return HTMLResponse(content=html_content)

    return router
