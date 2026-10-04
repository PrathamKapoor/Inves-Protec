"""Unit and integration tests for SANGYAN Landing Page, Investigation Workbench, and Demo fixtures."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sangyan.api.app import create_app
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.tenancy.repository import TenantRepository


@pytest.fixture
def web_client():
    engine = SQLiteDatabaseEngine(":memory:")
    MigrationRunner(engine).migrate()
    app = create_app(engine=engine, require_auth=False)
    client = TestClient(app)
    return client


def test_landing_page_renders_successfully(web_client):
    """Verify GET / returns 200 OK with editorial Denmu-style HTML, grainient canvas, and copy."""
    res = web_client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    html = res.text

    # Brand and typography
    assert "SANGYAN" in html
    assert "VERIFY BEFORE" in html
    assert "YOU TRUST" in html

    # Post-quantum cryptographic references
    assert "ML-DSA-65" in html
    assert "FIPS 204" in html

    # Grainient Canvas shader & reduced motion fallback
    assert "grainient-canvas" in html
    assert "prefers-reduced-motion" in html

    # 10-stage pipeline stepper
    assert "The 10-Stage Investigation Pipeline" in html
    assert "Intake" in html
    assert "Scam Chain" in html
    assert "Trust Seal" in html

    # Preloaded demos showcase
    assert "Telegram 500% Algo Yield" in html
    assert "Counterfeit Research Analyst" in html
    assert "Pre-IPO Offshore Escrow Trap" in html

    # Call to action
    assert "/workbench" in html


def test_investigation_workbench_renders_successfully(web_client):
    """Verify GET /workbench returns 200 OK with full interactive console and tabs."""
    res = web_client.get("/workbench")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    html = res.text

    # Header and context
    assert "INVESTIGATION WORKBENCH" in html
    assert "INVESTOR-DEFENSE" in html
    assert "SSE: CONNECTED" in html

    # Stepper capsules
    assert "step-intake" in html
    assert "step-verification" in html
    assert "step-trust" in html

    # Interactive tabs
    assert "01 // CONTENT & SIGNALS" in html
    assert "02 // CLAIMS & VERIFICATION" in html
    assert "03 // EVIDENCE GRAPH" in html
    assert "04 // SCAM CHAIN (12 STAGES)" in html
    assert "05 // TRUST-SAT (POST-QUANTUM)" in html
    assert "06 // STATUTORY GRIEVANCE" in html

    # SVG Graph container & node inspector
    assert "evidence-svg-graph" in html
    assert "NODE INSPECTOR" in html

    # Statutory grievance portals
    assert "SEBI SCORES 2.0" in html
    assert "1930" in html


def test_app_alias_route(web_client):
    """Verify GET /app serves the workbench."""
    res = web_client.get("/app")
    assert res.status_code == 200
    assert "INVESTIGATION WORKBENCH" in res.text


def test_demo_cases_api_listing(web_client):
    """Verify GET /api/v1/demo/cases returns metadata for all 3 demo cases."""
    res = web_client.get("/api/v1/demo/cases")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 3

    case_ids = {c["id"] for c in data}
    assert "case_telegram_algo" in case_ids
    assert "case_fake_sebi_ra" in case_ids
    assert "case_offshore_escrow" in case_ids

    for c in data:
        assert c["risk_level"] == "HIGH_RISK"
        assert c["claims_count"] >= 2
        assert c["signals_count"] >= 3


def test_demo_case_detail_api(web_client):
    """Verify GET /api/v1/demo/cases/{id} returns rich case details."""
    res = web_client.get("/api/v1/demo/cases/case_telegram_algo")
    assert res.status_code == 200
    case = res.json()
    assert case["id"] == "inv_demo_telegram_algo_2026"
    assert len(case["claims"]) >= 3
    assert len(case["signals"]) >= 4
    assert len(case["scam_chain"]) == 12
    assert "graph" in case
    assert len(case["graph"]["nodes"]) >= 8
    assert len(case["graph"]["edges"]) >= 6

    # Verify trust receipt post-quantum attributes
    rcpt = case["trust_receipt"]
    assert rcpt["algorithm_id"] == "ML-DSA-65"
    assert "sangyan-hsm-pkcs11" in rcpt["signing_key_id"]
    assert len(rcpt["content_digest"]) == 64  # SHA3-256 hex length


def test_demo_case_not_found(web_client):
    """Verify GET /api/v1/demo/cases/{invalid_id} returns 404."""
    res = web_client.get("/api/v1/demo/cases/non_existent_case")
    assert res.status_code == 404
