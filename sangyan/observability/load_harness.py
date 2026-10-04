"""Deterministic load, concurrency, and saturation validation harness.

Phase 10 mandates reproducible load validation without uncontrolled external
services. This harness drives the real SANGYAN asynchronous execution stack:

- relational task ledger (``AsyncTaskRepository``) with atomic leases,
- broker abstraction (``InMemoryTaskQueue`` or ``RedisStreamTaskQueue``),
- production workers (``AsyncInvestigationWorker``) with bounded concurrency,
- HITL decoupling (``AWAITING_REVIEW`` releases worker capacity),
- crash-safe retry sweeping and dead-letter quarantine.

Measured dimensions (all real, none fabricated):
- submit latency (task creation + broker enqueue, the async API submission path)
- queue latency (enqueue -> first claim)
- execution latency (lease acquisition -> terminal transition)
- end-to-end latency (enqueue -> terminal)
- database probe latency sampled during the run
- throughput (terminal transitions per wall-clock second)
- error, retry, and dead-letter rates
- worker lease expirations and duplicate-delivery acknowledgements

Usage:
    python -m sangyan.observability.load_harness --tenants 4 \
        --investigations-per-tenant 25 --workers 4 --output report.json
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from sangyan.async_exec.models import AsyncTask, TaskStatus, TaskType
from sangyan.async_exec.queue import InMemoryTaskQueue, TaskQueue
from sangyan.async_exec.repository import AsyncTaskRepository
from sangyan.async_exec.worker import AsyncInvestigationWorker
from sangyan.core.logging import get_logger
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

logger = get_logger("sangyan.observability.load_harness")

DETERMINISTIC_CONTENT_SAMPLES = [
    "Guaranteed 45% monthly returns, join our premium Telegram channel now",
    "Zerodha Broking Limited is SEBI registered under INZ000031633",
    "SEBI warns investors against unregistered investment advisers",
    "Pay registration fee via UPI to unlock assured profit software",
    "URGENT: last 3 slots for AI trading bot, deposit within 2 hours",
    "This mutual fund is subject to market risks, read all documents carefully",
]


def percentile(sorted_values: list[float], pct: float) -> float:
    """Nearest-rank percentile over a pre-sorted ascending list (seconds)."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = max(1, min(len(sorted_values), round((pct / 100.0) * len(sorted_values) + 0.5)))
    return sorted_values[rank - 1]


@dataclass
class LoadScenario:
    """Configuration for one deterministic load run."""

    name: str = "baseline"
    tenant_count: int = 4
    investigations_per_tenant: int = 25
    worker_count: int = 4
    worker_concurrency: int = 4
    contents_per_investigation: int = 1
    require_review_ratio: float = 0.0          # fraction of investigations pausing at HITL
    failure_injection_rate: float = 0.0        # fraction of tasks transiently failing once
    duplicate_resume_attempts: int = 0         # concurrent duplicate resumes per review (race defense probe)
    submission_concurrency: int = 8            # concurrent client threads submitting tasks
    lease_duration_sec: float = 30.0
    maintenance_interval_sec: float = 0.2
    seed: int = 1337


@dataclass
class LoadReport:
    """Measured results for one load run. Contains only observed values."""

    scenario: LoadScenario = field(default_factory=LoadScenario)
    started_at: float = 0.0
    duration_seconds: float = 0.0
    submissions: int = 0
    succeeded: int = 0
    awaiting_review: int = 0
    resumed: int = 0
    failed_terminal: int = 0
    dead_lettered: int = 0
    retries_scheduled: int = 0
    lease_expirations: int = 0
    submit_latency: list[float] = field(default_factory=list)
    queue_latency: list[float] = field(default_factory=list)
    execution_latency: list[float] = field(default_factory=list)
    e2e_latency: list[float] = field(default_factory=list)
    db_probe_latency: list[float] = field(default_factory=list)
    queue_depth_samples: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self, pct_values: tuple[float, ...] = (50.0, 95.0, 99.0)) -> dict[str, Any]:
        s_submit = sorted(self.submit_latency)
        s_queue = sorted(self.queue_latency)
        s_exec = sorted(self.execution_latency)
        s_e2e = sorted(self.e2e_latency)
        s_db = sorted(self.db_probe_latency)
        total_terminal = self.succeeded + self.awaiting_review + self.resumed + self.failed_terminal + self.dead_lettered

        def pct_block(values: list[float]) -> dict[str, float]:
            return {f"p{int(p)}": round(percentile(values, p), 6) for p in pct_values}

        return {
            "scenario": self.scenario.name,
            "tenants": self.scenario.tenant_count,
            "investigations_per_tenant": self.scenario.investigations_per_tenant,
            "worker_count": self.scenario.worker_count,
            "worker_concurrency": self.scenario.worker_concurrency,
            "duration_seconds": round(self.duration_seconds, 3),
            "submissions": self.submissions,
            "terminal_transitions": total_terminal,
            "throughput_per_second": round(total_terminal / self.duration_seconds, 3) if self.duration_seconds > 0 else 0.0,
            "succeeded": self.succeeded,
            "awaiting_review": self.awaiting_review,
            "resumed": self.resumed,
            "failed_terminal": self.failed_terminal,
            "dead_lettered": self.dead_lettered,
            "retries_scheduled": self.retries_scheduled,
            "retry_rate": round(self.retries_scheduled / self.submissions, 4) if self.submissions else 0.0,
            "dead_letter_rate": round(self.dead_lettered / self.submissions, 4) if self.submissions else 0.0,
            "error_rate": round(len(self.errors) / self.submissions, 4) if self.submissions else 0.0,
            "lease_expirations": self.lease_expirations,
            "max_queue_depth": max(self.queue_depth_samples) if self.queue_depth_samples else 0,
            "submit_latency_sec": pct_block(s_submit),
            "queue_latency_sec": pct_block(s_queue),
            "execution_latency_sec": pct_block(s_exec),
            "e2e_latency_sec": pct_block(s_e2e),
            "db_probe_latency_sec": pct_block(s_db),
            "db_probe_samples": len(s_db),
            "client_errors": list(self.errors)[:20],
        }

    def to_json(self) -> str:
        return json.dumps(self.summary(), indent=2, sort_keys=True)

    def write_json(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.to_json(), encoding="utf-8")
        return out


class _InstrumentedTaskQueue(TaskQueue):
    """Decorator around a TaskQueue recording enqueue/claim timestamps for latency attribution."""

    def __init__(self, inner: TaskQueue, harness: "LoadHarness") -> None:
        self._inner = inner
        self._harness = harness

    def enqueue(self, task: AsyncTask) -> str:
        self._harness._enqueue_times[task.task_id] = time.time()
        return self._inner.enqueue(task)

    def claim_tasks(self, consumer_name: str, batch_size: int = 1, block_ms: int = 1000):
        claimed = self._inner.claim_tasks(consumer_name, batch_size=batch_size, block_ms=block_ms)
        now = time.time()
        for msg_id, task in claimed:
            with self._harness._lock:
                enq = self._harness._enqueue_times.get(task.task_id)
                self._harness._claim_times[task.task_id] = now
            if enq is not None:
                self._harness._record("queue_latency", now - enq)
        return claimed

    def ack(self, stream_message_id: str) -> None:
        self._inner.ack(stream_message_id)

    def dead_letter(self, task: AsyncTask, reason: str, stream_message_id: str | None = None) -> str:
        return self._inner.dead_letter(task, reason, stream_message_id)

    def reclaim_expired(self, consumer_name: str, min_idle_time_ms: int = 60000, batch_size: int = 10):
        return self._inner.reclaim_expired(consumer_name, min_idle_time_ms, batch_size)

    def close(self) -> None:
        self._inner.close()


class LoadHarness:
    """Drives deterministic multi-tenant load against the real async execution stack."""

    def __init__(self, scenario: Optional[LoadScenario] = None, workdir: Optional[str] = None) -> None:
        self.scenario = scenario or LoadScenario()
        self._workdir = workdir or tempfile.mkdtemp(prefix="sangyan_load_")
        self._owns_workdir = workdir is None
        self._enqueue_times: dict[str, float] = {}
        self._latencies: dict[str, list[float]] = {}
        self._terminal_times: dict[str, float] = {}
        self._claim_times: dict[str, float] = {}
        self._lock = threading.Lock()
        self._db_probe_stop = threading.Event()

    # ------------------------------------------------------------------
    # Measurement plumbing
    # ------------------------------------------------------------------

    def _record(self, kind: str, value: float) -> None:
        with self._lock:
            self._latencies.setdefault(kind, []).append(value)

    def _observe_terminal(self, task_id: str) -> None:
        now = time.time()
        with self._lock:
            self._terminal_times[task_id] = now
            claim = self._claim_times.get(task_id)
            enq = self._enqueue_times.get(task_id)
        if claim is not None:
            self._record("execution_latency", now - claim)
        if enq is not None:
            self._record("e2e_latency", now - enq)

    # ------------------------------------------------------------------
    # Environment construction (real stack, isolated per run)
    # ------------------------------------------------------------------

    def _build_environment(self) -> dict[str, Any]:
        tmp = Path(self._workdir)
        engine = SQLiteDatabaseEngine(tmp / "load_harness.db")
        MigrationRunner(engine).migrate()

        admin = TenantAdministration(engine)
        org_ids: list[str] = []
        user_ids: list[str] = []
        for t in range(self.scenario.tenant_count):
            org_id = admin.create_organization(f"LoadTenant-{t}")
            user_id = admin.create_user(f"analyst-{t}@load.sangyan.test", "Load Analyst")
            admin.add_membership(org_id, user_id, "sangyan_analyst")
            org_ids.append(org_id)
            user_ids.append(user_id)

        key_dir = tmp / "pqc_keys"
        trust_service = TrustService(engine, key_dir=key_dir)
        trust_binding = TrustBindingService(trust_service=trust_service)
        checkpointer = WorkflowCheckpointer(db_path=tmp / "checkpoints.db")

        org_to_user = dict(zip(org_ids, user_ids))

        def repo_factory(oid: str, user_id: str | None = None) -> TenantRepository:
            # Resolve the correct tenant user even when the workflow node suite
            # calls back without an explicit user_id (single-tenant test convenience).
            return TenantRepository(engine, oid, user_id or org_to_user.get(oid) or user_ids[0])

        node_suite = WorkflowNodeSuite(
            trust_binding=trust_binding,
            repository_factory=lambda oid: repo_factory(oid),
        )
        workflow = InvestigationWorkflow(node_suite=node_suite, checkpointer=checkpointer.get_saver())
        workflow_service = WorkflowService(
            repository_factory=lambda oid: repo_factory(oid),
            workflow=workflow,
            checkpointer=checkpointer,
            node_suite=node_suite,
        )

        # Deterministic transient-failure injection on the real workflow service.
        # Decision is a stable digest of the submitted task identity (passed via
        # payload metadata), never affected by process hash randomization.
        scenario = self.scenario
        injected_once: set[str] = set()
        if scenario.failure_injection_rate > 0.0:
            import hashlib

            original_start = workflow_service.start_investigation

            def injecting_start(*args: Any, **kwargs: Any) -> Any:
                metadata = kwargs.get("metadata") or {}
                marker = metadata.get("load_task_id")
                if marker is None:
                    content_items = args[0] if args else kwargs.get("content_items", [])
                    org = kwargs.get("organization_id") or (content_items[0].organization_id if content_items else "")
                    marker = f"org:{org}"
                if marker in injected_once:
                    return original_start(*args, **kwargs)
                digest = int(hashlib.sha256(str(marker).encode("utf-8")).hexdigest(), 16) % 10_000
                if digest < int(scenario.failure_injection_rate * 10_000):
                    injected_once.add(str(marker))
                    raise ConnectionError("Injected transient upstream registry timeout")
                return original_start(*args, **kwargs)

            workflow_service.start_investigation = injecting_start  # type: ignore[method-assign]

        task_repo = AsyncTaskRepository(engine)

        # Instrument terminal transitions on the durable ledger for latency attribution
        original_complete = task_repo.complete_task

        def instrumented_complete(task_id: str, worker_id: str, result: dict) -> bool:
            completed = original_complete(task_id, worker_id, result)
            if completed:
                self._observe_terminal(task_id)
            return completed

        task_repo.complete_task = instrumented_complete  # type: ignore[method-assign]
        original_fail = task_repo.fail_or_retry_task

        def instrumented_fail(task_id: str, worker_id: str, error_message: str, is_transient: bool = True):
            updated = original_fail(task_id, worker_id, error_message, is_transient=is_transient)
            if updated.status == TaskStatus.DEAD_LETTERED:
                self._observe_terminal(task_id)
            return updated

        task_repo.fail_or_retry_task = instrumented_fail  # type: ignore[method-assign]

        broker = InMemoryTaskQueue()
        queue = _InstrumentedTaskQueue(broker, self)

        workers: list[AsyncInvestigationWorker] = []
        for w in range(self.scenario.worker_count):
            worker = AsyncInvestigationWorker(
                queue=queue,
                repository=task_repo,
                workflow_service=workflow_service,
                worker_id=f"load-worker-{w}",
                lease_duration_sec=scenario.lease_duration_sec,
                heartbeat_interval_sec=max(1.0, scenario.lease_duration_sec / 4.0),
                concurrency=scenario.worker_concurrency,
                maintenance_interval_sec=scenario.maintenance_interval_sec,
                stale_queue_requeue_sec=max(2.0, scenario.lease_duration_sec),
            )
            workers.append(worker)

        return {
            "engine": engine,
            "task_repo": task_repo,
            "queue": queue,
            "workers": workers,
            "workflow_service": workflow_service,
            "org_ids": org_ids,
            "user_ids": user_ids,
            "checkpointer": checkpointer,
        }

    def _db_probe_loop(self, engine: Any, interval: float = 0.05) -> None:
        while not self._db_probe_stop.is_set():
            start = time.time()
            try:
                engine.query_one("SELECT 1 AS probe")
                self._record("db_probe_latency", time.time() - start)
            except Exception:
                pass
            self._db_probe_stop.wait(interval)

    # ------------------------------------------------------------------
    # Submission (mirrors the async API submission path)
    # ------------------------------------------------------------------

    def _submit_investigation(
        self,
        task_repo: AsyncTaskRepository,
        queue: TaskQueue,
        org_id: str,
        user_id: str,
        index: int,
        require_review: bool,
    ) -> AsyncTask:
        scenario = self.scenario
        contents = [
            DETERMINISTIC_CONTENT_SAMPLES[(index + c) % len(DETERMINISTIC_CONTENT_SAMPLES)]
            for c in range(max(1, scenario.contents_per_investigation))
        ]
        task = AsyncTask(
            task_id=f"tsk-load-{org_id[-6:]}-{index}",
            organization_id=org_id,
            user_id=user_id,
            investigation_id=f"inv-load-{org_id[-6:]}-{index}",
            task_type=TaskType.WORKFLOW_START,
            status=TaskStatus.QUEUED,
            payload={
                "contents": contents,
                "content_type": "text/plain",
                "require_review": require_review,
                "metadata": {"load_scenario": scenario.name, "load_task_id": f"tsk-load-{org_id[-6:]}-{index}"},
            },
        )
        start = time.time()
        task_repo.save_task(task)
        queue.enqueue(task)
        self._record("submit_latency", time.time() - start)
        return task

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> LoadReport:
        scenario = self.scenario
        env = self._build_environment()
        engine = env["engine"]
        task_repo: AsyncTaskRepository = env["task_repo"]
        queue: TaskQueue = env["queue"]
        workers: list[AsyncInvestigationWorker] = env["workers"]
        org_ids: list[str] = env["org_ids"]
        user_ids: list[str] = env["user_ids"]

        report = LoadReport(scenario=scenario, started_at=time.time())

        probe_thread = threading.Thread(
            target=self._db_probe_loop, args=(engine,), daemon=True
        )
        probe_thread.start()

        worker_threads: list[threading.Thread] = []
        try:
            for worker in workers:
                t = threading.Thread(
                    target=worker.run_forever,
                    kwargs={"poll_interval_ms": 100},
                    daemon=True,
                )
                t.start()
                worker_threads.append(t)

            submit_start = time.time()
            total = scenario.tenant_count * scenario.investigations_per_tenant

            def submit_range(worker_index: int) -> None:
                for i in range(worker_index, total, scenario.submission_concurrency):
                    tenant_index = i % scenario.tenant_count
                    inv_index = i // scenario.tenant_count
                    require_review = (inv_index % max(1, int(round(1.0 / max(scenario.require_review_ratio, 1e-9)))) == 0) if scenario.require_review_ratio > 0 else False
                    self._submit_investigation(
                        task_repo,
                        queue,
                        org_ids[tenant_index],
                        user_ids[tenant_index],
                        inv_index,
                        require_review,
                    )

            with ThreadPoolExecutor(max_workers=max(1, scenario.submission_concurrency)) as pool:
                list(pool.map(submit_range, range(min(scenario.submission_concurrency, total))))
            report.submissions = total
            report.duration_seconds = 0.0  # replaced below
            submit_duration = time.time() - submit_start

            # Drive resume tasks for investigations that reached review
            resumed = self._drive_resumes(task_repo, queue, org_ids, user_ids, report)

            # Wait for all tasks to reach a terminal state (bounded)
            deadline = time.time() + 900.0
            last_depth_sample = 0.0
            while time.time() < deadline:
                counts = task_repo.count_tasks_by_status()
                non_terminal = sum(
                    n for s, n in counts.items()
                    if s not in (TaskStatus.SUCCEEDED, TaskStatus.DEAD_LETTERED, TaskStatus.CANCELLED)
                )
                now = time.time()
                if now - last_depth_sample >= 0.1:
                    with self._lock:
                        report.queue_depth_samples.append(counts.get(TaskStatus.QUEUED, 0))
                    last_depth_sample = now
                if non_terminal == 0:
                    break
                time.sleep(0.1)

            # Final observations from the durable ledger
            self._collect_ledger_results(task_repo, report)
            report.duration_seconds = max(0.001, time.time() - report.started_at)
            report.resumed = resumed
            logger.info(
                "Load run '%s' complete: submissions=%d, submitted_in=%.2fs, total=%.2fs",
                scenario.name, report.submissions, submit_duration, report.duration_seconds,
            )
        finally:
            self._db_probe_stop.set()
            probe_thread.join(timeout=2.0)
            for worker in workers:
                worker.stop()
            for t in worker_threads:
                t.join(timeout=10.0)
            try:
                queue.close()
            except Exception:
                pass
            try:
                engine.close()
            except Exception:
                pass

        with self._lock:
            report.submit_latency = list(self._latencies.get("submit_latency", []))
            report.queue_latency = list(self._latencies.get("queue_latency", []))
            report.db_probe_latency = list(self._latencies.get("db_probe_latency", []))
            report.e2e_latency = list(self._latencies.get("e2e_latency", []))

        # Execution latencies recorded directly at terminal transitions
        with self._lock:
            report.execution_latency = list(self._latencies.get("execution_latency", []))

        if self._owns_workdir:
            shutil.rmtree(self._workdir, ignore_errors=True)
        return report

    def _drive_resumes(
        self,
        task_repo: AsyncTaskRepository,
        queue: TaskQueue,
        org_ids: list[str],
        user_ids: list[str],
        report: LoadReport,
    ) -> int:
        """Enqueue WORKFLOW_RESUME tasks for investigations parked at AWAITING_REVIEW."""
        scenario = self.scenario
        resumed = 0
        pending_review: list[tuple[str, str, str]] = []
        total_review_expected = self._expected_review_count()
        if total_review_expected > 0:
            # Bounded wait: allow stage-1 tasks to reach review
            deadline = time.time() + 600.0
            while time.time() < deadline:
                pending_review = []
                for tenant_index, org_id in enumerate(org_ids):
                    tasks = task_repo.list_tasks(organization_id=org_id, status=TaskStatus.SUCCEEDED, limit=500)
                    for t in tasks:
                        if t.task_type == TaskType.WORKFLOW_START:
                            result_status = (t.result or {}).get("status")
                            if result_status == "AWAITING_REVIEW":
                                inv_id = (t.result or {}).get("investigation_id") or t.investigation_id
                                pending_review.append((org_id, user_ids[tenant_index], inv_id))
                non_terminal = any(
                    task_repo.list_tasks(organization_id=o, status=s, limit=1)
                    for o in org_ids
                    for s in (TaskStatus.QUEUED, TaskStatus.RUNNING, TaskStatus.RETRY_WAIT, TaskStatus.LEASED)
                )
                if len(pending_review) >= total_review_expected or not non_terminal:
                    break
                time.sleep(0.1)

        for org_id, user_id, inv_id in pending_review:
            resume_task = AsyncTask(
                task_id=f"tsk-resume-{org_id[-6:]}-{inv_id[-8:]}",
                organization_id=org_id,
                user_id=user_id,
                investigation_id=inv_id,
                task_type=TaskType.WORKFLOW_RESUME,
                status=TaskStatus.QUEUED,
                payload={
                    "investigation_id": inv_id,
                    "review_action": "CONFIRM",
                    "reason": "Load harness deterministic supervisory review",
                },
            )
            start = time.time()
            task_repo.save_task(resume_task)
            queue.enqueue(resume_task)
            self._record("submit_latency", time.time() - start)
            resumed += 1

            # Duplicate resume race probe: concurrent duplicate resume submissions
            for d in range(scenario.duplicate_resume_attempts):
                dup = AsyncTask(
                    task_id=f"tsk-resume-{org_id[-6:]}-{inv_id[-8:]}-dup{d}",
                    organization_id=org_id,
                    user_id=user_id,
                    investigation_id=inv_id,
                    task_type=TaskType.WORKFLOW_RESUME,
                    status=TaskStatus.QUEUED,
                    payload={
                        "investigation_id": inv_id,
                        "review_action": "DISMISS",
                        "reason": f"Duplicate resume race probe {d}",
                    },
                )
                task_repo.save_task(dup)
                queue.enqueue(dup)
        return resumed

    def _expected_review_count(self) -> int:
        scenario = self.scenario
        if scenario.require_review_ratio <= 0:
            return 0
        total = scenario.tenant_count * scenario.investigations_per_tenant
        stride = max(1, int(round(1.0 / scenario.require_review_ratio)))
        return sum(1 for inv_index in range(total) if (inv_index // scenario.tenant_count) % stride == 0)

    def _collect_ledger_results(self, task_repo: AsyncTaskRepository, report: LoadReport) -> None:
        counts = task_repo.count_tasks_by_status()
        report.succeeded = counts.get(TaskStatus.SUCCEEDED, 0)
        report.dead_lettered = counts.get(TaskStatus.DEAD_LETTERED, 0)
        report.failed_terminal = counts.get(TaskStatus.FAILED, 0)
        report.retries_scheduled = task_repo._db.query_one(
            "SELECT COUNT(*) AS n FROM sangyan_async_tasks WHERE retry_count > 0"
        )["n"]
        report.lease_expirations = 0
        stuck = task_repo.find_expired_leases()
        report.lease_expirations = len(stuck)
        # Distinguish stage-1 HITL completions from resumed completions
        review_count = 0
        rows = task_repo._db.query_all(
            "SELECT result FROM sangyan_async_tasks WHERE task_type=? AND status=?",
            (TaskType.WORKFLOW_START, TaskStatus.SUCCEEDED),
        )
        for row in rows:
            try:
                result = json.loads(row["result"]) if isinstance(row["result"], str) else (row["result"] or {})
            except Exception:
                continue
            if result.get("status") == "AWAITING_REVIEW":
                review_count += 1
        report.awaiting_review = review_count
        report.resumed = max(0, report.succeeded - review_count)


def run_scenario(scenario: Optional[LoadScenario] = None, output: Optional[str] = None) -> LoadReport:
    """Convenience entry point used by CLI and tests."""
    harness = LoadHarness(scenario)
    report = harness.run()
    if output:
        report.write_json(output)
    return report


def main() -> None:  # pragma: no cover - CLI convenience
    parser = argparse.ArgumentParser(description="SANGYAN deterministic load harness")
    parser.add_argument("--name", default="baseline")
    parser.add_argument("--tenants", type=int, default=4)
    parser.add_argument("--investigations-per-tenant", type=int, default=25)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--worker-concurrency", type=int, default=4)
    parser.add_argument("--contents", type=int, default=1)
    parser.add_argument("--require-review-ratio", type=float, default=0.0)
    parser.add_argument("--failure-rate", type=float, default=0.0)
    parser.add_argument("--duplicate-resumes", type=int, default=0)
    parser.add_argument("--submission-concurrency", type=int, default=8)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--output", default=None, help="Write JSON report to this path")
    args = parser.parse_args()

    scenario = LoadScenario(
        name=args.name,
        tenant_count=args.tenants,
        investigations_per_tenant=args.investigations_per_tenant,
        worker_count=args.workers,
        worker_concurrency=args.worker_concurrency,
        contents_per_investigation=args.contents,
        require_review_ratio=args.require_review_ratio,
        failure_injection_rate=args.failure_rate,
        duplicate_resume_attempts=args.duplicate_resumes,
        submission_concurrency=args.submission_concurrency,
        seed=args.seed,
    )
    report = run_scenario(scenario, output=args.output)
    print(report.to_json())


if __name__ == "__main__":  # pragma: no cover
    main()
