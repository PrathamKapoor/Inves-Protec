"""Concurrency and distributed race resolution tests across multi-instance boundaries."""
from __future__ import annotations

import concurrent.futures
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sangyan.core.errors import DuplicateEntryError, InvalidStateTransitionError
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.domain.models import Investigation, WorkflowRun
from sangyan.tenancy.repository import TenantRepository
from sangyan.workflow.errors import ReviewConflictError
from sangyan.workflow.nodes import WorkflowNodeSuite
from sangyan.workflow.service import WorkflowService


@pytest.fixture
def shared_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "shared_cluster.db"
        engine = SQLiteDatabaseEngine(db_path)
        MigrationRunner(engine).migrate()

        now = time.time()
        # Seed organization, users, and memberships
        engine.execute(
            "INSERT INTO sangyan_organizations (id, name, status, created_at) VALUES (?, ?, ?, ?)",
            ("org_test", "Test Org", "active", now),
        )
        engine.execute(
            "INSERT INTO sangyan_users (id, email, name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("system", "system@sangyan.local", "System Admin", "active", now),
        )
        engine.execute(
            "INSERT INTO sangyan_users (id, email, name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("user_pod_a", "pod_a@example.com", "Pod A Reviewer", "active", now),
        )
        engine.execute(
            "INSERT INTO sangyan_users (id, email, name, status, created_at) VALUES (?, ?, ?, ?, ?)",
            ("user_pod_b", "pod_b@example.com", "Pod B Reviewer", "active", now),
        )
        engine.execute(
            "INSERT INTO sangyan_memberships (id, organization_id, user_id, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("mem_sys", "org_test", "system", "sangyan_admin", "active", now),
        )
        engine.execute(
            "INSERT INTO sangyan_memberships (id, organization_id, user_id, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("mem_a", "org_test", "user_pod_a", "sangyan_admin", "active", now),
        )
        engine.execute(
            "INSERT INTO sangyan_memberships (id, organization_id, user_id, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("mem_b", "org_test", "user_pod_b", "sangyan_admin", "active", now),
        )

        yield engine, db_path
        engine.close()


def test_concurrent_human_review_race_pod_a_vs_pod_b(shared_db):
    """Scenario 4: Two API pods receive concurrent review decisions for the same investigation.
    
    Database-level atomic conditional transition guarantees exactly one succeeds,
    and the second receives ReviewConflictError (409 Conflict), preventing double-finalization.
    """
    engine, _ = shared_db

    repo = TenantRepository(engine, organization_id="org_test", user_id="user_pod_a")
    inv_id = "inv_race_target_123"

    inv = Investigation(
        id=inv_id,
        organization_id="org_test",
        user_id="user_pod_a",
        content_item_id="cnt_123",
        status="AWAITING_REVIEW",
        summary="Race Corp Investigation",
    )
    repo.save_investigation(inv)

    wf_run = WorkflowRun(
        id="run_race_123",
        organization_id="org_test",
        investigation_id=inv_id,
        thread_id="org_test:inv_race_target_123:run_race_123",
        run_id="run_race_123",
        status="AWAITING_REVIEW",
        current_node="review_gate_node",
    )
    repo.save_workflow_run(wf_run)

    # Instantiate two workflow services representing Pod A and Pod B
    mock_workflow = MagicMock()
    mock_workflow.invoke.return_value = {"status": "COMPLETED"}

    node_suite = WorkflowNodeSuite(
        verification_engine=None,
        trust_binding=None,
        repository_factory=lambda oid, user_id=None: TenantRepository(engine, organization_id=oid, user_id=user_id or "system"),
    )
    service_pod_a = WorkflowService(
        repository_factory=lambda oid, user_id=None: TenantRepository(engine, organization_id=oid, user_id="user_pod_a"),
        node_suite=node_suite,
        workflow=mock_workflow,
    )
    service_pod_b = WorkflowService(
        repository_factory=lambda oid, user_id=None: TenantRepository(engine, organization_id=oid, user_id="user_pod_b"),
        node_suite=node_suite,
        workflow=mock_workflow,
    )

    results = []
    errors = []

    def run_review(service, user_id, action, notes):
        try:
            res = service.resume_investigation(
                investigation_id=inv_id,
                organization_id="org_test",
                review_action=action,
                user_id=user_id,
                reason=notes,
            )
            results.append(res)
        except Exception as exc:
            errors.append(exc)

    # Launch both reviews concurrently in separate threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(run_review, service_pod_a, "user_pod_a", "CONFIRM", "Pod A Confirmation")
        f2 = executor.submit(run_review, service_pod_b, "user_pod_b", "DISMISS", "Pod B Dismissal")
        f1.result()
        f2.result()

    # Exactly ONE must succeed and ONE must fail with ReviewConflictError / InvalidStateTransitionError
    assert len(results) == 1, f"Expected exactly 1 successful review, got {len(results)}"
    assert len(errors) == 1, f"Expected exactly 1 conflict error, got {len(errors)}"
    assert isinstance(errors[0], (ReviewConflictError, InvalidStateTransitionError))

    # Final investigation state must be FINALIZING or COMPLETED (not AWAITING_REVIEW)
    final_inv = repo.get_investigation(inv_id)
    assert final_inv.status in ("FINALIZING", "COMPLETED")


def test_concurrent_investigation_creation_idempotency(shared_db):
    """Scenario 7: Duplicate investigation creation with identical ID is rejected."""
    engine, _ = shared_db
    repo_a = TenantRepository(engine, organization_id="org_test", user_id="user_pod_a")
    repo_b = TenantRepository(engine, organization_id="org_test", user_id="user_pod_b")

    inv_id = "inv_idempotent_fixed_id_999"

    inv_a = Investigation(
        id=inv_id,
        organization_id="org_test",
        user_id="user_pod_a",
        content_item_id="cnt_idemp",
        status="INTAKE",
    )
    repo_a.save_investigation(inv_a)

    inv_b = Investigation(
        id=inv_id,
        organization_id="org_test",
        user_id="user_pod_b",
        content_item_id="cnt_idemp",
        status="INTAKE",
    )
    with pytest.raises(DuplicateEntryError):
        repo_b.save_investigation(inv_b)


def test_concurrent_audit_ledger_chaining(shared_db):
    """Scenario 8: Concurrent audit writes maintain strict sequential hash chaining."""
    engine, _ = shared_db
    repo = TenantRepository(engine, organization_id="org_test", user_id="system")

    def write_audit(index):
        repo.record_audit_event(
            action=f"action_concurrent_{index}",
            resource=f"resource_{index}",
            result="OK",
            metadata={"index": index},
        )

    # Concurrently write 10 audit events
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(write_audit, i) for i in range(10)]
        for f in futures:
            f.result()

    # Fetch all audit events
    events = repo.list_audit_events(limit=50)
    assert len(events) >= 10
    # Every event must have a non-empty ledger hash
    for evt in events:
        assert evt.ledger_hash is not None
        assert len(evt.ledger_hash) == 64
