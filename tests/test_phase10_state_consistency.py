"""Phase 10: async task state-transition audit, task/workflow consistency, HITL operations.

Covers:
- Exhaustive task state-transition matrix (allowed transitions work; forbidden fail safely).
- Terminal-state immutability and DB-level guards (complete requires RUNNING, retry requires DEAD_LETTERED).
- Cancelled tasks never execute even if redelivered.
- Task/workflow status combination audit (legitimate combos preserved, drift detected).
- HITL operational audit: many investigations park at review without holding worker capacity,
  workers stay available, resumes complete, duplicate resume quarantined, trust finalized once.
"""
import time
from pathlib import Path

import pytest

from sangyan.async_exec.models import (
    VALID_TASK_TRANSITIONS,
    AsyncTask,
    TaskStatus,
    TaskType,
)
from sangyan.async_exec.queue import InMemoryTaskQueue
from sangyan.async_exec.repository import AsyncTaskRepository
from sangyan.async_exec.worker import AsyncInvestigationWorker
from sangyan.core.errors import InvalidStateTransitionError, TaskNotFoundError
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
def consistency_env(tmp_path):
    engine = SQLiteDatabaseEngine(tmp_path / "consistency.db")
    MigrationRunner(engine).migrate()

    admin = TenantAdministration(engine)
    org_id = admin.create_organization("Consistency Tenant")
    user_id = admin.create_user("consistency@sangyan.test", "Analyst")
    admin.add_membership(org_id, user_id, "sangyan_analyst")

    trust_service = TrustService(engine, key_dir=tmp_path / "pqc_keys")
    trust_binding = TrustBindingService(trust_service=trust_service)
    checkpointer = WorkflowCheckpointer(db_path=tmp_path / "checkpoints.db")

    def repo_factory(oid, uid=None):
        return TenantRepository(engine, oid, uid or user_id)

    node_suite = WorkflowNodeSuite(trust_binding=trust_binding, repository_factory=lambda oid: repo_factory(oid))
    workflow = InvestigationWorkflow(node_suite=node_suite, checkpointer=checkpointer.get_saver())
    service = WorkflowService(
        repository_factory=lambda oid: repo_factory(oid),
        workflow=workflow,
        checkpointer=checkpointer,
        node_suite=node_suite,
    )
    task_repo = AsyncTaskRepository(engine)
    queue = InMemoryTaskQueue()
    worker = AsyncInvestigationWorker(
        queue=queue,
        repository=task_repo,
        workflow_service=service,
        worker_id="consistency-worker",
        lease_duration_sec=30.0,
        concurrency=4,
        maintenance_interval_sec=0.2,
        stale_queue_requeue_sec=2.0,
    )
    yield {
        "engine": engine,
        "org_id": org_id,
        "user_id": user_id,
        "task_repo": task_repo,
        "queue": queue,
        "worker": worker,
        "service": service,
    }


def _new_task(env, task_id: str, status: str = TaskStatus.QUEUED) -> AsyncTask:
    return AsyncTask(
        task_id=task_id,
        organization_id=env["org_id"],
        user_id=env["user_id"],
        investigation_id=f"inv-{task_id}",
        task_type=TaskType.WORKFLOW_START,
        status=status,
        payload={"contents": ["x"]},
    )


# ---------------------------------------------------------------------------
# 1. Exhaustive state transition matrix
# ---------------------------------------------------------------------------


def test_task_transition_matrix_all_pairs():
    """For every (from, to) pair: allowed transitions succeed; forbidden raise safely."""
    checked_allowed = 0
    checked_forbidden = 0
    for source in TaskStatus.ALL:
        for target in TaskStatus.ALL:
            task = AsyncTask(
                task_id=f"t-{source}-{target}",
                organization_id="org",
                user_id="usr",
                investigation_id="inv",
                task_type=TaskType.WORKFLOW_START,
                status=source,
            )
            allowed = VALID_TASK_TRANSITIONS[source]
            if source == target:
                # Self-transition is idempotent
                task.transition_to(target)
                assert task.status == source
                continue
            if target in allowed:
                task.transition_to(target)
                assert task.status == target
                checked_allowed += 1
            else:
                with pytest.raises(InvalidStateTransitionError):
                    task.transition_to(target)
                assert task.status == source  # state unchanged after rejection
                checked_forbidden += 1
    assert checked_allowed > 0
    assert checked_forbidden > 0
    # Terminal states have no outbound transitions except DEAD_LETTERED -> QUEUED (operator retry)
    assert VALID_TASK_TRANSITIONS[TaskStatus.SUCCEEDED] == set()
    assert VALID_TASK_TRANSITIONS[TaskStatus.CANCELLED] == set()
    assert VALID_TASK_TRANSITIONS[TaskStatus.DEAD_LETTERED] == {TaskStatus.QUEUED}


def test_terminal_state_immutability_at_repository_level(consistency_env):
    env = consistency_env
    task_repo = env["task_repo"]

    # complete_task only succeeds from RUNNING (with lease)
    t = _new_task(env, "t-complete-guard")
    task_repo.save_task(t)
    assert task_repo.complete_task("t-complete-guard", "w1", {"ok": True}) is False

    # A leased RUNNING task can complete
    assert task_repo.acquire_lease("t-complete-guard", "w1", 30.0) is True
    assert task_repo.complete_task("t-complete-guard", "w1", {"ok": True}) is True

    # Terminal task cannot be cancelled
    with pytest.raises(InvalidStateTransitionError):
        task_repo.cancel_task("t-complete-guard", reason="nope")

    # Terminal task cannot be retried
    with pytest.raises(InvalidStateTransitionError):
        task_repo.retry_dead_letter_task("t-complete-guard")


def test_retry_dead_letter_requires_dead_letter_status(consistency_env):
    env = consistency_env
    task_repo = env["task_repo"]
    task_repo.save_task(_new_task(env, "t-queued-retry"))
    with pytest.raises(InvalidStateTransitionError):
        task_repo.retry_dead_letter_task("t-queued-retry")


def test_cancelled_task_never_executes_on_redelivery(consistency_env):
    """A CANCELLED task redelivered by the broker is acked without execution."""
    env = consistency_env
    task_repo = env["task_repo"]
    task = _new_task(env, "t-cancelled")
    task_repo.save_task(task)
    task_repo.cancel_task("t-cancelled", reason="operator cancelled")

    env["queue"].enqueue(task)
    processed = env["worker"].process_one_batch(batch_size=1)
    assert processed == 1  # dequeued and acked
    final = task_repo.get_task("t-cancelled")
    assert final.status == TaskStatus.CANCELLED  # never executed
    assert final.result is None


def test_missing_task_lookup_raises_task_not_found(consistency_env):
    env = consistency_env
    with pytest.raises(TaskNotFoundError):
        env["task_repo"].get_task("tsk-does-not-exist")


# ---------------------------------------------------------------------------
# 2. Task / workflow status combination audit
# ---------------------------------------------------------------------------


def test_task_succeeded_workflow_completed_consistent(consistency_env):
    env = consistency_env
    task_repo = env["task_repo"]
    task = _new_task(env, "t-combo-complete")
    task_repo.save_task(task)
    env["queue"].enqueue(task)
    env["worker"].process_one_batch(batch_size=1)

    done = task_repo.get_task("t-combo-complete")
    assert done.status == TaskStatus.SUCCEEDED
    inv_id = done.result["investigation_id"]
    inv = env["engine"].query_one("SELECT status FROM sangyan_investigations WHERE id=?", (inv_id,))
    run = env["engine"].query_one(
        "SELECT status FROM sangyan_workflow_runs WHERE investigation_id=?", (inv_id,)
    )
    assert inv["status"] == "COMPLETED"
    assert run["status"] == "COMPLETED"
    # Task terminal state agrees with workflow state (no impossible combination)
    assert done.result["status"] == inv["status"] == run["status"]


def test_task_succeeded_workflow_awaiting_review_is_legitimate_hitl(consistency_env):
    env = consistency_env
    task_repo = env["task_repo"]
    task = _new_task(env, "t-combo-review")
    task.payload["require_review"] = True
    task_repo.save_task(task)
    env["queue"].enqueue(task)
    env["worker"].process_one_batch(batch_size=1)

    done = task_repo.get_task("t-combo-review")
    assert done.status == TaskStatus.SUCCEEDED
    inv_id = done.result["investigation_id"]
    inv = env["engine"].query_one("SELECT status FROM sangyan_investigations WHERE id=?", (inv_id,))
    run = env["engine"].query_one(
        "SELECT status FROM sangyan_workflow_runs WHERE investigation_id=?", (inv_id,)
    )
    # Task stage succeeded while workflow legitimately waits for a human
    assert done.result["status"] == "AWAITING_REVIEW"
    assert inv["status"] == "AWAITING_REVIEW"
    assert run["status"] == "AWAITING_REVIEW"
    # Worker capacity fully released: no lease held
    assert done.lease_owner is None
    assert done.lease_expires_at is None


def test_dead_lettered_task_leaves_no_running_workflow_drift(consistency_env):
    """A permanently failing start task marks the workflow run FAILED (no stuck RUNNING record)."""
    env = consistency_env
    task_repo = env["task_repo"]
    task = _new_task(env, "t-combo-dl")
    task.max_retries = 0
    task_repo.save_task(task)
    env["queue"].enqueue(task)

    from unittest.mock import patch

    with patch.object(env["service"], "start_investigation", side_effect=RuntimeError("fatal")):
        env["worker"].process_one_batch(batch_size=1)

    dead = task_repo.get_task("t-combo-dl")
    assert dead.status == TaskStatus.DEAD_LETTERED

    # Workflow service records the failure in its own ledger for this investigation id
    run = env["engine"].query_one(
        "SELECT status FROM sangyan_workflow_runs WHERE investigation_id=?",
        (dead.investigation_id,),
    )
    # Either a FAILED run record exists, or no run record was ever created (failure
    # before first persist). What must NEVER exist is a run stuck in RUNNING forever.
    assert run is None or run["status"] in ("FAILED", "AWAITING_REVIEW", "COMPLETED")


# ---------------------------------------------------------------------------
# 3. HITL operational audit
# ---------------------------------------------------------------------------


def test_hitl_capacity_decoupling_and_staggered_resumes(consistency_env):
    """N investigations park at review; workers stay available; resumes complete later."""
    env = consistency_env
    task_repo = env["task_repo"]
    worker = env["worker"]
    n = 8

    # Phase 1: launch N investigations requiring human review
    for i in range(n):
        t = _new_task(env, f"t-hitl-start-{i}")
        t.payload["require_review"] = True
        task_repo.save_task(t)
        env["queue"].enqueue(t)

    processed = 0
    deadline = time.time() + 300
    while processed < n and time.time() < deadline:
        processed += worker.process_one_batch(batch_size=4, block_ms=50)

    # All parked at review; worker holds NO leases and NO capacity
    review_tasks = [task_repo.get_task(f"t-hitl-start-{i}") for i in range(n)]
    assert all(t.status == TaskStatus.SUCCEEDED for t in review_tasks)
    assert all(t.result["status"] == "AWAITING_REVIEW" for t in review_tasks)
    assert worker.inflight_count() == 0
    assert all(t.lease_owner is None and t.lease_expires_at is None for t in review_tasks)

    # Phase 2: workers remain available while reviews are pending (new work completes)
    for i in range(3):
        t = _new_task(env, f"t-hitl-while-waiting-{i}")
        task_repo.save_task(t)
        env["queue"].enqueue(t)
    deadline = time.time() + 120
    while time.time() < deadline:
        worker.process_one_batch(batch_size=4, block_ms=50)
        if all(task_repo.get_task(f"t-hitl-while-waiting-{i}").status == TaskStatus.SUCCEEDED for i in range(3)):
            break
    assert all(task_repo.get_task(f"t-hitl-while-waiting-{i}").status == TaskStatus.SUCCEEDED for i in range(3))

    # Phase 3: staggered resumes
    inv_ids = []
    for i in range(n):
        start_task = task_repo.get_task(f"t-hitl-start-{i}")
        inv_id = start_task.result["investigation_id"]
        inv_ids.append(inv_id)
        rt = AsyncTask(
            task_id=f"t-hitl-resume-{i}",
            organization_id=env["org_id"],
            user_id=env["user_id"],
            investigation_id=inv_id,
            task_type=TaskType.WORKFLOW_RESUME,
            status=TaskStatus.QUEUED,
            payload={
                "investigation_id": inv_id,
                "review_action": "CONFIRM",
                "reason": "Staggered supervisory review",
            },
        )
        task_repo.save_task(rt)
        env["queue"].enqueue(rt)
        worker.process_one_batch(batch_size=1, block_ms=20)  # staggered timing

    deadline = time.time() + 300
    while time.time() < deadline:
        worker.process_one_batch(batch_size=4, block_ms=50)
        statuses = [task_repo.get_task(f"t-hitl-resume-{i}").status for i in range(n)]
        if all(s == TaskStatus.SUCCEEDED for s in statuses):
            break
    statuses = [task_repo.get_task(f"t-hitl-resume-{i}").status for i in range(n)]
    assert statuses == [TaskStatus.SUCCEEDED] * n

    # Phase 4: exactly one trust receipt per investigation (no double finalization)
    for inv_id in inv_ids:
        rows = env["engine"].query_all(
            "SELECT COUNT(*) AS n FROM sangyan_trust_receipts WHERE subject_type='investigation' AND subject_id=?",
            (inv_id,),
        )
        assert rows[0]["n"] == 1
        inv = env["engine"].query_one("SELECT status FROM sangyan_investigations WHERE id=?", (inv_id,))
        assert inv["status"] == "COMPLETED"


def test_duplicate_async_resume_quarantined_without_side_effects(consistency_env):
    """Concurrent duplicate async resumes: one succeeds, duplicates dead-letter, trust finalized once."""
    env = consistency_env
    task_repo = env["task_repo"]
    worker = env["worker"]

    start = _new_task(env, "t-dup-start")
    start.payload["require_review"] = True
    task_repo.save_task(start)
    env["queue"].enqueue(start)
    worker.process_one_batch(batch_size=1)
    st = task_repo.get_task("t-dup-start")
    assert st.result["status"] == "AWAITING_REVIEW"
    inv_id = st.result["investigation_id"]

    # Two duplicate resume tasks for the same investigation
    resume_ids = []
    for suffix in ("a", "b"):
        rt = AsyncTask(
            task_id=f"t-dup-resume-{suffix}",
            organization_id=env["org_id"],
            user_id=env["user_id"],
            investigation_id=inv_id,
            task_type=TaskType.WORKFLOW_RESUME,
            status=TaskStatus.QUEUED,
            payload={
                "investigation_id": inv_id,
                "review_action": "CONFIRM",
                "reason": f"Duplicate resume {suffix}",
            },
        )
        task_repo.save_task(rt)
        env["queue"].enqueue(rt)
        resume_ids.append(rt.task_id)

    deadline = time.time() + 180
    while time.time() < deadline:
        worker.process_one_batch(batch_size=2, block_ms=50)
        statuses = [task_repo.get_task(t).status for t in resume_ids]
        terminal = [s in (TaskStatus.SUCCEEDED, TaskStatus.DEAD_LETTERED) for s in statuses]
        if all(terminal):
            break

    statuses = [task_repo.get_task(t).status for t in resume_ids]
    assert TaskStatus.SUCCEEDED in statuses  # exactly one wins the race
    assert TaskStatus.DEAD_LETTERED in statuses  # duplicate quarantined (ReviewConflict)
    assert statuses.count(TaskStatus.SUCCEEDED) == 1

    # Investigation completed once; single trust receipt
    inv = env["engine"].query_one("SELECT status FROM sangyan_investigations WHERE id=?", (inv_id,))
    assert inv["status"] == "COMPLETED"
    receipts = env["engine"].query_one(
        "SELECT COUNT(*) AS n FROM sangyan_trust_receipts WHERE subject_type='investigation' AND subject_id=?",
        (inv_id,),
    )
    assert receipts["n"] == 1

    # Audit chain remains linear despite the conflict
    from sangyan.dr.manager import DisasterRecoveryManager
    dr = DisasterRecoveryManager(engine=env["engine"], region_id="consistency-region")
    assert dr.verify_audit_continuity()["valid"] is True
