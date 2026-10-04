"""Tests for AsyncInvestigationWorker, bounded leasing, HITL decoupling, retries, and graceful stop."""
import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sangyan.async_exec.models import AsyncTask, TaskStatus, TaskType
from sangyan.async_exec.queue import InMemoryTaskQueue
from sangyan.async_exec.repository import AsyncTaskRepository
from sangyan.async_exec.worker import AsyncInvestigationWorker
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.domain.models import ContentItem
from sangyan.tenancy.repository import TenantAdministration, TenantRepository
from sangyan.trust.service import TrustService
from sangyan.verification.trust_binding import TrustBindingService
from sangyan.workflow.checkpointer import WorkflowCheckpointer
from sangyan.workflow.graph import InvestigationWorkflow
from sangyan.workflow.nodes import WorkflowNodeSuite
from sangyan.workflow.service import WorkflowService


@pytest.fixture
def worker_env():
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = Path(tmpdir) / "sangyan_worker_test.db"
        engine = SQLiteDatabaseEngine(db_path)
        MigrationRunner(engine).migrate()

        admin_svc = TenantAdministration(engine)
        org_id = admin_svc.create_organization("SEBI Investigation Wing")
        user_id = admin_svc.create_user("analyst@sebi.gov.in", "Lead Analyst")
        admin_svc.add_membership(org_id, user_id, "sangyan_analyst")

        key_dir = Path(tmpdir) / "pqc_keys"
        trust_service = TrustService(engine, key_dir=key_dir)
        trust_binding = TrustBindingService(trust_service=trust_service)

        cp_path = Path(tmpdir) / "checkpoints.db"
        checkpointer = WorkflowCheckpointer(db_path=cp_path)

        def repo_factory(oid: str, uid: str | None = None) -> TenantRepository:
            return TenantRepository(engine, oid, uid or user_id)

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

        queue = InMemoryTaskQueue()
        task_repo = AsyncTaskRepository(engine)

        worker = AsyncInvestigationWorker(
            queue=queue,
            repository=task_repo,
            workflow_service=service,
            worker_id="test-worker-01",
            lease_duration_sec=30.0,
            heartbeat_interval_sec=5.0,
        )

        yield {
            "tmpdir": tmpdir,
            "engine": engine,
            "org_id": org_id,
            "user_id": user_id,
            "workflow_service": service,
            "queue": queue,
            "task_repo": task_repo,
            "worker": worker,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_worker_happy_path_workflow_start(worker_env):
    worker = worker_env["worker"]
    queue = worker_env["queue"]
    task_repo = worker_env["task_repo"]
    org_id = worker_env["org_id"]
    user_id = worker_env["user_id"]

    # Create task
    task = task_repo.create_task(
        task_id="task-hp-01",
        organization_id=org_id,
        user_id=user_id,
        investigation_id="inv-hp-01",
        task_type=TaskType.WORKFLOW_START,
        payload={
            "contents": ["Promising guaranteed 40% returns on WhatsApp group"],
            "require_review": False,
        },
    )
    queue.enqueue(task)

    # Process one batch
    processed = worker.process_one_batch(batch_size=1)
    assert processed == 1

    # Verify task in repository
    completed_task = task_repo.get_task("task-hp-01")
    assert completed_task.status == TaskStatus.SUCCEEDED
    assert completed_task.completed_at is not None
    assert completed_task.result is not None
    assert completed_task.result["status"] == "COMPLETED"
    assert completed_task.result["trust_receipt_id"] is not None


def test_worker_hitl_decoupling_awaiting_review(worker_env):
    worker = worker_env["worker"]
    queue = worker_env["queue"]
    task_repo = worker_env["task_repo"]
    org_id = worker_env["org_id"]
    user_id = worker_env["user_id"]

    # Create task requiring review
    task = task_repo.create_task(
        task_id="task-hitl-01",
        organization_id=org_id,
        user_id=user_id,
        investigation_id="inv-hitl-01",
        task_type=TaskType.WORKFLOW_START,
        payload={
            "contents": ["Urgent stock recommendation alert with dubious SEBI registration"],
            "require_review": True,
        },
    )
    queue.enqueue(task)

    # Process one batch
    processed = worker.process_one_batch(batch_size=1)
    assert processed == 1

    # Worker must complete stage and mark task SUCCEEDED with AWAITING_REVIEW
    completed_task = task_repo.get_task("task-hitl-01")
    assert completed_task.status == TaskStatus.SUCCEEDED
    assert completed_task.result["status"] == "AWAITING_REVIEW"
    assert completed_task.result["investigation_id"] is not None

    # Capacity freed: worker is not leasing or holding capacity
    assert completed_task.lease_expires_at is None or completed_task.is_terminal()


def test_worker_resume_workflow_completion(worker_env):
    worker = worker_env["worker"]
    queue = worker_env["queue"]
    task_repo = worker_env["task_repo"]
    org_id = worker_env["org_id"]
    user_id = worker_env["user_id"]

    # 1. Start investigation awaiting review
    task_start = task_repo.create_task(
        task_id="task-res-01",
        organization_id=org_id,
        user_id=user_id,
        investigation_id="inv-res-01",
        task_type=TaskType.WORKFLOW_START,
        payload={
            "contents": ["Dubious crypto investment bot promising daily returns"],
            "require_review": True,
        },
    )
    queue.enqueue(task_start)
    worker.process_one_batch(batch_size=1)

    start_res = task_repo.get_task("task-res-01")
    assert start_res.result["status"] == "AWAITING_REVIEW"
    actual_inv_id = start_res.result["investigation_id"]

    # 2. Enqueue WORKFLOW_RESUME task
    task_resume = task_repo.create_task(
        task_id="task-res-02",
        organization_id=org_id,
        user_id=user_id,
        investigation_id=actual_inv_id,
        task_type=TaskType.WORKFLOW_RESUME,
        payload={
            "investigation_id": actual_inv_id,
            "review_action": "CONFIRM",
            "reason": "Supervisor reviewed and confirmed fraudulent intent",
        },
    )
    queue.enqueue(task_resume)

    # Process resume batch
    worker.process_one_batch(batch_size=1)

    res_task = task_repo.get_task("task-res-02")
    assert res_task.status == TaskStatus.SUCCEEDED
    assert res_task.result["status"] == "COMPLETED"
    assert res_task.result["trust_receipt_id"] is not None


def test_worker_cancel_workflow(worker_env):
    worker = worker_env["worker"]
    queue = worker_env["queue"]
    task_repo = worker_env["task_repo"]
    org_id = worker_env["org_id"]
    user_id = worker_env["user_id"]

    # 1. Start investigation
    task_start = task_repo.create_task(
        task_id="task-cnc-01",
        organization_id=org_id,
        user_id=user_id,
        investigation_id="inv-cnc-01",
        task_type=TaskType.WORKFLOW_START,
        payload={
            "contents": ["Content to be cancelled before review"],
            "require_review": True,
        },
    )
    queue.enqueue(task_start)
    worker.process_one_batch(batch_size=1)

    start_res = task_repo.get_task("task-cnc-01")
    actual_inv_id = start_res.result["investigation_id"]

    # 2. Cancel
    task_cancel = task_repo.create_task(
        task_id="task-cnc-02",
        organization_id=org_id,
        user_id=user_id,
        investigation_id=actual_inv_id,
        task_type=TaskType.WORKFLOW_CANCEL,
        payload={
            "investigation_id": actual_inv_id,
            "reason": "Duplicate claim filed in another branch",
        },
    )
    queue.enqueue(task_cancel)
    worker.process_one_batch(batch_size=1)

    cnc_task = task_repo.get_task("task-cnc-02")
    assert cnc_task.status == TaskStatus.SUCCEEDED
    assert cnc_task.result["status"] == "CANCELLED"


def test_worker_transient_failure_and_retry(worker_env):
    worker = worker_env["worker"]
    queue = worker_env["queue"]
    task_repo = worker_env["task_repo"]
    org_id = worker_env["org_id"]
    user_id = worker_env["user_id"]

    task = task_repo.create_task(
        task_id="task-err-01",
        organization_id=org_id,
        user_id=user_id,
        investigation_id="inv-err-01",
        task_type=TaskType.WORKFLOW_START,
        payload={"contents": ["Content causing transient network drop"]},
    )
    queue.enqueue(task)

    # Patch start_investigation to raise transient error
    with patch.object(
        worker_env["workflow_service"],
        "start_investigation",
        side_effect=ConnectionError("Simulated upstream registry timeout"),
    ):
        worker.process_one_batch(batch_size=1)

    # Task should have transitioned to RETRY_WAIT and re-enqueued
    updated = task_repo.get_task("task-err-01")
    assert updated.retry_count == 1
    assert "Simulated upstream registry timeout" in (updated.error_message or "")


def test_worker_dead_letter_on_exhausted_retries(worker_env):
    worker = worker_env["worker"]
    queue = worker_env["queue"]
    task_repo = worker_env["task_repo"]
    org_id = worker_env["org_id"]
    user_id = worker_env["user_id"]

    task = task_repo.create_task(
        task_id="task-dl-01",
        organization_id=org_id,
        user_id=user_id,
        investigation_id="inv-dl-01",
        task_type=TaskType.WORKFLOW_START,
        payload={"contents": ["Permanent failure content"]},
        max_retries=1,
    )
    # Simulate already at retry 1
    task_repo._db.execute(
        "UPDATE sangyan_async_tasks SET retry_count=1 WHERE task_id='task-dl-01'"
    )
    task_stale = task_repo.get_task("task-dl-01")
    queue.enqueue(task_stale)

    with patch.object(
        worker_env["workflow_service"],
        "start_investigation",
        side_effect=ValueError("Fatal parsing exception"),
    ):
        worker.process_one_batch(batch_size=1)

    dl_task = task_repo.get_task("task-dl-01")
    assert dl_task.status == TaskStatus.DEAD_LETTERED
    assert dl_task.is_terminal()
    assert "Fatal parsing exception" in dl_task.error_message


def test_worker_graceful_stop(worker_env):
    worker = worker_env["worker"]
    assert not worker.is_stopped()
    worker.stop()
    assert worker.is_stopped()
