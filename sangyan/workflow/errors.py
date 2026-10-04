"""Workflow and orchestration exceptions for SANGYAN."""
from __future__ import annotations

from sangyan.core.errors import PermissionDeniedError, SangyanError


class WorkflowError(SangyanError):
    """Base exception for workflow and execution pipeline failures."""

    def __init__(self, message: str, code: str = "WORKFLOW_ERROR", status_code: int = 500) -> None:
        super().__init__(message, code=code, status_code=status_code)


class ReviewConflictError(WorkflowError):
    """Raised when concurrent review submissions conflict or review has already been finalized."""

    def __init__(self, message: str = "Investigation review already resolved or in conflicting state.") -> None:
        super().__init__(message, code="REVIEW_CONFLICT", status_code=409)


class CannotCancelCompletedInvestigationError(WorkflowError):
    """Raised when attempting to cancel an investigation that has already completed."""

    def __init__(self, message: str = "Cannot cancel an investigation that has already completed.") -> None:
        super().__init__(message, code="CANNOT_CANCEL_COMPLETED", status_code=400)


class InvestigationCancelledError(WorkflowError):
    """Raised when attempting to resume or execute an investigation that was cancelled."""

    def __init__(self, message: str = "Investigation was cancelled and cannot be resumed.") -> None:
        super().__init__(message, code="INVESTIGATION_CANCELLED", status_code=400)


class CheckpointNotFoundError(WorkflowError):
    """Raised when a requested checkpoint or thread state cannot be located."""

    def __init__(self, message: str = "Workflow checkpoint not found.") -> None:
        super().__init__(message, code="CHECKPOINT_NOT_FOUND", status_code=404)


class TenantMismatchError(PermissionDeniedError):
    """Raised when a thread, checkpoint, or investigation is accessed across tenant boundaries."""

    def __init__(self, message: str = "Cross-tenant access to workflow state is strictly prohibited.") -> None:
        super().__init__(message)


class RetryableWorkflowError(WorkflowError):
    """Raised on transient failures (network, lock contention) that may be retried."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="RETRYABLE_WORKFLOW_ERROR", status_code=503)


class NonRetryableWorkflowError(WorkflowError):
    """Raised on permanent errors (validation, security violation, data corruption)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="NON_RETRYABLE_WORKFLOW_ERROR", status_code=400)
