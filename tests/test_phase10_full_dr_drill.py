"""Phase 10: end-to-end disaster recovery drill (Section 16) with workload continuity.

Scenario executed against the real stack:
1. Region A PRIMARY_ACTIVE: investigations executing, one awaiting review, one
   in flight (crashed worker, expired lease), one queued but undelivered.
2. Region A fails -> fenced -> writes rejected.
3. Region B promoted (epoch 2) -> workers recover pending work from the
   relational ledger (outbox re-drive + lease reclaim).
4. HITL review continues on region B; investigations complete with trust receipts.
5. Verifications: no duplicate business effects, no lost tasks, no stale-region
   writes, no audit fork, trust continuity, monotonic epochs.
Simulated timing (detection/promotion/first write) is recorded — local
simulation only, not a production RTO/RPO guarantee.
"""
import time
from pathlib import Path

import pytest

from sangyan.async_exec.models import AsyncTask, TaskStatus, TaskType
from sangyan.async_exec.queue import InMemoryTaskQueue
from sangyan.async_exec.repository import AsyncTaskRepository
from sangyan.async_exec.worker import AsyncInvestigationWorker
from sangyan.core.errors import StaleRegionError
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.dr.manager import DisasterRecoveryManager
from sangyan.dr.models import RegionRole
from sangyan.tenancy.repository import TenantAdministration, TenantRepository
from sangyan.trust.service import TrustService
from sangyan.verification.trust_binding import TrustBindingService
from sangyan.workflow.checkpointer import WorkflowCheckpointer
from sangyan.workflow.graph import InvestigationWorkflow
from sangyan.workflow.nodes import WorkflowNodeSuite
from sangyan.workflow.service import WorkflowService


@pytest.fixture
def drill(tmp_path):
    engine = SQLiteDatabaseEngine(tmp_path / "full_dr_drill.db")
    MigrationRunner(engine).migrate()

    admin = TenantAdministration(engine)
    org_id = admin.create_organization("Drill Tenant")
    user_id = admin.create_user("drill@sangyan.test", "Drill Analyst")
    admin.add_membership(org_id, user_id, "sangyan_analyst")

    dr = DisasterRecoveryManager(
        engine=engine, region_id="region-a", default_role=RegionRole.PRIMARY_ACTIVE, default_epoch=1
    )
    dr.register_region("region-b", role=RegionRole.STANDBY_READY, cluster_epoch=1)

    trust_service = TrustService(engine, key_dir=tmp_path / "pqc_keys")
    trust_binding = TrustBindingService(trust_service=trust_service)
    checkpointer = WorkflowCheckpointer(db_path=tmp_path / "checkpoints.db")

    active_region = ["region-a"]

    def repo_factory(oid, uid=None, region: str = None):
        # Bound to region-a initially; after promotion we bind to region-b
        return TenantRepository(engine, oid, uid or user_id, dr_manager=dr, region_id=region or active_region[0])

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

    yield {
        "engine": engine,
        "org_id": org_id,
        "user_id": user_id,
        "dr": dr,
        "service": service,
        "task_repo": task_repo,
        "queue": queue,
        "repo_factory": repo_factory,
        "active_region": active_region,
        "tmp_path": tmp_path,
    }
    engine.close()


def _worker(env, worker_id: str, lease_sec: float = 30.0) -> AsyncInvestigationWorker:
    return AsyncInvestigationWorker(
        queue=env["queue"],
        repository=env["task_repo"],
        workflow_service=env["service"],
        worker_id=worker_id,
        lease_duration_sec=lease_sec,
        heartbeat_interval_sec=max(1.0, lease_sec / 4),
        concurrency=2,
        maintenance_interval_sec=0.2,
        stale_queue_requeue_sec=2.0,
    )


def _submit(env, task_id: str, require_review: bool = False) -> AsyncTask:
    task = AsyncTask(
        task_id=task_id,
        organization_id=env["org_id"],
        user_id=env["user_id"],
        investigation_id=f"inv-{task_id}",
        task_type=TaskType.WORKFLOW_START,
        status=TaskStatus.QUEUED,
        payload={
            "contents": ["Guaranteed 300% returns via WhatsApp trading group"],
            "require_review": require_review,
        },
    )
    env["task_repo"].save_task(task)
    env["queue"].enqueue(task)
    return task


def _drill(env):
    engine = env["engine"]
    task_repo = env["task_repo"]
    dr = env["dr"]
    queue = env["queue"]

    timings: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Region A: normal workload
    # ------------------------------------------------------------------
    _submit(env, "tks-dr-done-1")
    _submit(env, "tks-dr-done-2")
    _submit(env, "tks-dr-review", require_review=True)
    # Task queued in ledger but never delivered (crash between save & enqueue)
    stranded = AsyncTask(
        task_id="tks-dr-stranded",
        organization_id=env["org_id"],
        user_id=env["user_id"],
        investigation_id="inv-tks-dr-stranded",
        task_type=TaskType.WORKFLOW_START,
        status=TaskStatus.QUEUED,
        payload={"contents": ["Stranded submission before broker delivery"]},
    )
    task_repo.save_task(stranded)
    engine.execute(
        "UPDATE sangyan_async_tasks SET updated_at=? WHERE task_id='tks-dr-stranded'",
        (time.time() - 120.0,),
    )

    worker_a = _worker(env, "worker-a-crashes")
    # Two investigations complete on A
    for _ in range(2):
        assert worker_a.process_one_batch(batch_size=1, block_ms=100) == 1
    # Review investigation reaches AWAITING_REVIEW
    assert worker_a.process_one_batch(batch_size=1, block_ms=100) == 1
    review_task = task_repo.get_task("tks-dr-review")
    assert review_task.result["status"] == "AWAITING_REVIEW"
    review_inv_id = review_task.result["investigation_id"]

    # One task crashes mid-flight on A (lease acquired, worker dies)
    _submit(env, "tks-dr-crashed")
    claimed = queue.claim_tasks(consumer_name=worker_a.worker_id, batch_size=1, block_ms=100)
    assert len(claimed) == 1
    msg_id, crashed_task = claimed[0]
    task_repo.acquire_lease("tks-dr-crashed", worker_id=worker_a.worker_id, lease_duration_sec=0.3)
    time.sleep(0.6)  # lease expires; worker A never acks (it "died")

    # ------------------------------------------------------------------
    # Region A failure detection & fencing
    # ------------------------------------------------------------------
    t_detect = time.time()
    dr.fence_region("region-a", reason="Simulated catastrophic loss of region A")
    timings["failure_detection_to_fence"] = time.time() - t_detect

    # Stale region A writes must be rejected (HTTP 409 class errors)
    repo_a = env["repo_factory"](env["org_id"], env["user_id"], region="region-a")
    with pytest.raises(StaleRegionError):
        repo_a.record_audit_event(action="stale_write", resource="x", result="REJECTED")

    # ------------------------------------------------------------------
    # Region B promotion
    # ------------------------------------------------------------------
    t_promo = time.time()
    promoted = dr.promote_region("region-b", reason="Regional failure failover")
    timings["promotion_duration"] = time.time() - t_promo
    assert promoted.role == RegionRole.PRIMARY_ACTIVE
    assert promoted.cluster_epoch == 2
    env["active_region"][0] = "region-b"

    t_first = time.time()
    repo_b = env["repo_factory"](env["org_id"], env["user_id"], region="region-b")
    repo_b.record_audit_event(action="first_write_after_promotion", resource="drill", result="SUCCESS")
    timings["first_successful_write"] = time.time() - t_first

    # ------------------------------------------------------------------
    # Region B workers recover pending work from the relational ledger
    # ------------------------------------------------------------------
    worker_b = _worker(env, "worker-b-recovers")

    # 1) Stranded QUEUED task: outbox re-drive (aged beyond stale threshold)
    worker_b._redrive_stale_queued()
    # 2) Crashed worker's pending stream message + expired lease: reclaim
    worker_b._check_and_reclaim_leases()

    # Process everything to completion
    deadline = time.time() + 15
    while time.time() < deadline:
        worker_b._requeue_due_retries()
        worker_b.process_one_batch(batch_size=2, block_ms=50)
        counts = task_repo.count_tasks_by_status()
        non_terminal = sum(
            n for s, n in counts.items()
            if s not in (TaskStatus.SUCCEEDED, TaskStatus.DEAD_LETTERED, TaskStatus.CANCELLED)
        )
        if non_terminal == 0:
            break
        time.sleep(0.05)

    return timings, review_inv_id


def test_full_dr_drill_recovers_all_work_without_duplicates(drill):
    env = drill
    timings, review_inv_id = _drill(env)
    task_repo = env["task_repo"]

    # Every task terminal and successful; none lost, none dead-lettered
    counts = task_repo.count_tasks_by_status()
    assert counts.get(TaskStatus.SUCCEEDED, 0) == 5
    assert counts.get(TaskStatus.DEAD_LETTERED, 0) == 0
    assert sum(counts.values()) == 5

    # No duplicate business effects: exactly one workflow run per investigation
    runs = env["engine"].query_all(
        "SELECT investigation_id, COUNT(*) AS n FROM sangyan_workflow_runs GROUP BY investigation_id"
    )
    assert len(runs) == 5
    for row in runs:
        assert row["n"] == 1

    # Timing recorded (local simulation only - not a production guarantee)
    assert all(k in timings and timings[k] >= 0 for k in
               ("failure_detection_to_fence", "promotion_duration", "first_successful_write"))


def test_full_dr_drill_hitl_review_continues_after_failover(drill):
    env = drill
    _, review_inv_id = _drill(env)

    # HITL review continues on region B via a resume task
    task_repo = env["task_repo"]
    resume = AsyncTask(
        task_id="tks-dr-resume",
        organization_id=env["org_id"],
        user_id=env["user_id"],
        investigation_id=review_inv_id,
        task_type=TaskType.WORKFLOW_RESUME,
        status=TaskStatus.QUEUED,
        payload={
            "investigation_id": review_inv_id,
            "review_action": "CONFIRM",
            "reason": "Reviewed after regional failover",
        },
    )
    task_repo.save_task(resume)
    env["queue"].enqueue(resume)

    worker_b = _worker(env, "worker-b-review")
    deadline = time.time() + 180
    while time.time() < deadline:
        worker_b.process_one_batch(batch_size=1, block_ms=50)
        if task_repo.get_task("tks-dr-resume").status == TaskStatus.SUCCEEDED:
            break
    assert task_repo.get_task("tks-dr-resume").status == TaskStatus.SUCCEEDED

    inv = env["engine"].query_one("SELECT status, trust_receipt_id FROM sangyan_investigations WHERE id=?",
                                  (review_inv_id,))
    assert inv["status"] == "COMPLETED"
    assert inv["trust_receipt_id"] is not None


def test_full_dr_drill_audit_trust_and_fencing_integrity(drill):
    env = drill
    _drill(env)
    dr = env["dr"]

    # 1. Audit ledger continuity: no fork across failover
    continuity = dr.verify_audit_continuity()
    assert continuity["valid"] is True
    assert continuity["event_count"] > 0

    # 2. Exactly one trust receipt per completed investigation:
    #    2 completed on region A + stranded + crashed = 4 completed non-review
    #    investigations (the review investigation finalizes only after resume).
    receipts = env["engine"].query_one(
        "SELECT COUNT(*) AS n FROM sangyan_trust_receipts WHERE subject_type='investigation'"
    )
    assert receipts["n"] == 4
    per_inv = env["engine"].query_all(
        "SELECT i.id, COUNT(tr.id) AS n FROM sangyan_investigations i "
        "LEFT JOIN sangyan_trust_receipts tr ON tr.subject_id = i.id AND tr.subject_type='investigation' "
        "WHERE i.status='COMPLETED' GROUP BY i.id"
    )
    assert len(per_inv) == 4
    for row in per_inv:
        assert row["n"] == 1  # no double finalization

    # 3. Stale region A remains fenced; epoch monotonic
    a = dr.get_region("region-a")
    assert a.is_fenced is True
    b = dr.get_region("region-b")
    assert b.role == RegionRole.PRIMARY_ACTIVE
    assert b.cluster_epoch == 2

    # 4. Stale A writes still rejected after drill
    repo_a = env["repo_factory"](env["org_id"], env["user_id"], region="region-a")
    with pytest.raises(StaleRegionError):
        repo_a.record_audit_event(action="post_drill_stale_write", resource="x", result="REJECTED")
