"""Relational persistence repository for asynchronous tasks and execution outbox."""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from sangyan.async_exec.models import AsyncTask, TaskStatus
from sangyan.core.errors import (
    DomainValidationError,
    DuplicateEntryError,
    InvalidStateTransitionError,
    NotFoundError,
    TaskNotFoundError,
)
from sangyan.core.logging import get_logger
from sangyan.database.engine import DatabaseEngine

logger = get_logger("sangyan.async_exec.repository")


class AsyncTaskRepository:
    """Database repository for durable task lifecycle and atomic lease management."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._db = engine

    def save_task(self, task: AsyncTask) -> str:
        """Persist a newly created task into sangyan_async_tasks."""
        errors = task.validate()
        if errors:
            raise DomainValidationError(f"Invalid async task: {errors}", errors=errors)

        now = time.time()
        task.created_at = task.created_at or now
        task.updated_at = now

        self._db.execute(
            """
            INSERT INTO sangyan_async_tasks (
                task_id, organization_id, user_id, investigation_id, task_type,
                status, payload, result, error_message, retry_count, max_retries,
                lease_owner, lease_expires_at, next_attempt_at,
                created_at, updated_at, completed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                task.task_id,
                task.organization_id,
                task.user_id,
                task.investigation_id,
                task.task_type,
                task.status,
                json.dumps(task.payload),
                json.dumps(task.result) if task.result is not None else None,
                task.error_message,
                task.retry_count,
                task.max_retries,
                task.lease_owner,
                task.lease_expires_at,
                task.next_attempt_at,
                task.created_at,
                task.updated_at,
                task.completed_at,
            ),
        )
        return task.task_id

    def create_task(
        self,
        task_id: str,
        organization_id: str,
        user_id: str,
        investigation_id: str,
        task_type: str,
        payload: Optional[dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> AsyncTask:
        """Create and persist a new async task record."""
        task = AsyncTask(
            task_id=task_id,
            organization_id=organization_id,
            user_id=user_id,
            investigation_id=investigation_id,
            task_type=task_type,
            payload=payload or {},
            max_retries=max_retries,
        )
        self.save_task(task)
        return task

    def get_task(self, task_id: str, organization_id: Optional[str] = None) -> AsyncTask:
        """Fetch an async task by ID with optional tenant isolation check."""
        if organization_id:
            row = self._db.query_one(
                "SELECT * FROM sangyan_async_tasks WHERE task_id=? AND organization_id=?",
                (task_id, organization_id),
            )
        else:
            row = self._db.query_one(
                "SELECT * FROM sangyan_async_tasks WHERE task_id=?",
                (task_id,),
            )

        if row is None:
            raise TaskNotFoundError(f"Async task '{task_id}' not found")
        return AsyncTask.from_dict(row)

    def get_task_or_none(self, task_id: str, organization_id: Optional[str] = None) -> Optional[AsyncTask]:
        try:
            return self.get_task(task_id, organization_id=organization_id)
        except TaskNotFoundError:
            return None

    def acquire_lease(
        self,
        task_id: str,
        worker_id: str,
        lease_duration_sec: float = 60.0,
    ) -> bool:
        """Atomically acquire execution lease on a task if it is QUEUED, RETRY_WAIT, or has an expired lease."""
        now = time.time()
        new_expires_at = now + lease_duration_sec

        # Can acquire if:
        # 1. status in ('QUEUED', 'RETRY_WAIT')
        # 2. OR status in ('LEASED', 'RUNNING') but lease_expires_at < now
        with self._db.transaction():
            row = self._db.query_one(
                "SELECT status, lease_owner, lease_expires_at FROM sangyan_async_tasks WHERE task_id=?",
                (task_id,),
            )
            if row is None:
                return False

            status = row["status"]
            expires_at = float(row["lease_expires_at"]) if row["lease_expires_at"] is not None else 0.0

            can_acquire = False
            if status in (TaskStatus.QUEUED, TaskStatus.RETRY_WAIT):
                can_acquire = True
            elif status in (TaskStatus.LEASED, TaskStatus.RUNNING) and expires_at < now:
                can_acquire = True

            if not can_acquire:
                return False

            rowcount = self._db.execute(
                """
                UPDATE sangyan_async_tasks
                SET status=?, lease_owner=?, lease_expires_at=?, next_attempt_at=NULL, updated_at=?
                WHERE task_id=? AND (status IN (?,?) OR lease_expires_at < ?)
                """,
                (
                    TaskStatus.RUNNING,
                    worker_id,
                    new_expires_at,
                    now,
                    task_id,
                    TaskStatus.QUEUED,
                    TaskStatus.RETRY_WAIT,
                    now,
                ),
            )
            return rowcount > 0

    def renew_lease(
        self,
        task_id: str,
        worker_id: str,
        lease_duration_sec: float = 60.0,
    ) -> bool:
        """Renew active lease for worker heartbeat."""
        now = time.time()
        new_expires_at = now + lease_duration_sec

        rowcount = self._db.execute(
            """
            UPDATE sangyan_async_tasks
            SET lease_expires_at=?, updated_at=?
            WHERE task_id=? AND lease_owner=? AND status=? AND lease_expires_at >= ?
            """,
            (new_expires_at, now, task_id, worker_id, TaskStatus.RUNNING, now),
        )
        return rowcount > 0

    def complete_task(
        self,
        task_id: str,
        worker_id: str,
        result: dict[str, Any],
    ) -> bool:
        """Mark task as SUCCEEDED with result and clear lease."""
        now = time.time()
        rowcount = self._db.execute(
            """
            UPDATE sangyan_async_tasks
            SET status=?, result=?, lease_owner=NULL, lease_expires_at=NULL, next_attempt_at=NULL,
                updated_at=?, completed_at=?
            WHERE task_id=? AND (lease_owner=? OR lease_owner IS NULL) AND status=?
            """,
            (
                TaskStatus.SUCCEEDED,
                json.dumps(result),
                now,
                now,
                task_id,
                worker_id,
                TaskStatus.RUNNING,
            ),
        )
        return rowcount > 0

    def fail_or_retry_task(
        self,
        task_id: str,
        worker_id: str,
        error_message: str,
        is_transient: bool = True,
    ) -> AsyncTask:
        """Record task failure; transition to RETRY_WAIT (if retries remain) or DEAD_LETTERED.

        Transient failures persist an explicit ``next_attempt_at`` retry deadline so a
        relational sweeper can re-drive delivery without any worker blocking inline or
        holding crash-unsafe in-process timers.
        """
        now = time.time()
        with self._db.transaction():
            task = self.get_task(task_id)
            new_retry_count = task.retry_count + 1

            if is_transient and new_retry_count <= task.max_retries:
                target_status = TaskStatus.RETRY_WAIT
                backoff_delay = task.compute_backoff_delay()
                next_attempt_at = now + backoff_delay
                # Clear lease so any worker/sweeper can re-drive after backoff
                self._db.execute(
                    """
                    UPDATE sangyan_async_tasks
                    SET status=?, error_message=?, retry_count=?, lease_owner=NULL,
                        lease_expires_at=NULL, next_attempt_at=?, updated_at=?
                    WHERE task_id=?
                    """,
                    (target_status, error_message, new_retry_count, next_attempt_at, now, task_id),
                )
                logger.info(
                    "Task %s failed transiently; retry %d/%d scheduled in %.2fs",
                    task_id, new_retry_count, task.max_retries, backoff_delay,
                )
            else:
                target_status = TaskStatus.DEAD_LETTERED
                self._db.execute(
                    """
                    UPDATE sangyan_async_tasks
                    SET status=?, error_message=?, retry_count=?, lease_owner=NULL,
                        lease_expires_at=NULL, next_attempt_at=NULL, updated_at=?, completed_at=?
                    WHERE task_id=?
                    """,
                    (target_status, error_message, new_retry_count, now, now, task_id),
                )

            task.status = target_status
            task.error_message = error_message
            task.retry_count = new_retry_count
            task.lease_owner = None
            task.lease_expires_at = None
            task.updated_at = now
            if target_status == TaskStatus.RETRY_WAIT:
                task.next_attempt_at = next_attempt_at
            else:
                task.next_attempt_at = None
            if target_status == TaskStatus.DEAD_LETTERED:
                task.completed_at = now
            return task

    def retry_dead_letter_task(self, task_id: str, organization_id: Optional[str] = None) -> AsyncTask:
        """Manually or administratively re-queue a DEAD_LETTERED task."""
        now = time.time()
        with self._db.transaction():
            task = self.get_task(task_id, organization_id=organization_id)
            if task.status != TaskStatus.DEAD_LETTERED:
                raise InvalidStateTransitionError(
                    f"Only DEAD_LETTERED tasks can be retried; task '{task_id}' is in status '{task.status}'"
                )

            self._db.execute(
                """
                UPDATE sangyan_async_tasks
                SET status=?, retry_count=0, error_message=NULL, lease_owner=NULL, lease_expires_at=NULL,
                    next_attempt_at=NULL, updated_at=?, completed_at=NULL
                WHERE task_id=?
                """,
                (TaskStatus.QUEUED, now, task_id),
            )
            task.status = TaskStatus.QUEUED
            task.retry_count = 0
            task.error_message = None
            task.lease_owner = None
            task.lease_expires_at = None
            task.updated_at = now
            task.completed_at = None
            return task

    def cancel_task(self, task_id: str, organization_id: Optional[str] = None, reason: str = "") -> AsyncTask:
        """Cancel an in-flight or queued task."""
        now = time.time()
        with self._db.transaction():
            task = self.get_task(task_id, organization_id=organization_id)
            if task.is_terminal():
                raise InvalidStateTransitionError(
                    f"Cannot cancel task '{task_id}' in terminal status '{task.status}'"
                )

            error_msg = f"Task cancelled: {reason}" if reason else "Task cancelled"
            self._db.execute(
                """
                UPDATE sangyan_async_tasks
                SET status=?, error_message=?, lease_owner=NULL, lease_expires_at=NULL,
                    updated_at=?, completed_at=?
                WHERE task_id=?
                """,
                (TaskStatus.CANCELLED, error_msg, now, now, task_id),
            )
            task.status = TaskStatus.CANCELLED
            task.error_message = error_msg
            task.lease_owner = None
            task.lease_expires_at = None
            task.updated_at = now
            task.completed_at = now
            return task

    def list_tasks(
        self,
        organization_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AsyncTask]:
        """List tasks with pagination and optional status / organization filters."""
        query = "SELECT * FROM sangyan_async_tasks WHERE 1=1"
        params: list[Any] = []

        if organization_id:
            query += " AND organization_id=?"
            params.append(organization_id)
        if status:
            query += " AND status=?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._db.query_all(query, tuple(params))
        return [AsyncTask.from_dict(r) for r in rows]

    def list_dead_letter(
        self,
        organization_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[AsyncTask]:
        """Query dead-lettered tasks."""
        return self.list_tasks(
            organization_id=organization_id,
            status=TaskStatus.DEAD_LETTERED,
            limit=limit,
        )

    def find_expired_leases(self, now: Optional[float] = None) -> list[AsyncTask]:
        """Find active tasks whose lease has expired for recovery."""
        current = now if now is not None else time.time()
        rows = self._db.query_all(
            """
            SELECT * FROM sangyan_async_tasks
            WHERE status IN (?,?) AND lease_expires_at < ?
            ORDER BY lease_expires_at ASC LIMIT 50
            """,
            (TaskStatus.LEASED, TaskStatus.RUNNING, current),
        )
        return [AsyncTask.from_dict(r) for r in rows]

    def find_retry_due_tasks(self, now: Optional[float] = None, limit: int = 50) -> list[AsyncTask]:
        """Find RETRY_WAIT tasks whose backoff deadline has elapsed and require re-delivery."""
        current = now if now is not None else time.time()
        rows = self._db.query_all(
            """
            SELECT * FROM sangyan_async_tasks
            WHERE status=? AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
            ORDER BY next_attempt_at ASC LIMIT ?
            """,
            (TaskStatus.RETRY_WAIT, current, limit),
        )
        return [AsyncTask.from_dict(r) for r in rows]

    def mark_retry_requeued(self, task_id: str, now: Optional[float] = None) -> bool:
        """Atomically flip a due RETRY_WAIT task to QUEUED so exactly one sweeper re-enqueues it.

        Returns True only for the winning caller; losing racers observe rowcount 0 and skip.
        """
        current = now if now is not None else time.time()
        rowcount = self._db.execute(
            """
            UPDATE sangyan_async_tasks
            SET status=?, updated_at=?
            WHERE task_id=? AND status=? AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
            """,
            (TaskStatus.QUEUED, current, task_id, TaskStatus.RETRY_WAIT, current),
        )
        return rowcount > 0

    def find_stale_queued_tasks(self, older_than_sec: float = 30.0, limit: int = 50) -> list[AsyncTask]:
        """Find QUEUED tasks never delivered to the broker (outbox re-drive).

        Covers worker crashes between relational QUEUED transition and broker enqueue,
        and re-drives task ledger truth after Redis stream loss.
        """
        now = time.time()
        rows = self._db.query_all(
            """
            SELECT * FROM sangyan_async_tasks
            WHERE status=? AND updated_at <= ? AND (lease_expires_at IS NULL OR lease_expires_at < ?)
            ORDER BY updated_at ASC LIMIT ?
            """,
            (TaskStatus.QUEUED, now - older_than_sec, now, limit),
        )
        return [AsyncTask.from_dict(r) for r in rows]

    def count_outstanding_tasks(
        self,
        organization_id: Optional[str] = None,
        now: Optional[float] = None,
    ) -> int:
        """Count non-terminal (in-flight or awaiting delivery) tasks, optionally per tenant."""
        current = now if now is not None else time.time()
        query = """
            SELECT COUNT(*) AS n FROM sangyan_async_tasks
            WHERE status IN (?,?,?,?,?)
              AND (lease_expires_at IS NULL OR lease_expires_at >= ?)
        """
        params: list[Any] = [
            TaskStatus.QUEUED,
            TaskStatus.LEASED,
            TaskStatus.RUNNING,
            TaskStatus.RETRY_WAIT,
            TaskStatus.FAILED,
            current,
        ]
        if organization_id:
            query += " AND organization_id=?"
            params.append(organization_id)
        row = self._db.query_one(query, tuple(params))
        return int(row["n"]) if row else 0

    def count_tasks_by_status(self, organization_id: Optional[str] = None) -> dict[str, int]:
        """Aggregate task counts per status for queue-depth telemetry."""
        query = "SELECT status, COUNT(*) AS n FROM sangyan_async_tasks"
        params: list[Any] = []
        if organization_id:
            query += " WHERE organization_id=?"
            params.append(organization_id)
        query += " GROUP BY status"
        rows = self._db.query_all(query, tuple(params))
        return {r["status"]: int(r["n"]) for r in rows}

    # Statuses eligible for operational-telemetry retention pruning.
    # DEAD_LETTERED is NEVER auto-prunable (investigation/quarantine evidence);
    # non-terminal statuses are never prunable (work in flight).
    PRUNEABLE_STATUSES = (TaskStatus.SUCCEEDED, TaskStatus.CANCELLED)

    def prune_tasks(
        self,
        older_than_days: float,
        status: Optional[str] = None,
        organization_id: Optional[str] = None,
        limit: int = 1000,
    ) -> int:
        """Delete terminal task ledger rows older than the retention window.

        Restricts to terminal operational statuses (SUCCEEDED/CANCELLED by
        default). Dead-lettered tasks and audit records are never removed by
        this path; investigation evidence lives in separate tables untouched
        by retention.
        """
        statuses = (status,) if status else self.PRUNEABLE_STATUSES
        for s in statuses:
            if s not in self.PRUNEABLE_STATUSES:
                raise DomainValidationError(
                    f"Refusing to prune status '{s}': only {self.PRUNEABLE_STATUSES} are retention-prunable. "
                    "Dead-lettered tasks are quarantine evidence and audit events are cryptographic records."
                )

        cutoff = time.time() - max(0.0, older_than_days) * 86400.0
        deleted = 0
        for s in statuses:
            # Portable bounded delete (works on SQLite and PostgreSQL without
            # dialect-specific DELETE ... LIMIT syntax).
            select_sql = (
                "SELECT task_id FROM sangyan_async_tasks "
                "WHERE status=? AND completed_at IS NOT NULL AND completed_at <= ?"
            )
            select_params: list[Any] = [s, cutoff]
            if organization_id:
                select_sql += " AND organization_id=?"
                select_params.append(organization_id)
            select_sql += " LIMIT ?"
            select_params.append(limit)
            rows = self._db.query_all(select_sql, tuple(select_params))
            for row in rows:
                deleted += int(
                    self._db.execute(
                        "DELETE FROM sangyan_async_tasks WHERE task_id=?", (row["task_id"],)
                    )
                )
        return deleted
