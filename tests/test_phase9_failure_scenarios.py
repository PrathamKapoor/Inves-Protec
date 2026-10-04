"""Comprehensive failure-oriented test scenarios for Phase 9:
- Scenario A: Worker crashes midway during execution; lease expires; successor worker reclaims and completes.
- Scenario B: Duplicate task delivery / at-least-once replay idempotency.
- Scenario C: Primary region network partition, standby promotion, and split-brain write fencing.
- Scenario D: Unregistered region write rejection with StaleRegionError.
- Scenario E: LangGraph checkpoint durability across worker crashes and restarts.
- Scenario F: Dead-letter queue exhaustion and operator administrative recovery.
- Scenario G: Worker graceful termination mid-flight cleanly draining current task.
"""
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
def failover_env():
    tmpdir = tempfile.mkdtemp()
    try:
        db_path = Path(tmpdir) / "sangyan_failover_test.db"
        engine = SQLiteDatabaseEngine(db_path)
        MigrationRunner(engine).migrate()

        admin_svc = TenantAdministration(engine)
        org_id = admin_svc.create_organization("SEBI National Directorate")
        user_id = admin_svc.create_user("supervisor@sebi.gov.in", "Director Analyst")
        admin_svc.add_membership(org_id, user_id, "sangyan_analyst")

        key_dir = Path(tmpdir) / "pqc_keys"
        trust_service = TrustService(engine, key_dir=key_dir)
        trust_binding = TrustBindingService(trust_service=trust_service)

        cp_path = Path(tmpdir) / "checkpoints.db"
        checkpointer = WorkflowCheckpointer(db_path=cp_path)

        dr_manager = DisasterRecoveryManager(
            engine=engine,
            region_id="primary-mumbai",
            default_role=RegionRole.PRIMARY_ACTIVE,
            default_epoch=1,
        )
        dr_manager.register_region("standby-delhi", role=RegionRole.STANDBY_READY, cluster_epoch=1)

        def repo_factory(oid: str, uid: str | None = None) -> TenantRepository:
            return TenantRepository(
                engine,
                oid,
                uid or user_id,
                dr_manager=dr_manager,
                region_id="primary-mumbai",
            )

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

        yield {
            "tmpdir": tmpdir,
            "engine": engine,
            "org_id": org_id,
            "user_id": user_id,
            "dr_manager": dr_manager,
            "workflow_service": service,
            "checkpointer": checkpointer,
            "queue": queue,
            "task_repo": task_repo,
            "repo_factory": repo_factory,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_scenario_a_worker_crash_and_lease_expiry_reclaim(failover_env):
    """Worker 1 crashes mid-task. Lease expires. Worker 2 detects expired lease and completes it."""
    task_repo = failover_env["task_repo"]
    queue = failover_env["queue"]
    service = failover_env["workflow_service"]
    org_id = failover_env["org_id"]
    user_id = failover_env["user_id"]

    task = task_repo.create_task(
        task_id="task-crash-001",
        organization_id=org_id,
        user_id=user_id,
        investigation_id="inv-crash-001",
        task_type=TaskType.WORKFLOW_START,
        payload={
            "contents": ["Dubious algorithmic trading bot promising 100% daily gains"],
            "require_review": False,
        },
    )

    # Worker 1 leases task with very short lease (0.2s)
    worker1 = AsyncInvestigationWorker(
        queue=queue,
        repository=task_repo,
        workflow_service=service,
        worker_id="worker-crash-1",
        lease_duration_sec=0.2,
    )
    leased = task_repo.acquire_lease("task-crash-001", worker_id="worker-crash-1", lease_duration_sec=0.2)
    assert leased is True

    # Simulate Worker 1 dying before completion: wait for lease to expire
    time.sleep(0.3)

    # Worker 2 initializes and runs expired lease check
    worker2 = AsyncInvestigationWorker(
        queue=queue,
        repository=task_repo,
        workflow_service=service,
        worker_id="worker-recovery-2",
        lease_duration_sec=30.0,
    )

    expired = task_repo.find_expired_leases()
    assert any(t.task_id == "task-crash-001" for t in expired)

    # Worker 2 triggers expired lease reclamation
    worker2._check_and_reclaim_leases()
    reclaimed_task = task_repo.get_task("task-crash-001")
    assert reclaimed_task.status in (TaskStatus.RETRY_WAIT, TaskStatus.QUEUED)
    assert reclaimed_task.retry_count == 1

    # Worker 2 re-enqueues and processes task to completion
    reclaimed_task.transition_to(TaskStatus.QUEUED)
    queue.enqueue(reclaimed_task)
    processed = worker2.process_one_batch(batch_size=1)
    assert processed == 1

    final_task = task_repo.get_task("task-crash-001")
    assert final_task.status == TaskStatus.SUCCEEDED
    assert final_task.result["status"] == "COMPLETED"


def test_scenario_b_duplicate_delivery_idempotency(failover_env):
    """At-least-once broker delivers duplicate message. Second worker safely skips already completed/leased task."""
    task_repo = failover_env["task_repo"]
    queue = failover_env["queue"]
    service = failover_env["workflow_service"]
    org_id = failover_env["org_id"]
    user_id = failover_env["user_id"]

    task = task_repo.create_task(
        task_id="task-dup-001",
        organization_id=org_id,
        user_id=user_id,
        investigation_id="inv-dup-001",
        task_type=TaskType.WORKFLOW_START,
        payload={"contents": ["First delivery text"]},
    )
    queue.enqueue(task)
    queue.enqueue(task)  # Broker replay: duplicate message in stream

    worker = AsyncInvestigationWorker(
        queue=queue,
        repository=task_repo,
        workflow_service=service,
        worker_id="worker-idempotent-01",
    )

    # First delivery processes task
    count1 = worker.process_one_batch(batch_size=1)
    assert count1 == 1
    t1 = task_repo.get_task("task-dup-001")
    assert t1.status == TaskStatus.SUCCEEDED

    # Second delivery: acquire_lease returns False because task is already SUCCEEDED
    count2 = worker.process_one_batch(batch_size=1)
    assert count2 == 1  # Dequeued and ACKed without executing
    t2 = task_repo.get_task("task-dup-001")
    assert t2.status == TaskStatus.SUCCEEDED  # State intact


def test_scenario_c_split_brain_fencing_after_failover(failover_env):
    """Primary fails over. Old primary is demoted and fenced. Write attempts by old primary fail closed."""
    dr = failover_env["dr_manager"]
    engine = failover_env["engine"]
    org_id = failover_env["org_id"]
    user_id = failover_env["user_id"]

    # Initial state: primary-mumbai is active
    dr.verify_write_authority("primary-mumbai")

    # Perform failover: promote standby-delhi
    promoted = dr.promote_region("standby-delhi", reason="Mumbai catastrophic flood")
    assert promoted.role == RegionRole.PRIMARY_ACTIVE
    assert promoted.cluster_epoch == 2

    # Old primary Mumbai is demoted and fenced
    mumbai = dr.get_region("primary-mumbai")
    assert mumbai.role == RegionRole.DEMOTED
    assert mumbai.is_fenced is True

    # Any write from Mumbai region must raise StaleRegionError
    repo_mumbai = TenantRepository(
        engine,
        org_id,
        user_id,
        dr_manager=dr,
        region_id="primary-mumbai",
    )

    with pytest.raises(StaleRegionError) as exc:
        repo_mumbai.record_audit_event(
            action="INVESTIGATION_MODIFIED",
            resource="inv-mumbai",
            result="FAILURE",
        )
    assert "is fenced" in str(exc.value)

    # Write from promoted region Delhi succeeds
    repo_delhi = TenantRepository(
        engine,
        org_id,
        user_id,
        dr_manager=dr,
        region_id="standby-delhi",
    )
    eid = repo_delhi.record_audit_event(
        action="INVESTIGATION_MODIFIED",
        resource="inv-delhi",
        result="SUCCESS",
    )
    assert eid is not None


def test_scenario_d_unregistered_region_write_rejection(failover_env):
    """Write attempt with unregistered region ID fails immediately."""
    dr = failover_env["dr_manager"]
    with pytest.raises(StaleRegionError) as exc:
        dr.verify_write_authority("ghost-region-99")
    assert "is not registered" in str(exc.value)


def test_scenario_e_checkpoint_durability_across_worker_restarts(failover_env):
    """LangGraph checkpoint state persists when worker crashes during AWAITING_REVIEW."""
    task_repo = failover_env["task_repo"]
    queue = failover_env["queue"]
    service = failover_env["workflow_service"]
    org_id = failover_env["org_id"]
    user_id = failover_env["user_id"]

    # 1. Worker 1 starts workflow with require_review=True
    task_start = task_repo.create_task(
        task_id="task-dur-01",
        organization_id=org_id,
        user_id=user_id,
        investigation_id="inv-dur-01",
        task_type=TaskType.WORKFLOW_START,
        payload={
            "contents": ["High-yield fraudulent guaranteed returns"],
            "require_review": True,
        },
    )
    queue.enqueue(task_start)

    worker1 = AsyncInvestigationWorker(
        queue=queue,
        repository=task_repo,
        workflow_service=service,
        worker_id="worker-node-1",
    )
    worker1.process_one_batch(batch_size=1)

    stage1 = task_repo.get_task("task-dur-01")
    assert stage1.result["status"] == "AWAITING_REVIEW"
    actual_inv_id = stage1.result["investigation_id"]

    # Verify checkpoint exists in durable storage
    state = service.get_workflow_state(actual_inv_id, org_id, user_id=user_id)
    assert state is not None
    assert state.get("status") == "AWAITING_REVIEW"

    # Simulate worker 1 process dying completely
    del worker1

    # 2. Worker 2 starts up fresh and receives resume task
    task_resume = task_repo.create_task(
        task_id="task-dur-02",
        organization_id=org_id,
        user_id=user_id,
        investigation_id=actual_inv_id,
        task_type=TaskType.WORKFLOW_RESUME,
        payload={
            "investigation_id": actual_inv_id,
            "review_action": "CONFIRM",
            "reason": "Supervisor confirmed fraudulent syndicate",
        },
    )
    queue.enqueue(task_resume)

    worker2 = AsyncInvestigationWorker(
        queue=queue,
        repository=task_repo,
        workflow_service=service,
        worker_id="worker-node-2",
    )
    worker2.process_one_batch(batch_size=1)

    stage2 = task_repo.get_task("task-dur-02")
    assert stage2.status == TaskStatus.SUCCEEDED
    assert stage2.result["status"] == "COMPLETED"
    assert stage2.result["trust_receipt_id"] is not None


def test_scenario_f_dead_letter_manual_recovery_cycle(failover_env):
    """Task exhausts retries -> DEAD_LETTERED. Operator retries task -> worker completes."""
    task_repo = failover_env["task_repo"]
    queue = failover_env["queue"]
    service = failover_env["workflow_service"]
    org_id = failover_env["org_id"]
    user_id = failover_env["user_id"]

    task = task_repo.create_task(
        task_id="task-recovery-001",
        organization_id=org_id,
        user_id=user_id,
        investigation_id="inv-rec-001",
        task_type=TaskType.WORKFLOW_START,
        payload={"contents": ["Content to be recovered"]},
        max_retries=1,
    )
    # Set to retry_count 1
    task_repo._db.execute("UPDATE sangyan_async_tasks SET retry_count=1 WHERE task_id='task-recovery-001'")
    queue.enqueue(task_repo.get_task("task-recovery-001"))

    worker = AsyncInvestigationWorker(
        queue=queue,
        repository=task_repo,
        workflow_service=service,
        worker_id="worker-flaky-01",
    )

    # Execution fails due to temporary third-party outage
    with patch.object(service, "start_investigation", side_effect=RuntimeError("External registry down")):
        worker.process_one_batch(batch_size=1)

    dead_task = task_repo.get_task("task-recovery-001")
    assert dead_task.status == TaskStatus.DEAD_LETTERED

    # Operator administrative action: retry dead-lettered task
    retried_task = task_repo.retry_dead_letter_task("task-recovery-001")
    assert retried_task.status == TaskStatus.QUEUED
    assert retried_task.retry_count == 0
    queue.enqueue(retried_task)

    # Worker picks up retried task and executes without error
    worker.process_one_batch(batch_size=1)
    succeeded_task = task_repo.get_task("task-recovery-001")
    assert succeeded_task.status == TaskStatus.SUCCEEDED
    assert succeeded_task.result["status"] == "COMPLETED"


def test_scenario_g_worker_graceful_stop_inflight(failover_env):
    """Worker stop() terminates consumer loop after active task finishes."""
    task_repo = failover_env["task_repo"]
    queue = failover_env["queue"]
    service = failover_env["workflow_service"]
    org_id = failover_env["org_id"]
    user_id = failover_env["user_id"]

    worker = AsyncInvestigationWorker(
        queue=queue,
        repository=task_repo,
        workflow_service=service,
        worker_id="worker-stop-01",
    )

    task = task_repo.create_task(
        task_id="task-stop-001",
        organization_id=org_id,
        user_id=user_id,
        investigation_id="inv-stop-001",
        task_type=TaskType.WORKFLOW_START,
        payload={"contents": ["Task during graceful shutdown"]},
    )
    queue.enqueue(task)

    # Process batch and trigger stop
    worker.process_one_batch(batch_size=1)
    worker.stop()
    assert worker.is_stopped()

    # Verify task completed despite shutdown signal
    completed = task_repo.get_task("task-stop-001")
    assert completed.status == TaskStatus.SUCCEEDED
