# SANGYAN — Project Handoff

## 1. Current Phase
Phase 8 — Distributed Production Architecture, PostgreSQL Checkpointing, Redis Rate Limiting & Cloud Resilience (COMPLETED)

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
  - **PostgreSQL Connection Pooling Engine**: Implemented `PostgresDatabaseEngine` using `psycopg_pool.ConnectionPool` (`min_size=2`, `max_size=20`, `timeout=10.0s`), thread-local connection binding in `transaction()` (`self._local = threading.local()`), `execute()` returning affected rowcounts, pool health metrics, and ping verification.
  - **Durable LangGraph PostgreSQL Checkpointing**: Integrated `PostgresSaver` checkpointer supporting pooled PostgreSQL connections, schema initialization (`saver.setup()`), and tenant-scoped thread identity (`<org_id>:<inv_id>:<run_id>`) preventing cross-tenant access.
  - **Distributed Redis Rate Limiter & Cluster-Wide Lockout**: Implemented `RedisRateLimiter` with atomic Lua script (`LUA_TOKEN_BUCKET_SCRIPT`) and `RedisFailedAuthTracker` sliding-window sorted set lockout. Supports `fail_closed_mutations`, `fail_open`, and transparent `local_fallback`.
  - **Database-Level Atomic Review Concurrency**: Eliminated process-local review locks. Governed human-in-the-loop transitions with atomic SQL (`UPDATE sangyan_investigations SET status='FINALIZING' WHERE id=? AND status='AWAITING_REVIEW'`), raising `ReviewConflictError` (409 Conflict) on competing pods.
  - **Chained Audit Ledger Serialization**: Added PostgreSQL transaction-level advisory locking (`pg_advisory_xact_lock(918273)`) to serialize audit chain writes per-tenant and eliminate hash chain forks.
  - **Offsite Cloud Backup Replication & Isolated Remote Restore**: Implemented `S3BackupStorage` and `LocalMockCloudStorage` with strict pre-upload encryption enforcement (rejects plaintext uploads), SHA-256 checksum validation, retry with exponential backoff, isolated download and decryption, and retention pruning preserving latest verified backups.
  - **OpenTelemetry Distributed Tracing & Privacy Guardrails**: Implemented `TracingMiddleware`, `trace_span`, and `sanitize_span_attributes` rejecting raw claims, tokens, and PII from span attributes, with zero-overhead `NoOpTracer` fallback.
  - **Distributed Helm & Multi-Replica Topology**: Provided `values-distributed.yaml`, relaxed `replicaCount` validation, added `hpa.yaml`, egress to Redis in `networkpolicy.yaml`, and created multi-replica cluster topology in `docker-compose.distributed.yml`.

## 3. Files Changed / Created
- `Dockerfile` (Multi-stage non-root container packaging with CIS hardening)
- `.dockerignore` (Strict context exclusion: `.git`, `.env*`, tests, local DBs, keys)
- `docker-compose.yml` (Single-replica topology, migration init, automated backup service)
- `.env.example` (Production configuration template with secure defaults and instructions)
- `pyproject.toml` (Added missing runtime dependencies: `pyjwt`, `prometheus-client`, `langgraph`, `langgraph-checkpoint-sqlite`; bumped version to 0.7.0)
- `sangyan/config.py` (Unified configuration loader and fail-closed production validator)
- `sangyan/cli.py` (Click CLI for serve, migrate, backup, restore, prune, health)
- `sangyan/database/backup.py` (BackupManager with AES-256-GCM encryption, SHA-256 checksums, safe restore, pruning)
- `sangyan/database/migrations.py` (Advisory and double-checked transaction locking)
- `sangyan/api/app.py` (Lifespan management, durable checkpointer, decoupled health routes)
- `deploy/helm/sangyan/` (Full Helm chart: Chart, values, schema, deployment, service, ingress, networkpolicy, job, cronjob, pvc, servicemonitor)
- `tests/test_config.py` (7 tests for configuration loading and strict validation)
- `tests/test_health_probes.py` (5 tests for liveness, readiness, migration degradation, zero secret leakage)
- `tests/test_backup.py` (6 tests for backup creation, AES-256-GCM encryption, verification, isolated restore, pruning)
- `tests/test_migration_concurrency.py` (2 tests for migration locking and concurrency safety)
- `tests/test_container_hardening.py` (3 tests for Dockerfile CIS compliance, non-root user, .dockerignore)
- `tests/test_k8s_manifests.py` (3 tests for Helm chart syntax, single-replica enforcement, security contexts)
- `decisions.md` (Recorded architectural decisions D-051 through D-058)
- `flow.md` (Section 12 Distributed Runtime Architecture, Checkpoint Durability, Redis Rate Limiting & Cloud Resilience Flow)
- `MODEL_CHANGES.md` (Section 11 PostgreSQL Pooling, Redis Rate Limiting, Cloud Backup Manifest, Tracing, and Helm Scaling)
- `decisions.md` (Recorded architectural decisions D-059 through D-066)
- `sangyan/database/postgres.py` (PostgresDatabaseEngine with ConnectionPool, thread-local transactions, pool status, and ping)
- `sangyan/database/engine.py` (Added affected rowcount reporting to execute())
- `sangyan/tenancy/repository.py` (Atomic conditional status transition and pg_advisory_xact_lock audit serialization)
- `sangyan/workflow/service.py` (Database-level review race resolution and cancellation atomic transitions)
- `sangyan/workflow/checkpointer.py` (PostgresSaver checkpointing with schema provisioning and thread access validation)
- `sangyan/security/redis_limiter.py` (RedisRateLimiter atomic token bucket Lua script and RedisFailedAuthTracker)
- `sangyan/database/cloud_backup.py` (S3BackupStorage, LocalMockCloudStorage, pre-upload encryption enforcement, isolated restore)
- `sangyan/security/tracing.py` (TracingMiddleware, trace_span, sanitize_span_attributes, NoOpTracer)
- `sangyan/api/app.py` (Integrated Redis rate limiter, Postgres checkpointer, TracingMiddleware, enhanced /health/ready probe)
- `sangyan/cli.py` (Added backup upload and backup restore-cloud commands)
- `deploy/helm/sangyan/` (values-distributed.yaml, hpa.yaml, relaxed replicaCount schema, Redis network policy egress)
- `docker-compose.distributed.yml` (Multi-replica API, PostgreSQL, Redis, migration, and backup services)
- `tests/test_database_postgres.py` (6 tests for pooling, isolation, rowcount, ping, pool status)
- `tests/test_postgres_checkpointing.py` (6 tests for PostgresSaver, setup, persistence, recovery, cross-tenant isolation)
- `tests/test_redis_rate_limiting.py` (5 tests for Lua token bucket, cluster lockout, fail_closed, fail_open, local fallback)
- `tests/test_tracing.py` (4 tests for W3C propagation, header injection, PII attribute sanitization, NoOpTracer)
- `tests/test_cloud_backup.py` (4 tests for pre-upload encryption enforcement, upload/restore, retention pruning, retry backoff)
- `tests/test_distributed_concurrency.py` (3 tests for Pod A vs Pod B review races, idempotent creation, audit lock serialization)
- `tests/test_distributed_scenarios.py` (5 tests for readiness probe, cluster rate limit exhaustion, shared auth lockout, Helm scaling)
- `handoff.md` (Updated project status and Phase 8 completion)

## 4. Current Architecture / State
- Package: `sangyan` (version `0.7.0`, installed in editable mode in Python 3.13 venv)
- Database: Dual SQLite WAL / PostgreSQL engine with connection pooling (`psycopg_pool`), migrations 001..004, and advisory locking.
- Topology: Multi-replica horizontally scalable (`replicaCount >= 2`, HPA 2-10 replicas) backed by Redis cluster and PostgreSQL pool.
- Workflow Checkpointing: Pluggable SQLite WAL (`SqliteSaver`) or PostgreSQL (`PostgresSaver`) with tenant thread isolation.
- Security Gateway: Dual authentication (JWT Bearer + prefixed hashed API keys), multi-tenant RBAC, distributed Redis token-bucket rate limiter, cluster-wide failed-auth lockout, transport headers, 2 MB body bounds, Prometheus metrics, and OpenTelemetry tracing.
- Concurrency Control: Database-level atomic conditional state transitions (`UPDATE ... WHERE status='AWAITING_REVIEW'`) resolving human-in-the-loop review races with HTTP 409 Conflict.
- Health Probes: Decoupled `/health/live` (process alive), `/health/ready` (evaluates DB connectivity, migration currency, and Redis availability per failure mode).
- Backup & Disaster Recovery: Online snapshots, AES-256-GCM encryption, PBKDF2 key derivation, SHA-256 manifests, isolated restore verification, and S3-compatible offsite replication (`S3BackupStorage`) with strict pre-upload encryption enforcement.
- Tracing & Privacy: OpenTelemetry W3C trace propagation with privacy boundary rejecting raw claims, tokens, and PII.

## 5. Decisions Made
- D-001 through D-058: Phase 1 to Phase 7 decisions.
- D-059: PostgreSQL Connection Pooling & Thread-Local Transaction Isolation
- D-060: LangGraph PostgreSQL Workflow Checkpointing (`PostgresSaver`) & Thread Isolation
- D-061: Redis Distributed Rate Limiting (Lua Token Bucket) & Failure Modes
- D-062: Database-Level Human Review Concurrency & Mutual Exclusion
- D-063: Distributed Idempotency & Tamper-Evident Chained Audit Serialization
- D-064: Offsite Cloud Backup Replication, Pre-Upload Encryption & Isolated Restore
- D-065: OpenTelemetry Distributed Tracing & Sensitive Data Redaction
- D-066: Horizontal Multi-Replica Pod Topology, Autoscaling & Network Policies

## 6. Requirements and Constraints
- Git authorship: strictly `PrathamKapoor <prathamkapoor027@gmail.com>`. Zero AI attribution across code, tests, docs, and git commit history.
- Research & Paper Guardrail: strictly do NOT touch `paper/`, `research/`, `*.tex`.
- Investor-Safety Guardrail: no investment advice, price predictions, buy/sell calls, broker endorsements.
- Distributed State Isolation: No process-local state for rate limiting, review locks, or auth throttling. All state resides in Redis or PostgreSQL.
- Pre-Upload Encryption Invariant: Cloud storage adapters strictly reject unencrypted backups. Plaintext database dumps never touch cloud object storage.
- Epistemic Trace Privacy: Spans and logs must never contain raw user input, investment claims, credentials, or PII.

## 7. Testing and Verification
- Full test suite: **239 passed in 48.67s**, 0 failures, exit code 0 (`python -m pytest tests`).
  - Baseline tests (Phases 1-7): 205/205 passing.
  - Phase 8 distributed tests: 34/34 passing:
    * `tests/test_database_postgres.py` (6 tests)
    * `tests/test_postgres_checkpointing.py` (6 tests)
    * `tests/test_redis_rate_limiting.py` (5 tests)
    * `tests/test_tracing.py` (4 tests)
    * `tests/test_cloud_backup.py` (4 tests)
    * `tests/test_distributed_concurrency.py` (3 tests)
    * `tests/test_distributed_scenarios.py` (5 tests)
- Concurrency & Race Verification:
  - Verified concurrent human review race between Pod A and Pod B: exactly one pod transitions to `FINALIZING` and the competing pod receives `ReviewConflictError` (409 Conflict).
  - Verified duplicate investigation creation: second attempt raises `DuplicateEntryError`.
  - Verified audit ledger serialization: transactional advisory lock guarantees strictly sequential hash chaining without forks.
  - Verified cluster-wide rate limit exhaustion: token consumption on Pod A exhausts limit and rejects requests on Pod B.
  - Verified cluster-wide failed-auth lockout: 3 failures on Pod A throttles requests on Pod B.
- Cloud Backup & Restore Verification:
  - Verified pre-upload encryption enforcement: unencrypted archive upload raises `ValueError`.
  - Verified end-to-end cloud replication, SHA-256 verification, remote download, and isolated restore with SQLite `PRAGMA integrity_check == 'ok'`.
  - Verified retention pruning: keeps newest N backups and guarantees the latest verified backup is never deleted.
- Kubernetes Manifest Verification:
  - `tests/test_k8s_manifests.py` and `test_scenario_15_helm_manifest_distributed_scaling` verified `values-distributed.yaml`, HPA (min 2, max 10), and NetworkPolicy with Redis egress.

## 8. Next Phase / Immediate Priorities
- **Phase 9: Enterprise Multi-Region Disaster Recovery, Asynchronous Task Queue & Streaming Intelligence**:
  - Asynchronous background workers for long-running batch investigations (Celery / ARQ / Redis Streams).
  - Real-time Server-Sent Events (SSE) / WebSocket streaming of LangGraph node execution progress to frontend.
  - Multi-region active-passive failover and automated cross-region database read replicas.
