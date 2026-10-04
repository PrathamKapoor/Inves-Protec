"""Asynchronous task execution worker with bounded leasing, HITL decoupling, and failure recovery.

Phase 10 hardening:
- Bounded concurrent task execution (``concurrency`` slots) instead of one-task-at-a-time.
- Crash-safe retry scheduling: transient failures persist an explicit ``next_attempt_at``
  deadline in the relational task ledger; a periodic sweeper re-drives delivery. Workers
  never sleep inline while holding capacity and never rely on in-process timers that die
  with the process.
- Outbox re-drive: QUEUED tasks that never reached the broker (worker crash between the
  relational transition and broker enqueue, or Redis stream loss) are re-enqueued by the
  sweeper. PostgreSQL task ledger remains the business source of truth.
- Stream-level reclaim: pending messages stranded by crashed consumers are reclaimed via
  ``reclaim_expired`` and either executed (lease won) or acknowledged (lease lost), so
  at-least-once delivery never leaks pending entries.
"""
from __future__ import annotations

import os
import signal
import socket
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Optional

from sangyan.async_exec.models import AsyncTask, TaskStatus, TaskType
from sangyan.async_exec.queue import TaskQueue
from sangyan.async_exec.repository import AsyncTaskRepository
from sangyan.core.errors import (
    StaleRegionError,
)
from sangyan.core.logging import get_logger
from sangyan.domain.models import ContentItem
from sangyan.security.telemetry import MetricsRegistry
from sangyan.workflow.errors import (
    InvestigationCancelledError,
    ReviewConflictError,
)
from sangyan.workflow.service import WorkflowService

logger = get_logger("sangyan.async_exec.worker")


class AsyncInvestigationWorker:
    """Production asynchronous worker consuming tasks from Redis Streams with bounded leases.

    Enforces HITL decoupling: when an investigation reaches review_gate_node (AWAITING_REVIEW),
    the worker completes the task stage and frees capacity immediately. Resumption occurs via
    a separate WORKFLOW_RESUME task upon human supervisor action.
    """

    def __init__(
        self,
        queue: TaskQueue,
        repository: AsyncTaskRepository,
        workflow_service: WorkflowService,
        worker_id: Optional[str] = None,
        lease_duration_sec: float = 60.0,
        heartbeat_interval_sec: float = 15.0,
        metrics_registry: Optional[MetricsRegistry] = None,
        concurrency: int = 4,
        maintenance_interval_sec: float = 1.0,
        stale_queue_requeue_sec: float = 30.0,
    ) -> None:
        hostname = socket.gethostname()
        pid = os.getpid()
        self.worker_id = worker_id or f"worker-{hostname}-{pid}-{int(time.time() * 1000) % 10000}"
        self.queue = queue
        self.repository = repository
        self.workflow_service = workflow_service
        self.lease_duration_sec = lease_duration_sec
        self.heartbeat_interval_sec = heartbeat_interval_sec
        self.metrics = metrics_registry or MetricsRegistry.get_default()
        self.concurrency = max(1, int(concurrency))
        self.maintenance_interval_sec = max(0.1, float(maintenance_interval_sec))
        self.stale_queue_requeue_sec = max(1.0, float(stale_queue_requeue_sec))

        self._stop_event = threading.Event()
        self._inflight_lock = threading.Lock()
        self._inflight_task_ids: set[str] = set()
        self._heartbeat_stop_events: dict[str, threading.Event] = {}
        self._last_maintenance = 0.0
        self._executor: Optional[ThreadPoolExecutor] = None
        self._futures: set[Future] = set()
        self._futures_lock = threading.Lock()

    def stop(self) -> None:
        """Signal the worker to gracefully stop after in-flight tasks complete."""
        logger.info("Worker %s received stop signal. Initiating graceful shutdown...", self.worker_id)
        self._stop_event.set()

    def is_stopped(self) -> bool:
        return self._stop_event.is_set()

    def inflight_count(self) -> int:
        with self._inflight_lock:
            return len(self._inflight_task_ids)

    def run_forever(self, poll_interval_ms: int = 1000) -> None:
        """Main consumer loop; runs until stop() is invoked or SIGTERM received."""
        self._install_signal_handlers()
        logger.info(
            "Worker %s started; listening for stream tasks (concurrency=%d)...",
            self.worker_id,
            self.concurrency,
        )
        self._executor = ThreadPoolExecutor(
            max_workers=self.concurrency, thread_name_prefix="sangyan-task"
        )
        try:
            while not self._stop_event.is_set():
                try:
                    # 1. Periodic maintenance: lease recovery, retry sweeper, outbox re-drive
                    self._maybe_run_maintenance()

                    # 2. Respect bounded concurrency: pause claiming when saturated
                    if self.inflight_count() >= self.concurrency:
                        time.sleep(0.05)
                        continue

                    # 3. Claim tasks from broker consumer group
                    claimed = self.queue.claim_tasks(
                        consumer_name=self.worker_id,
                        batch_size=1,
                        block_ms=poll_interval_ms,
                    )

                    for msg_id, task in claimed:
                        if self._stop_event.is_set():
                            break
                        self._submit_task(msg_id, task)

                except Exception as exc:
                    logger.error("Unhandled exception in worker %s loop: %s", self.worker_id, exc)
                    time.sleep(1.0)
        finally:
            # Graceful drain: wait for in-flight tasks before releasing resources
            self._drain_inflight()
            if self._executor is not None:
                self._executor.shutdown(wait=True)
                self._executor = None
            logger.info("Worker %s graceful shutdown complete.", self.worker_id)

    def process_one_batch(self, batch_size: int = 1, block_ms: int = 100) -> int:
        """Process a single batch of tasks synchronously. Useful for tests and single-cycle execution."""
        self._maybe_run_maintenance()
        claimed = self.queue.claim_tasks(
            consumer_name=self.worker_id,
            batch_size=batch_size,
            block_ms=block_ms,
        )
        count = 0
        for msg_id, task in claimed:
            self._process_claimed_task(msg_id, task)
            count += 1
        return count

    # -------------------------------------------------------------------
    # Concurrency plumbing
    # -------------------------------------------------------------------

    def _submit_task(self, stream_msg_id: str, task: AsyncTask) -> None:
        """Submit claimed task to the bounded executor."""
        executor = self._executor
        if executor is None:  # Not running via run_forever (defensive)
            self._process_claimed_task(stream_msg_id, task)
            return

        with self._inflight_lock:
            self._inflight_task_ids.add(task.task_id)
        try:
            self.metrics.worker_inflight_tasks.set(self.inflight_count())
        except Exception:
            pass

        future = executor.submit(self._process_claimed_task, stream_msg_id, task)

        def _done(f: Future, task_id: str = task.task_id) -> None:
            exc = f.exception()
            if exc is not None:
                logger.error("Task %s executor crashed unexpectedly: %s", task_id, exc)
            with self._inflight_lock:
                self._inflight_task_ids.discard(task_id)
            with self._futures_lock:
                self._futures.discard(f)
            try:
                self.metrics.worker_inflight_tasks.set(self.inflight_count())
            except Exception:
                pass

        with self._futures_lock:
            self._futures.add(future)
        future.add_done_callback(_done)

    def _drain_inflight(self, timeout_sec: float = 120.0) -> None:
        """Wait for all in-flight tasks to finish (bounded)."""
        deadline = time.time() + timeout_sec
        while self.inflight_count() > 0 and time.time() < deadline:
            time.sleep(0.05)
        remaining = self.inflight_count()
        if remaining > 0:
            logger.warning(
                "Worker %s drained with %d task(s) still in flight; leases will expire for recovery.",
                self.worker_id,
                remaining,
            )

    # -------------------------------------------------------------------
    # Maintenance: lease recovery, retry sweeper, outbox re-drive
    # -------------------------------------------------------------------

    def _maybe_run_maintenance(self) -> None:
        now = time.time()
        if now - self._last_maintenance < self.maintenance_interval_sec:
            return
        self._last_maintenance = now
        try:
            self._check_and_reclaim_leases()
        except Exception as exc:
            logger.error("Error during expired lease check: %s", exc)
        try:
            self._requeue_due_retries()
        except Exception as exc:
            logger.error("Error during retry sweep: %s", exc)
        try:
            self._redrive_stale_queued()
        except Exception as exc:
            logger.error("Error during stale queue re-drive: %s", exc)
        try:
            self._publish_queue_depth()
        except Exception:
            pass

    def _check_and_reclaim_leases(self) -> None:
        """Recover crashed workers' tasks at both the relational and broker layer."""
        # 1. Broker-level reclaim of pending messages stranded by dead consumers
        try:
            min_idle_ms = int(self.lease_duration_sec * 1000) + 500
            stranded = self.queue.reclaim_expired(
                consumer_name=self.worker_id,
                min_idle_time_ms=min_idle_ms,
                batch_size=10,
            )
            for msg_id, task in stranded:
                self._handle_reclaimed_message(msg_id, task)
        except Exception as exc:
            logger.warning("Stream-level reclaim failed: %s", exc)

        # 2. Relational expired leases (crashed worker between claim and completion)
        expired = self.repository.find_expired_leases()
        for exp_task in expired:
            logger.warning(
                "Found expired lease for task %s (owner was %s); clearing for recovery",
                exp_task.task_id,
                exp_task.lease_owner,
            )
            try:
                self.repository.fail_or_retry_task(
                    task_id=exp_task.task_id,
                    worker_id=exp_task.lease_owner or "unknown",
                    error_message="Worker lease expired without completion",
                    is_transient=True,
                )
                try:
                    self.metrics.task_lease_expirations_total.inc()
                except Exception:
                    pass
            except Exception as exc:
                logger.error("Failed to recover expired lease for task %s: %s", exp_task.task_id, exc)

    def _handle_reclaimed_message(self, msg_id: str, task: AsyncTask) -> None:
        """Process a stream message stranded by a dead consumer.

        The atomic relational lease inside ``_process_claimed_task`` arbitrates:
        the winner executes; losers acknowledge the stranded duplicate so the
        pending list drains without duplicate business effects.
        """
        fresh = self.repository.get_task_or_none(task.task_id)
        if fresh is None:
            self.queue.ack(msg_id)
            return

        if fresh.is_terminal():
            self.queue.ack(msg_id)
            return

        if fresh.status == TaskStatus.RETRY_WAIT:
            # Retry sweeper owns re-delivery timing; drop stranded duplicate.
            self.queue.ack(msg_id)
            return

        logger.info("Reclaiming stranded task %s from stream after worker crash", fresh.task_id)
        self._process_claimed_task(msg_id, fresh)

    def _requeue_due_retries(self) -> None:
        """Re-drive RETRY_WAIT tasks whose backoff deadline has elapsed (crash-safe retry scheduling)."""
        due = self.repository.find_retry_due_tasks(limit=50)
        for task in due:
            if self.repository.mark_retry_requeued(task.task_id):
                refreshed = self.repository.get_task_or_none(task.task_id)
                if refreshed is not None:
                    logger.info("Retry sweeper re-queuing task %s (attempt %d)", task.task_id, task.retry_count)
                    self.queue.enqueue(refreshed)

    def _redrive_stale_queued(self) -> None:
        """Re-enqueue QUEUED tasks that never reached the broker (outbox re-drive after crash or Redis loss)."""
        stale = self.repository.find_stale_queued_tasks(older_than_sec=self.stale_queue_requeue_sec)
        for task in stale:
            logger.warning("Outbox re-drive: re-enqueuing stale QUEUED task %s", task.task_id)
            self.queue.enqueue(task)

    def _publish_queue_depth(self) -> None:
        """Publish queue saturation telemetry: depth by status, oldest task age, broker backlog."""
        counts = self.repository.count_tasks_by_status()
        for status_name in TaskStatus.ALL:
            self.metrics.task_queue_depth.labels(status=status_name).set(counts.get(status_name, 0))

        # Oldest deliverable task age (QUEUED or RETRY_WAIT) - saturation early-warning
        try:
            row = self.repository._db.query_one(
                "SELECT MIN(updated_at) AS oldest FROM sangyan_async_tasks WHERE status IN (?,?)",
                (TaskStatus.QUEUED, TaskStatus.RETRY_WAIT),
            )
            oldest = row.get("oldest") if row else None
            age = max(0.0, time.time() - float(oldest)) if oldest is not None else 0.0
            self.metrics.task_oldest_queued_seconds.set(age)
        except Exception:
            pass

        # Broker pending entries (stream backlog) when the queue exposes it
        pending_fn = getattr(self.queue, "pending_count", None)
        if callable(pending_fn):
            try:
                self.metrics.task_stream_pending.set(pending_fn())
            except Exception:
                pass

    # -------------------------------------------------------------------
    # Task execution
    # -------------------------------------------------------------------

    def _process_claimed_task(self, stream_msg_id: str, task: AsyncTask) -> None:
        """Execute a single task under relational lease and lease heartbeat."""
        task_id = task.task_id

        # 1. Acquire atomic relational lease in sangyan_async_tasks
        acquired = self.repository.acquire_lease(
            task_id=task_id,
            worker_id=self.worker_id,
            lease_duration_sec=self.lease_duration_sec,
        )
        if not acquired:
            # Lease could not be acquired (e.g. another worker already running, or already completed)
            logger.info("Worker %s skipping task %s (lease already held or completed)", self.worker_id, task_id)
            self.queue.ack(stream_msg_id)
            return

        with self._inflight_lock:
            self._inflight_task_ids.add(task_id)

        # Start heartbeat
        heartbeat_stop = threading.Event()
        with self._inflight_lock:
            self._heartbeat_stop_events[task_id] = heartbeat_stop
        hb_thread = threading.Thread(
            target=self._lease_heartbeat_loop,
            args=(task_id, heartbeat_stop),
            daemon=True,
        )
        hb_thread.start()

        start_time = time.time()
        try:
            logger.info("Worker %s executing task %s (type=%s)", self.worker_id, task_id, task.task_type)
            result = self._execute_task_payload(task)

            # Mark task SUCCEEDED in relational ledger
            self.repository.complete_task(task_id, self.worker_id, result)
            self.queue.ack(stream_msg_id)
            try:
                self.metrics.task_execution_seconds.observe(max(0.0, time.time() - start_time))
                self.metrics.tasks_total.labels(task_type=task.task_type, status=TaskStatus.SUCCEEDED).inc()
            except Exception:
                pass
            logger.info("Worker %s completed task %s successfully", self.worker_id, task_id)

        except StaleRegionError as stale_err:
            # Fenced or standby region: do not retry immediately; fail closed
            logger.error("Task %s rejected due to stale region: %s", task_id, stale_err)
            updated = self.repository.fail_or_retry_task(task_id, self.worker_id, str(stale_err), is_transient=False)
            try:
                self.metrics.tasks_total.labels(task_type=task.task_type, status=TaskStatus.DEAD_LETTERED).inc()
            except Exception:
                pass
            self.queue.dead_letter(updated, reason=str(stale_err), stream_message_id=stream_msg_id)

        except (ReviewConflictError, InvestigationCancelledError) as biz_err:
            logger.warning("Task %s encountered business conflict: %s", task_id, biz_err)
            updated = self.repository.fail_or_retry_task(task_id, self.worker_id, str(biz_err), is_transient=False)
            try:
                self.metrics.tasks_total.labels(task_type=task.task_type, status=TaskStatus.DEAD_LETTERED).inc()
            except Exception:
                pass
            self.queue.dead_letter(updated, reason=str(biz_err), stream_message_id=stream_msg_id)

        except Exception as exc:
            logger.error("Task %s failed during execution: %s", task_id, exc)
            updated_task = self.repository.fail_or_retry_task(
                task_id,
                self.worker_id,
                error_message=str(exc),
                is_transient=True,
            )
            if updated_task.status == TaskStatus.DEAD_LETTERED:
                try:
                    self.metrics.task_dead_letters_total.labels(task_type=task.task_type).inc()
                    self.metrics.tasks_total.labels(task_type=task.task_type, status=TaskStatus.DEAD_LETTERED).inc()
                except Exception:
                    pass
                self.queue.dead_letter(updated_task, reason=str(exc), stream_message_id=stream_msg_id)
            else:
                # Task transitioned to RETRY_WAIT with explicit next_attempt_at.
                # Acknowledge the current message; the relational retry sweeper
                # re-drives delivery after backoff (crash-safe, non-blocking).
                self.queue.ack(stream_msg_id)
                try:
                    self.metrics.task_retries_total.labels(task_type=task.task_type).inc()
                    self.metrics.tasks_total.labels(task_type=task.task_type, status=TaskStatus.RETRY_WAIT).inc()
                except Exception:
                    pass

        finally:
            heartbeat_stop.set()
            hb_thread.join(timeout=1.0)
            with self._inflight_lock:
                self._inflight_task_ids.discard(task_id)
                self._heartbeat_stop_events.pop(task_id, None)

    def _execute_task_payload(self, task: AsyncTask) -> dict[str, Any]:
        """Dispatch task to appropriate workflow service method based on task_type."""
        payload = task.payload

        if task.task_type == TaskType.WORKFLOW_START:
            raw_contents = payload.get("contents", [])
            from sangyan.domain.models import normalize_content_type

            content_type = normalize_content_type(payload.get("content_type", "text"))
            items = [
                ContentItem(
                    organization_id=task.organization_id,
                    content_type=content_type,
                    raw_content=c,
                )
                for c in raw_contents
            ]
            require_review = bool(payload.get("require_review", False))
            meta = payload.get("metadata", {})

            state = self.workflow_service.start_investigation(
                content_items=items,
                user_id=task.user_id,
                organization_id=task.organization_id,
                run_id=payload.get("run_id"),
                require_review=require_review,
                metadata=meta,
            )

            # HITL Decoupling check:
            # If status is AWAITING_REVIEW, workflow stage 1 is complete!
            # Return status and investigation identifiers so worker exits cleanly.
            inv_id = state.get("investigation_id", task.investigation_id)
            st = state.get("status", "COMPLETED")
            return {
                "status": st,
                "investigation_id": inv_id,
                "thread_id": state.get("thread_id"),
                "findings_count": len(state.get("findings", [])),
                "trust_receipt_id": state.get("trust_receipt_id"),
            }

        elif task.task_type == TaskType.WORKFLOW_RESUME:
            inv_id = payload.get("investigation_id", task.investigation_id)
            action = payload.get("review_action") or payload.get("action")
            reason = payload.get("reason", "")
            finding_id = payload.get("finding_id")

            state = self.workflow_service.resume_investigation(
                investigation_id=inv_id,
                review_action=action,
                user_id=task.user_id,
                organization_id=task.organization_id,
                reason=reason,
                finding_id=finding_id,
            )
            return {
                "status": state.get("status", "COMPLETED"),
                "investigation_id": inv_id,
                "trust_receipt_id": state.get("trust_receipt_id"),
            }

        elif task.task_type == TaskType.WORKFLOW_CANCEL:
            inv_id = payload.get("investigation_id", task.investigation_id)
            reason = payload.get("reason", "")
            self.workflow_service.cancel_investigation(
                investigation_id=inv_id,
                user_id=task.user_id,
                organization_id=task.organization_id,
                reason=reason,
            )
            return {
                "status": "CANCELLED",
                "investigation_id": inv_id,
            }

        else:
            raise ValueError(f"Unknown task_type: {task.task_type}")

    def _lease_heartbeat_loop(self, task_id: str, stop_signal: threading.Event) -> None:
        """Periodically renew lease in sangyan_async_tasks while execution is active."""
        while not stop_signal.is_set():
            stop_signal.wait(timeout=self.heartbeat_interval_sec)
            if stop_signal.is_set():
                break
            try:
                renewed = self.repository.renew_lease(
                    task_id=task_id,
                    worker_id=self.worker_id,
                    lease_duration_sec=self.lease_duration_sec,
                )
                if not renewed:
                    logger.warning("Heartbeat failed to renew lease for task %s (worker %s)", task_id, self.worker_id)
            except Exception as exc:
                logger.error("Error during lease heartbeat for task %s: %s", task_id, exc)

    def _install_signal_handlers(self) -> None:
        def _handle_term(signum, frame):
            logger.info("Worker received signal %d; shutting down...", signum)
            self.stop()

        try:
            signal.signal(signal.SIGTERM, _handle_term)
            signal.signal(signal.SIGINT, _handle_term)
        except (ValueError, AttributeError):
            pass  # May fail if not in main thread (e.g. during test fixtures)
