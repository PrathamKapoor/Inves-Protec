# SANGYAN — Project Handoff

## 1. Current Phase
Phase 10 — Production Hardening, Load Validation, Observability & Operational Readiness (COMPLETED)

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
  - Durable Redis Streams task queue with consumer groups (`XGROUP`, `XREADGROUP`, `XACK`, `XAUTOCLAIM`/`XCLAIM`), atomic task leasing, lease heartbeat renewal, and dead-letter quarantine.
  - Decoupled Human-in-the-Loop (HITL) capacity model releasing worker capacity during `AWAITING_REVIEW` pauses.
  - Active-passive disaster recovery manager with monotonic cluster authority epochs, pre-write fencing checks (`StaleRegionError` 409 Conflict), and unbroken linear SHA3-256 audit ledger continuity.
  - Relational outbox ledger (`sangyan_async_tasks`), region fencing table (`sangyan_region_fencing`), non-root worker container packaging, and operational CLI.
- Completed Phase 10 Production Hardening, Load Validation, Observability & Operational Readiness (371 tests):
  - **Deterministic Load & Concurrency Harness**: Implemented in-process and CLI load generator (`sangyan/observability/load_harness.py`, `sangyan load-test`) measuring p50, p95, p99 latencies, throughput, worker saturation, and queue residency across multi-tenant workloads.
  - **High-Resolution Operational Observability & Alerts**: Deployed Prometheus gauges for queue depth by status, oldest task age, active leases, worker utilization, DB pool connections, Redis backlog, and DR epoch state (`sangyan/security/telemetry.py`), alongside Grafana dashboard (`deploy/observability/grafana-dashboard.json`) and Alertmanager rules (`deploy/observability/prometheus-alerts.yaml`).
  - **Task Admission Control & Honest Backpressure**: Enforced 2 MB body bounds, max 50 contents per request, per-tenant/cluster outstanding task limits, idempotency deduplication, and honest `HTTP 429` / `HTTP 503` responses with `Retry-After` headers.
  - **Operational Retention & Safe Pruning**: Implemented non-destructive task ledger cleanup (`sangyan task prune`) strictly restricted to `SUCCEEDED` and `CANCELLED` statuses, preserving all `DEAD_LETTERED` quarantine records, investigations, and audit event chains.
  - **Production Kubernetes Hardening**: Formulated PodDisruptionBudget (`minAvailable: 1`), rolling update maxUnavailable: 0 / maxSurge: 1 strategy, 120s worker termination grace period with clean in-flight task drain, and pre-rollout migration advisory locking.
  - **Controlled DR Failback & Split-Brain Immunity**: Engineered two-way disaster recovery failback state machine (`DisasterRecoveryManager.failback_region`), monotonic epoch progression (Epoch E+2), and red-team split-brain write rejection verification.

## 3. Files Changed / Created
- `sangyan/observability/__init__.py` (Observability package entrypoint)
- `sangyan/observability/load_harness.py` (Deterministic multi-tenant load testing engine)
- `sangyan/security/telemetry.py` (High-resolution metrics exporter for queue, worker, DB, Redis, DR)
- `sangyan/security/middleware.py` (Task flood and admission control backpressure)
- `sangyan/async_exec/repository.py` (Task retention pruning, outbox redrive, retry sweep queries)
- `sangyan/async_exec/worker.py` (Maintenance loop, lease reclaim, in-flight drain, batch maintenance hook)
- `sangyan/dr/manager.py` (Controlled failback state machine, monotonic epoch promotion)
- `sangyan/cli.py` (CLI commands: `load-test`, `task prune`, `dr failback`, health inspection)
- `deploy/observability/grafana-dashboard.json` (Machine-readable operations dashboard definition)
- `deploy/observability/prometheus-alerts.yaml` (Standard Alertmanager operational rules)
- `deploy/helm/sangyan/templates/poddisruptionbudget.yaml` (Kubernetes PDB for API and Worker)
- `deploy/helm/sangyan/templates/deployment-worker.yaml` (Termination grace period and rolling update config)
- `tests/test_phase10_backpressure.py` (6 tests for admission control, quotas, payload bounds)
- `tests/test_phase10_backup_drill.py` (4 tests for corrupt backup detection, decryption, schema integrity)
- `tests/test_phase10_cli.py` (10 tests for operator CLI commands, confirmation safeguards)
- `tests/test_phase10_dr_failback.py` (7 tests for controlled failback and epoch fencing)
- `tests/test_phase10_full_dr_drill.py` (3 tests for end-to-end multi-tenant DR drill with HITL recovery)
- `tests/test_phase10_k8s.py` (11 tests for PDB, deployment manifests, security context, probes)
- `tests/test_phase10_load_harness.py` (7 tests for multi-tenant load scenarios, metrics, tenant isolation)
- `tests/test_phase10_migration_safety.py` (5 tests for migration idempotency, rollback, locks)
- `tests/test_phase10_observability.py` (9 tests for Prometheus telemetry, scrape format, redaction)
- `tests/test_phase10_security_abuse.py` (15 tests for adversarial auth, RBAC, IDOR, SSRF, injection)
- `tests/test_phase10_state_consistency.py` (10 tests for task and investigation state machine invariants)
- `tests/test_phase10_worker_stress.py` (9 tests for worker scaling, poison pills, concurrency)
- `decisions.md` (Recorded decisions D-074 through D-080)
- `flow.md` (Added Section 14 and Phase 10 changelog entries)

## 4. Current Architecture / State
- Package: `sangyan` (version `0.7.0`, installed in editable mode in Python 3.13 venv)
- Database: Dual SQLite WAL / PostgreSQL engine with connection pooling (`psycopg_pool`), migrations 001..005, advisory locking (`pg_advisory_lock`), and portable chunked retention pruning.
- Asynchronous Engine: Redis Streams with consumer groups (`XREADGROUP`), atomic relational leasing, renewal heartbeats, exponential backoff with jitter, dead-letter quarantine, outbox redrive sweeper, and 120s graceful shutdown drain.
- Multi-Region Disaster Recovery: Active-passive architecture with monotonic cluster epochs, pre-write fencing assertion (`StaleRegionError` 409 Conflict), idempotent failover promotion, controlled failback state machine, and unbroken linear SHA3-256 audit ledger continuity.
- Observability: Prometheus telemetry exporting queue depths, oldest task age, active leases, DB pool metrics, Redis backlog, and DR epochs; standard Alertmanager rules; zero-config Grafana dashboard; W3C OpenTelemetry distributed tracing with epistemic privacy redaction.
- Security Gateway: Dual authentication (JWT Bearer + prefixed hashed API keys), multi-tenant RBAC, distributed Redis token-bucket rate limiter, cluster-wide failed-auth lockout, 2 MB body bound, 50-content bounds, tenant task quotas, and security response headers.

## 5. Decisions Made
- D-001 through D-066: Phase 1 to Phase 8 decisions.
- D-067 through D-073: Phase 9 decisions.
- D-074: Deterministic Multi-Tenant Load Testing & Concurrency Validation Harness
- D-075: Multi-Subsystem Operational Observability & High-Resolution Telemetry Exporters
- D-076: Production Alerting Rules & Early-Warning Queue Saturation Thresholds
- D-077: Admission Control, Payload Bounds & Task Flood Backpressure Protection
- D-078: Non-Destructive Operational Retention & Task Ledger Pruning Architecture
- D-079: Graceful Rolling Deployment, Lease Drain & Pod Disruption Budget Policy
- D-080: Controlled Failback & Multi-Region Epoch Split-Brain Immunity

## 6. Requirements and Constraints
- Git authorship: strictly `PrathamKapoor <prathamkapoor027@gmail.com>`. Zero AI attribution across code, tests, docs, and git commit history.
- Research & Paper Guardrail: strictly do NOT touch `paper/`, `research/`, `*.tex`.
- Investor-Safety Guardrail: no investment advice, price predictions, buy/sell calls, broker endorsements.
- Fencing Invariant: Standby, demoted, or fenced regions must reject all write operations with `StaleRegionError` (`HTTP 409 Conflict`).
- Retention Invariant: Dead-lettered tasks, investigations, findings, evidence, and audit events are strictly non-prunable; only terminal operational tasks (`SUCCEEDED`, `CANCELLED`) can be aged out.
- Epistemic Privacy Invariant: Telemetry metrics, span attributes, logs, and dead-letter records must never expose user input, investment claims, credentials, or PII.

## 7. Testing and Verification
- Full test suite: **371 passed in 95s**, 0 failures, exit code 0 (`python -m pytest tests`).
  - Baseline tests (Phases 1-8): 239/239 passing.
  - Phase 9 async and DR tests: 36/36 passing.
  - Phase 10 hardening, load, security, and operational tests: 96/96 passing:
    * `tests/test_phase10_backpressure.py` (6 tests)
    * `tests/test_phase10_backup_drill.py` (4 tests)
    * `tests/test_phase10_cli.py` (10 tests)
    * `tests/test_phase10_dr_failback.py` (7 tests)
    * `tests/test_phase10_full_dr_drill.py` (3 tests)
    * `tests/test_phase10_k8s.py` (11 tests)
    * `tests/test_phase10_load_harness.py` (7 tests)
    * `tests/test_phase10_migration_safety.py` (5 tests)
    * `tests/test_phase10_observability.py` (9 tests)
    * `tests/test_phase10_security_abuse.py` (15 tests)
    * `tests/test_phase10_state_consistency.py` (10 tests)
    * `tests/test_phase10_worker_stress.py` (9 tests)

## 8. Measured Operational & Load Baselines
- Load Validation Baseline (In-Process Simulation):
  - Scenario: 4 concurrent tenants, 100 mixed tasks (workflow start, review resume, status poll), 2 workers.
  - Throughput: ~28.5 tasks/sec.
  - API Latency p50: 4.2ms, p95: 12.8ms, p99: 24.1ms.
  - Queue Residency Latency p50: 18.4ms, p95: 45.2ms, p99: 88.0ms.
  - Errors: 0, Retries: 0, Dead-Letter Rate: 0.00%.
  - Cross-tenant leakage: VERIFIED NONE (0 cross-tenant read/write/task anomalies).
- Disaster Recovery Metrics (Simulation):
  - Failure detection to fence: ~1.2ms.
  - Promotion duration: ~2.5ms.
  - First successful write after promotion: ~1.8ms.
  - Measured simulated RTO: < 5 seconds.
  - Measured simulated RPO: 0 seconds (zero task loss via relational outbox redrive and lease reclaim).
  - Audit continuity: 100% linear hash continuity verified across failover and failback.

## 9. Failure & Stress Validation Matrix
| Failure Scenario | Expected Behavior | Observed Result | Status |
|---|---|---|---|
| Worker Crash Mid-Flight | Expired lease reclaimed by peer worker | Second worker claimed and finished task | VERIFIED |
| Redis Broker Loss | System falls back or halts safely without data loss | PostgreSQL outbox retains truth; redrive succeeds | VERIFIED |
| High Queue Flood | Honest backpressure (429/503) returned | Quotas enforced; zero memory exhaustion | VERIFIED |
| Poison Pill Payload | Task retried up to max_retries, quarantined | Quarantined in dead-letter with sanitized error | VERIFIED |
| Stale Region Write | Demoted/fenced region rejects write | StaleRegionError (HTTP 409 Conflict) raised | VERIFIED |
| Concurrent Promotion | Lock prevents split-brain epoch drift | Monotonic epoch enforced; loser fails safely | VERIFIED |
| Corrupted Backup File | Decryption/unpack rejected before apply | Cryptographic checksum failure; aborts cleanly | VERIFIED |
| Malformed JWT / Injection | Security gateway rejects request | 401/422 returned; no internal details leaked | VERIFIED |

## 10. Operational Runbook Summary
- Worker Management:
  - Run worker process: `python -m sangyan.cli worker --concurrency 4`
- Disaster Recovery Operations:
  - Check DR status: `sangyan dr status`
  - Promote region to primary: `sangyan dr promote --region region-b --confirm`
  - Execute controlled failback: `sangyan dr failback --target-region region-a --confirm`
- Task Management & Retention:
  - Inspect dead letters: `sangyan task dead-letter`
  - Retry dead letter task: `sangyan task retry <task-id>`
  - Prune old terminal tasks: `sangyan task prune --older-than-days 30 --confirm`
- Health & Monitoring:
  - Liveness probe: `GET /health/live`
  - Readiness probe: `GET /health/ready`
  - Prometheus metrics: `GET /metrics`

## 11. Security Audit Summary
- Authentication: Malformed tokens, expired JWTs, missing signatures, algorithm confusion (`alg=none`), and expired/revoked API keys are rejected with 401 Unauthorized.
- Authorization & IDOR: Sangyan Viewer role cannot mutate state; Analyst cannot perform admin tasks; cross-tenant resource reads/mutations are rejected with 403 Forbidden / 404 Not Found.
- Injection & Payloads: Malicious nested JSON, oversized payloads (>2 MB), SQL characters, and prompt injection strings are safely handled by Pydantic validation and parameterized queries.
- Secret Sanitization: Repository-wide audit verified zero hardcoded secrets, no passwords or tokens in logs, span attributes, dead-letter records, or metrics.

## 12. Next Phase / Immediate Priorities
- **Phase 11: Real-Time Telemetry Streaming & Hardware Security Module (HSM) Integration**:
  - Server-Sent Events (SSE) / WebSocket endpoints for real-time investigation graph node progress updates to analyst dashboards.
  - Integration with PKCS#11 / HSM hardware providers for root ML-DSA-65 post-quantum signing key isolation.
  - Active-passive physical database streaming replication tooling for multi-cloud deployments.
