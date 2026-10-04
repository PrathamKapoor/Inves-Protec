"""Phase 11: End-to-End Operational Lifecycle Acceptance Test.

Executes a complete 26-step lifecycle covering:
1. Migration execution (migrations 001 - 007)
2. PKCS#11 HSM Simulator token initialization with PIN authentication
3. TrustService integration with hardware signing provider
4. Real-time InvestigationEventBroker initialization and DB persistence
5. Node suite & workflow wiring with event telemetry
6. Asynchronous task queue & repository setup
7. Asynchronous investigation start with supervisory review required
8. Worker execution of initial workflow stages
9. Workflow pauses at review gate (AWAITING_REVIEW)
10. Event broker records monotonic progress events for all pipeline stages
11. Real-time SSE streaming replay (Last-Event-ID / after_sequence)
12. SSE wire format validation (id, event, data, trailing double-newline)
13. Supervisory analyst submits review confirmation (CONFIRM)
14. Worker executes asynchronous workflow resume task
15. Trust finalization executes using HSM signing provider
16. Hardware key non-extractability invariant enforcement (CKR_ATTRIBUTE_SENSITIVE)
17. Trust receipt persisted with signing_key_id in database
18. Cryptographic verification of trust receipt using ML-DSA-65 public key
19. Replay full SSE event audit trail to completion
20. HSM key rotation to generation-2 (hsm-key-v2)
21. Historical trust receipt verification succeeds post-rotation
22. PostgreSQL physical replication monitoring and standby health check
23. Disaster Recovery Manager registration of primary and standby regions
24. Controlled zero-data-loss DR switchover to standby region with epoch progression
25. Split-brain fencing rejects writes from stale demoted region
26. Unbroken linear cryptographic audit hash chain verification
"""

import json
import tempfile
import time
from pathlib import Path

import pytest

from sangyan.async_exec.models import AsyncTask, TaskStatus, TaskType
from sangyan.async_exec.queue import InMemoryTaskQueue
from sangyan.async_exec.repository import AsyncTaskRepository
from sangyan.async_exec.worker import AsyncInvestigationWorker
from sangyan.core.errors import CryptoError, StaleRegionError
from sangyan.crypto.signing_provider import PKCS11SimulatorSigningProvider
from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.database.replication import PostgresReplicationManager
from sangyan.dr.manager import DisasterRecoveryManager
from sangyan.dr.models import RegionRole
from sangyan.realtime.broker import InvestigationEventBroker
from sangyan.tenancy.repository import TenantAdministration, TenantRepository
from sangyan.trust.service import TrustService
from sangyan.verification.trust_binding import TrustBindingService
from sangyan.workflow.checkpointer import WorkflowCheckpointer
from sangyan.workflow.graph import InvestigationWorkflow
from sangyan.workflow.nodes import WorkflowNodeSuite
from sangyan.workflow.service import WorkflowService


def test_phase11_26_step_operational_lifecycle():
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "sangyan_e2e_phase11.db"
    engine = SQLiteDatabaseEngine(db_path)

    try:
        # STEP 1: Execute migrations up to 007
        runner = MigrationRunner(engine)
        applied = runner.migrate()
        assert len(applied) == 7

        # Setup tenant organization and user
        admin = TenantAdministration(engine)
        org_id = admin.create_organization("SEBI Directorate of Enforcement")
        user_id = admin.create_user("director@sebi.gov.in", "Director General")
        admin.add_membership(org_id, user_id, "sangyan_analyst")

        # STEP 2: Initialize PKCS#11 HSM Simulator signing provider
        hsm_provider = PKCS11SimulatorSigningProvider(
            slot_id=0,
            token_label="Sangyan-HSM-Prod",
            user_pin="hsm-secret-pin-777",
            key_identifier="ml-dsa-key-v1",
        )
        assert hsm_provider.is_hardware() is True
        hsm_health = hsm_provider.health()
        assert hsm_health["status"] == "HEALTHY"
        assert hsm_health["authenticated"] is True
        assert hsm_health["key_identifier"] == "ml-dsa-key-v1"

        # STEP 3: Configure TrustService with the HSM provider
        trust_service = TrustService(engine=engine, signing_provider=hsm_provider)
        assert trust_service.public_key == hsm_provider.public_key

        # STEP 4: Real-time InvestigationEventBroker initialization
        event_broker = InvestigationEventBroker(engine=engine)

        # STEP 5: Wire node suite & workflow with event broker
        trust_binding = TrustBindingService(trust_service=trust_service)
        cp_path = Path(tmpdir) / "checkpoints.db"
        checkpointer = WorkflowCheckpointer(db_path=cp_path)

        def repo_factory(oid: str, uid: str | None = None) -> TenantRepository:
            return TenantRepository(engine, oid, uid or user_id)

        node_suite = WorkflowNodeSuite(
            trust_binding=trust_binding,
            repository_factory=lambda oid: repo_factory(oid),
            event_broker=event_broker,
        )
        workflow = InvestigationWorkflow(
            node_suite=node_suite,
            checkpointer=checkpointer.get_saver(),
        )
        workflow_service = WorkflowService(
            repository_factory=lambda oid: repo_factory(oid),
            workflow=workflow,
            checkpointer=checkpointer,
            node_suite=node_suite,
            event_broker=event_broker,
        )

        # STEP 6: Asynchronous task queue and worker setup
        queue = InMemoryTaskQueue()
        task_repo = AsyncTaskRepository(engine)
        worker = AsyncInvestigationWorker(
            queue=queue,
            repository=task_repo,
            workflow_service=workflow_service,
            worker_id="phase11-worker-01",
            lease_duration_sec=30.0,
            heartbeat_interval_sec=5.0,
        )

        # STEP 7: Enqueue investigation requiring supervisory review
        investigation_id = "inv-e2e-phase11"
        start_task = task_repo.create_task(
            task_id="task-start-001",
            organization_id=org_id,
            user_id=user_id,
            investigation_id=investigation_id,
            task_type=TaskType.WORKFLOW_START,
            payload={
                "contents": [
                    "Guaranteed 500% monthly crypto returns through institutional algorithmic arbitrage on Telegram",
                ],
                "require_review": True,
            },
        )
        queue.enqueue(start_task)

        # STEP 8: Worker processes workflow start task
        processed_start = worker.process_one_batch(batch_size=1)
        assert processed_start == 1

        # STEP 9: Workflow pauses at review gate (AWAITING_REVIEW)
        start_task_res = task_repo.get_task("task-start-001")
        assert start_task_res.status == TaskStatus.SUCCEEDED
        assert start_task_res.result["status"] == "AWAITING_REVIEW"
        investigation_id = start_task_res.result["investigation_id"]
        assert investigation_id.startswith("inv_")

        # STEP 10: Event broker records monotonic progress events for pipeline stages
        events_stage1 = event_broker.get_events(investigation_id, org_id)
        assert len(events_stage1) >= 4, f"Expected at least 4 stage events, got {len(events_stage1)}"
        sequences = [e.sequence for e in events_stage1]
        assert sequences == sorted(sequences), "Event sequence numbers must be monotonic"
        assert sequences == list(range(1, len(events_stage1) + 1)), "Event sequences must be strictly incrementing 1..N"

        # STEP 11: Real-time SSE streaming replay (after_sequence)
        replayed_events = event_broker.get_events(investigation_id, org_id, after_sequence=2)
        assert len(replayed_events) == len(events_stage1) - 2
        for ev in replayed_events:
            assert ev.sequence > 2

        # STEP 12: SSE wire format validation
        sample_event = events_stage1[0]
        sse_wire = sample_event.to_sse_message()
        assert f"id: {sample_event.event_id}\n" in sse_wire
        assert f"event: {sample_event.event_type}\n" in sse_wire
        assert "data: {" in sse_wire
        assert sse_wire.endswith("\n\n")

        # STEP 13: Supervisory analyst submits review confirmation (CONFIRM)
        resume_task = task_repo.create_task(
            task_id="task-resume-001",
            organization_id=org_id,
            user_id=user_id,
            investigation_id=investigation_id,
            task_type=TaskType.WORKFLOW_RESUME,
            payload={
                "investigation_id": investigation_id,
                "review_action": "CONFIRM",
                "reason": "Supervisor confirmed fraudulent high-yield investment scheme",
            },
        )
        queue.enqueue(resume_task)

        # STEP 14: Worker executes asynchronous workflow resume task
        processed_resume = worker.process_one_batch(batch_size=1)
        assert processed_resume == 1

        # STEP 15: Trust finalization executes using HSM signing provider
        resume_task_res = task_repo.get_task("task-resume-001")
        assert resume_task_res.status == TaskStatus.SUCCEEDED
        assert resume_task_res.result["status"] == "COMPLETED"
        receipt_id = resume_task_res.result["trust_receipt_id"]
        assert receipt_id is not None

        # STEP 16: Hardware key non-extractability invariant enforcement (CKR_ATTRIBUTE_SENSITIVE)
        with pytest.raises(CryptoError, match="CKR_ATTRIBUTE_SENSITIVE"):
            hsm_provider.get_private_key_attribute()

        # STEP 17: Trust receipt persisted with signing_key_id in database
        receipt_row = engine.query_one("SELECT * FROM sangyan_trust_receipts WHERE id=?", (receipt_id,))
        assert receipt_row is not None
        assert receipt_row["signing_key_id"] == "ml-dsa-key-v1"
        assert receipt_row["algorithm_id"] == "ML-DSA-65"

        # STEP 18: Cryptographic verification of trust receipt using ML-DSA-65 public key
        # Load receipt and verify cryptographic signature on content_digest
        receipt_obj = trust_service.get_receipt(receipt_id)
        assert receipt_obj is not None
        assert trust_service.signing_provider.verify(
            receipt_obj.content_digest.encode("utf-8"),
            receipt_obj.signature,
            public_key=receipt_obj.public_key,
        ) is True
        assert trust_service.signing_provider.verify(
            b"tampered_content_digest_777",
            receipt_obj.signature,
            public_key=receipt_obj.public_key,
        ) is False

        # Verify direct document signing and verification
        sample_doc = {"investigation_id": investigation_id, "status": "VERIFIED_FRAUD"}
        doc_receipt = trust_service.sign_document("investigation", investigation_id, sample_doc)
        assert trust_service.verify_document(doc_receipt, sample_doc) is True
        assert trust_service.verify_document(doc_receipt, {"tampered": True}) is False

        # STEP 19: Replay full SSE event audit trail to completion
        final_events = event_broker.get_events(investigation_id, org_id)
        event_types = [str(e.event_type) for e in final_events]
        assert "INVESTIGATION_STARTED" in event_types
        assert "INTAKE_COMPLETED" in event_types
        assert "TRUST_FINALIZATION_COMPLETED" in event_types
        assert "INVESTIGATION_COMPLETED" in event_types

        # STEP 20: HSM key rotation to generation-2 (ml-dsa-key-v2)
        trust_service.rotate_key("ml-dsa-key-v2")
        assert hsm_provider.key_identifier == "ml-dsa-key-v2"
        assert trust_service.key_identifier == "ml-dsa-key-v2"

        # STEP 21: Historical trust receipt verification succeeds post-rotation
        # The receipt signed by key v1 must still verify successfully!
        assert trust_service.verify_document(doc_receipt, sample_doc) is True

        # Sign a new document under v2
        receipt_v2 = trust_service.sign_document("test", "test-doc-v2", {"message": "v2 document"})
        assert receipt_v2.signing_key_id == "ml-dsa-key-v2"
        assert trust_service.verify_document(receipt_v2, {"message": "v2 document"}) is True

        # STEP 22: PostgreSQL physical replication monitoring and standby health check
        repl_mgr = PostgresReplicationManager(engine=engine)
        status = repl_mgr.get_replication_status()
        assert status["role"] == "PRIMARY"
        health = repl_mgr.validate_standby_health()
        assert health["healthy"] is True

        # STEP 23: Disaster Recovery Manager registration of primary and standby regions
        dr_mgr = DisasterRecoveryManager(
            engine=engine,
            region_id="ap-south-primary",
            default_role=RegionRole.PRIMARY_ACTIVE,
            default_epoch=1,
        )
        dr_mgr.register_region("ap-south-standby", role=RegionRole.STANDBY_READY)

        # STEP 24: Controlled zero-data-loss DR switchover to standby region with epoch progression
        switchover_res = repl_mgr.controlled_switchover(
            dr_manager=dr_mgr,
            primary_region="ap-south-primary",
            standby_region="ap-south-standby",
            reason="Controlled regional switchover drill",
        )
        assert switchover_res["status"] == "SWITCHOVER_COMPLETED"
        assert switchover_res["old_primary"] == "ap-south-primary"
        assert switchover_res["new_primary"] == "ap-south-standby"
        assert switchover_res["new_epoch"] == 2

        # STEP 25: Split-brain fencing rejects writes from stale demoted region
        with pytest.raises(StaleRegionError):
            dr_mgr.verify_write_authority("ap-south-primary")

        # Active promoted region succeeds
        dr_mgr.verify_write_authority("ap-south-standby")

        # STEP 26: Unbroken linear cryptographic audit hash chain verification
        audit_res = dr_mgr.verify_audit_continuity()
        assert audit_res["valid"] is True, f"Audit hash chain broken: {audit_res}"
        assert audit_res["event_count"] >= 0

    finally:
        engine.close()
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
