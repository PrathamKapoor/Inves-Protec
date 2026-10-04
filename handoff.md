# SANGYAN — Project Handoff

## 1. Current Phase
Phase 6 — Production API, Authentication, Authorization & Security Hardening (COMPLETED)

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
- Completed Phase 6 Production API, Authentication, Authorization & Security Hardening (177 tests):
  - Database Migration 004: Added `sangyan_api_keys` table with indexed prefix lookup, tenant scoping, revocation, and last_used tracking.
  - Gateway Authentication Engine (`Authenticator`): Dual external authentication supporting RFC 7519 JWT Bearer tokens and prefixed hashed API keys (`sgy_<8hex>_<32hex>`).
  - Mutual Credential Exclusivity: Presenting both Bearer token and X-API-Key in a single request returns HTTP 400 Bad Request (`AmbiguousAuthenticationError`).
  - Cryptographic JWT Validator (`JwtValidator`): Strict algorithm allowlist (`HS256`, `RS256`, `ES256`, `EdDSA`), mandatory claim checks (`sub`, `org_id`, `iss`, `aud`, `exp`, `nbf`, `iat`), rejection of `alg=none`, and bounded 30s clock skew tolerance (`leeway=30`).
  - Hashed API Key Engine (`sangyan.security.api_keys`): Secure key generation (plaintext shown only once), SHA-256 digest persistence, constant-time HMAC verification (`hmac.compare_digest`), prefix-based O(1) indexed lookup, atomic `last_used_at` updates, and admin CRUD endpoints.
  - Contextual Multi-Tenant RBAC Matrix: Zero-trust tenant parameter verification (`principal.organization_id == req.organization_id`), 403 on mismatch, IDOR/BOLA defense (foreign tenant resources return 404/403 with zero enumeration), role permissions across `sangyan_viewer`, `sangyan_analyst`, `sangyan_admin`.
  - Token-Bucket Rate Limiter (`TokenBucketRateLimiter`): Sliding token bucket across 5 endpoint classes (`auth`: 10, `investigation`: 30, `workflow_mutate`: 20, `read`: 120, `default`: 60) and failed-authentication IP throttling (5 failures in 60s -> HTTP 429 lockout with Retry-After).
  - HTTP Transport Security: Injects `nosniff`, `DENY`, `strict-origin-when-cross-origin`, `CSP: default-src 'self'`, `Cache-Control: no-store, no-cache` on API routes, request body size bound (2 MB limit, HTTP 413), and request correlation `X-Request-ID`.
  - Low-Cardinality Telemetry & Redaction: Prometheus metrics exporter at `/metrics` with route template normalizer (`/api/v1/investigations/{id}`) to prevent label cardinality explosion; regex-based sensitive-data redaction (`redact_sensitive_text`, `RedactingLogFilter`) stripping tokens, API keys, private keys, passwords, and OTPs.

## 3. Files Changed / Created
- `sangyan/database/migrations.py` (Migration 004 `sangyan_api_keys` and indexes)
- `sangyan/security/__init__.py` (Security package exports)
- `sangyan/security/models.py` (Principal, ApiKey, SecurityConfig, security exceptions)
- `sangyan/security/jwt.py` (JwtValidator, create_jwt_token, algorithm allowlist, claim checks)
- `sangyan/security/api_keys.py` (API key generation, format validation, SHA-256 hashing, constant-time verification)
- `sangyan/security/rate_limiter.py` (TokenBucket, FailedAuthTracker, TokenBucketRateLimiter, RATE_LIMIT_POLICIES)
- `sangyan/security/middleware.py` (SecurityHeadersMiddleware, RequestSizeLimiterMiddleware, CorrelationIdMiddleware, RateLimiterMiddleware)
- `sangyan/security/telemetry.py` (MetricsRegistry, PrometheusMetricsMiddleware, RedactingLogFilter, redact_sensitive_text, normalize_route)
- `sangyan/security/auth.py` (Authenticator, extract_credentials, enforce_tenant_boundary, require_role, require_permission)
- `sangyan/tenancy/models.py` (Added `api_key:manage` permission to `sangyan_admin`)
- `sangyan/tenancy/repository.py` (TenantRepository API key CRUD: save, get, get_by_prefix, list, revoke, update_last_used)
- `sangyan/api/routes.py` (Secured all endpoints with Principal dependency, tenant boundary checks, RBAC enforcement, and API key management routes)
- `sangyan/api/app.py` (Wired security middlewares, metrics endpoint, restricted CORS, and Authenticator)
- `tests/test_database.py` (Updated for Migration 004 verification)
- `tests/test_security_phase6.py` (32 comprehensive unit and integration security tests)
- `decisions.md` (Recorded architectural decisions D-044 through D-050)
- `flow.md` (Section 10 API Security Architecture, diagrams, and Session Changelog)
- `MODEL_CHANGES.md` (Section 9 Principal, ApiKey, SecurityConfig, and Migration 004 schema)
- `handoff.md` (Updated project status and Phase 6 completion)

## 4. Current Architecture / State
- Package: `sangyan` (installed in editable mode in Python 3.13 venv)
- Database: Migrations 001, 002, 003, 004 creating 21 core relational tables. SQLite WAL mode enabled.
- Cryptography: Pure-Python ML-DSA-65 (`dilithium-py`) + SHA3-256 canonical JSON.
- Security Gateway: Dual authentication (JWT Bearer + prefixed hashed API keys), strict mutual exclusivity, cryptographic token validation, and constant-time key verification.
- Tenancy & RBAC: `Principal` identity representation, zero-trust parameter validation, IDOR/BOLA protection, and `sangyan_viewer` / `sangyan_analyst` / `sangyan_admin` role enforcement.
- Rate Limiting: In-memory sliding token buckets per endpoint category and failed-auth IP lockout middleware.
- Transport Hardening: Defensive headers (`nosniff`, `DENY`, `strict-origin-when-cross-origin`, `CSP`, `no-store`), 2 MB request payload bound, and `X-Request-ID` correlation.
- Observability: Low-cardinality Prometheus metrics at `/metrics`, route template normalization, and automatic credential log redaction.
- Ingestion (`sangyan.ingest`): Text cleaning, URL extraction, bounded streaming fetcher.
- Content Intelligence (`sangyan.intelligence`): Multilingual identification, atomic claims, entity resolver, observable safety signals.
- Authoritative Verification (`sangyan.verification`): Source registry, snapshots, adapters (SEBI, MCA, Circulars, Domains, Market Infrastructure, Payment), conflict resolution, post-quantum trust receipts.
- Correlation & Guidance (`sangyan.correlation`): Graph correlator, 12-stage scam chains, 14-pattern taxonomy, safe guidance, grievance router, explainer with uncertainty abstentions, investigation orchestrator, and PQC investigation trust receipts.
- Workflow Orchestration (`sangyan.workflow`): LangGraph StateGraph, durable SQLite checkpointing, human-in-the-loop review interruption, bounded retries, concurrency locking, and post-quantum trust finalization.
- API (`sangyan.api`): FastAPI REST API, workflow execution endpoints, server-rendered HTML inspection views with Section 40 banners, and Prometheus metrics.

## 5. Decisions Made
- D-001 through D-043: Phase 1 to Phase 5 decisions.
- D-044: Multi-Scheme External Authentication Boundary (JWT & API Key) & Canonical Principal Model
- D-045: Cryptographic JWT Validation, Allowed Algorithms & Key Lifecycle
- D-046: Hashed API Key Storage, Key Generation & Prefixed Lookup (Migration 004)
- D-047: Strict Multi-Tenant Isolation, IDOR/BOLA Protection & Contextual RBAC Matrix
- D-048: Token-Bucket Rate Limiting Middleware & Failed-Authentication Throttling
- D-049: Hardened HTTP Security Headers, Restricted CORS & Request Body Bounds
- D-050: Low-Cardinality Telemetry, Prometheus Metrics, Request Correlation & Structured Redacted Logging

## 6. Requirements and Constraints
- Git authorship: strictly `PrathamKapoor <prathamkapoor027@gmail.com>`. Zero AI attribution across code, tests, docs, and git commit history.
- Preservation of PQC cryptography (`dilithium-py` ML-DSA-65, SHA3-256, canonical JSON).
- Strict orchestration boundaries: LangGraph orchestrates domain services without duplicating business logic in graph nodes.
- Durable persistence: StateGraph checkpoints survive process restart, worker crashes, and review interruptions via SQLite WAL checkpointer.
- Strict non-investment advice guardrails: no price predictions, no buy/sell calls, no broker endorsements.
- Multi-tenant isolation: Thread IDs, checkpoints, and REST parameters pre-validated to prevent cross-tenant leakage.
- Fail-closed security: Authentication and authorization boundaries fail closed; telemetry fails open.

## 7. Testing and Verification
- Full test suite: **177 passed in 28.28s**, 0 failures, exit code 0 (`python -m pytest tests -v`).
- `tests/test_security_phase6.py`: 32 passed (JWT validation, algorithms allowlist, claims, clock skew, asymmetric RSA, API key generation/parsing/verification/revocation, ambiguous credentials, rate limiter, failed-auth throttling, route normalization, log redaction, security headers, request body bound, Prometheus metrics, tenant isolation, RBAC).
- `tests/test_workflow.py`: 12 passed (workflow scenarios and state transitions).
- `tests/test_api.py`: 10 passed (REST endpoints, batch investigation endpoint, HTML inspection views, workflow start/resume lifecycle, workflow cancellation).
- `tests/test_database.py`: 4 passed (Migrations 001, 002, 003, 004 schema and idempotency).
- `tests/test_verification.py`: 28 passed.
- `tests/test_correlation.py`: 20 passed.
- `tests/test_intelligence.py`: 19 passed.
- `tests/test_domain.py`: 22 passed.
- `tests/test_ingest.py`: 7 passed.
- `tests/test_verification_extended.py`: 11 passed.
- `tests/test_persistence.py`: 4 passed.
- `tests/test_crypto.py`: 3 passed.
- `tests/test_trust.py`: 2 passed.
- `tests/test_security.py`: 3 passed.

## 8. Next Phase / Immediate Priorities
- **Phase 7: Production Deployment & Operation**:
  - Docker containerization with non-root security context.
  - Helm / Kubernetes manifests with resource bounds.
  - Production environment configuration templates.
  - Backup & disaster recovery procedures for SQLite WAL checkpointer and relational tables.
