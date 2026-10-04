"""Domain models, state machine transitions, and serialization for asynchronous tasks."""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from sangyan.core.errors import InvalidStateTransitionError


class TaskStatus:
    QUEUED = "QUEUED"
    LEASED = "LEASED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    RETRY_WAIT = "RETRY_WAIT"
    FAILED = "FAILED"
    DEAD_LETTERED = "DEAD_LETTERED"
    CANCELLED = "CANCELLED"

    ALL = (
        QUEUED,
        LEASED,
        RUNNING,
        SUCCEEDED,
        RETRY_WAIT,
        FAILED,
        DEAD_LETTERED,
        CANCELLED,
    )
    TERMINAL = (SUCCEEDED, DEAD_LETTERED, CANCELLED)


class TaskType:
    WORKFLOW_START = "WORKFLOW_START"
    WORKFLOW_RESUME = "WORKFLOW_RESUME"
    WORKFLOW_CANCEL = "WORKFLOW_CANCEL"

    ALL = (WORKFLOW_START, WORKFLOW_RESUME, WORKFLOW_CANCEL)


VALID_TASK_TRANSITIONS: dict[str, set[str]] = {
    TaskStatus.QUEUED: {
        TaskStatus.LEASED,
        TaskStatus.RUNNING,
        TaskStatus.CANCELLED,
    },
    TaskStatus.LEASED: {
        TaskStatus.RUNNING,
        TaskStatus.QUEUED,
        TaskStatus.RETRY_WAIT,
        TaskStatus.FAILED,
        TaskStatus.DEAD_LETTERED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.RUNNING: {
        TaskStatus.SUCCEEDED,
        TaskStatus.RETRY_WAIT,
        TaskStatus.FAILED,
        TaskStatus.DEAD_LETTERED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.RETRY_WAIT: {
        TaskStatus.QUEUED,
        TaskStatus.LEASED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.FAILED: {
        TaskStatus.RETRY_WAIT,
        TaskStatus.DEAD_LETTERED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.DEAD_LETTERED: {
        TaskStatus.QUEUED,  # manual/administrative re-queue
    },
    TaskStatus.SUCCEEDED: set(),
    TaskStatus.CANCELLED: set(),
}


@dataclass
class AsyncTask:
    """Relational task record tracking lifecycle, leasing, retries, and results."""

    task_id: str
    organization_id: str
    user_id: str
    investigation_id: str
    task_type: str
    status: str = TaskStatus.QUEUED
    payload: dict[str, Any] = field(default_factory=dict)
    result: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    lease_owner: Optional[str] = None
    lease_expires_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.task_id:
            errors.append("task_id is required")
        if not self.organization_id:
            errors.append("organization_id is required")
        if not self.user_id:
            errors.append("user_id is required")
        if not self.investigation_id:
            errors.append("investigation_id is required")
        if self.task_type not in TaskType.ALL:
            errors.append(f"invalid task_type '{self.task_type}'; must be one of {TaskType.ALL}")
        if self.status not in TaskStatus.ALL:
            errors.append(f"invalid status '{self.status}'; must be one of {TaskStatus.ALL}")
        if self.retry_count < 0:
            errors.append("retry_count cannot be negative")
        if self.max_retries < 0:
            errors.append("max_retries cannot be negative")
        return errors

    def can_transition_to(self, target_status: str) -> bool:
        if self.status == target_status:
            return True
        allowed = VALID_TASK_TRANSITIONS.get(self.status, set())
        return target_status in allowed

    def transition_to(self, target_status: str, reason: Optional[str] = None) -> None:
        if not self.can_transition_to(target_status):
            msg = f"Cannot transition task '{self.task_id}' from '{self.status}' to '{target_status}'"
            if reason:
                msg += f": {reason}"
            raise InvalidStateTransitionError(msg)
        self.status = target_status
        self.updated_at = time.time()
        if target_status in TaskStatus.TERMINAL:
            self.completed_at = self.updated_at

    def is_lease_active(self, now: Optional[float] = None) -> bool:
        if not self.lease_owner or not self.lease_expires_at:
            return False
        current = now if now is not None else time.time()
        return current < self.lease_expires_at

    def is_terminal(self) -> bool:
        return self.status in TaskStatus.TERMINAL

    def compute_backoff_delay(
        self,
        base_sec: float = 1.0,
        max_sec: float = 30.0,
        jitter: bool = True,
    ) -> float:
        """Calculate exponential backoff delay with decorrelated jitter."""
        exp_delay = min(max_sec, base_sec * (2 ** self.retry_count))
        if not jitter:
            return exp_delay
        # Full jitter between [base_sec/2, exp_delay]
        return random.uniform(base_sec * 0.5, exp_delay)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "investigation_id": self.investigation_id,
            "task_type": self.task_type,
            "status": self.status,
            "payload": dict(self.payload),
            "result": dict(self.result) if self.result is not None else None,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "lease_owner": self.lease_owner,
            "lease_expires_at": self.lease_expires_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> AsyncTask:
        raw_payload = d.get("payload", {})
        payload = json.loads(raw_payload) if isinstance(raw_payload, str) else dict(raw_payload or {})
        raw_result = d.get("result")
        result = json.loads(raw_result) if isinstance(raw_result, str) else (dict(raw_result) if raw_result is not None else None)

        return cls(
            task_id=d["task_id"],
            organization_id=d["organization_id"],
            user_id=d["user_id"],
            investigation_id=d["investigation_id"],
            task_type=d["task_type"],
            status=d.get("status", TaskStatus.QUEUED),
            payload=payload,
            result=result,
            error_message=d.get("error_message"),
            retry_count=int(d.get("retry_count", 0)),
            max_retries=int(d.get("max_retries", 3)),
            lease_owner=d.get("lease_owner"),
            lease_expires_at=float(d["lease_expires_at"]) if d.get("lease_expires_at") is not None else None,
            created_at=float(d.get("created_at", time.time())),
            updated_at=float(d.get("updated_at", time.time())),
            completed_at=float(d["completed_at"]) if d.get("completed_at") is not None else None,
        )
