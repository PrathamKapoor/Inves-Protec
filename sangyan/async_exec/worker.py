"""Asynchronous task execution worker with bounded leasing, HITL decoupling, and failure recovery."""
from __future__ import annotations

import json
import os
import signal
import socket
import sys
import threading
import time
from typing import Any, Optional

from sangyan.async_exec.models import AsyncTask, TaskStatus, TaskType
from sangyan.async_exec.queue import TaskQueue
from sangyan.async_exec.repository import AsyncTaskRepository
from sangyan.core.errors import (
    StaleRegionError,
    StorageError,
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

        self._stop_event = threading.Event()
        self._current_task_id: Optional[str] = None
        self._current_task_lock = threading.Lock()
        self._heartbeat_thread: Optional[threading.Thread] = None

    def stop(self) -> None:
        """Signal the worker to gracefully stop after current task completes."""
        logger.info("Worker %s received stop signal. Initiating graceful shutdown...", self.worker_id)
        self._stop_event.set()

    def is_stopped(self) -> bool:
        return self._stop_event.is_set()

    def run_forever(self, poll_interval_ms: int = 1000) -> None:
        """Main consumer loop; runs until stop() is invoked or SIGTERM received."""
        self._install_signal_handlers()
        logger.info("Worker %s started; listening for stream tasks...", self.worker_id)

        last_reclaim_check = 0.0
        reclaim_interval_sec = 30.0

        while not self._stop_event.is_set():
            try:
                # 1. Periodically check and reclaim expired leases
                now = time.time()
                if now - last_reclaim_check >= reclaim_interval_sec:
                    self._check_and_reclaim_leases()
                    last_reclaim_check = now

                # 2. Claim tasks from broker consumer group
                claimed = self.queue.claim_tasks(
                    consumer_name=self.worker_id,
                    batch_size=1,
                    block_ms=poll_interval_ms,
                )

                if not claimed:
                    continue

                for msg_id, task in claimed:
                    if self._stop_event.is_set():
                        break
                    self._process_claimed_task(msg_id, task)

            except Exception as exc:
                logger.error("Unhandled exception in worker %s loop: %s", self.worker_id, exc)
                time.sleep(1.0)

        logger.info("Worker %s graceful shutdown complete.", self.worker_id)

    def process_one_batch(self, batch_size: int = 1, block_ms: int = 100) -> int:
        """Process a single batch of tasks. Useful for tests and single-cycle execution."""
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

        with self._current_task_lock:
            self._current_task_id = task_id

        # Start heartbeat
        heartbeat_stop = threading.Event()
        hb_thread = threading.Thread(
            target=self._lease_heartbeat_loop,
            args=(task_id, heartbeat_stop),
            daemon=True,
        )
        hb_thread.start()

        try:
            logger.info("Worker %s executing task %s (type=%s)", self.worker_id, task_id, task.task_type)
            result = self._execute_task_payload(task)

            # Mark task SUCCEEDED in relational ledger
            self.repository.complete_task(task_id, self.worker_id, result)
            self.queue.ack(stream_msg_id)
            logger.info("Worker %s completed task %s successfully", self.worker_id, task_id)

        except StaleRegionError as stale_err:
            # Fenced or standby region: do not retry immediately; fail closed
            logger.error("Task %s rejected due to stale region: %s", task_id, stale_err)
            self.repository.fail_or_retry_task(task_id, self.worker_id, str(stale_err), is_transient=False)
            self.queue.dead_letter(task, reason=str(stale_err), stream_message_id=stream_msg_id)

        except (ReviewConflictError, InvestigationCancelledError) as biz_err:
            logger.warning("Task %s encountered business conflict: %s", task_id, biz_err)
            self.repository.fail_or_retry_task(task_id, self.worker_id, str(biz_err), is_transient=False)
            self.queue.dead_letter(task, reason=str(biz_err), stream_message_id=stream_msg_id)

        except Exception as exc:
            logger.error("Task %s failed during execution: %s", task_id, exc)
            updated_task = self.repository.fail_or_retry_task(
                task_id,
                self.worker_id,
                error_message=str(exc),
                is_transient=True,
            )
            if updated_task.status == TaskStatus.DEAD_LETTERED:
                self.queue.dead_letter(updated_task, reason=str(exc), stream_message_id=stream_msg_id)
            else:
                # Task transitioned to RETRY_WAIT; re-enqueue into broker stream with backoff
                self.queue.ack(stream_msg_id)
                backoff_delay = updated_task.compute_backoff_delay()
                logger.info("Task %s scheduled for retry in %.2fs (attempt %d/%d)",
                            task_id, backoff_delay, updated_task.retry_count, updated_task.max_retries)
                time.sleep(backoff_delay)
                self.queue.enqueue(updated_task)

        finally:
            heartbeat_stop.set()
            hb_thread.join(timeout=1.0)
            with self._current_task_lock:
                self._current_task_id = None

    def _execute_task_payload(self, task: AsyncTask) -> dict[str, Any]:
        """Dispatch task to appropriate workflow service method based on task_type."""
        payload = task.payload

        if task.task_type == TaskType.WORKFLOW_START:
            raw_contents = payload.get("contents", [])
            content_type = payload.get("content_type", "TEXT")
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
            inv = self.workflow_service.cancel_investigation(
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

    def _check_and_reclaim_leases(self) -> None:
        """Check for expired leases and return them to the stream or re-claim."""
        try:
            expired = self.repository.find_expired_leases()
            for exp_task in expired:
                logger.warning("Found expired lease for task %s (owner was %s); clearing for recovery",
                               exp_task.task_id, exp_task.lease_owner)
                self.repository.fail_or_retry_task(
                    task_id=exp_task.task_id,
                    worker_id=exp_task.lease_owner or "unknown",
                    error_message="Worker lease expired without completion",
                    is_transient=True,
                )
        except Exception as exc:
            logger.error("Error during expired lease check: %s", exc)

    def _install_signal_handlers(self) -> None:
        def _handle_term(signum, frame):
            logger.info("Worker received signal %d; shutting down...", signum)
            self.stop()

        try:
            signal.signal(signal.SIGTERM, _handle_term)
            signal.signal(signal.SIGINT, _handle_term)
        except (ValueError, AttributeError):
            pass  # May fail if not in main thread (e.g. during test fixtures)
