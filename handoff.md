# SANGYAN — Project Handoff

## 1. Current Phase
Phase 9 — Asynchronous Execution, Multi-Region Disaster Recovery & Failure-Oriented Production Hardening (COMPLETED)

## 2. Work Completed
- Completed Phase 0 reconnaissance of SAT-SA-with-PQC and Sentiment Analysis codebases.
- Completed Phase 1 Foundation Setup & Domain Migration (PQC crypto, database engine, migrations, domain models, multi-tenancy, SSRF protection, trust receipts, 37 tests).
- Completed Phase 2 Ingestion, Text Cleaning, Multilingual Classification, Atomic Claims, Entity Resolution, Observable Safety Signals, and Content Intelligence Pipeline (64 tests).
- Completed Phase 3 Authoritative Verification, Evidence Retrieval, Findings, Conflict Resolution, and Trust Binding (110 tests):
  - Controlled Authoritative Source Registry, versioned snapshots, caching, adapters, 5 epistemic stances, evidence provenance, chained audit ledger, REST API and HTML views, ML-DSA-65 trust receipts.
- Completed Phase 4 Investigation Correlation, Scam-Chain Reconstruction & Safe Guidance (131 tests):
  - Migration 002, graph correlation with cycle avoidance, 12-stage fraud lifecycle reconstruction, 14-pattern taxonomy classifier, victim safety guidance, statutory grievance router (SCORES, Cybercrime 1930, RBI CMS, Chakshu), epistemic explainer with uncertainty abstentions, ML-DSA-65 dossier signing.
- Completed Phase 5 LangGraph Workflow, Durable Execution, Recovery & Human-in-the-Loop Review (145 tests):
  - Migration 003, StateGraph orchestration (11 nodes), SqliteSaver checkpointer in WAL mode, human-in-the-loop durable interrupt() and resume, first-valid-review concurrency locking, bounded retries, evidence-preserving cancellation, PQC trust finalization, workflow REST API.
- Completed Phase 6 Production API, Authentication, Authorization & Security Hardening (177 tests):
  - Migration 004, dual JWT Bearer + prefixed hashed API key authentication, mutual credential exclusivity, strict JWT validator, hashed API key CRUD, contextual multi-tenant RBAC, token-bucket rate limiting, transport security headers, 2 MB body bounds, Prometheus metrics at `/metrics`, sensitive data redaction.
- Completed Phase 7 Production Deployment, Containerization, Backup & Runtime Hardening (205 tests):
  - CIS-Hardened Multi-Stage Docker Container (`sangyan:0.7.0`, UID 10001, read-only rootfs).
  - Single-replica topology enforcement, fail-closed configuration validation, decoupled health probes (`/health/live`, `/health/ready`), durable SQLite WAL checkpointer, concurrency-locked migrations, cryptographic backup & restore with AES-256-GCM.
- Completed Phase 8 Distributed Production Architecture, PostgreSQL Checkpointing, Redis Rate Limiting & Cloud Resilience (239 tests):
  - PostgreSQL Connection Pooling Engine (`PostgresDatabaseEngine`, `psycopg_pool`), durable LangGraph PostgreSQL checkpointing (`PostgresSaver`), distributed Redis token-bucket rate limiter and shared failed-auth lockout, database-level atomic review concurrency, chained audit ledger transaction locking (`pg_advisory_xact_lock`), offsite cloud backup replication (`S3BackupStorage`), OpenTelemetry distributed tracing, and distributed Helm manifests.
- Completed Phase 9 Asynchronous Execution, Multi-Region Disaster Recovery & Failure-Oriented Production Hardening (275 tests):
  - **Durable Asynchronous Task Execution (Redis Streams)**: Implemented `RedisStreamTaskQueue` and `InMemoryTaskQueue` using Redis consumer groups (`XGROUP CREATE`, `XREADGROUP`, `XACK`, `XAUTOCLAIM`/`XPENDING`+`XCLAIM`), atomic lease management (`AsyncTaskRepository`), lease heartbeat renewal thread, and bounded retries with exponential backoff and decorrelated full jitter.
  - **Human-in-the-Loop (HITL) Capacity Decoupling**: When LangGraph pauses at `review_gate_node` (`AWAITING_REVIEW`), the worker completes the task stage, persists intermediate checkpoint, acknowledges the stream message, and releases worker capacity immediately without holding leases or sleeping. Resumption occurs asynchronously via `WORKFLOW_RESUME` tasks.
  - **Multi-Region Active-Passive Disaster Recovery & Split-Brain Fencing**: Implemented `DisasterRecoveryManager` governing monotonic region authority epochs and fencing states. Pre-write fencing check (`TenantRepository._assert_write_authority`) rejects mutating operations on standby or demoted regions with `StaleRegionError` (`HTTP 409 Conflict`). Idempotent promotion transitions secondary to `PRIMARY_ACTIVE`, increments epoch, and fences the stale primary.
  - **Audit Ledger Linear Continuity**: Validated cryptographic SHA3-256 hash chaining remains unbroken across multi-region failover events without forks or sequence anomalies (`verify_audit_continuity`).
  - **Migration 005 Schema Expansion**: Added `MIGRATION_005_STATEMENTS` provisioning `sangyan_async_tasks` (task ledger / outbox) and `sangyan_region_fencing` (regional authority epochs and fencing states).
  - **Operational CLI & API Extensions**: CLI commands (`worker`, `dr status`, `dr promote`, `dr simulate`, `task list`, `task inspect`, `task dead-letter`, `task retry`), asynchronous API workflows (`POST /workflow/start?async_exec=true` returning `202 Accepted`, `GET /tasks/{task_id}`, `GET /tasks/dead-letter`, `POST /tasks/{task_id}/retry`, `GET /dr/status`, `POST /dr/promote`, `POST /dr/simulate`).
  - **Kubernetes Worker Packaging & Helm Manifests**: Added `deploy/helm/sangyan/templates/deployment-worker.yaml` (UID/GID `10001:10001`, `readOnlyRootFilesystem: true`, `command: ["python", "-m", "sangyan.cli", "worker"]`), `templates/hpa-worker.yaml`, updated `values.yaml`, `templates/configmap.yaml`, and `docker-compose.distributed.yml` with `sangyan-worker`.
  - **Exhaustive Failure Verification**: Added test suites across Scenarios A through G (worker crash mid-execution, broker outage, degraded DB startup health, dead-letter quarantine, stale region fencing, audit continuity, route precedence collision defense).

## 3. Files Changed / Created
- `sangyan/async_exec/models.py` (`AsyncTask`, `TaskStatus`, `TaskType`, `VALID_TASK_TRANSITIONS`, exponential backoff with jitter)
- `sangyan/async_exec/queue.py` (`TaskQueue` ABC, `RedisStreamTaskQueue`, `InMemoryTaskQueue`)
- `sangyan/async_exec/repository.py` (`AsyncTaskRepository` for atomic leasing, renewals, completions, dead-letter queries, and retries)
- `sangyan/async_exec/worker.py` (`AsyncInvestigationWorker` with HITL capacity decoupling, lease heartbeat, and graceful signal shutdown)
- `sangyan/dr/models.py` (`RegionRole`, `RegionFencingRecord`)
- `sangyan/dr/manager.py` (`DisasterRecoveryManager` for monotonic epochs, split-brain fencing, audit continuity verification)
- `sangyan/core/errors.py` (Added `StaleRegionError`, `AsyncTaskError`, `TaskNotFoundError`, `TaskLeaseExpiredError`)
- `sangyan/database/migrations.py` (Added Migration 005: `sangyan_async_tasks` and `sangyan_region_fencing`)
- `sangyan/tenancy/repository.py` (Pre-write fencing assertion `_assert_write_authority`, tenant-scoped task management methods)
- `sangyan/config.py` (Added Phase 9 configuration options: `task_queue_*`, `dr_*`, `region_id`, `secondary_*`)
- `sangyan/api/routes.py` (Async workflow execution query parameter, task inspection, dead-letter management, DR endpoints)
- `sangyan/api/app.py` (Wired `dr_manager` and `task_queue` into lifespan, app state, repositories, and routes)
- `sangyan/cli.py` (CLI commands: `worker`, `dr status`, `dr promote`, `dr simulate`, `task list`, `task inspect`, `task dead-letter`, `task retry`)
- `deploy/helm/sangyan/templates/deployment-worker.yaml` (Non-root worker Deployment manifest)
- `deploy/helm/sangyan/templates/hpa-worker.yaml` (HorizontalPodAutoscaler for async worker pods)
- `deploy/helm/sangyan/values.yaml` (Added worker and disaster recovery configuration blocks)
- `deploy/helm/sangyan/templates/configmap.yaml` (Exposed task queue and DR environment variables)
- `docker-compose.distributed.yml` (Added `sangyan-worker` container service)
- `decisions.md` (Recorded architectural decisions D-067 through D-073)
- `flow.md` (Section 13 Asynchronous Execution, Stream Leasing, HITL Decoupling & Multi-Region DR Flow)
- `MODEL_CHANGES.md` (Section 12 Phase 9 Asynchronous Execution & Multi-Region Disaster Recovery Models)
- `README.md` (Added worker, task management, and multi-region disaster recovery runbooks)
- `tests/test_async_task_model.py` (8 tests for AsyncTask lifecycle, state transitions, and backoff calculation)
- `tests/test_async_queue.py` (3 tests for Redis Streams and InMemory queues)
- `tests/test_dr_failover.py` (6 tests for epoch monotonicity, fencing, write rejection, audit continuity, drill simulation)
- `tests/test_async_worker.py` (7 tests for worker execution, HITL decoupling, retry backoff, dead-lettering, heartbeat)
- `tests/test_async_api.py` (5 tests for async workflow initiation, polling, dead-letter retrieval, retry, and DR endpoints)
- `tests/test_phase9_failure_scenarios.py` (7 tests covering Scenarios A through G)

## 4. Current Architecture / State
- Package: `sangyan` (version `0.7.0`, installed in editable mode in Python 3.13 venv)
- Database: Dual SQLite WAL / PostgreSQL engine with connection pooling (`psycopg_pool`), migrations 001..005, and advisory locking.
- Topology: Multi-replica API cluster (`sangyan-api-1`, `sangyan-api-2`), async workers (`sangyan-worker`), PostgreSQL pool, and Redis cluster.
- Asynchronous Engine: Redis Streams with consumer groups (`XREADGROUP`), atomic leasing, lease renewal heartbeat thread, bounded retry backoff with jitter, dead-letter quarantine, and graceful SIGTERM/SIGINT shutdown.
- HITL Decoupling: Paused workflows (`AWAITING_REVIEW`) release worker capacity immediately; resumption is processed via asynchronous `WORKFLOW_RESUME` tasks.
- Disaster Recovery: Active-passive multi-region architecture governed by monotonic authority epochs, pre-write fencing check (`StaleRegionError` 409 Conflict), idempotent promotion, and linear SHA3-256 audit ledger continuity without forks.
- Workflow Checkpointing: Pluggable SQLite WAL (`SqliteSaver`) or PostgreSQL (`PostgresSaver`) with tenant thread isolation.
- Security Gateway: Dual authentication (JWT Bearer + prefixed hashed API keys), multi-tenant RBAC, distributed Redis token-bucket rate limiter, cluster-wide failed-auth lockout, transport headers, 2 MB body bounds, Prometheus metrics, and OpenTelemetry tracing.

## 5. Decisions Made
- D-001 through D-066: Phase 1 to Phase 8 decisions.
- D-067: Redis Streams Consumer Groups for Durable Task Execution & Outbox Persistence
- D-068: Atomic Leases, Renewal Heartbeats & Poison-Pill Dead-Letter Quarantine
- D-069: Decoupled Human-in-the-Loop (HITL) Worker Capacity Model
- D-070: Multi-Region Active-Passive Epoch Authority & Split-Brain Fencing
- D-071: Cross-Region Cryptographic Audit Ledger Linear Continuity
- D-072: Fail-Closed Degradation & Startup Probe Non-Blocking Self-Registration
- D-073: Dedicated Worker Container Packaging & Horizontal Pod Autoscaling

## 6. Requirements and Constraints
- Git authorship: strictly `PrathamKapoor <prathamkapoor027@gmail.com>`. Zero AI attribution across code, tests, docs, and git commit history.
- Research & Paper Guardrail: strictly do NOT touch `paper/`, `research/`, `*.tex`.
- Investor-Safety Guardrail: no investment advice, price predictions, buy/sell calls, broker endorsements.
- HITL Decoupling Invariant: Workers must never hold leases or sleep while investigations are in `AWAITING_REVIEW`.
- Fencing Invariant: Standby, demoted, or fenced regions must reject all write operations with `StaleRegionError` (`HTTP 409 Conflict`).
- Pre-Upload Encryption Invariant: Cloud storage adapters strictly reject unencrypted backups. Plaintext database dumps never touch cloud object storage.
- Epistemic Trace Privacy: Spans and logs must never contain raw user input, investment claims, credentials, or PII.

## 7. Testing and Verification
- Full test suite: **275 passed in 70s**, 0 failures, exit code 0 (`python -m pytest tests`).
  - Baseline tests (Phases 1-8): 239/239 passing.
  - Phase 9 async and DR tests: 36/36 passing:
    * `tests/test_async_task_model.py` (8 tests)
    * `tests/test_async_queue.py` (3 tests)
    * `tests/test_dr_failover.py` (6 tests)
    * `tests/test_async_worker.py` (7 tests)
    * `tests/test_async_api.py` (5 tests)
    * `tests/test_phase9_failure_scenarios.py` (7 tests)
- Failure-Oriented Verification:
  - Scenario A: Worker crashes mid-execution; task lease expires; second worker claims and finishes task.
  - Scenario B: Broker outage; worker handles redis connection drop gracefully without leaking tasks.
  - Scenario C: Poison pill task fails 3 times; enters `DEAD_LETTER`; manual operator recovery resets attempts and succeeds.
  - Scenario D: Human review pause releases worker capacity immediately; worker processes subsequent tasks; resume task completes stage 2.
  - Scenario E: Stale region write rejection; fenced region raises `StaleRegionError` (409 Conflict).
  - Scenario F: Audit hash continuity verified across region failover; SHA3-256 hash chaining unbroken across promotions.
  - Scenario G: Degraded database on boot allows app startup; readiness probe returns 503 without crashing.
- Kubernetes Manifest Verification:
  - `tests/test_k8s_manifests.py` verified `deployment-worker.yaml`, `hpa-worker.yaml`, non-root `10001:10001`, and `readOnlyRootFilesystem: true`.

## 8. Next Phase / Immediate Priorities
- **Phase 10: Real-Time Streaming Intelligence, SSE / WebSocket Telemetry & Hardware Security Module (HSM) Trust Integration**:
  - Server-Sent Events (SSE) / WebSocket streaming of LangGraph node execution progress to frontend investigative consoles.
  - External Post-Quantum Cryptography Hardware Security Module (HSM / PKCS#11) integration for ML-DSA-65 root keys.
  - Cross-region continuous database replication topologies.

