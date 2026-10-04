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
from sangyan.database.engine import DatabaseEngine


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
                lease_owner, lease_expires_at, created_at, updated_at, completed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                SET status=?, lease_owner=?, lease_expires_at=?, updated_at=?
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
            SET status=?, result=?, lease_owner=NULL, lease_expires_at=NULL,
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
        """Record task failure; transition to RETRY_WAIT (if retries remain) or DEAD_LETTERED."""
        now = time.time()
        with self._db.transaction():
            task = self.get_task(task_id)
            new_retry_count = task.retry_count + 1

            if is_transient and new_retry_count <= task.max_retries:
                target_status = TaskStatus.RETRY_WAIT
                # Clear lease so worker/backoff can re-claim
                self._db.execute(
                    """
                    UPDATE sangyan_async_tasks
                    SET status=?, error_message=?, retry_count=?, lease_owner=NULL,
                        lease_expires_at=NULL, updated_at=?
                    WHERE task_id=?
                    """,
                    (target_status, error_message, new_retry_count, now, task_id),
                )
            else:
                target_status = TaskStatus.DEAD_LETTERED
                self._db.execute(
                    """
                    UPDATE sangyan_async_tasks
                    SET status=?, error_message=?, retry_count=?, lease_owner=NULL,
                        lease_expires_at=NULL, updated_at=?, completed_at=?
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
                    updated_at=?, completed_at=NULL
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
