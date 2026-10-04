# SANGYAN (संज्ञान)
### Investor Safety & Content Intelligence Platform

> **INVESTIGATE → VERIFY → EXPLAIN → PROTECT → GUIDE**

SANGYAN is an evidence-grounded investor safety and content intelligence platform designed to protect Indian retail investors from digital fraud, misleading financial promotions, unregistered entities, and high-risk schemes.

---

## What SANGYAN Does

1. **Intake & Normalization**: Accepts suspicious text, URLs, forwarded messages, screenshots, and documents.
2. **Decomposition**: Breaks compound messages into discrete, independently testable claims.
3. **Signal Detection**: Identifies 20+ observable financial persuasion and scam signals (guaranteed returns, urgency, authority impersonation, withdrawal fees, etc.).
4. **Authoritative Verification**: Queries official regulatory registries (SEBI, recognized exchanges, official circulars) rather than hallucinating status.
5. **Evidence Grounding**: Constructs a transparent evidence graph with explicit multi-valued statuses (`SUPPORTED`, `CONTRADICTED`, `PARTIALLY_SUPPORTED`, `UNVERIFIED`, `CONFLICTING`, `OUTDATED`, `INSUFFICIENT_EVIDENCE`).
6. **Explainability ("Why Flagged")**: Explains the exact observed facts, evidence citations, authority tiers, and explicit limitations.
7. **Safe Action Guidance**: Recommends non-investment next steps (grievance filing via SCORES, 1930 Cybercrime escalation, evidence preservation).
8. **Cryptographic Integrity**: Employs Post-Quantum Cryptography (ML-DSA-65 / Dilithium) and SHA3-256 canonical digests to produce verifiable investigation receipts.

---

## Core Guardrails — What SANGYAN Never Does

- **NO investment advice**: Never recommends buying, selling, or holding any security.
- **NO price predictions**: Never forecasts market moves or stock targets.
- **NO broker/scheme promotion**: Does not promote any financial product, intermediary, or commission-earning opportunity.
- **NO black-box fraud scores**: Avoids arbitrary "97% scam probability" numbers; exposes concrete claims and observable signals.
- **NO regulatory hallucinations**: Never invents SEBI registration numbers or legal status; distinguishes authoritative facts from model interpretations.

---

## Authority Tier Hierarchy

- **T0**: Regulator / Government / Official authority (SEBI, RBI, MCA, Cybercrime Portal)
- **T1**: Exchange / Depository / Official infrastructure (NSE, BSE, NSDL, CDSL)
- **T2**: Registered intermediary / primary authoritative entity
- **T3**: Established secondary source / financial press
- **T4**: General web source
- **T5**: Social media / user-generated content (evidence to investigate, not truth)

---

## Repository Structure

```text
C:\Projects\Sangyan/
├── sangyan/                    # Core Python application package
│   ├── api/                    # FastAPI routes, views, security middlewares, lifespan
│   ├── async_exec/             # Async task models, Redis Streams, leasing, workers
│   ├── cli.py                  # Operational CLI (serve, migrate, backup, dr, task, db)
│   ├── config.py               # Unified SangyanConfig loader & production validator
│   ├── core/                   # Errors, logging, identifiers
│   ├── correlation/            # Graph correlator, scam chains, taxonomy, guidance, explainer
│   ├── crypto/                 # Post-quantum cryptography (ML-DSA-65), PKCS#11 / HSM
│   ├── database/               # DatabaseEngine, migrations 001-007, replication, backups
│   ├── domain/                 # Investor-safety domain records & validation
│   ├── dr/                     # Active-passive DR manager, split-brain fencing, epochs
│   ├── ingest/                 # Text cleaner, bounded streaming fetcher, SSRF security
│   ├── intelligence/           # Multilingual detection, claims, entities, signals
│   ├── realtime/               # Real-time SSE event broker, streaming models, replay
│   ├── security/               # Auth gateway (JWT/API key), RBAC, rate limiter, telemetry
│   ├── tenancy/                # Multi-tenancy, memberships, sessions, repository
│   ├── trust/                  # PQC receipts & verification service, key rotation
│   ├── verification/           # Authoritative sources, snapshots, adapters, conflict resolver
│   ├── web/                    # Landing page, Investigation Workbench, Grainient, demo fixtures
│   └── workflow/               # LangGraph StateGraph, durable checkpointer, review gate
├── deploy/
│   ├── helm/sangyan/           # Production Helm chart (Deployment, Worker, HPA, PDB)
│   └── observability/          # Grafana dashboard & Prometheus Alertmanager rules
├── tests/                      # Comprehensive test suite (394 tests)
├── Dockerfile                  # CIS-hardened non-root multi-stage production container
├── docker-compose.yml          # Production Compose stack with volume mounts
├── docker-compose.distributed.yml # Distributed multi-pod Compose environment
├── .dockerignore               # Strict build context exclusion
├── .env.example                # Production environment template
├── decisions.md                # Append-only architectural decision log (D-001..D-088)
├── flow.md                     # Runtime execution, call flows, and Phase 1-11 architecture
├── handoff.md                  # Development phase state & operational runbooks
├── MODEL_CHANGES.md            # Domain models, schema contracts, and migrations 001-007
└── pyproject.toml              # Project manifest and dependencies (v0.7.0)
```

---

## Getting Started (Local Development)

### Prerequisites
- Python >= 3.10 (tested on Python 3.13)
- OpenSSL or libsodium (optional, pure-Python fallback included)

### Local Virtualenv Setup
```bash
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

### Running Test Suite
```bash
python -m pytest tests/ -v
```
All 400 tests should pass cleanly (0 failures, 0 regressions).

---

## Web Interfaces & Interactive Presentation

SANGYAN includes zero-tooling, production-grade web interfaces served directly by FastAPI without requiring external Node.js or webpack build steps:

1. **Editorial Landing Page (`GET /`)**:
   - **Denmu Editorial Aesthetic**: Minimal, grid-based, dark charcoal (`#07090e`), off-white typography, and electric purple/indigo accents (`#7c3aed`, `#6366f1`).
   - **Grainient Shader Canvas**: Dynamic GPU-accelerated canvas background generating smooth mathematical radial gradient drift with procedural film grain overlay, with automatic `prefers-reduced-motion` detection.
   - **Compelling Storytelling**: The Deception Crisis, 4-Tier Authority Hierarchy, Three Core Modes (`CHECK`, `VERIFY`, `RESPOND`), 10-Stage Pipeline Stepper, and Architecture Credibility specifications.
   - **Live Walkthrough Launchers**: Direct 1-click links to launch preloaded real-world case studies in the workbench.

2. **Investigation Workbench (`GET /workbench` and `GET /app`)**:
   - **Live Real-Time Telemetry**: Real-time Server-Sent Events (SSE) subscriber synchronizing the 10-stage pipeline stepper live.
   - **Interactive SVG Knowledge Graph**: Force/circular layout rendering investigations, claims, entities, payment VPAs, and authoritative sources with clickable attribute inspection.
   - **Forensic 12-Stage Scam Chain**: End-to-end criminal lifecycle visualization from initial social bait to loss realization.
   - **TRUST-SAT Cryptographic Verification Panel**: NIST FIPS 204 ML-DSA-65 post-quantum verification panel with live interactive `[ VERIFY RECEIPT ]` validation.
   - **Statutory Grievance Escalation**: Pre-formatted, one-click complaint drafts for SEBI SCORES 2.0 (`scores.sebi.gov.in`) and the 1930 Cybercrime Portal (`cybercrime.gov.in`), plus JSON evidentiary dossier export.


---

## Production Deployment & Containerization

### Architecture & Single-Replica Constraint

> **IMPORTANT OPERATIONAL INVARIANT**: SANGYAN is architected to run with **`replicas: 1`** in its current deployment model.
>
> **Rationale**: SANGYAN utilizes:
> 1. In-process token bucket rate limiters and failed-authentication trackers.
> 2. Process-level thread locks for concurrent investigation mutual exclusion.
> 3. File-backed SQLite Write-Ahead Logging (WAL) checkpoint persistence.
>
> Running multiple container replicas without a shared distributed cache (Redis) and distributed lock manager will cause rate limit drift and checkpoint split-brain. Multi-replica horizontal scaling is scheduled for Phase 8.

---

### Container Packaging (Docker)

SANGYAN uses a multi-stage Docker build with non-root security context:
- Base: `python:3.13-slim`
- User: `sangyan` (UID `10001`, GID `10001`)
- Rootfs: Application code is mounted read-only (`chmod 0555`).
- Persistent Volumes: `/app/data`, `/app/checkpoints`, `/app/keys`, `/app/backups`, and `/tmp`.
- No build tools (compilers, git) in final runtime stage.

#### Building Container
```bash
docker build -t sangyan:0.7.0 .
```

#### Running Container Standalone
```bash
docker run -d \
  --name sangyan-api \
  --user 10001:10001 \
  --read-only \
  -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e JWT_SECRET=your-secure-random-32-byte-secret-key-here \
  -e ALLOWED_ORIGINS="https://sangyan.yourorg.gov.in" \
  -v sangyan-data:/app/data \
  -v sangyan-checkpoints:/app/checkpoints \
  -v sangyan-keys:/app/keys \
  -v sangyan-backups:/app/backups \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  sangyan:0.7.0
```

---

### Docker Compose Deployment

A complete production stack is defined in `docker-compose.yml`:
1. `sangyan-migration`: One-off initialization container executing `python -m sangyan.cli migrate` before the API starts.
2. `sangyan-api`: The core REST and workflow service with persistent storage volumes and healthchecks.
3. `sangyan-backup`: Scheduled backup runner executing automated daily encrypted backups.

```bash
# 1. Create environment file from template
cp .env.example .env
# Edit .env and supply a high-entropy JWT_SECRET and BACKUP_ENCRYPTION_PASSWORD

# 2. Start the stack
docker compose up -d

# 3. Check status
docker compose ps
docker compose logs -f sangyan-api
```

---

### Distributed Production Deployment (Multi-Replica Scaling)

Phase 8 enables horizontal scaling across multiple API replicas backed by PostgreSQL connection pooling and a Redis cluster.

#### Multi-Replica Docker Compose:
```bash
# Start distributed topology (2 API pods, PostgreSQL, Redis, migration job, backup worker)
docker compose -f docker-compose.distributed.yml up -d

# Verify cluster status
docker compose -f docker-compose.distributed.yml ps
```

#### Multi-Replica Helm Deployment:
```bash
# Deploy with distributed values (3 replicas, HPA 2-10, PostgresSaver, Redis rate limiting)
helm upgrade --install sangyan deploy/helm/sangyan \
  --namespace sangyan \
  -f deploy/helm/sangyan/values.yaml \
  -f deploy/helm/sangyan/values-distributed.yaml
```

---

### Kubernetes & Helm Deployment

The production Helm chart is located in `deploy/helm/sangyan/`.

#### Chart Highlights:
- **Horizontal Scaling & HPA**: Supports `replicaCount >= 2` and automated scaling (`hpa.yaml`) between 2 and 10 replicas.
- **Pod Security**: `runAsNonRoot: true`, `runAsUser: 10001`, `runAsGroup: 10001`, `seccompProfile.type: RuntimeDefault`.
- **Container Security**: `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ["ALL"]`.
- **Pre-Rollout Migration Hook**: `Job` template (`job-migration.yaml`) runs `sangyan.cli migrate` as a Helm pre-install / pre-upgrade hook.
- **Backup CronJob**: `CronJob` template (`cronjob-backup.yaml`) runs daily at 02:00 UTC with automated AES-256-GCM encryption.
- **Ingress Hardening**: Enforces TLS, sets `client_max_body_size 2m`, and returns HTTP 404 for `/metrics` requests from outside the cluster.
- **NetworkPolicy**: Restricts ingress to Ingress controller and Prometheus; restricts egress to DNS (53), HTTPS (443), PostgreSQL (5432), and Redis (6379).

#### Deploying with Helm:
```bash
# 1. Create the sangyan namespace
kubectl create namespace sangyan

# 2. Create the production secret
kubectl create secret generic sangyan-secrets \
  --namespace sangyan \
  --from-literal=jwt-secret="your-secure-random-32-byte-secret-key-here" \
  --from-literal=backup-encryption-password="your-strong-backup-password-here"

# 3. Lint the chart
helm lint deploy/helm/sangyan

# 4. Dry-run render templates
helm template sangyan deploy/helm/sangyan -f deploy/helm/sangyan/values.yaml

# 5. Install or upgrade
helm upgrade --install sangyan deploy/helm/sangyan \
  --namespace sangyan \
  -f deploy/helm/sangyan/values.yaml
```

---

## Operational CLI Runbook

SANGYAN includes a full Click-based management CLI invoked via `python -m sangyan.cli`:

### 1. API Server
```bash
# Start server in production mode
python -m sangyan.cli serve --host 0.0.0.0 --port 8000

# Start server with custom config file
python -m sangyan.cli serve --config /app/config/sangyan.json
```

### 2. Database Migrations
```bash
# Check current migration version and pending migrations
python -m sangyan.cli migrate-status

# Execute all pending migrations (holds concurrency lock)
python -m sangyan.cli migrate
```

### 3. Cryptographic Backups
```bash
# Create an encrypted backup archive
python -m sangyan.cli backup create \
  --backup-dir /app/backups \
  --encrypt-password "YourStrongPasswordHere"

# Verify integrity and checksum of an existing backup
python -m sangyan.cli backup verify \
  --backup-id sangyan_bkp_20261004_120000_123456_a1b2c3 \
  --backup-dir /app/backups \
  --decrypt-password "YourStrongPasswordHere"

# Restore a backup into an isolated directory
python -m sangyan.cli backup restore \
  --backup-id sangyan_bkp_20261004_120000_123456_a1b2c3 \
  --backup-dir /app/backups \
  --target-dir /app/data_restored \
  --decrypt-password "YourStrongPasswordHere"

# Prune old backups past retention threshold
python -m sangyan.cli backup prune \
  --backup-dir /app/backups \
  --keep-days 30

# Replicate encrypted backup to S3/GCS cloud storage
python -m sangyan.cli backup upload \
  --archive /app/backups/sangyan_bkp_20261004_120000_123456_a1b2c3.tar.gz.enc \
  --bucket my-sangyan-cloud-backups \
  --prefix backups

# Restore and verify directly from cloud storage
python -m sangyan.cli backup restore-cloud \
  --backup-id sangyan_bkp_20261004_120000_123456_a1b2c3 \
  --bucket my-sangyan-cloud-backups \
  --target-dir /app/data_cloud_restored \
  --decrypt-password "YourStrongPasswordHere"
```

### 4. Operational Health Check
```bash
# Query health endpoint via CLI
python -m sangyan.cli health --url http://localhost:8000
```

### 5. Asynchronous Task Worker
```bash
# Start an async investigation worker
python -m sangyan.cli worker \
  --group sangyan-workers \
  --consumer worker-pod-1 \
  --poll-ms 1000 \
  --lease-sec 60 \
  --batch-size 10
```

### 6. Asynchronous Task Management
```bash
# List tasks by status and tenant
python -m sangyan.cli task list --org test-org --status RUNNING

# Inspect task details and execution timeline
python -m sangyan.cli task inspect task_12345678 --org test-org

# List quarantined dead-letter tasks
python -m sangyan.cli task dead-letter --org test-org

# Re-queue a dead-letter task for retry
python -m sangyan.cli task retry task_12345678 --org test-org
```

### 7. Multi-Region Disaster Recovery & Fencing
```bash
# Check regional role, authority epoch, and health
python -m sangyan.cli dr status

# Promote standby region to PRIMARY_ACTIVE (increments epoch and fences stale primary)
python -m sangyan.cli dr promote ap-south-1 --reason "Primary region datacenter outage"

# Simulate end-to-end failover drill without taking production offline
python -m sangyan.cli dr simulate ap-south-1 eu-central-1
```


---

## Operational Health & Telemetry Semantics

| Endpoint | Purpose | Semantics |
|---|---|---|
| `GET /health/live` | **Liveness Probe** | Process-level check. Returns `200 OK` if the Python event loop and ASGI server are responsive. Does NOT fail on external dependency degradation. |
| `GET /health/ready` | **Readiness Probe** | Traffic readiness check. Verifies database connectivity, active schema migration currency, and checkpointer availability. Returns `503 Service Unavailable` if database is down or pending migrations exist. |
| `GET /health` | **Startup Probe** | Composite check for container boot and initialization. |
| `GET /metrics` | **Telemetry** | Prometheus low-cardinality metrics exporter (internal cluster access only; blocked at public ingress). |

**Security Guarantee**: Health probe responses never disclose secret tokens, database credentials, internal stack traces, or filesystem paths.

---

## Backup & Disaster Recovery Procedure

### Backup Architecture
1. **Online Snapshot**: SQLite WAL is flushed and copied safely using `VACUUM INTO` without taking the database offline.
2. **Workflow Checkpoints**: Workflow state checkpoint database (`workflow_checkpoints.db`) is snapshot in parallel.
3. **PQC Signing Keys**: Dilithium / ML-DSA-65 keys and active snapshot registry metadata are included.
4. **Integrity Manifest**: A SHA-256 digest is calculated over the unencrypted tarball and stored in `backup_manifest.json`.
5. **Authenticated Encryption**: The tarball is encrypted using **AES-256-GCM** with a 256-bit key derived via **PBKDF2** (100,000 iterations of HMAC-SHA256).

### Disaster Recovery Runbook
To perform an isolated, zero-risk disaster recovery verification:

1. Locate the desired backup artifact (`sangyan_bkp_*.tar.gz.enc`) in `/app/backups/`.
2. Execute an isolated restore to a temporary verification directory:
   ```bash
   python -m sangyan.cli backup restore \
     --backup-id <BACKUP_ID> \
     --target-dir /tmp/disaster_recovery_test \
     --decrypt-password "<BACKUP_PASSWORD>"
   ```
3. The restore utility automatically:
   - Validates header magic (`SGYBKP1\0`).
   - Authenticates and decrypts the AES-256-GCM ciphertext.
   - Verifies the SHA-256 digest against `backup_manifest.json`.
   - Extracts the tarball using path-traversal protection (`filter="data"`).
   - Executes `PRAGMA integrity_check` on the restored database.
   - Verifies the restored schema matches the recorded migration version.
4. Once verified, stop the API container, replace `/app/data/sangyan.db` and `/app/checkpoints/workflow_checkpoints.db` with the restored files, and restart the container.

### Multi-Region Failover & Split-Brain Fencing
In a cross-region active-passive setup (e.g., Primary: `ap-south-1`, Standby: `eu-central-1`):
1. **Epoch Monotonicity & Fencing**: Write authority is governed by monotonic epochs recorded in `sangyan_region_fencing`. Standby or stale regions reject write requests immediately with `StaleRegionError` (`HTTP 409 Conflict`).
2. **Failover Execution**:
   ```bash
   # In the secondary region, initiate promotion:
   python -m sangyan.cli dr promote eu-central-1 --reason "Primary region failure"
   ```
   This atomically transitions `eu-central-1` to `PRIMARY_ACTIVE`, increments the global epoch, and fences `ap-south-1`.
3. **Audit Ledger Continuity**: After failover, verify cryptographic SHA3-256 hash chaining remains unbroken across region boundaries:
   ```python
   from sangyan.dr.manager import DisasterRecoveryManager
   dr_manager.verify_audit_continuity(tenant_repo)
   ```

### 8. Controlled Disaster Recovery Failback
Following failover repair, return write authority safely to the original primary:
```bash
# Execute operator-confirmed controlled failback to region-a:
python -m sangyan.cli dr failback --target-region region-a --confirm
```
This safely demotes the secondary to `STANDBY_READY`, promotes `region-a` with incremented cluster epoch, reconciles state, and verifies unbroken cryptographic audit chain continuity.

### 9. Load Testing & Concurrency Validation Harness
```bash
# Run deterministic multi-tenant load validation
python -m sangyan.cli load-test \
  --concurrency 8 \
  --tenants 4 \
  --tasks 100 \
  --output load_results.json
```

### 10. Operational Task Retention Pruning
```bash
# Prune old terminal tasks (SUCCEEDED, CANCELLED) older than 30 days
# (Dead letters and audit logs are never pruned)
python -m sangyan.cli task prune --older-than-days 30 --confirm
```

### 11. Database Streaming Replication & DR Switchover (`sangyan db`)
```bash
# Inspect PostgreSQL physical WAL streaming replication lag and standby health
python -m sangyan.cli db replication-status

# Promote a standby database replica to read-write primary (increments DR epoch)
python -m sangyan.cli db promote --region ap-south-2 --confirm

# Execute zero-data-loss controlled switchover between primary and standby regions
python -m sangyan.cli db switchover --primary ap-south-1 --standby ap-south-2 --confirm
```

### 12. Real-Time Investigation Progress Streaming (Server-Sent Events)
```bash
# Live stream investigation stage events over standard HTTP text/event-stream
curl -N -H "Authorization: Bearer <TOKEN>" \
  http://localhost:8000/api/v1/investigations/<INVESTIGATION_ID>/events

# Replay missed events following disconnection using Last-Event-ID header
curl -N -H "Authorization: Bearer <TOKEN>" \
  -H "Last-Event-ID: 4" \
  http://localhost:8000/api/v1/investigations/<INVESTIGATION_ID>/events

# Visual Inspection UI with live 10-stage stepper
# Open in browser: http://localhost:8000/inspect/investigation/<INVESTIGATION_ID>
```

### 13. Hardware Security Module (HSM) PKCS#11 Cryptographic Signing
- Configure `SANGYAN_SIGNING_PROVIDER=pkcs11` (or `pkcs11_simulator` for local validation).
- Configure `SANGYAN_PKCS11_LIB_PATH=/usr/lib/softhsm/libsofthsm2.so` and `SANGYAN_PKCS11_PIN=<PIN>`.
- Private keys remain strictly isolated within hardware tokens (`CKR_ATTRIBUTE_SENSITIVE`).
- Fail-closed verification prevents silent fallback to software signing.
- Key rotation preserves indefinite forensic validity of historical trust receipts via indexed `signing_key_id`.

---

## Observability, Dashboards & Alerting

- **Grafana Dashboard**: Import `deploy/observability/grafana-dashboard.json` into Grafana for real-time visualization of queue depth by status, worker utilization, DB connection pool state, Redis backlog, and DR epoch.
- **Prometheus Alert Rules**: Deploy `deploy/observability/prometheus-alerts.yaml` to Alertmanager for automated early-warning alerts on queue congestion, worker fleet starvation, database connection exhaustion, and DR authority conflicts.
- **Distributed Tracing**: Standard W3C `traceparent` headers with OpenTelemetry collectors, strictly enforcing epistemic redaction of investment claims, PII, and credentials.

---

## Security & Investor-Safety Invariants

- **Fail-Closed Configuration**: If `ENVIRONMENT=production`, the application refuses to start if `JWT_SECRET` has insufficient entropy (< 32 characters), uses default passwords, allows wildcard CORS, or disables authentication.
- **Zero AI Attribution**: All code, documentation, and Git commits strictly reflect project authorship (`PrathamKapoor <prathamkapoor027@gmail.com>`).
- **Research Integrity**: Research publications and LaTeX sources in `paper/` and `research/` are strictly isolated from runtime deployments.
- **Sensitive Data Redaction**: Automatic in-flight log and error scrubbing strips JWTs, API keys, private keys, passwords, and OTPs.
