"""Tests for asynchronous task API endpoints, multi-tenant isolation, and DR REST operations."""
import tempfile
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from sangyan.api.app import create_app
from sangyan.async_exec.models import AsyncTask, TaskStatus, TaskType
from sangyan.async_exec.queue import InMemoryTaskQueue
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.dr.manager import DisasterRecoveryManager
from sangyan.dr.models import RegionRole
from sangyan.security.jwt import create_jwt_token
from sangyan.security.models import SecurityConfig
from sangyan.tenancy.repository import TenantAdministration, TenantRepository
from sangyan.trust.service import TrustService
from sangyan.verification.engine import ClaimVerificationEngine
from sangyan.verification.trust_binding import TrustBindingService
from sangyan.workflow.checkpointer import WorkflowCheckpointer
from sangyan.workflow.graph import InvestigationWorkflow
from sangyan.workflow.nodes import WorkflowNodeSuite
from sangyan.workflow.service import WorkflowService


@pytest.fixture
def api_test_context():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_async_api.db"
        key_dir = Path(tmpdir) / "keys"
        engine = SQLiteDatabaseEngine(db_path)
        MigrationRunner(engine).migrate()

        admin = TenantAdministration(engine)
        org_a = admin.create_organization("Alpha Corporation")
        org_b = admin.create_organization("Beta Corporation")

        user_a_analyst = admin.create_user("analyst@alpha.org", "Alpha Analyst")
        user_a_admin = admin.create_user("admin@alpha.org", "Alpha Admin")
        user_b_analyst = admin.create_user("analyst@beta.org", "Beta Analyst")

        admin.add_membership(org_a, user_a_analyst, "sangyan_analyst")
        admin.add_membership(org_a, user_a_admin, "sangyan_admin")
        admin.add_membership(org_b, user_b_analyst, "sangyan_analyst")

        trust = TrustService(engine, key_dir=key_dir)
        trust_binding = TrustBindingService(trust)
        verif_engine = ClaimVerificationEngine(trust_binding=trust_binding)

        dr_mgr = DisasterRecoveryManager(
            engine=engine,
            region_id="primary-south-1",
            default_role=RegionRole.PRIMARY_ACTIVE,
            default_epoch=1,
        )
        dr_mgr.register_region("standby-dc2", role=RegionRole.STANDBY_READY, cluster_epoch=1)

        task_queue = InMemoryTaskQueue()

        def repo_factory(oid: str, uid: str | None = None) -> TenantRepository:
            actor = uid or user_a_analyst
            if oid == org_b:
                actor = user_b_analyst
            return TenantRepository(engine, oid, actor, dr_manager=dr_mgr, region_id="primary-south-1")

        node_suite = WorkflowNodeSuite(
            trust_binding=trust_binding,
            repository_factory=lambda oid: repo_factory(oid),
        )

        wf_checkpointer = WorkflowCheckpointer(in_memory=True)
        workflow = InvestigationWorkflow(
            node_suite=node_suite,
            checkpointer=wf_checkpointer.get_saver(),
        )

        wf_service = WorkflowService(
            repository_factory=lambda oid: repo_factory(oid),
            workflow=workflow,
            checkpointer=wf_checkpointer,
            node_suite=node_suite,
        )

        sec_config = SecurityConfig(
            jwt_secret="super-secret-key-that-is-at-least-32-bytes-long!",
            rate_limit_enabled=False,
        )

        app = create_app(
            engine=engine,
            trust_service=trust,
            verification_engine=verif_engine,
            workflow_service=wf_service,
            dr_manager=dr_mgr,
            task_queue=task_queue,
            security_config=sec_config,
        )
        client = TestClient(app)

        # Helper to generate JWT
        def make_token(sub: str, org: str, roles: list[str], permissions: list[str]) -> str:
            return create_jwt_token(
                payload={
                    "sub": sub,
                    "org_id": org,
                    "roles": roles,
                    "scopes": permissions,
                },
                secret_or_key=sec_config.jwt_secret,
                algorithm="HS256",
            )

        token_a_analyst = make_token(
            user_a_analyst, org_a, ["sangyan_analyst"],
            ["investigation:read", "investigation:create", "investigation:review"]
        )
        token_a_admin = make_token(
            user_a_admin, org_a, ["sangyan_admin"],
            ["investigation:read", "investigation:create", "tenant:manage"]
        )
        token_b_analyst = make_token(
            user_b_analyst, org_b, ["sangyan_analyst"],
            ["investigation:read", "investigation:create", "investigation:review"]
        )

        yield {
            "client": client,
            "engine": engine,
            "dr_mgr": dr_mgr,
            "task_queue": task_queue,
            "org_a": org_a,
            "org_b": org_b,
            "token_a_analyst": token_a_analyst,
            "token_a_admin": token_a_admin,
            "token_b_analyst": token_b_analyst,
            "user_a_analyst": user_a_analyst,
        }
        engine.close()


def test_async_workflow_start_accepted(api_test_context):
    client = api_test_context["client"]
    token = api_test_context["token_a_analyst"]
    task_queue = api_test_context["task_queue"]
    org_a = api_test_context["org_a"]
    user_a = api_test_context["user_a_analyst"]

    response = client.post(
        "/api/v1/workflow/start?async_exec=true",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "contents": ["Dubious stock recommendation in telegram channel"],
            "content_type": "text",
            "organization_id": org_a,
            "user_id": user_a,
            "require_review": True,
        },
    )
    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "QUEUED"
    assert "poll_url" in data

    # Verify task in queue
    claimed = task_queue.claim_tasks("test-worker", batch_size=1)
    assert len(claimed) == 1
    assert claimed[0][1].task_id == data["task_id"]


def test_get_task_status_and_tenant_isolation(api_test_context):
    client = api_test_context["client"]
    token_a = api_test_context["token_a_analyst"]
    token_b = api_test_context["token_b_analyst"]
    org_a = api_test_context["org_a"]
    user_a = api_test_context["user_a_analyst"]

    # Start task as Org A
    start_res = client.post(
        "/api/v1/workflow/start?async_exec=true",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "contents": ["Confidential tip for Org A"],
            "content_type": "text",
            "organization_id": org_a,
            "user_id": user_a,
        },
    )
    assert start_res.status_code == 202
    task_id = start_res.json()["task_id"]

    # Org A can inspect task
    get_res_a = client.get(
        f"/api/v1/tasks/{task_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert get_res_a.status_code == 200
    assert get_res_a.json()["task_id"] == task_id
    assert get_res_a.json()["status"] == "QUEUED"

    # Tenant Isolation: Org B cannot access Org A's task -> 404 Not Found
    get_res_b = client.get(
        f"/api/v1/tasks/{task_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert get_res_b.status_code == 404

    # Tenant Isolation: Org B attempting to tamper query param organization_id -> 403 Forbidden
    get_res_tamper = client.get(
        f"/api/v1/tasks/{task_id}?organization_id={api_test_context['org_a']}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert get_res_tamper.status_code == 403


def test_async_workflow_resume_accepted(api_test_context):
    client = api_test_context["client"]
    token = api_test_context["token_a_analyst"]
    org_a = api_test_context["org_a"]
    user_a = api_test_context["user_a_analyst"]

    response = client.post(
        "/api/v1/workflow/inv_test_123/resume?async_exec=true",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "action": "CONFIRM",
            "organization_id": org_a,
            "user_id": user_a,
            "reason": "Supervisor confirmed fraud",
        },
    )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "QUEUED"
    assert data["investigation_id"] == "inv_test_123"


def test_dead_letter_and_retry_api(api_test_context):
    client = api_test_context["client"]
    token = api_test_context["token_a_analyst"]
    engine = api_test_context["engine"]
    org_a = api_test_context["org_a"]
    user_a = api_test_context["user_a_analyst"]

    # Insert a dead-lettered task directly into outbox table
    task_id = "task-dead-001"
    now = 1700000000.0
    engine.execute(
        """
        INSERT INTO sangyan_async_tasks
        (task_id, organization_id, user_id, investigation_id, task_type, status, payload, retry_count, max_retries, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (task_id, org_a, user_a, "inv-dead-01", "WORKFLOW_START", "DEAD_LETTERED", "{}", 3, 3, now, now),
    )

    # List dead-letter tasks
    dl_res = client.get(
        "/api/v1/tasks/dead-letter",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dl_res.status_code == 200
    dl_tasks = dl_res.json()
    assert any(t["task_id"] == task_id for t in dl_tasks)

    # Retry the task
    retry_res = client.post(
        f"/api/v1/tasks/{task_id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert retry_res.status_code == 200
    retried_task = retry_res.json()
    assert retried_task["status"] == "QUEUED"
    assert retried_task["task_id"] == task_id


def test_dr_api_endpoints(api_test_context):
    client = api_test_context["client"]
    token_analyst = api_test_context["token_a_analyst"]
    token_admin = api_test_context["token_a_admin"]

    # 1. DR status
    status_res = client.get(
        "/api/v1/dr/status",
        headers={"Authorization": f"Bearer {token_analyst}"},
    )
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["active_primary"] == "primary-south-1"
    assert status_data["current_epoch"] == 1

    # 2. Non-admin attempting to promote -> 403 Forbidden
    promote_forbidden = client.post(
        "/api/v1/dr/promote?region_id=standby-dc2&reason=Unauthorized+drill",
        headers={"Authorization": f"Bearer {token_analyst}"},
    )
    assert promote_forbidden.status_code == 403

    # 3. Admin promoting standby region -> 200 OK
    promote_ok = client.post(
        "/api/v1/dr/promote?region_id=standby-dc2&reason=Admin+failover+drill",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert promote_ok.status_code == 200
    promoted_rec = promote_ok.json()
    assert promoted_rec["role"] == "PRIMARY_ACTIVE"
    assert promoted_rec["cluster_epoch"] == 2

    # 4. Admin simulating failover -> 200 OK
    sim_ok = client.post(
        "/api/v1/dr/simulate?from_region=standby-dc2&to_region=primary-south-1&reason=Return+failover",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert sim_ok.status_code == 200
    report = sim_ok.json()
    assert report["failover_status"] == "SUCCESS"
    assert report["epoch"] == 3
    assert report["audit_continuity"]["valid"] is True
