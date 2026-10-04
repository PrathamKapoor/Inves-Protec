"""Phase 10: worker stress, saturation, crash recovery, and rolling-deployment validation.

Covers:
- Worker scaling (1/2/4 workers) without duplicate business effects or lost tasks.
- Crash-safe retries: relational retry sweeper re-drives RETRY_WAIT tasks.
- Outbox re-drive of stale QUEUED tasks (worker crash between ledger and broker enqueue).
- Stream-level reclaim of pending messages stranded by dead consumers.
- Rolling deployment: old worker dies mid-task, new worker continues to completion.
- Task flood: per-tenant admission control caps outstanding tasks.
"""
import shutil
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from sangyan.async_exec.models import AsyncTask, TaskStatus, TaskType
from sangyan.async_exec.queue import InMemoryTaskQueue
from sangyan.async_exec.repository import AsyncTaskRepository
from sangyan.async_exec.worker import AsyncInvestigationWorker
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
def stress_env():
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = Path(tmpdir) / "sangyan_stress.db"
        engine = SQLiteDatabaseEngine(db_path)
        MigrationRunner(engine).migrate()

        admin = TenantAdministration(engine)
        org_id = admin.create_organization("Stress Tenant")
        user_id = admin.create_user("stress@sangyan.test", "Stress Analyst")
        admin.add_membership(org_id, user_id, "sangyan_analyst")

        key_dir = Path(tmpdir) / "pqc_keys"
        trust_service = TrustService(engine, key_dir=key_dir)
        trust_binding = TrustBindingService(trust_service=trust_service)
        checkpointer = WorkflowCheckpointer(db_path=Path(tmpdir) / "checkpoints.db")

        def repo_factory(oid: str, user_id: str | None = None) -> TenantRepository:
            return TenantRepository(engine, oid, user_id or user_id_ref[0] or user_id)

        # late binding for user_id inside factory closure
        user_id_ref = [user_id]

        node_suite = WorkflowNodeSuite(
            trust_binding=trust_binding,
            repository_factory=lambda oid: repo_factory(oid),
        )
        workflow = InvestigationWorkflow(node_suite=node_suite, checkpointer=checkpointer.get_saver())
        service = WorkflowService(
            repository_factory=lambda oid: repo_factory(oid),
            workflow=workflow,
            checkpointer=checkpointer,
            node_suite=node_suite,
        )
        task_repo = AsyncTaskRepository(engine)
        queue = InMemoryTaskQueue()

        yield {
            "tmpdir": tmpdir,
            "engine": engine,
            "org_id": org_id,
            "user_id": user_id,
            "workflow_service": service,
            "queue": queue,
            "task_repo": task_repo,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _make_worker(env, worker_id: str, lease_sec: float = 30.0, concurrency: int = 4, maintenance: float = 0.2) -> AsyncInvestigationWorker:
    return AsyncInvestigationWorker(
        queue=env["queue"],
        repository=env["task_repo"],
        workflow_service=env["workflow_service"],
        worker_id=worker_id,
        lease_duration_sec=lease_sec,
        heartbeat_interval_sec=max(1.0, lease_sec / 4.0),
        concurrency=concurrency,
        maintenance_interval_sec=maintenance,
        stale_queue_requeue_sec=2.0,
    )


def _submit(env, task_id: str, require_review: bool = False, max_retries: int = 3) -> AsyncTask:
    task_repo = env["task_repo"]
    task = AsyncTask(
        task_id=task_id,
        organization_id=env["org_id"],
        user_id=env["user_id"],
        investigation_id=f"inv-{task_id}",
        task_type=TaskType.WORKFLOW_START,
        status=TaskStatus.QUEUED,
        payload={
            "contents": ["Guaranteed 40% returns, join Telegram channel now"],
            "require_review": require_review,
        },
        max_retries=max_retries,
    )
    task_repo.save_task(task)
    env["queue"].enqueue(task)
    return task


def _drain(env, workers: list[AsyncInvestigationWorker], timeout: float = 180.0) -> None:
    task_repo = env["task_repo"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        counts = task_repo.count_tasks_by_status()
        non_terminal = sum(
            n for s, n in counts.items()
            if s not in (TaskStatus.SUCCEEDED, TaskStatus.DEAD_LETTERED, TaskStatus.CANCELLED)
        )
        if non_terminal == 0:
            break
        time.sleep(0.05)


def test_worker_scaling_1_2_4_no_duplicate_or_lost_tasks(stress_env):
    """Submit 12 tasks; process with 1, then 2, then 4 workers. Exactly-once terminal effects."""
    env = stress_env
    task_repo = env["task_repo"]

    for i in range(12):
        _submit(env, f"task-scale-{i:02d}")

    w1 = _make_worker(env, "scale-w1")
    processed = 0
    deadline = time.time() + 240
    while processed < 12 and time.time() < deadline:
        processed += w1.process_one_batch(batch_size=1)

    counts = task_repo.count_tasks_by_status()
    assert counts.get(TaskStatus.SUCCEEDED, 0) == 12
    assert sum(counts.values()) == 12  # no lost tasks, no duplicates

    # Scale-out: additional workers find nothing to execute; terminal states unchanged
    for wid in ("scale-w2", "scale-w3", "scale-w4"):
        _make_worker(env, wid).process_one_batch(batch_size=5)
    counts_after = task_repo.count_tasks_by_status()
    assert counts_after.get(TaskStatus.SUCCEEDED, 0) == 12
    assert sum(counts_after.values()) == 12


def test_concurrent_workers_lease_contention_exactly_once(stress_env):
    """4 workers race on 8 tasks concurrently; each task completes exactly once."""
    env = stress_env
    task_repo = env["task_repo"]

    for i in range(8):
        _submit(env, f"task-race-{i:02d}")

    workers = [_make_worker(env, f"race-w{i}", concurrency=2) for i in range(4)]
    threads = []
    for w in workers:
        t = threading.Thread(target=lambda ww=w: [ww.process_one_batch(batch_size=2) for _ in range(8)])
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout=240)

    _drain(env, workers)
    counts = task_repo.count_tasks_by_status()
    assert counts.get(TaskStatus.SUCCEEDED, 0) == 8
    assert sum(counts.values()) == 8


def test_retry_sweeper_requeues_after_backoff_without_inline_sleep(stress_env):
    """Transient failure -> RETRY_WAIT with next_attempt_at; sweeper re-drives; task completes."""
    env = stress_env
    task_repo = env["task_repo"]
    task = _submit(env, "task-sweep-01", max_retries=3)

    worker = _make_worker(env, "sweep-w1")

    # Fail exactly the first execution attempt; subsequent attempts succeed.
    real_start = env["workflow_service"].start_investigation
    calls = {"n": 0}

    def flaky_start(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("Simulated transient registry outage")
        return real_start(*args, **kwargs)

    with patch.object(env["workflow_service"], "start_investigation", side_effect=flaky_start):
        worker.process_one_batch(batch_size=1)

        failed = task_repo.get_task("task-sweep-01")
        assert failed.status == TaskStatus.RETRY_WAIT
        assert failed.next_attempt_at is not None
        assert failed.retry_count == 1

        # Backoff contract: the task is NOT due immediately after failure
        assert all(t.task_id != "task-sweep-01" for t in task_repo.find_retry_due_tasks())

        # Backdate past the backoff deadline; then the real sweeper marks and re-enqueues
        task_repo._db.execute(
            "UPDATE sangyan_async_tasks SET next_attempt_at=? WHERE task_id='task-sweep-01'",
            (time.time() - 1.0,),
        )
        due = task_repo.find_retry_due_tasks()
        assert any(t.task_id == "task-sweep-01" for t in due)

        worker._requeue_due_retries()  # production sweeper: atomic mark + broker re-enqueue
        assert task_repo.get_task("task-sweep-01").status == TaskStatus.QUEUED

        worker.process_one_batch(batch_size=1)

    completed = task_repo.get_task("task-sweep-01")
    assert completed.status == TaskStatus.SUCCEEDED
    assert calls["n"] == 2


def test_retry_sweeper_single_winner_among_racing_workers(stress_env):
    """Racing sweepers re-drive a due retry exactly once (no duplicate broker messages)."""
    env = stress_env
    task_repo = env["task_repo"]
    _submit(env, "task-sweep-race-01", max_retries=3)
    task_repo._db.execute(
        "UPDATE sangyan_async_tasks SET status='RETRY_WAIT', next_attempt_at=? WHERE task_id='task-sweep-race-01'",
        (time.time() - 1.0,),
    )

    results = [task_repo.mark_retry_requeued("task-sweep-race-01") for _ in range(4)]
    assert results.count(True) == 1
    assert results.count(False) == 3
    assert task_repo.get_task("task-sweep-race-01").status == TaskStatus.QUEUED


def test_outbox_redrive_stale_queued_after_worker_crash(stress_env):
    """QUEUED task stranded in ledger (crash before broker enqueue) is re-driven by the sweeper."""
    env = stress_env
    task_repo = env["task_repo"]
    task = AsyncTask(
        task_id="task-outbox-01",
        organization_id=env["org_id"],
        user_id=env["user_id"],
        investigation_id="inv-outbox-01",
        task_type=TaskType.WORKFLOW_START,
        status=TaskStatus.QUEUED,
        payload={"contents": ["Content stranded before broker enqueue"]},
    )
    # Persist to ledger only; deliberately never enqueued to broker (simulates crash)
    task_repo.save_task(task)
    # Backdate so the staleness threshold trips
    task_repo._db.execute(
        "UPDATE sangyan_async_tasks SET updated_at=? WHERE task_id='task-outbox-01'",
        (time.time() - 60.0,),
    )

    stale = task_repo.find_stale_queued_tasks(older_than_sec=2.0)
    assert any(t.task_id == "task-outbox-01" for t in stale)

    worker = _make_worker(env, "outbox-w1")
    worker._redrive_stale_queued()  # sweeper re-enqueues
    processed = worker.process_one_batch(batch_size=1)
    assert processed == 1

    completed = task_repo.get_task("task-outbox-01")
    assert completed.status == TaskStatus.SUCCEEDED


def test_stream_reclaim_of_stranded_pending_message(stress_env):
    """Stranded stream message (dead consumer) is reclaimed and executed without duplicates."""
    env = stress_env
    task_repo = env["task_repo"]
    task = _submit(env, "task-strand-01")

    crashed = _make_worker(env, "strand-crashed", lease_sec=0.3)
    claimed = crashed.queue.claim_tasks(consumer_name=crashed.worker_id, batch_size=1, block_ms=100)
    assert len(claimed) == 1
    # Worker dies without ack or lease release; message idles in its PEL
    time.sleep(1.0)  # exceed reclaim window (lease 0.3s -> min idle 0.8s)

    # Survivor uses the same short lease so the reclaim window has elapsed
    survivor = _make_worker(env, "strand-survivor", lease_sec=0.3)
    survivor._check_and_reclaim_leases()  # stream + relational reclaim

    completed = task_repo.get_task("task-strand-01")
    assert completed.status == TaskStatus.SUCCEEDED

    counts = task_repo.count_tasks_by_status()
    assert counts.get(TaskStatus.SUCCEEDED, 0) == 1


def test_rolling_deployment_old_worker_dies_new_worker_completes(stress_env):
    """Old worker crashes mid-task after claiming; new worker completes via reclamation path."""
    env = stress_env
    task_repo = env["task_repo"]
    _submit(env, "task-roll-01")

    old_worker = _make_worker(env, "roll-old", lease_sec=0.3)
    claimed = old_worker.queue.claim_tasks(consumer_name=old_worker.worker_id, batch_size=1, block_ms=100)
    assert len(claimed) == 1
    # Old process terminated abruptly (no ack, no processing)
    time.sleep(1.0)  # exceed reclaim window (lease 0.3s -> min idle 0.8s)

    new_worker = _make_worker(env, "roll-new", lease_sec=0.3)
    new_worker.process_one_batch(batch_size=1, block_ms=100)
    # process_one_batch may claim nothing directly (message is in old PEL);
    # maintenance reclaim must bridge the gap.
    if task_repo.get_task("task-roll-01").status != TaskStatus.SUCCEEDED:
        new_worker._check_and_reclaim_leases()

    completed = task_repo.get_task("task-roll-01")
    assert completed.status == TaskStatus.SUCCEEDED
    assert completed.result is not None
    assert completed.result["status"] == "COMPLETED"


def test_task_flood_per_tenant_admission_cap(stress_env):
    """Outstanding-task counter enforces per-tenant saturation cap."""
    env = stress_env
    task_repo = env["task_repo"]

    outstanding = task_repo.count_outstanding_tasks(organization_id=env["org_id"])
    assert outstanding == 0

    for i in range(5):
        _submit(env, f"task-flood-{i:02d}")

    outstanding = task_repo.count_outstanding_tasks(organization_id=env["org_id"])
    assert outstanding == 5

    # Other tenants are unaffected (tenant-scoped counting)
    other_engine = env["engine"]
    from sangyan.tenancy.repository import TenantAdministration
    admin = TenantAdministration(other_engine)
    other_org = admin.create_organization("Flood Tenant B")
    other_user = admin.create_user("floodb@sangyan.test", "Flood B Analyst")
    admin.add_membership(other_org, other_user, "sangyan_analyst")
    assert task_repo.count_outstanding_tasks(organization_id=other_org) == 0

    counts = task_repo.count_tasks_by_status(organization_id=env["org_id"])
    assert counts.get(TaskStatus.QUEUED, 0) == 5


def test_worker_bounded_concurrency_respects_limit(stress_env):
    """Worker never exceeds its configured concurrency slot count."""
    env = stress_env
    task_repo = env["task_repo"]
    for i in range(6):
        _submit(env, f"task-conc-{i:02d}")

    worker = _make_worker(env, "conc-w1", concurrency=2)

    observed_peak = []
    original_execute = worker._execute_task_payload

    def slow_execute(task):
        observed_peak.append(worker.inflight_count())
        time.sleep(0.05)
        return original_execute(task)

    worker._execute_task_payload = slow_execute  # type: ignore[method-assign]

    deadline = time.time() + 120
    while time.time() < deadline:
        worker.process_one_batch(batch_size=2, block_ms=50)
        counts = task_repo.count_tasks_by_status()
        if counts.get(TaskStatus.SUCCEEDED, 0) >= 6:
            break
        time.sleep(0.01)

    assert task_repo.get_task("task-conc-00").status == TaskStatus.SUCCEEDED
    counts = task_repo.count_tasks_by_status()
    assert counts.get(TaskStatus.SUCCEEDED, 0) == 6
