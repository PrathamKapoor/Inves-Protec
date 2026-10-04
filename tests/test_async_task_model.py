"""Tests for asynchronous task domain model, state transitions, validation, and backoff."""
import json
import time
import pytest

from sangyan.async_exec.models import AsyncTask, TaskStatus, TaskType, VALID_TASK_TRANSITIONS
from sangyan.core.errors import InvalidStateTransitionError


def test_task_model_initialization_and_validation():
    task = AsyncTask(
        task_id="task-001",
        organization_id="org-sebi",
        user_id="analyst-1",
        investigation_id="inv-100",
        task_type=TaskType.WORKFLOW_START,
        payload={"query": "test investigation"},
    )
    assert task.status == TaskStatus.QUEUED
    assert task.retry_count == 0
    assert task.max_retries == 3
    assert task.lease_owner is None
    assert task.lease_expires_at is None
    assert task.validate() == []
    assert not task.is_terminal()


def test_task_model_validation_errors():
    invalid_task = AsyncTask(
        task_id="",
        organization_id="",
        user_id="",
        investigation_id="",
        task_type="INVALID_TYPE",
        status="INVALID_STATUS",
        retry_count=-1,
        max_retries=-2,
    )
    errors = invalid_task.validate()
    assert "task_id is required" in errors
    assert "organization_id is required" in errors
    assert "user_id is required" in errors
    assert "investigation_id is required" in errors
    assert any("invalid task_type" in e for e in errors)
    assert any("invalid status" in e for e in errors)
    assert "retry_count cannot be negative" in errors
    assert "max_retries cannot be negative" in errors


def test_task_valid_state_transitions():
    task = AsyncTask(
        task_id="task-002",
        organization_id="org-1",
        user_id="user-1",
        investigation_id="inv-1",
        task_type=TaskType.WORKFLOW_START,
    )

    # QUEUED -> RUNNING
    task.transition_to(TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING
    assert not task.is_terminal()
    assert task.completed_at is None

    # RUNNING -> SUCCEEDED (terminal)
    task.transition_to(TaskStatus.SUCCEEDED)
    assert task.status == TaskStatus.SUCCEEDED
    assert task.is_terminal()
    assert task.completed_at is not None

    # Self-transition is always allowed
    task.transition_to(TaskStatus.SUCCEEDED)
    assert task.status == TaskStatus.SUCCEEDED


def test_task_invalid_state_transitions():
    task = AsyncTask(
        task_id="task-003",
        organization_id="org-1",
        user_id="user-1",
        investigation_id="inv-1",
        task_type=TaskType.WORKFLOW_START,
        status=TaskStatus.SUCCEEDED,
    )

    # Terminal SUCCEEDED cannot transition to RUNNING or QUEUED
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        task.transition_to(TaskStatus.RUNNING)
    assert "Cannot transition task" in str(exc_info.value)

    # CANCELLED cannot transition to RUNNING
    cancelled_task = AsyncTask(
        task_id="task-004",
        organization_id="org-1",
        user_id="user-1",
        investigation_id="inv-1",
        task_type=TaskType.WORKFLOW_START,
        status=TaskStatus.CANCELLED,
    )
    with pytest.raises(InvalidStateTransitionError):
        cancelled_task.transition_to(TaskStatus.RUNNING)


def test_task_retry_and_dead_letter_cycle():
    task = AsyncTask(
        task_id="task-005",
        organization_id="org-1",
        user_id="user-1",
        investigation_id="inv-1",
        task_type=TaskType.WORKFLOW_START,
        status=TaskStatus.RUNNING,
    )

    # RUNNING -> RETRY_WAIT -> QUEUED
    task.transition_to(TaskStatus.RETRY_WAIT)
    assert task.status == TaskStatus.RETRY_WAIT
    task.transition_to(TaskStatus.QUEUED)
    assert task.status == TaskStatus.QUEUED

    # QUEUED -> RUNNING -> FAILED -> DEAD_LETTERED
    task.transition_to(TaskStatus.RUNNING)
    task.transition_to(TaskStatus.FAILED)
    task.transition_to(TaskStatus.DEAD_LETTERED)
    assert task.status == TaskStatus.DEAD_LETTERED
    assert task.is_terminal()

    # Manual retry re-queues from DEAD_LETTERED -> QUEUED
    task.transition_to(TaskStatus.QUEUED)
    assert task.status == TaskStatus.QUEUED


def test_task_lease_active():
    now = time.time()
    task = AsyncTask(
        task_id="task-006",
        organization_id="org-1",
        user_id="user-1",
        investigation_id="inv-1",
        task_type=TaskType.WORKFLOW_START,
        lease_owner="worker-1",
        lease_expires_at=now + 60.0,
    )
    assert task.is_lease_active(now=now) is True
    assert task.is_lease_active(now=now + 61.0) is False

    # No owner
    task.lease_owner = None
    assert task.is_lease_active(now=now) is False


def test_task_backoff_calculation():
    task = AsyncTask(
        task_id="task-007",
        organization_id="org-1",
        user_id="user-1",
        investigation_id="inv-1",
        task_type=TaskType.WORKFLOW_START,
    )

    # Without jitter: 1 * 2^0 = 1.0, 1 * 2^1 = 2.0, 1 * 2^2 = 4.0
    task.retry_count = 0
    assert task.compute_backoff_delay(base_sec=1.0, jitter=False) == 1.0
    task.retry_count = 1
    assert task.compute_backoff_delay(base_sec=1.0, jitter=False) == 2.0
    task.retry_count = 2
    assert task.compute_backoff_delay(base_sec=1.0, jitter=False) == 4.0

    # Max clamp
    task.retry_count = 10
    assert task.compute_backoff_delay(base_sec=1.0, max_sec=10.0, jitter=False) == 10.0

    # With jitter: delay is within [base_sec * 0.5, exp_delay]
    task.retry_count = 3  # exp_delay = 8.0
    for _ in range(20):
        jittered = task.compute_backoff_delay(base_sec=1.0, max_sec=30.0, jitter=True)
        assert 0.5 <= jittered <= 8.0


def test_task_serialization_round_trip():
    original = AsyncTask(
        task_id="task-008",
        organization_id="org-sebi",
        user_id="user-99",
        investigation_id="inv-200",
        task_type=TaskType.WORKFLOW_START,
        status=TaskStatus.SUCCEEDED,
        payload={"param_a": 123, "param_b": "value"},
        result={"risk_score": 0.85, "verdict": "FLAGGED"},
        error_message=None,
        retry_count=1,
        max_retries=3,
        lease_owner="worker-xyz",
        lease_expires_at=1700000000.0,
        created_at=1699999000.0,
        updated_at=1700000050.0,
        completed_at=1700000050.0,
    )

    data = original.to_dict()
    assert isinstance(data, dict)
    assert data["payload"] == {"param_a": 123, "param_b": "value"}
    assert data["result"]["risk_score"] == 0.85

    # Reconstruct from dict
    restored = AsyncTask.from_dict(data)
    assert restored.task_id == original.task_id
    assert restored.organization_id == original.organization_id
    assert restored.user_id == original.user_id
    assert restored.investigation_id == original.investigation_id
    assert restored.task_type == original.task_type
    assert restored.status == original.status
    assert restored.payload == original.payload
    assert restored.result == original.result
    assert restored.retry_count == original.retry_count
    assert restored.lease_owner == original.lease_owner
    assert restored.lease_expires_at == original.lease_expires_at
    assert restored.completed_at == original.completed_at

    # Test reconstruction when payload and result are serialized JSON strings (as in DB)
    db_row = dict(data)
    db_row["payload"] = json.dumps(data["payload"])
    db_row["result"] = json.dumps(data["result"])
    restored_from_db = AsyncTask.from_dict(db_row)
    assert restored_from_db.payload == original.payload
    assert restored_from_db.result == original.result
