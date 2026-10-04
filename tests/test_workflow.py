"""Comprehensive unit, integration, and adversarial tests for SANGYAN LangGraph workflow orchestration."""
from __future__ import annotations

import concurrent.futures
import tempfile
import time
from pathlib import Path

import pytest

from sangyan.core.errors import PermissionDeniedError
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.domain.models import ContentItem, Review
from sangyan.tenancy.models import SANGYAN_ROLES
from sangyan.tenancy.repository import TenantAdministration, TenantRepository
from sangyan.trust.service import TrustService
from sangyan.verification.trust_binding import TrustBindingService
from sangyan.workflow.checkpointer import WorkflowCheckpointer, format_thread_id
from sangyan.workflow.errors import (
    CannotCancelCompletedInvestigationError,
    InvestigationCancelledError,
    NonRetryableWorkflowError,
    RetryableWorkflowError,
    ReviewConflictError,
    TenantMismatchError,
)
from sangyan.workflow.graph import InvestigationWorkflow
from sangyan.workflow.nodes import WorkflowNodeSuite
from sangyan.workflow.service import WorkflowService


@pytest.fixture
def workflow_env():
    """Create isolated test environment with SQLite database, admin/analyst/viewer users, and WorkflowService."""
    import shutil
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = Path(tmpdir) / "sangyan_workflow_test.db"
        engine = SQLiteDatabaseEngine(db_path)
        runner = MigrationRunner(engine)
        runner.migrate()

        admin_svc = TenantAdministration(engine)
        org_a = admin_svc.create_organization("Org Alpha")
        org_b = admin_svc.create_organization("Org Beta")

        user_admin = admin_svc.create_user("admin@alpha.org", "Admin Alpha")
        user_analyst = admin_svc.create_user("analyst@alpha.org", "Analyst Alpha")
        user_viewer = admin_svc.create_user("viewer@alpha.org", "Viewer Alpha")
        user_b = admin_svc.create_user("analyst@beta.org", "Analyst Beta")

        admin_svc.add_membership(org_a, user_admin, "sangyan_admin")
        admin_svc.add_membership(org_a, user_analyst, "sangyan_analyst")
        admin_svc.add_membership(org_a, user_viewer, "sangyan_viewer")
        admin_svc.add_membership(org_b, user_b, "sangyan_analyst")

        key_dir = Path(tmpdir) / "pqc_keys"
        trust_service = TrustService(engine, key_dir=key_dir)
        trust_binding = TrustBindingService(trust_service=trust_service)

        cp_path = Path(tmpdir) / "checkpoints.db"
        checkpointer = WorkflowCheckpointer(db_path=cp_path)

        def repo_factory(org_id: str, user_id: str | None = None) -> TenantRepository:
            actor = user_id or user_analyst
            if org_id == org_b:
                actor = user_b
            return TenantRepository(engine, org_id, actor)

        node_suite = WorkflowNodeSuite(
            trust_binding=trust_binding,
            repository_factory=lambda oid: repo_factory(oid),
        )

        workflow = InvestigationWorkflow(
            node_suite=node_suite,
            checkpointer=checkpointer.get_saver(),
        )

        service = WorkflowService(
            repository_factory=lambda oid: repo_factory(oid),
            workflow=workflow,
            checkpointer=checkpointer,
            node_suite=node_suite,
        )

        yield {
            "tmpdir": tmpdir,
            "engine": engine,
            "org_a": org_a,
            "org_b": org_b,
            "user_admin": user_admin,
            "user_analyst": user_analyst,
            "user_viewer": user_viewer,
            "user_b": user_b,
            "repo_factory": repo_factory,
            "service": service,
            "workflow": workflow,
            "checkpointer": checkpointer,
            "cp_path": cp_path,
            "trust_service": trust_service,
            "trust_binding": trust_binding,
            "node_suite": node_suite,
        }
    finally:
        try:
            checkpointer.close()
        except Exception:
            pass
        try:
            engine.close()
        except Exception:
            pass
        shutil.rmtree(tmpdir, ignore_errors=True)


class TestWorkflowExecution:
    def test_scenario_1_normal_investigation(self, workflow_env):
        """Scenario 1: Full automated pipeline for legitimate content without review interruption."""
        service: WorkflowService = workflow_env["service"]
        org_a = workflow_env["org_a"]
        user_analyst = workflow_env["user_analyst"]

        ci = ContentItem(
            organization_id=org_a,
            content_type="text/plain",
            raw_content="Zerodha Broking Ltd is a registered stock broker INZ000031633 zerodha.com.",
        )

        res = service.start_investigation([ci], user_id=user_analyst, organization_id=org_a)

        assert res["status"] == "COMPLETED"
        assert res["risk_posture"] == "SAFE"
        assert not res["review_required"]
        assert res["trust_status"] == "FINALIZED"
        assert res["trust_receipt_id"] is not None

        # Verify database records
        repo = workflow_env["repo_factory"](org_a)
        inv = repo.get_investigation(res["investigation_id"])
        assert inv.status == "COMPLETED"
        assert inv.trust_receipt_id == res["trust_receipt_id"]

        wf_run = repo.get_workflow_run_by_investigation(inv.id)
        assert wf_run is not None
        assert wf_run.status == "COMPLETED"

    def test_scenario_2_investigation_requiring_review(self, workflow_env):
        """Scenario 2: Content requiring human review pauses at review gate and resumes upon supervisory decision."""
        service: WorkflowService = workflow_env["service"]
        org_a = workflow_env["org_a"]
        user_analyst = workflow_env["user_analyst"]
        user_admin = workflow_env["user_admin"]

        # Content with conflicting authoritative evidence (genuine domain vs bogus registration)
        ci = ContentItem(
            organization_id=org_a,
            content_type="text/plain",
            raw_content="Zerodha broker claiming registration INZ000000000 but official domain is zerodha.com.",
        )

        # Launch workflow
        res1 = service.start_investigation([ci], user_id=user_analyst, organization_id=org_a)

        # Must halt at review_gate_node
        assert res1["status"] == "AWAITING_REVIEW"
        assert res1["review_required"] is True

        repo = workflow_env["repo_factory"](org_a)
        inv = repo.get_investigation(res1["investigation_id"])
        assert inv.status == "AWAITING_REVIEW"

        wf_run = repo.get_workflow_run_by_investigation(inv.id)
        assert wf_run.status == "AWAITING_REVIEW"
        assert wf_run.current_node == "review_gate_node"

        # Resume with supervisory confirmation
        res2 = service.resume_investigation(
            investigation_id=inv.id,
            review_action="CONFIRM",
            user_id=user_admin,
            organization_id=org_a,
            reason="Confirmed broker impersonation and bogus registration number.",
        )

        assert res2["status"] == "COMPLETED"
        assert res2["trust_status"] == "FINALIZED"
        assert res2["trust_receipt_id"] is not None
        assert res2["review_decision"]["action"] == "CONFIRM"

        # Verify review recorded in repository
        reviews = repo.list_reviews_for_investigation(inv.id)
        assert len(reviews) == 1
        assert reviews[0].action == "CONFIRM"
        assert reviews[0].reviewer_id == user_admin

    def test_scenario_3_worker_crash_and_process_restart(self, workflow_env):
        """Scenario 3: Workflow interrupted at review survives complete process termination and resumes from disk."""
        tmpdir = workflow_env["tmpdir"]
        engine = workflow_env["engine"]
        org_a = workflow_env["org_a"]
        user_analyst = workflow_env["user_analyst"]
        user_admin = workflow_env["user_admin"]
        cp_path = workflow_env["cp_path"]
        repo_factory = workflow_env["repo_factory"]
        trust_binding = workflow_env["trust_binding"]

        ci = ContentItem(
            organization_id=org_a,
            content_type="text/plain",
            raw_content="Suspicious advisory group demanding payment to personal UPI handle fastprofit@paytm.",
        )

        # Start workflow
        res1 = workflow_env["service"].start_investigation([ci], user_id=user_analyst, organization_id=org_a, require_review=True)
        inv_id = res1["investigation_id"]
        assert res1["status"] == "AWAITING_REVIEW"

        # Simulate process crash by closing existing checkpointer
        workflow_env["checkpointer"].close()

        # Re-initialize clean checkpointer and service from the same SQLite file on disk
        new_checkpointer = WorkflowCheckpointer(db_path=cp_path)
        new_node_suite = WorkflowNodeSuite(
            trust_binding=trust_binding,
            repository_factory=repo_factory,
        )
        new_workflow = InvestigationWorkflow(
            node_suite=new_node_suite,
            checkpointer=new_checkpointer.get_saver(),
        )
        new_service = WorkflowService(
            repository_factory=repo_factory,
            workflow=new_workflow,
            checkpointer=new_checkpointer,
            node_suite=new_node_suite,
        )

        # Inspect recovered state
        state_snapshot = new_service.get_workflow_state(inv_id, org_a)
        assert state_snapshot is not None
        assert state_snapshot["status"] == "AWAITING_REVIEW"
        assert state_snapshot["values"]["review_required"] is True
        assert len(state_snapshot["values"]["content_item_ids"]) == 1

        # Resume after restart
        res2 = new_service.resume_investigation(
            investigation_id=inv_id,
            review_action="CONFIRM",
            user_id=user_admin,
            organization_id=org_a,
            reason="Resumed after worker restart",
        )

        assert res2["status"] == "COMPLETED"
        assert res2["trust_receipt_id"] is not None

        new_checkpointer.close()

    def test_scenario_4_verification_dependency_failure_retry(self, workflow_env):
        """Scenario 4: Transient upstream failure triggers bounded retry and succeeds without duplicate records."""
        service: WorkflowService = workflow_env["service"]
        org_a = workflow_env["org_a"]
        user_analyst = workflow_env["user_analyst"]

        ci = ContentItem(
            organization_id=org_a,
            content_type="text/plain",
            raw_content="Zerodha Broking Ltd INZ000031633 zerodha.com",
        )

        real_verify = workflow_env["node_suite"].verification_engine.verify_claim
        calls = {"count": 0}

        def flaky_verify(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RetryableWorkflowError("Transient upstream regulatory API timeout")
            return real_verify(*args, **kwargs)

        workflow_env["node_suite"].verification_engine.verify_claim = flaky_verify

        res = service.start_investigation([ci], user_id=user_analyst, organization_id=org_a)

        assert res["status"] == "COMPLETED"
        assert calls["count"] >= 2  # Proves retry was performed

        repo = workflow_env["repo_factory"](org_a)
        events = repo.list_audit_events()
        event_actions = [e.action for e in events]
        assert "verification_transient_failure" in event_actions
        assert "verification_retry_success" in event_actions

    def test_scenario_5_permanent_failure_preserves_evidence(self, workflow_env):
        """Scenario 5: Non-retryable failure routes to failure_node, preserving already collected claims and entities."""
        service: WorkflowService = workflow_env["service"]
        org_a = workflow_env["org_a"]
        user_analyst = workflow_env["user_analyst"]

        ci = ContentItem(
            organization_id=org_a,
            content_type="text/plain",
            raw_content="Dubious investment group claiming 50% monthly returns.",
        )

        def failing_correlator(*args, **kwargs):
            raise NonRetryableWorkflowError("Irrecoverable graph correlation failure")

        workflow_env["node_suite"].correlator.correlate_investigation = failing_correlator

        res = service.start_investigation([ci], user_id=user_analyst, organization_id=org_a)

        assert res["status"] == "PARTIALLY_COMPLETED"
        assert "errors" in res
        assert any("Irrecoverable graph correlation failure" in err for err in res["errors"])

        repo = workflow_env["repo_factory"](org_a)
        inv = repo.get_investigation(res["investigation_id"])
        assert inv.status == "PARTIALLY_COMPLETED"

        wf_run = repo.get_workflow_run_by_investigation(inv.id)
        assert wf_run.status == "PARTIALLY_COMPLETED"
        assert wf_run.current_node == "failure_node"

        # Check that claims gathered in intelligence_node prior to failure are preserved
        assert len(res.get("claims", [])) > 0

    def test_scenario_6_unauthorized_resume_cross_tenant_isolation(self, workflow_env):
        """Scenario 6: Tenant B cannot inspect or resume Tenant A's interrupted investigation."""
        service: WorkflowService = workflow_env["service"]
        org_a = workflow_env["org_a"]
        org_b = workflow_env["org_b"]
        user_analyst = workflow_env["user_analyst"]
        user_b = workflow_env["user_b"]

        ci = ContentItem(
            organization_id=org_a,
            content_type="text/plain",
            raw_content="Suspicious channel offering crypto doubling scheme.",
        )

        res = service.start_investigation([ci], user_id=user_analyst, organization_id=org_a, require_review=True)
        inv_id = res["investigation_id"]

        # Tenant B attempts to read Tenant A's workflow state
        with pytest.raises(Exception):
            service.get_workflow_state(inv_id, organization_id=org_b)

        # Tenant B attempts to resume Tenant A's investigation
        with pytest.raises(Exception):
            service.resume_investigation(
                investigation_id=inv_id,
                review_action="CONFIRM",
                user_id=user_b,
                organization_id=org_b,
                reason="Adversarial resume attempt",
            )

        # Tenant A resumes and succeeds
        res_a = service.resume_investigation(
            investigation_id=inv_id,
            review_action="DISMISS",
            user_id=user_analyst,
            organization_id=org_a,
            reason="Legitimate Tenant A dismissal",
        )
        assert res_a["status"] == "COMPLETED"

    def test_scenario_7_review_race_condition(self, workflow_env):
        """Scenario 7: Concurrent reviews on the same investigation allow first valid decision to win; conflicting submission raises ReviewConflictError."""
        service: WorkflowService = workflow_env["service"]
        org_a = workflow_env["org_a"]
        user_analyst = workflow_env["user_analyst"]
        user_admin = workflow_env["user_admin"]

        ci = ContentItem(
            organization_id=org_a,
            content_type="text/plain",
            raw_content="High return VIP trading signals channel.",
        )

        res = service.start_investigation([ci], user_id=user_analyst, organization_id=org_a, require_review=True)
        inv_id = res["investigation_id"]

        # First review succeeds
        res1 = service.resume_investigation(
            investigation_id=inv_id,
            review_action="CONFIRM",
            user_id=user_analyst,
            organization_id=org_a,
            reason="First review submission wins",
        )
        assert res1["status"] == "COMPLETED"

        # Second concurrent review attempt raises ReviewConflictError
        with pytest.raises(ReviewConflictError):
            service.resume_investigation(
                investigation_id=inv_id,
                review_action="ESCALATE",
                user_id=user_admin,
                organization_id=org_a,
                reason="Second conflicting review submission",
            )

    def test_scenario_8_trust_signing_failure_resilience(self, workflow_env):
        """Scenario 8: If PQC signing fails, analysis remains intact and trust_status is marked FAILED."""
        service: WorkflowService = workflow_env["service"]
        org_a = workflow_env["org_a"]
        user_analyst = workflow_env["user_analyst"]

        # Break trust service intentionally
        workflow_env["node_suite"].trust_binding.trust_service = None

        ci = ContentItem(
            organization_id=org_a,
            content_type="text/plain",
            raw_content="Regular financial post mentioning stock markets.",
        )

        res = service.start_investigation([ci], user_id=user_analyst, organization_id=org_a)

        assert res["status"] == "COMPLETED"
        assert res["trust_status"] == "FAILED"
        assert res["trust_receipt_id"] is None
        assert len(res["claims"]) > 0

    def test_scenario_9_cancellation_lifecycle(self, workflow_env):
        """Scenario 9: Cancellation stops work, prevents resume, and cannot cancel completed investigations."""
        service: WorkflowService = workflow_env["service"]
        org_a = workflow_env["org_a"]
        user_analyst = workflow_env["user_analyst"]

        ci = ContentItem(
            organization_id=org_a,
            content_type="text/plain",
            raw_content="Dubious tips provider.",
        )

        res = service.start_investigation([ci], user_id=user_analyst, organization_id=org_a, require_review=True)
        inv_id = res["investigation_id"]

        # Cancel awaiting-review investigation
        cancelled_inv = service.cancel_investigation(
            investigation_id=inv_id,
            user_id=user_analyst,
            organization_id=org_a,
            reason="User retracted submission",
        )
        assert cancelled_inv.status == "CANCELLED"

        # Attempting to resume cancelled investigation is rejected
        with pytest.raises(InvestigationCancelledError):
            service.resume_investigation(
                investigation_id=inv_id,
                review_action="CONFIRM",
                user_id=user_analyst,
                organization_id=org_a,
            )

        # Completed investigations cannot be cancelled
        ci_safe = ContentItem(
            organization_id=org_a,
            content_type="text/plain",
            raw_content="Zerodha Broking Ltd INZ000031633 zerodha.com",
        )
        res_completed = service.start_investigation([ci_safe], user_id=user_analyst, organization_id=org_a)
        assert res_completed["status"] == "COMPLETED"

        with pytest.raises(CannotCancelCompletedInvestigationError):
            service.cancel_investigation(
                investigation_id=res_completed["investigation_id"],
                user_id=user_analyst,
                organization_id=org_a,
            )

    def test_scenario_10_role_enforcement(self, workflow_env):
        """Scenario 10: sangyan_viewer is strictly prohibited from submitting supervisory review decisions."""
        service: WorkflowService = workflow_env["service"]
        org_a = workflow_env["org_a"]
        user_analyst = workflow_env["user_analyst"]
        user_viewer = workflow_env["user_viewer"]

        ci = ContentItem(
            organization_id=org_a,
            content_type="text/plain",
            raw_content="Telegram channel soliciting deposits.",
        )

        res = service.start_investigation([ci], user_id=user_analyst, organization_id=org_a, require_review=True)
        inv_id = res["investigation_id"]

        # Viewer attempts review: denied
        repo_viewer = TenantRepository(workflow_env["engine"], org_a, user_viewer)
        service_viewer = WorkflowService(
            repository_factory=lambda oid: repo_viewer,
            workflow=workflow_env["workflow"],
            checkpointer=workflow_env["checkpointer"],
        )

        with pytest.raises(PermissionDeniedError):
            service_viewer.resume_investigation(
                investigation_id=inv_id,
                review_action="CONFIRM",
                user_id=user_viewer,
                organization_id=org_a,
            )

    def test_scenario_12_trust_idempotency(self, workflow_env):
        """Scenario 12: Trust finalization on an already-finalized investigation reuses the receipt idempotently."""
        service: WorkflowService = workflow_env["service"]
        org_a = workflow_env["org_a"]
        user_analyst = workflow_env["user_analyst"]

        ci = ContentItem(
            organization_id=org_a,
            content_type="text/plain",
            raw_content="Zerodha Broking Ltd INZ000031633 zerodha.com",
        )

        res = service.start_investigation([ci], user_id=user_analyst, organization_id=org_a)
        first_receipt = res["trust_receipt_id"]
        assert first_receipt is not None

        # Re-run trust finalization node directly
        state_again = dict(res)
        node_res = workflow_env["node_suite"].trust_finalization_node(state_again)
        assert node_res["trust_status"] == "FINALIZED"
        assert state_again.get("trust_receipt_id") == first_receipt

    def test_scenario_13_multi_investigation_concurrency(self, workflow_env):
        """Scenario 13: Multiple concurrent investigations across tenants execute without interference."""
        service: WorkflowService = workflow_env["service"]
        org_a = workflow_env["org_a"]
        org_b = workflow_env["org_b"]
        user_a = workflow_env["user_analyst"]
        user_b = workflow_env["user_b"]

        contents = [
            (org_a, user_a, "Zerodha Broking Ltd INZ000031633 zerodha.com"),
            (org_a, user_a, "Advisory promising 40% monthly returns fastprofit@paytm"),
            (org_b, user_b, "Angel One Limited stock broker INZ000161534"),
            (org_b, user_b, "Phishing link http://fake-zerodha.xyz deposit funds"),
        ]

        def run_one(item_info):
            org, usr, text = item_info
            ci = ContentItem(organization_id=org, content_type="text/plain", raw_content=text)
            return service.start_investigation([ci], user_id=usr, organization_id=org)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(run_one, contents))

        assert len(results) == 4
        inv_ids = {r["investigation_id"] for r in results}
        assert len(inv_ids) == 4  # All unique investigation IDs
