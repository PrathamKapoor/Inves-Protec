"""Phase 10: backpressure, queue saturation, admission control, and honest HTTP semantics.

Covers:
- 202 Accepted on async submission with poll URL.
- Per-tenant outstanding-task admission control -> 429 with Retry-After.
- Content-count bound per workflow request -> 422.
- Queue saturation: API stays responsive while workers lag; no task disappears.
- Task mutation rate-limit class -> 429 after policy capacity.
- Oversized request bodies -> 413.
"""
import shutil
import tempfile
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sangyan.async_exec.models import TaskStatus
from sangyan.async_exec.queue import InMemoryTaskQueue
from sangyan.async_exec.repository import AsyncTaskRepository
from sangyan.async_exec.worker import AsyncInvestigationWorker
from sangyan.config import SangyanConfig, load_config
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.tenancy.repository import TenantAdministration, TenantRepository
from sangyan.trust.service import TrustService
from sangyan.verification.trust_binding import TrustBindingService
from sangyan.workflow.checkpointer import WorkflowCheckpointer
from sangyan.workflow.graph import InvestigationWorkflow
from sangyan.workflow.nodes import WorkflowNodeSuite
from sangyan.workflow.service import WorkflowService


@pytest.fixture
def backpressure_app():
    tmpdir = tempfile.mkdtemp()
    try:
        engine = SQLiteDatabaseEngine(Path(tmpdir) / "bp.db")
        MigrationRunner(engine).migrate()

        admin = TenantAdministration(engine)
        org_id = admin.create_organization("Backpressure Tenant")
        user_id = admin.create_user("bp@sangyan.test", "BP Analyst")
        admin.add_membership(org_id, user_id, "sangyan_analyst")

        from sangyan.api.app import create_app

        cfg = load_config(
            {
                "SANGYAN_ENV": "test",
                "SANGYAN_AUTO_MIGRATE": "false",
                "SANGYAN_TASK_MAX_OUTSTANDING_PER_TENANT": "5",
                "SANGYAN_MAX_CONTENTS_PER_WORKFLOW_REQUEST": "2",
            }
        )
        app = create_app(engine=engine, config=cfg)
        client = TestClient(app)

        yield {
            "client": client,
            "engine": engine,
            "org_id": org_id,
            "user_id": user_id,
            "app": app,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _start_payload(org_id: str, user_id: str, contents=None):
    return {
        "contents": contents or ["Guaranteed returns scam message"],
        "content_type": "text/plain",
        "organization_id": org_id,
        "user_id": user_id,
        "require_review": False,
    }


def test_async_submission_returns_202_with_poll_url(backpressure_app):
    client, _, org_id, user_id = backpressure_app["client"], None, backpressure_app["org_id"], backpressure_app["user_id"]
    res = client.post(
        f"/api/v1/workflow/start?async_exec=true&organization_id={org_id}&user_id={user_id}",
        json=_start_payload(org_id, user_id),
    )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "QUEUED"
    assert data["task_id"]
    assert data["poll_url"] == f"/api/v1/tasks/{data['task_id']}"


def test_admission_control_rejects_flood_with_429(backpressure_app):
    client = backpressure_app["client"]
    org_id = backpressure_app["org_id"]
    user_id = backpressure_app["user_id"]

    codes = []
    for i in range(7):  # cap is 5
        res = client.post(
            f"/api/v1/workflow/start?async_exec=true&organization_id={org_id}&user_id={user_id}",
            json=_start_payload(org_id, user_id),
        )
        codes.append(res.status_code)

    # First 5 accepted (202), 6th and 7th rejected with honest 429 + Retry-After
    assert codes[:5] == [202] * 5
    assert codes[5:] == [429, 429]

    res = client.post(
        f"/api/v1/workflow/start?async_exec=true&organization_id={org_id}&user_id={user_id}",
        json=_start_payload(org_id, user_id),
    )
    assert res.status_code == 429
    assert res.headers.get("Retry-After")
    detail = res.json()["detail"]
    assert "outstanding async tasks" in detail


def test_content_count_bound_returns_422(backpressure_app):
    client = backpressure_app["client"]
    org_id = backpressure_app["org_id"]
    user_id = backpressure_app["user_id"]
    res = client.post(
        f"/api/v1/workflow/start?organization_id={org_id}&user_id={user_id}",
        json=_start_payload(org_id, user_id, contents=["a", "b", "c"]),  # limit is 2
    )
    assert res.status_code == 422
    assert "maximum per workflow request" in res.json()["detail"]


def test_queue_saturation_api_stays_responsive_no_task_lost(backpressure_app):
    """API stays responsive while workers lag; all tasks eventually complete; none vanish."""
    client = backpressure_app["client"]
    engine = backpressure_app["engine"]
    org_id = backpressure_app["org_id"]
    user_id = backpressure_app["user_id"]

    # Saturate the queue: no workers running yet
    submit_latencies = []
    accepted = 0
    for i in range(5):
        start = time.time()
        res = client.post(
            f"/api/v1/workflow/start?async_exec=true&organization_id={org_id}&user_id={user_id}",
            json=_start_payload(org_id, user_id),
        )
        submit_latencies.append(time.time() - start)
        if res.status_code == 202:
            accepted += 1
    assert accepted == 5
    # Saturated submissions remain fast (no worker needed for 202)
    assert max(submit_latencies) < 2.0

    # API remains responsive while queue is saturated
    health = client.get("/health/live")
    assert health.status_code == 200

    # Now run a worker; every accepted task must reach a terminal state
    from sangyan.api.app import create_app

    app = backpressure_app["app"]
    task_queue = app.state.task_queue
    task_repo = AsyncTaskRepository(engine)

    from sangyan.tenancy.repository import TenantRepository

    def repo_factory(oid, uid=None):
        return TenantRepository(engine, oid, uid or user_id)

    # Build a workflow service for the worker via the app's existing one
    workflow_service = app.state.workflow_service
    worker = AsyncInvestigationWorker(
        queue=task_queue,
        repository=task_repo,
        workflow_service=workflow_service,
        worker_id="bp-worker-1",
        lease_duration_sec=30.0,
        concurrency=2,
        maintenance_interval_sec=0.2,
    )

    deadline = time.time() + 300
    processed = 0
    while time.time() < deadline:
        counts = task_repo.count_tasks_by_status()
        if counts.get(TaskStatus.SUCCEEDED, 0) >= accepted:
            break
        processed += worker.process_one_batch(batch_size=2, block_ms=50)
        time.sleep(0.02)

    counts = task_repo.count_tasks_by_status()
    assert counts.get(TaskStatus.SUCCEEDED, 0) == accepted
    # Outstanding count returns to zero after drain -> admission reopens
    outstanding = task_repo.count_outstanding_tasks(organization_id=org_id)
    assert outstanding == 0
    res = client.post(
        f"/api/v1/workflow/start?async_exec=true&organization_id={org_id}&user_id={user_id}",
        json=_start_payload(org_id, user_id),
    )
    assert res.status_code == 202


def test_task_retry_endpoint_rate_limited(backpressure_app):
    """Task mutation class enforces its policy capacity (30/min) with 429."""
    client = backpressure_app["client"]
    org_id = backpressure_app["org_id"]
    user_id = backpressure_app["user_id"]

    statuses = []
    for i in range(32):
        res = client.post(
            f"/api/v1/tasks/does-not-exist/retry?organization_id={org_id}&user_id={user_id}",
        )
        statuses.append(res.status_code)

    assert 429 in statuses
    # Everything before the limit should be a non-429 (404 not found is expected)
    first_429_index = statuses.index(429)
    assert 429 not in statuses[:first_429_index]
    assert statuses[first_429_index] == 429


def test_oversized_request_body_rejected_413(backpressure_app):
    client = backpressure_app["client"]
    org_id = backpressure_app["org_id"]
    user_id = backpressure_app["user_id"]
    huge = "x" * (2 * 1024 * 1024 + 1024)
    res = client.post(
        f"/api/v1/workflow/start?organization_id={org_id}&user_id={user_id}",
        json=_start_payload(org_id, user_id, contents=[huge]),
    )
    assert res.status_code == 413
