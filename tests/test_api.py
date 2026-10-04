"""Tests for SANGYAN REST API and HTML inspection views."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from sangyan.api.app import create_app
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.domain.models import Claim, ContentItem, Evidence, Finding
from sangyan.tenancy.repository import TenantAdministration, TenantRepository
from sangyan.trust.service import TrustService
from sangyan.verification.engine import ClaimVerificationEngine
from sangyan.verification.trust_binding import TrustBindingService


@pytest.fixture
def app_and_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_api.db"
        key_dir = Path(tmpdir) / "keys"
        engine = SQLiteDatabaseEngine(db_path)
        MigrationRunner(engine).migrate()

        admin = TenantAdministration(engine)
        org_id = admin.create_organization("API Test Org")
        user_id = admin.create_user("analyst@api.org", "API Analyst")
        admin.add_membership(org_id, user_id, "sangyan_analyst")

        repo = TenantRepository(engine, org_id, user_id)
        trust = TrustService(engine, key_dir=key_dir)
        trust_binding = TrustBindingService(trust)
        verif_engine = ClaimVerificationEngine(trust_binding=trust_binding)

        app = create_app(
            engine=engine,
            trust_service=trust,
            verification_engine=verif_engine,
        )
        client = TestClient(app)

        yield client, repo, org_id, user_id
        engine.close()


def test_health_check(app_and_repo):
    client, _, _, _ = app_and_repo
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["sources_registered"] >= 7


def test_list_sources(app_and_repo):
    client, _, org_id, user_id = app_and_repo
    res = client.get(f"/api/v1/sources?organization_id={org_id}&user_id={user_id}")
    assert res.status_code == 200
    sources = res.json()
    assert len(sources) >= 7
    source_ids = [s["source_id"] for s in sources]
    assert "src_sebi_intermediaries" in source_ids
    assert "src_mca_registry" in source_ids
    assert "src_nse_members" in source_ids


def test_verify_single_claim_supported(app_and_repo):
    client, repo, org_id, user_id = app_and_repo
    payload = {
        "statement": "Zerodha Broking Limited is SEBI registered under INZ000031633.",
        "claim_type": "regulatory",
        "organization_id": org_id,
        "user_id": user_id,
    }
    res = client.post("/api/v1/verify/claim", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUPPORTED"
    assert data["finding"]["status"] == "SUPPORTED"
    assert data["evidence_count"] >= 1
    assert data["trust_receipt_id"] is not None


def test_verify_single_claim_contradicted(app_and_repo):
    client, repo, org_id, user_id = app_and_repo
    payload = {
        "statement": "We offer 100% guaranteed monthly returns on your capital.",
        "claim_type": "return",
        "organization_id": org_id,
        "user_id": user_id,
    }
    res = client.post("/api/v1/verify/claim", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "CONTRADICTED"
    assert "SEBI/HO/MIRSD" in data["finding"]["rationale"]


def test_verify_content_item_pipeline(app_and_repo):
    client, repo, org_id, user_id = app_and_repo
    payload = {
        "content_type": "text",
        "raw_content": (
            "Zerodha Broking is SEBI registered under INZ000031633. "
            "However transfer funds to personal VPA fastprofit24@paytm for guaranteed 50% returns."
        ),
        "organization_id": org_id,
        "user_id": user_id,
    }
    res = client.post("/api/v1/verify/content", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["overall_status"] in {"HIGH_RISK", "SUSPICIOUS"}
    assert len(data["outcomes"]) >= 2
    assert data["investigation"]["id"] is not None


def test_html_inspection_claim_views(app_and_repo):
    client, repo, org_id, user_id = app_and_repo

    # 1. Setup SUPPORTED claim
    item = ContentItem(organization_id=org_id, content_type="text", raw_content="Registered broker")
    item_id = repo.save_content_item(item)
    c1 = Claim(content_item_id=item_id, statement="Zerodha Broking INZ000031633.", claim_type="regulatory")
    c1_id = repo.save_claim(c1)
    c1.id = c1_id

    ev1 = Evidence(source_id="src_sebi_intermediaries", claim_id=c1_id, excerpt="Active INZ000031633", stance="SUPPORTS")
    ev1_id = repo.save_evidence(ev1)
    f1 = Finding(claim_id=c1_id, statement=c1.statement, status="SUPPORTED", rationale="Corroborated by SEBI.", evidence_refs=[ev1_id])
    repo.save_finding(f1)

    res = client.get(f"/inspect/claim/{c1_id}?organization_id={org_id}&user_id={user_id}")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "SUPPORTED" in res.text
    assert "Active INZ000031633" in res.text

    # 2. Setup INSUFFICIENT_EVIDENCE claim and check mandatory banner
    c2 = Claim(content_item_id=item_id, statement="Generic unverified assertion", claim_type="other")
    c2_id = repo.save_claim(c2)
    c2.id = c2_id
    f2 = Finding(claim_id=c2_id, statement=c2.statement, status="INSUFFICIENT_EVIDENCE", rationale="No record.")
    repo.save_finding(f2)

    res2 = client.get(f"/inspect/claim/{c2_id}?organization_id={org_id}&user_id={user_id}")
    assert res2.status_code == 200
    # Mandatory Section 40 requirement:
    assert "INSUFFICIENT EVIDENCE" in res2.text
    assert "This does NOT establish that the claim is false" in res2.text

    # 3. Setup CONFLICTING claim and check side-by-side opposing evidence
    c3 = Claim(content_item_id=item_id, statement="Disputed broker status", claim_type="regulatory")
    c3_id = repo.save_claim(c3)
    c3.id = c3_id
    ev_a = Evidence(source_id="src_sebi_intermediaries", claim_id=c3_id, excerpt="Registry shows active license", stance="SUPPORTS")
    ev_b = Evidence(source_id="src_sebi_circulars", claim_id=c3_id, excerpt="Enforcement order cancelled operations", stance="CONTRADICTS")
    eva_id = repo.save_evidence(ev_a)
    evb_id = repo.save_evidence(ev_b)
    f3 = Finding(claim_id=c3_id, statement=c3.statement, status="CONFLICTING", rationale="Discrepancy across registries.", evidence_refs=[eva_id, evb_id])
    repo.save_finding(f3)


    res3 = client.get(f"/inspect/claim/{c3_id}?organization_id={org_id}&user_id={user_id}")
    assert res3.status_code == 200
    assert "CONFLICTING" in res3.text
    assert "Source A" in res3.text
    assert "Source B" in res3.text


def test_html_inspection_investigation(app_and_repo):
    client, repo, org_id, user_id = app_and_repo
    item = ContentItem(organization_id=org_id, content_type="text", raw_content="Broker statement")
    item_id = repo.save_content_item(item)
    c = Claim(content_item_id=item_id, statement="Zerodha is SEBI registered.", claim_type="regulatory")
    c_id = repo.save_claim(c)

    from sangyan.domain.models import Investigation
    inv = Investigation(
        organization_id=org_id,
        user_id=user_id,
        content_item_id=item_id,
        claim_ids=[c_id],
        summary="Investigation completed with full evidence.",
        metadata={"overall_status": "SAFE"},
    )
    inv_id = repo.save_investigation(inv)

    res = client.get(f"/inspect/investigation/{inv_id}?organization_id={org_id}&user_id={user_id}")
    assert res.status_code == 200
    assert "Investigation Overview" in res.text
    assert "SAFE" in res.text
    assert "Zerodha is SEBI registered." in res.text


def test_investigate_batch_api(app_and_repo):
    client, repo, org_id, user_id = app_and_repo
    payload = {
        "contents": [
            "Join our VIP Telegram group for guaranteed stock recommendations: https://t.me/profit_club",
            "Pay via UPI to zerodha.pay@okhdfcbank or fastprofit@paytm",
            "Withdrawal blocked. Pay ₹15,000 withdrawal tax to release funds immediately.",
        ],
        "content_type": "text",
        "organization_id": org_id,
        "user_id": user_id,
    }
    res = client.post("/api/v1/investigate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["overall_status"] == "HIGH_RISK"
    assert data["content_count"] == 3
    assert len(data["scam_chain"]) == 12
    assert len(data["correlations"]) >= 1
    assert len(data["guidance"]) >= 1
    assert data["grievance"]["category"] in {"INVESTMENT_SCAM", "CYBER_FRAUD"}
    assert "1930" in data["grievance"]["helpline"]

    # Test querying sub-resources
    inv_id = data["investigation_id"]
    res_corr = client.get(f"/api/v1/investigations/{inv_id}/correlations?organization_id={org_id}&user_id={user_id}")
    assert res_corr.status_code == 200
    assert len(res_corr.json()) >= 1

    res_sc = client.get(f"/api/v1/investigations/{inv_id}/scam_chain?organization_id={org_id}&user_id={user_id}")
    assert res_sc.status_code == 200
    assert len(res_sc.json()) == 12

    res_grv = client.get(f"/api/v1/investigations/{inv_id}/grievance?organization_id={org_id}&user_id={user_id}")
    assert res_grv.status_code == 200
    assert res_grv.json()["category"] in {"INVESTMENT_SCAM", "CYBER_FRAUD"}


def test_workflow_api_lifecycle(app_and_repo):
    client, repo, org_id, user_id = app_and_repo

    # 1. Start workflow requiring review
    payload = {
        "contents": [
            "Join our VIP Telegram group https://t.me/profit_club with guaranteed returns.",
            "Transfer funds to fastprofit@paytm.",
        ],
        "organization_id": org_id,
        "user_id": user_id,
        "require_review": True,
    }
    res = client.post("/api/v1/workflow/start", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "AWAITING_REVIEW"
    assert data["review_required"] is True
    inv_id = data["investigation_id"]

    # 2. Get workflow state
    res_state = client.get(f"/api/v1/workflow/{inv_id}/state?organization_id={org_id}&user_id={user_id}")
    assert res_state.status_code == 200
    state_data = res_state.json()
    assert state_data["status"] == "AWAITING_REVIEW"

    # 3. List workflow runs
    res_runs = client.get(f"/api/v1/workflow/runs?organization_id={org_id}&user_id={user_id}")
    assert res_runs.status_code == 200
    runs = res_runs.json()
    assert len(runs) >= 1
    assert runs[0]["investigation_id"] == inv_id

    # 4. Resume workflow
    res_resume = client.post(
        f"/api/v1/workflow/{inv_id}/resume",
        json={
            "action": "CONFIRM",
            "user_id": user_id,
            "organization_id": org_id,
            "reason": "Confirmed fraudulent solicitation",
        },
    )
    assert res_resume.status_code == 200
    resume_data = res_resume.json()
    assert resume_data["status"] == "COMPLETED"
    assert resume_data["trust_status"] == "FINALIZED"
    assert resume_data["trust_receipt_id"] is not None


def test_workflow_api_cancellation(app_and_repo):
    client, repo, org_id, user_id = app_and_repo

    # Start workflow requiring review
    payload = {
        "contents": ["Dubious advisory claim"],
        "organization_id": org_id,
        "user_id": user_id,
        "require_review": True,
    }
    res = client.post("/api/v1/workflow/start", json=payload)
    assert res.status_code == 200
    inv_id = res.json()["investigation_id"]

    # Cancel workflow
    res_cancel = client.post(
        f"/api/v1/workflow/{inv_id}/cancel",
        json={
            "user_id": user_id,
            "organization_id": org_id,
            "reason": "User requested withdrawal",
        },
    )
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "CANCELLED"

    # Resuming cancelled workflow must return 400
    res_resume = client.post(
        f"/api/v1/workflow/{inv_id}/resume",
        json={
            "action": "CONFIRM",
            "user_id": user_id,
            "organization_id": org_id,
        },
    )
    assert res_resume.status_code == 400


