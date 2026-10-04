# SANGYAN — Project Handoff

## 1. Current Phase
Phase 5 — LangGraph Workflow, Durable Execution, Recovery & Human-in-the-Loop Review (COMPLETED)

## 2. Work Completed
- Completed Phase 0 reconnaissance of SAT-SA-with-PQC and Sentiment Analysis codebases.
- Completed Phase 1 Foundation Setup & Domain Migration (PQC crypto, database engine, migrations, domain models, multi-tenancy, SSRF protection, trust receipts, 37 tests).
- Completed Phase 2 Ingestion, Text Cleaning, Multilingual Classification, Atomic Claims, Entity Resolution, Observable Safety Signals, and Content Intelligence Pipeline (64 tests).
- Completed Phase 3 Authoritative Verification, Evidence Retrieval, Findings, Conflict Resolution, and Trust Binding (110 tests):
  - Established Controlled Authoritative Source Registry (`AuthoritativeSourceRegistry`).
  - Implemented versioned, reproducible `RegistrySnapshot` with SHA3-256 integrity verification and `SnapshotManager`.
  - Implemented thread-safe in-memory `VerificationCache` and sliding-window `RateLimiter`.
  - Implemented modular `VerificationAdapter` architecture (SEBI, MCA, Circulars, Official Domains, Market Infrastructure, Payment Destination).
  - Standardized on 5 epistemic verification stances (`SUPPORTED`, `CONTRADICTED`, `CONFLICTING`, `OUTDATED`, `INSUFFICIENT_EVIDENCE`).
  - Enhanced `Evidence` domain entity with full provenance metadata, raw and normalized values, time-validity bounds, and multi-dimensional quality metrics.
  - Implemented tamper-evident chained audit ledger (`AuditEvent`) with SHA3-256 predecessor hash chaining.
  - Implemented lightweight FastAPI REST service (`sangyan.api`) with human HTML inspection views and mandatory Section 40 absence-of-evidence banners.
  - Implemented deterministic conflict resolution handling opposing authoritative records.
  - Implemented post-quantum trust binding with ML-DSA-65 signatures.
- Completed Phase 4 Investigation Correlation, Scam-Chain Reconstruction & Safe Guidance (131 tests):
  - Database Migration 002: Added `sangyan_correlations`, `sangyan_scam_chain_stages`, `sangyan_grievance_records` with multi-tenant index scoping.
  - Domain Model Expansion: Added `CorrelationEdge`, `InvestigationStage`, `GrievanceRecord`, `InvestigationExplanation`, and associated enums with full validation.
  - Tenancy Repository CRUD: Scoped CRUD operations for correlations, scam-chain stages, and grievance records.
  - Investigation Correlation Engine (`InvestigationCorrelator`): Deterministic multi-content and cross-entity graph correlation with typed edges, strict strength hierarchy (`STRONG`, `MEDIUM`, `WEAK`), bounded traversal safeguards (max 5 hops, max 200 edges, max 25 related contents), cycle avoidance, and canonical entity normalizers (phone, UPI, domain, registration).
  - Scam-Chain Reconstructor (`ScamChainReconstructor`): 12-stage fraud lifecycle reconstruction (`LURE_FIRST_CONTACT` through `SECONDARY_RECOVERY_SCAM`) with distinct epistemic stage statuses (`OBSERVED`, `SUPPORTED`, `INFERRED`, `NOT_OBSERVED`, `UNKNOWN`), inferred prerequisite logic (withdrawal block/fee implies deposit & fake returns), and contextual hard-negative suppression for legitimate regulatory advisories.
  - Controlled Scam Taxonomy Classifier (`ScamTaxonomyClassifier`): Multi-label 14-pattern fraud classification requiring signal and contradiction combinations with zero bare-keyword triggering.
  - Safe Guidance Engine (`GuidanceEngine`): Non-investment, victim-centric actionable safety guidance, urgent 1930 / cybercrime golden-hour financial freeze, account/credential hygiene, and forensic incident preservation checklist (UTR, VPA, chats, APKs).
  - Grievance Problem Classifier & Router (`GrievanceRouter`): 9-category problem classification with official statutory routing to SEBI SCORES 2.0, Cybercrime 1930, RBI CMS, and DoT Chakshu without automated external submission.
  - Epistemic Investigation Explainer (`InvestigationExplainer`): Transparent "Why was this flagged?" rationales linked directly to authoritative evidence IDs and mandatory "What we don't know" explicit uncertainty abstentions.
  - End-to-End Investigation Orchestrator (`InvestigationOrchestrator`): Multi-content pipeline execution synthesizing findings, correlation networks, scam stages, taxonomy, guidance, grievance records, and explainability dossiers.
  - Investigation Post-Quantum Trust Binding (`bind_investigation`, `verify_investigation_integrity`): NIST FIPS 204 ML-DSA-65 digital signing of canonical investigation payloads into verifiable `TrustReceipt` objects.
  - API & Inspection Views: Exposed `/api/v1/investigate` batch endpoint and sub-resource endpoints for correlations, scam chains, guidance, and grievances.
- Completed Phase 5 LangGraph Workflow, Durable Execution, Recovery & Human-in-the-Loop Review (145 tests):
  - Database Migration 003: Added `sangyan_workflow_runs` with scoped tenant indexes, retry tracking, and checkpoint pointers.
  - Domain Model Expansion: Added `WorkflowRun`, `WORKFLOW_RUN_STATUSES`, and expanded `INVESTIGATION_STATUSES` (`CORRELATING`, `FINALIZING`, `PARTIALLY_COMPLETED`, `CANCELLED`).
  - StateGraph Orchestration: Implemented typed workflow state `InvestigationWorkflowState` and 11 distinct execution nodes coordinating underlying domain engines without duplicating business logic (`sangyan/workflow/nodes.py`, `sangyan/workflow/graph.py`).
  - Durable SQLite Checkpointing: Implemented `WorkflowCheckpointer` wrapping LangGraph `SqliteSaver` in WAL mode with canonical tenant-scoped composite thread identities (`organization_id:investigation_id:run_id`).
  - Human-in-the-Loop Review Interruption: Implemented durable `interrupt()` at `review_gate_node` pausing execution for ambiguous/conflicting evidence, surviving process crashes/worker restarts, and resuming cleanly upon authorized supervisor decision via `Command(resume=...)`.
  - Epistemic Concurrency & RBAC Enforcement: First valid review decision wins under investigation locks; conflicting concurrent reviews raise `ReviewConflictError`; `sangyan_viewer` is strictly forbidden from submitting review decisions; cross-tenant access is blocked.
  - Bounded Retries & Error Isolation: Exponential backoff with audit logging for transient failures; `failure_node` preserves all prior gathered evidence with `PARTIALLY_COMPLETED` status.
  - Cancellation Semantics: Implemented `cancel_investigation()` halting in-flight work while preserving evidence and rejecting resumption of cancelled investigations.
  - Post-Quantum Trust Finalization: NIST FIPS 204 ML-DSA-65 dossier signing positioned after review gate with idempotent receipt reuse.
  - REST Workflow Endpoints: Exposed `/api/v1/workflow/start`, `/api/v1/workflow/{id}/resume`, `/api/v1/workflow/{id}/cancel`, `/api/v1/workflow/{id}/state`, and `/api/v1/workflow/runs`.

## 3. Files Changed / Created
- `sangyan/database/migrations.py` (Migration 003 statements and registration)
- `sangyan/domain/models.py`, `sangyan/domain/__init__.py` (WorkflowRun, WORKFLOW_RUN_STATUSES, expanded INVESTIGATION_STATUSES)
- `sangyan/tenancy/repository.py` (WorkflowRun CRUD, error_message metadata support)
- `sangyan/workflow/__init__.py` (Package exports)
- `sangyan/workflow/errors.py` (WorkflowError, ReviewConflictError, CannotCancelCompletedInvestigationError, InvestigationCancelledError, CheckpointNotFoundError, TenantMismatchError, RetryableWorkflowError, NonRetryableWorkflowError)
- `sangyan/workflow/state.py` (InvestigationWorkflowState TypedDict, create_initial_workflow_state)
- `sangyan/workflow/checkpointer.py` (WorkflowCheckpointer, thread formatting and tenant validation)
- `sangyan/workflow/nodes.py` (WorkflowNodeSuite with 11 execution nodes and should_review_condition)
- `sangyan/workflow/graph.py` (InvestigationWorkflow StateGraph compilation)
- `sangyan/workflow/service.py` (WorkflowService managing lifecycle, concurrency locks, cancellation, and resumes)
- `sangyan/api/app.py`, `sangyan/api/routes.py` (REST workflow endpoints and factory wiring)
- `tests/test_database.py` (Migration 003 verification)
- `tests/test_workflow.py` (12 comprehensive workflow acceptance tests covering all scenarios)
- `tests/test_api.py` (10 tests including workflow lifecycle and cancellation REST tests)
- `decisions.md` (Architectural decisions D-037 through D-043)
- `flow.md` (Section 9 LangGraph pipeline architecture and Session Changelog)
- `MODEL_CHANGES.md` (Section 8 workflow models, state contracts, and Migration 003 schema)
- `handoff.md` (Updated project status and Phase 5 completion)

## 4. Current Architecture / State
- Package: `sangyan` (installed in editable mode in Python 3.13 venv)
- Database: Migrations 001, 002, 003 creating 20 core relational tables. SQLite WAL mode enabled.
- Cryptography: Pure-Python ML-DSA-65 (`dilithium-py`) + SHA3-256 canonical JSON.
- Security: Socket-level SSRF validation with private/loopback/link-local IP blocking.
- Tenancy: `TenantRepository` enforcing organization boundaries and RBAC permissions across all tables.
- Ingestion (`sangyan.ingest`): Text cleaning, URL extraction, bounded streaming fetcher.
- Content Intelligence (`sangyan.intelligence`): Multilingual identification, atomic claims, entity resolver, observable safety signals.
- Authoritative Verification (`sangyan.verification`): Source registry, snapshots, adapters (SEBI, MCA, Circulars, Domains, Market Infrastructure, Payment), conflict resolution, post-quantum trust receipts.
- Correlation & Guidance (`sangyan.correlation`): Graph correlator, 12-stage scam chains, 14-pattern taxonomy, safe guidance, grievance router, explainer with uncertainty abstentions, investigation orchestrator, and PQC investigation trust receipts.
- Workflow Orchestration (`sangyan.workflow`): LangGraph StateGraph, durable SQLite checkpointing, human-in-the-loop review interruption, bounded retries, concurrency locking, and post-quantum trust finalization.
- API (`sangyan.api`): FastAPI REST API, workflow execution endpoints, and server-rendered HTML inspection views with Section 40 banners.

## 5. Decisions Made
- D-001 through D-036: Phase 1 to Phase 4 decisions.
- D-037: LangGraph StateGraph Architecture & Workflow State Model
- D-038: Durable SQLite Checkpointing & Tenant-Scoped Thread Identity (`org:inv:run`)
- D-039: Human-in-the-Loop Durable Interruption & Resume Semantics
- D-040: Fault Resilience, Bounded Retry Policy & Error Classification
- D-041: Workflow Cancellation Semantics & Partial State Preservation
- D-042: Epistemic Review Concurrency & Multi-Tenant Authorization Guardrails
- D-043: Post-Quantum Trust Finalization & Idempotent Dossier Signing

## 6. Requirements and Constraints
- Git authorship: strictly `PrathamKapoor <prathamkapoor027@gmail.com>`. Zero AI attribution across code, tests, docs, and git commit history.
- Preservation of PQC cryptography (`dilithium-py` ML-DSA-65, SHA3-256, canonical JSON).
- Strict orchestration boundaries: LangGraph orchestrates domain services without duplicating business logic in graph nodes.
- Durable persistence: StateGraph checkpoints survive process restart, worker crashes, and review interruptions via SQLite WAL checkpointer.
- Strict non-investment advice guardrails: no price predictions, no buy/sell calls, no broker endorsements.
- Multi-tenant isolation: Thread IDs and checkpoints pre-validated to prevent cross-tenant leakage.

## 7. Testing and Verification
- Full test suite: **145 passed in 24.76s**, 0 failures, exit code 0 (`python -m pytest tests -v`).
- `tests/test_workflow.py`: 12 passed (Scenarios 1-13: normal investigation, review interruption, crash restart, dependency failure retry, permanent failure evidence preservation, cross-tenant isolation, review race condition, trust signing failure resilience, cancellation lifecycle, role enforcement, trust idempotency, multi-tenant concurrency).
- `tests/test_api.py`: 10 passed (REST endpoints, batch investigation endpoint, HTML inspection views, workflow start/resume lifecycle, workflow cancellation).
- `tests/test_correlation.py`: 20 passed.
- `tests/test_verification_extended.py`: 10 passed.
- `tests/test_verification.py`: 28 passed.
- `tests/test_intelligence.py`: 19 passed.
- `tests/test_domain.py`: 22 passed.
- `tests/test_ingest.py`: 7 passed.
- `tests/test_database.py`: 4 passed (including Migration 003).
- `tests/test_crypto.py`: 3 passed.
- `tests/test_security.py`: 3 passed.
- `tests/test_trust.py`: 2 passed.
- `tests/test_persistence.py`: 4 passed.

## 8. Known Issues / Risks
- None identified in Phase 1, Phase 2, Phase 3, Phase 4, or Phase 5.

## 9. Unfinished Work
- Phase 6: REST API & Security (external auth, JWT/API key authentication, rate limiting middleware, metrics).
- Phase 7: Next.js Frontend.

## 10. Next Subphase
Phase 6: REST API & Security (Production authorization middleware, rate limiting, OpenAPI specifications, telemetry, and security audit).

## 11. Critical Context
- Target environment uses Python 3.13 venv at `C:\Projects\SIH26\TRUST-SAT\.venv313repro`.
- All Git operations must maintain `PrathamKapoor <prathamkapoor027@gmail.com>`.
- Preserved zero AI attribution across all files and git logs.

## 12. Agent Instructions
- Ensure tests pass with real output before committing.
- Keep `decisions.md` and `flow.md` updated in the same step as code changes.
