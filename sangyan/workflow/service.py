"""High-level orchestration service managing workflow execution, human review, and tenancy boundaries."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional

from langgraph.types import Command

from sangyan.core.errors import NotFoundError, PermissionDeniedError
from sangyan.domain.base import new_id
from sangyan.domain.models import ContentItem, Investigation, REVIEW_ACTIONS, WorkflowRun
from sangyan.tenancy.repository import TenantRepository
from sangyan.workflow.checkpointer import WorkflowCheckpointer, format_thread_id, validate_thread_access
from sangyan.workflow.errors import (
    CannotCancelCompletedInvestigationError,
    InvestigationCancelledError,
    ReviewConflictError,
    TenantMismatchError,
    WorkflowError,
)
from sangyan.realtime.broker import get_event_broker
from sangyan.realtime.models import InvestigationEventType
from sangyan.workflow.graph import InvestigationWorkflow
from sangyan.workflow.nodes import WorkflowNodeSuite
from sangyan.workflow.state import InvestigationWorkflowState, create_initial_workflow_state


class WorkflowService:
    """Production service coordinating LangGraph investigation workflows with multi-tenant governance."""

    def __init__(
        self,
        repository_factory: Callable[[str], TenantRepository],
        workflow: Optional[InvestigationWorkflow] = None,
        checkpointer: Optional[WorkflowCheckpointer] = None,
        node_suite: Optional[WorkflowNodeSuite] = None,
        event_broker: Optional[Any] = None,
    ) -> None:
        self.repository_factory = repository_factory
        self.checkpointer = checkpointer or WorkflowCheckpointer(in_memory=True)
        self.event_broker = event_broker or get_event_broker()
        self.node_suite = node_suite or WorkflowNodeSuite(
            repository_factory=repository_factory,
            event_broker=self.event_broker,
        )
        self.workflow = workflow or InvestigationWorkflow(
            node_suite=self.node_suite,
            checkpointer=self.checkpointer.get_saver(),
        )
        self._investigation_locks: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def _get_inv_lock(self, inv_id: str) -> threading.Lock:
        with self._global_lock:
            if inv_id not in self._investigation_locks:
                self._investigation_locks[inv_id] = threading.Lock()
            return self._investigation_locks[inv_id]

    def _get_repo(self, organization_id: str, user_id: Optional[str] = None) -> TenantRepository:
        import inspect
        sig = inspect.signature(self.repository_factory)
        if len(sig.parameters) >= 2 or any(p.name == "user_id" for p in sig.parameters.values()):
            return self.repository_factory(organization_id, user_id=user_id) if "user_id" in sig.parameters else self.repository_factory(organization_id, user_id)
        repo = self.repository_factory(organization_id)
        if user_id and hasattr(repo, "user_id") and repo.user_id != user_id:
            return TenantRepository(repo._db, organization_id, user_id)
        return repo

    # -----------------------------------------------------------------------
    # 1. Start Investigation Workflow
    # -----------------------------------------------------------------------
    def start_investigation(
        self,
        content_items: list[ContentItem],
        user_id: str,
        organization_id: str,
        run_id: Optional[str] = None,
        require_review: bool = False,
        metadata: Optional[dict[str, Any]] = None,
    ) -> InvestigationWorkflowState:
        """Start a new LangGraph investigation workflow instance within tenant boundary."""
        if not content_items:
            raise ValueError("At least one ContentItem is required to start an investigation.")

        # Ensure all content items match organization_id
        for ci in content_items:
            if ci.organization_id != organization_id:
                raise TenantMismatchError(
                    f"ContentItem {ci.id} organization '{ci.organization_id}' does not match '{organization_id}'"
                )

        repo = self._get_repo(organization_id, user_id)
        inv_id = new_id("inv")
        r_id = run_id or new_id("run")
        th_id = format_thread_id(organization_id, inv_id, r_id)

        # Record initial WorkflowRun in relational database
        wf_run = WorkflowRun(
            organization_id=organization_id,
            investigation_id=inv_id,
            thread_id=th_id,
            run_id=r_id,
            status="RUNNING",
            current_node="intake_node",
            metadata=dict(metadata or {}),
        )
        repo.save_workflow_run(wf_run)

        # Build initial state
        initial_state = create_initial_workflow_state(
            content_items=content_items,
            organization_id=organization_id,
            user_id=user_id,
            investigation_id=inv_id,
            run_id=r_id,
            thread_id=th_id,
            force_review=require_review,
            metadata=metadata,
        )

        repo.record_audit_event(
            action="workflow_started",
            resource=f"investigation:{inv_id}",
            result="RUNNING",
            metadata={"thread_id": th_id, "run_id": r_id, "content_count": len(content_items)},
        )

        try:
            (self.event_broker or get_event_broker()).publish(
                investigation_id=inv_id,
                organization_id=organization_id,
                event_type=InvestigationEventType.INVESTIGATION_STARTED,
                node_name="start",
                payload={"run_id": r_id, "content_count": len(content_items), "require_review": require_review},
            )
        except Exception:
            pass

        # Execute graph
        try:
            res = self.workflow.invoke(initial_state, thread_id=th_id)
        except Exception as exc:
            repo.record_audit_event(
                action="workflow_execution_failed",
                resource=f"investigation:{inv_id}",
                result="FAILED",
                metadata={"error": str(exc), "run_id": r_id},
            )
            try:
                latest_state = self.get_workflow_state(inv_id, organization_id)
                preserved_state = dict(latest_state["values"]) if latest_state else dict(initial_state)
            except Exception:
                preserved_state = dict(initial_state)

            preserved_state["errors"] = preserved_state.get("errors", []) + [str(exc)]
            failure_update = self.node_suite.failure_node(preserved_state)
            preserved_state.update(failure_update)
            repo.update_workflow_run(
                wf_run.id,
                status=failure_update.get("status", "FAILED"),
                current_node="failure_node",
                error_message=str(exc),
            )
            return preserved_state

        # Inspect post-execution status
        current_snapshot = self.workflow.get_state(th_id)
        if current_snapshot.next and "review_gate_node" in current_snapshot.next:
            # Paused at review gate
            repo.update_workflow_run(
                wf_run.id,
                status="AWAITING_REVIEW",
                current_node="review_gate_node",
            )
            res["status"] = "AWAITING_REVIEW"
        elif res.get("status") == "COMPLETED":
            repo.update_workflow_run(
                wf_run.id,
                status="COMPLETED",
                current_node="completion_node",
            )
        elif res.get("status") == "FAILED":
            repo.update_workflow_run(
                wf_run.id,
                status="FAILED",
                current_node="failure_node",
            )

        return res

    # -----------------------------------------------------------------------
    # 2. Resume Interrupted Investigation (Human-in-the-Loop)
    # -----------------------------------------------------------------------
    def resume_investigation(
        self,
        investigation_id: str,
        review_action: str,
        user_id: str,
        organization_id: str,
        reason: str = "",
        finding_id: Optional[str] = None,
    ) -> InvestigationWorkflowState:
        """Resume an investigation paused at review_gate_node with an authorized supervisory decision."""
        if review_action not in REVIEW_ACTIONS:
            raise ValueError(f"Invalid review action '{review_action}'; must be one of {REVIEW_ACTIONS}")

        repo = self._get_repo(organization_id, user_id)

        # Check tenant permissions: caller must have 'investigation:review'
        repo._require_permission("investigation:review")

        # Retrieve investigation and verify tenant ownership
        inv = repo.get_investigation(investigation_id)
        if inv.organization_id != organization_id:
            raise TenantMismatchError(
                f"Investigation '{investigation_id}' belongs to organization '{inv.organization_id}', "
                f"not caller '{organization_id}'."
            )

        # Pre-flight status check
        if inv.status == "CANCELLED":
            raise InvestigationCancelledError(f"Cannot resume cancelled investigation '{investigation_id}'.")
        if inv.status != "AWAITING_REVIEW":
            raise ReviewConflictError(
                f"Investigation '{investigation_id}' is in status '{inv.status}', not 'AWAITING_REVIEW'."
            )

        # Retrieve active WorkflowRun
        wf_run = repo.get_workflow_run_by_investigation(investigation_id)
        if wf_run is None:
            raise NotFoundError(f"Active workflow run for investigation '{investigation_id}' not found.")

        validate_thread_access(wf_run.thread_id, organization_id)

        # Atomic conditional database state transition (AWAITING_REVIEW -> FINALIZING)
        # Governed at the database layer to guarantee mutual exclusion across multiple pods/workers
        transitioned = repo.transition_investigation_status(
            investigation_id,
            from_status="AWAITING_REVIEW",
            to_status="FINALIZING",
        )
        if not transitioned:
            current_inv = repo.get_investigation(investigation_id)
            if current_inv.status == "CANCELLED":
                raise InvestigationCancelledError(f"Cannot resume cancelled investigation '{investigation_id}'.")
            raise ReviewConflictError(
                f"Investigation '{investigation_id}' was already transitioned out of AWAITING_REVIEW "
                f"(current status: '{current_inv.status}')."
            )

        review_decision = {
            "reviewer_id": user_id,
            "action": review_action,
            "reason": reason or f"Reviewed with action {review_action}",
            "finding_id": finding_id,
            "occurred_at": time.time(),
        }

        # Update WorkflowRun status
        repo.update_workflow_run(wf_run.id, status="RUNNING", current_node="review_gate_node")

        try:
            (self.event_broker or get_event_broker()).publish(
                investigation_id=investigation_id,
                organization_id=organization_id,
                event_type=InvestigationEventType.REVIEW_SUBMITTED,
                node_name="resume",
                payload={"action": review_action, "reviewer_id": user_id, "reason": reason},
            )
        except Exception:
            pass

        # Resume execution in LangGraph; on failure, revert the investigation to
        # AWAITING_REVIEW so transient errors (worker crash, registry outage,
        # stale region) remain recoverable instead of wedging it in FINALIZING.
        try:
            res = self.workflow.invoke(Command(resume=review_decision), thread_id=wf_run.thread_id)
        except Exception as exc:
            repo.transition_investigation_status(
                investigation_id,
                from_status="FINALIZING",
                to_status="AWAITING_REVIEW",
                summary=f"Resume failed; reverted to AWAITING_REVIEW: {exc}",
            )
            repo.update_workflow_run(wf_run.id, status="AWAITING_REVIEW", current_node="review_gate_node")
            repo.record_audit_event(
                action="workflow_resume_failed",
                resource=f"investigation:{investigation_id}",
                result="REVERTED_TO_AWAITING_REVIEW",
                metadata={"error": str(exc), "run_id": wf_run.run_id},
            )
            raise

        if res.get("status") == "COMPLETED":
            repo.update_workflow_run(wf_run.id, status="COMPLETED", current_node="completion_node")
        elif res.get("status") == "FAILED":
            repo.update_workflow_run(wf_run.id, status="FAILED", current_node="failure_node")

        return res

    # -----------------------------------------------------------------------
    # 3. Cancel Investigation
    # -----------------------------------------------------------------------
    def cancel_investigation(
        self,
        investigation_id: str,
        user_id: str,
        organization_id: str,
        reason: str = "",
    ) -> Investigation:
        """Cancel an in-flight or awaiting-review investigation while preserving prior evidence."""
        repo = self._get_repo(organization_id, user_id)
        repo._require_permission("investigation:create")

        inv = repo.get_investigation(investigation_id)
        if inv.organization_id != organization_id:
            raise TenantMismatchError("Cannot cancel investigation from another tenant.")

        if inv.status == "COMPLETED":
            raise CannotCancelCompletedInvestigationError(
                f"Investigation '{investigation_id}' is already COMPLETED and cannot be cancelled."
            )
        if inv.status == "CANCELLED":
            return inv

        cancel_summary = f"Cancelled by user {user_id}. Reason: {reason or 'No reason provided'}"
        transitioned = repo.transition_investigation_status(
            investigation_id,
            from_status=inv.status,
            to_status="CANCELLED",
            summary=cancel_summary,
        )
        if not transitioned:
            fresh = repo.get_investigation(investigation_id)
            if fresh.status == "COMPLETED":
                raise CannotCancelCompletedInvestigationError(
                    f"Investigation '{investigation_id}' is already COMPLETED and cannot be cancelled."
                )
            if fresh.status == "CANCELLED":
                return fresh

        wf_run = repo.get_workflow_run_by_investigation(investigation_id)
        if wf_run is not None:
            repo.update_workflow_run(wf_run.id, status="CANCELLED")

        repo.record_audit_event(
            action="workflow_cancelled",
            resource=f"investigation:{investigation_id}",
            result="CANCELLED",
            metadata={"user_id": user_id, "reason": reason},
        )

        return repo.get_investigation(investigation_id)

    # -----------------------------------------------------------------------
    # 4. State & Run Query Inspection
    # -----------------------------------------------------------------------
    def get_workflow_state(
        self,
        investigation_id: str,
        organization_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Retrieve current graph checkpoint state for an investigation."""
        repo = self._get_repo(organization_id, user_id)
        inv = repo.get_investigation(investigation_id)
        if inv.organization_id != organization_id:
            raise TenantMismatchError("Cannot access workflow state across tenant boundaries.")

        wf_run = repo.get_workflow_run_by_investigation(investigation_id)
        if wf_run is None:
            return None

        validate_thread_access(wf_run.thread_id, organization_id)
        snapshot = self.workflow.get_state(wf_run.thread_id)
        return {
            "values": dict(snapshot.values) if snapshot else {},
            "next": list(snapshot.next) if snapshot and snapshot.next else [],
            "thread_id": wf_run.thread_id,
            "run_id": wf_run.run_id,
            "status": wf_run.status,
            "current_node": wf_run.current_node,
        }

    def get_workflow_run(
        self,
        investigation_id: str,
        organization_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[WorkflowRun]:
        """Query workflow run record by investigation ID."""
        repo = self._get_repo(organization_id, user_id)
        return repo.get_workflow_run_by_investigation(investigation_id)

    def list_workflow_runs(
        self,
        organization_id: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> list[WorkflowRun]:
        """List workflow runs for an organization."""
        repo = self._get_repo(organization_id, user_id)
        return repo.list_workflow_runs(limit=limit, offset=offset, status=status)
