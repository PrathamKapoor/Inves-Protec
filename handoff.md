# SANGYAN — Project Handoff

## 1. Current Phase
Phase 7 — Production Deployment, Containerization, Backup & Runtime Hardening (COMPLETED)

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
  - **CIS-Hardened Multi-Stage Docker Container**: Based on `python:3.13-slim`, dedicated non-root user `sangyan` (UID 10001, GID 10001), hardened read-only application files (`0555`), write-restricted volumes (`/app/data`, `/app/checkpoints`, `/app/keys`, `/app/backups`, `/tmp`), zero build tools in runtime, `.dockerignore` context hygiene, exec-form entrypoint `["python", "-m", "sangyan.cli"]`.
  - **Single-Replica Topology Invariants**: Documented and enforced `replicas: 1` constraint across Helm and Compose. Prevents multi-replica state drift for in-process rate limiting, SQLite WAL checkpointing, and thread-local investigation locks.
  - **Strict Production Configuration Validation**: Implemented `SangyanConfig`, `load_config()`, and `validate_production_config(strict=True)` in `sangyan/config.py`. Enforces 256-bit secret entropy, rejects known default tokens, forbids wildcard CORS in production, and mandates authentication.
  - **Decoupled Operational Health Semantics**: Implemented `/health/live` (process responsiveness), `/health/ready` (database connectivity and migration currency), and legacy `/health` (startup readiness) with zero secret or stack trace leakage.
  - **Durable LangGraph SQLite WAL Checkpoint Persistence**: Configured persistent disk-backed checkpointing at `/app/checkpoints/workflow_checkpoints.db` surviving pod restarts, rolling upgrades, and SIGTERM termination.
  - **Concurrency-Locked Database Migration Lifecycle**: Added PostgreSQL advisory locking (`pg_advisory_lock(837192)`) and SQLite immediate transaction double-checked locking in `MigrationRunner`. Designed Kubernetes pre-rollout Job hook (`job-migration.yaml`).
  - **Automated Cryptographic Backup & Isolated Restore**: Implemented `BackupManager` in `sangyan/database/backup.py` with SQLite online `VACUUM INTO` snapshots, WAL flushing, SHA-256 integrity digest manifests, PBKDF2 (100k rounds) + AES-256-GCM encryption, directory-traversal-safe restore (`_safe_extract_tar`), automatic retention pruning, and isolated PRAGMA integrity verification.
  - **Production Kubernetes & Helm Deployment**: Production-grade Helm chart in `deploy/helm/sangyan/` with `values.schema.json`, Ingress with TLS and external `/metrics` blocking (404), strict `NetworkPolicy`, `ServiceMonitor`, resource limits, and backup `CronJob`.
  - **Full Operational CLI**: Implemented Click CLI in `sangyan/cli.py` (`serve`, `migrate`, `migrate-status`, `backup create`, `backup verify`, `backup restore`, `backup prune`, `health`).

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
- `flow.md` (Section 11 Production Runtime Architecture, Deployment Rollout & Disaster Recovery Flow)
- `MODEL_CHANGES.md` (Section 10 SangyanConfig, BackupMetadata, Helm values schema)
- `handoff.md` (Updated project status and Phase 7 completion)

## 4. Current Architecture / State
- Package: `sangyan` (version `0.7.0`, installed in editable mode in Python 3.13 venv)
- Container Image: `sangyan:0.7.0` (built and verified locally with Docker)
- Database: Dual SQLite WAL / PostgreSQL engine with migrations 001..004 and concurrency locking.
- Topology: Single-replica (`replicas: 1`) API pod with pre-rollout migration Job and scheduled backup CronJob.
- Security Gateway: Dual authentication (JWT Bearer + prefixed hashed API keys), multi-tenant RBAC, token-bucket rate limiter, transport headers, 2 MB body bounds, Prometheus telemetry with credential redaction.
- Health Probes: Decoupled `/health/live` (process alive), `/health/ready` (DB connected & migrations applied), `/health` (startup).
- Backup & Restore: Online SQLite WAL snapshots, AES-256-GCM encryption, PBKDF2 key derivation, SHA-256 manifests, isolated restore verification.
- Ingress Boundary: TLS termination, 2 MB client payload bound, `/metrics` blocked with HTTP 404.
- Network Policy: Ingress restricted to ingress-controller and Prometheus scraper; egress restricted to DNS (53), HTTPS (443), and optional Postgres (5432).

## 5. Decisions Made
- D-001 through D-050: Phase 1 to Phase 6 decisions.
- D-051: Production Container Packaging, Base Image & CIS Non-Root User (UID 10001)
- D-052: Single-Replica Production Topology Constraint & Multi-Worker Elimination
- D-053: Fail-Closed Production Configuration Validation & Secret Boundary
- D-054: Decoupled Operational Health, Liveness & Readiness Semantics
- D-055: Durable SQLite WAL LangGraph Checkpoint Persistence
- D-056: Database Migration Lifecycle, Concurrency Locking & Pre-Rollout Hook
- D-057: Cryptographic Backup, Integrity Manifests, AES-256-GCM Encryption & Safe Restore
- D-058: Kubernetes & Helm Production Deployment Architecture

## 6. Requirements and Constraints
- Git authorship: strictly `PrathamKapoor <prathamkapoor027@gmail.com>`. Zero AI attribution across code, tests, docs, and git commit history.
- Research & Paper Guardrail: strictly do NOT touch `paper/`, `research/`, `*.tex`.
- Investor-Safety Guardrail: no investment advice, price predictions, buy/sell calls, broker endorsements.
- Single-Replica Invariant: SANGYAN MUST run with `replicas: 1` due to process-local rate limiters, SQLite WAL single-writer semantics, and in-memory thread locks. Horizontal scaling requires distributed cache/locking infrastructure (deferred to future distributed roadmap).
- Read-Only Root Filesystem: Application code directory is read-only (`0555`). All persistent writes must go to dedicated mounted volumes (`/app/data`, `/app/checkpoints`, `/app/keys`, `/app/backups`, `/tmp`).
- Non-Root Execution: Must run as UID 10001 (sangyan). Never run as root.
- Secret Hygiene: No plaintext secrets in image layers, Git commits, Helm values, metrics, or health probes.

## 7. Testing and Verification
- Full test suite: **205 passed in 33.06s**, 0 failures, exit code 0 (`python -m pytest tests -v`).
  - Baseline tests: 177/177 passing.
  - Phase 7 tests: 28/28 passing (`tests/test_config.py`, `tests/test_health_probes.py`, `tests/test_backup.py`, `tests/test_migration_concurrency.py`, `tests/test_container_hardening.py`, `tests/test_k8s_manifests.py`).
- Docker Container Runtime Verification:
  - Built image: `sangyan:0.7.0` (multi-stage build succeeded).
  - Verified non-root user: `id` output `uid=10001(sangyan) gid=10001(sangyan)`.
  - Verified read-only rootfs: writing to `/app/sangyan` rejected with `Read-only file system`.
  - Verified live API: container started with `python -m sangyan.cli serve`, `/health/live` returned 200 `{"status": "alive"}`, `/health/ready` returned 200 `{"status": "ready"}`.
  - Verified graceful shutdown: `docker stop` cleanly trapped SIGTERM, logged shutdown sequence, and exited 0 within grace period.
  - Verified encrypted backup in container: `python -m sangyan.cli backup create --encrypt-password ...` successfully produced encrypted archive with manifest and SHA-256 checksum.
- Docker Compose Verification: `docker compose config` passed validation with 0 errors.
- Helm Chart Verification:
  - `helm lint deploy/helm/sangyan` passed with 0 errors and 0 warnings.
  - `helm template sangyan deploy/helm/sangyan` successfully rendered all 10 Kubernetes resource manifests.
- Cluster Status: Kubernetes live cluster deployment is marked as **BLOCKED** due to no active local Kubernetes cluster, but all manifests and Helm charts are statically verified and linted.

## 8. Next Phase / Immediate Priorities
- **Phase 8: High-Availability & Distributed Scaling Roadmap (Future Scope)**:
  - External PostgreSQL with HA connection pooling (PgBouncer).
  - Distributed Redis-backed rate limiting and session tracking (enabling horizontal replica scaling > 1).
  - LangGraph Postgres checkpointer integration (`PostgresSaver`).
  - S3 / GCS cloud object storage adapter for offsite backup replication.
  - OpenTelemetry distributed tracing integration (Jaeger / OTel Collector).
