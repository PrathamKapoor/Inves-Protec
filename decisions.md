# SANGYAN — Architecture & Implementation Decisions

This file is an append-only record of architectural, domain, security, data, and implementation decisions made in the SANGYAN project. Historical decisions are never rewritten; any reversal must explicitly supersede an earlier decision entry.

---

### D-001: Standalone SANGYAN Repository Initialization & Packaging Architecture
- Date / phase / commit: 2026-10-04, Phase 1, uncommitted
- Context: The project requires transforming prior supervisory (SAT-SA-with-PQC) and content analysis architectures into a shippable, production-ready, standalone investor-safety platform called SANGYAN. The root directory `C:\Projects\Sangyan` was an uninitialized workspace.
- Decision: Initialize a clean standalone Git repository in `C:\Projects\Sangyan` with Git author identity `PrathamKapoor <prathamkapoor027@gmail.com>`. Organize the core Python backend package under `sangyan/` with standard packaging via `pyproject.toml`, preserving clean modular separation (`sangyan.core`, `sangyan.crypto`, `sangyan.database`, `sangyan.domain`, `sangyan.tenancy`, `sangyan.security`, `sangyan.trust`).
- Why: SANGYAN is an independent investor-safety product for Indian retail investors, requiring clean separation from legacy SOC/MLOps telemetry. Clean packaging ensures standard installation, deployability, and dependency isolation.
- Alternatives considered: Developing in-place inside `C:\Projects\SIH26\TRUST-SAT` (rejected: would pollute prior research and violate repo isolation); mono-repo subfolder (rejected: active workspace is `C:\Projects\Sangyan`).
- Consequences: All code, migrations, tests, and documentation reside in `C:\Projects\Sangyan`. Python code will execute against the pre-equipped Python 3.13 environment.
- Files: `pyproject.toml`, `sangyan/__init__.py`, `.gitignore`

---

### D-002: Cryptographic Infrastructure Preservation (Pure Python ML-DSA-65 & SHA3-256)
- Date / phase / commit: 2026-10-04, Phase 1, uncommitted
- Context: Investor investigation records require tamper-evident cryptographic provenance and receipts that resist both classical and quantum computing attacks, without introducing fragile C-extension dependencies on Windows.
- Decision: Port and reuse the post-quantum cryptographic primitives from SAT-SA (`dilithium-py` ML-DSA-65 and `kyber-py` ML-KEM-768) and standard library SHA3-256 (`hashlib.sha3_256`) along with deterministic canonical JSON serialization into `sangyan.crypto`.
- Why: `dilithium-py 1.4.0` and `kyber-py 1.2.0` are pure-Python, verified thread-safe via serialized lock (`_PQC_LOCK`), and already installed and tested in the environment. Canonical JSON ensures identical byte serialization across platforms.
- Alternatives considered: Using classical RSA/ECDSA (rejected: prompt mandates PQC ML-DSA-65 preserving SAT-SA trust layer); using liboqs C-bindings (rejected: difficult build dependencies on Windows).
- Consequences: Investigation receipts and finding digests will be signed with quantum-resistant ML-DSA-65 signatures.
- Files: `sangyan/crypto/hashing.py`, `sangyan/crypto/providers.py`

---

### D-003: Storage & Migration Architecture (Dual-Dialect DatabaseEngine SQLite/PostgreSQL)
- Date / phase / commit: 2026-10-04, Phase 1, uncommitted
- Context: SANGYAN must operate both in local/air-gapped environments (using SQLite) and in multi-tenant hosted environments (using PostgreSQL 16), with deterministic schema versioning and transactional safety.
- Decision: Adopt the statement-level `DatabaseEngine` abstraction (`SQLiteDatabaseEngine` and `PostgresDatabaseEngine`) with `threading.RLock`, row-factories returning dicts, transactional context manager (`with engine.transaction():`), and linear migration tracking via `schema_migrations`.
- Why: The existing `DatabaseEngine` has been battle-tested in SAT-SA with over 1300 tests. It avoids heavy ORM overhead, eliminates dialect discrepancies, and enables zero-dependency offline SQLite operation.
- Alternatives considered: SQLAlchemy or Tortoise ORM (rejected: adds heavy runtime overhead and potential async session complexity; violates prompt instruction to reuse proven database abstraction).
- Consequences: All database operations use parameterized statements (`?` syntax with auto-translation to `%s` in Postgres).
- Files: `sangyan/database/engine.py`, `sangyan/database/migrations.py`

---

### D-004: Tenant Isolation & Multi-Tenancy Architecture
- Date / phase / commit: 2026-10-04, Phase 1, uncommitted
- Context: Investigations may contain sensitive user submissions or organization-specific review workflows. Cross-tenant leakage must be structurally impossible.
- Decision: Implement mandatory `organization_id` tenancy scoping on all persisted investigation records (`sangyan_content_items`, `sangyan_investigations`, `sangyan_findings`, `sangyan_reviews`). Provide `TenantRepository` that binds caller identity and organization context, strictly validating permissions on every operation.
- Why: Public-good investor safety platforms handling suspicious messages or user grievances must guarantee privacy and strict isolation.
- Alternatives considered: Single-tenant schema (rejected: fails enterprise/institutional deployment requirement); row-level security in Postgres only (rejected: breaks parity with local SQLite offline mode).
- Consequences: Every repository query requires an active `organization_id` parameter.
- Files: `sangyan/tenancy/models.py`, `sangyan/tenancy/repository.py`

---

### D-005: SANGYAN Investor-Safety Domain Model Definition
- Date / phase / commit: 2026-10-04, Phase 1, uncommitted
- Context: The platform requires domain models that represent investor content decomposition, claim verification, entity resolution, observable safety signals, and safe action guidance, replacing SAT-SA's SOC telemetry model.
- Decision: Implement 10 core domain records in `sangyan.domain`:
  1. `ContentItem`: Raw content submitted (text, URL, doc) with SHA3-256 digest and media type.
  2. `Claim`: Atomically evaluable assertion with explicit status (`SUPPORTED`, `CONTRADICTED`, `PARTIALLY_SUPPORTED`, `UNVERIFIED`, `CONFLICTING`, `OUTDATED`, `INSUFFICIENT_EVIDENCE`).
  3. `Entity`: Named subject (`BROKER`, `ADVISER`, `RESEARCH_ANALYST`, `APP`, `UPI`, `REGULATOR`, `EXCHANGE`, `COMPANY`, etc.).
  4. `Source`: Origin of evidence with authoritative tier hierarchy (`T0_REGULATOR` down to `T5_USER_GENERATED`) and freshness timestamps.
  5. `Evidence`: Factual excerpt or structured record with stance, relevance, and cryptographic hash.
  6. `Signal`: Observable property (`GUARANTEED_RETURN`, `URGENCY`, `WITHDRAWAL_FEE`, `AUTHORITY_IMPERSONATION`, etc.).
  7. `Finding`: Grounded conclusion connecting claim, evidence refs, source refs, confidence vector, and limitations.
  8. `ActionGuidance`: Safe non-investment next step (grievance, cybercrime reporting, verification).
  9. `Investigation`: Aggregated envelope binding claims, entities, signals, findings, and guidance under tenant ownership.
  10. `Review`: Authenticated human review decision (`CONFIRM`, `DISMISS`, `ESCALATE`, `DEFER`, `ANNOTATE`).
- Why: Explicitly fulfills prompt Sections 7-19. Never forces uncertainty into a binary true/false score; claims are evaluated independently.
- Alternatives considered: Single monolithic Investigation object (rejected: lacks granular claim/signal graph); SOC Finding adaptation (rejected: SOC semantics like IP alerts do not fit investor safety).
- Consequences: Each domain record provides `validate() -> list[str]`, `to_dict()`, and `from_dict()`.
- Files: `sangyan/domain/base.py`, `sangyan/domain/models.py`

---

### D-006: Schema Migrations & Storage Primitives for Phase 1
- Date / phase / commit: 2026-10-04, Phase 1, uncommitted
- Context: Durable persistence of the Phase 1 domain records and tenant data requires structured SQL tables across SQLite and PostgreSQL.
- Decision: Create Migration 001 (`create_sangyan_core_tables`) defining:
  - `sangyan_organizations`, `sangyan_users`, `sangyan_memberships`, `sangyan_sessions`
  - `sangyan_content_items`, `sangyan_claims`, `sangyan_entities`, `sangyan_sources`
  - `sangyan_evidence`, `sangyan_signals`, `sangyan_findings`, `sangyan_action_guidance`
  - `sangyan_investigations`, `sangyan_reviews`, `sangyan_trust_receipts`, `sangyan_audit_events`
- Why: Provides complete relational backing for all domain records while adhering to SQLite and PostgreSQL syntax conventions (using dialect-neutral SQL).
- Alternatives considered: Dynamic schema generation from dataclasses (rejected: non-deterministic and un-versioned).
- Consequences: Running `MigrationRunner.migrate()` automatically sets up all required tables in clean databases.
- Files: `sangyan/database/migrations.py`

---

### D-007: SSRF Protection & Network Boundary Foundation
- Date / phase / commit: 2026-10-04, Phase 1, uncommitted
- Context: Future ingestion will fetch URLs provided by users (e.g., suspicious investment sites). This poses severe SSRF (Server-Side Request Forgery) and DNS-rebinding risks to internal networks and cloud metadata services.
- Decision: Port and integrate the dual-check SSRF protection module from the Sentiment system into `sangyan.security.ssrf`. It enforces scheme restrictions (`http`, `https`), blocked hostnames, private/loopback/link-local/multicast IP address rejections, and hooks socket connections to prevent DNS-rebinding time-of-check to time-of-use (TOCTOU) exploits.
- Why: Production investor safety systems must be hardened against malicious link submissions.
- Alternatives considered: Basic URL parse regex (rejected: completely vulnerable to DNS-rebinding and loopback tricks); external proxy only (rejected: creates an external operational dependency for local/air-gapped use).
- Consequences: Any network fetching in later phases must execute within `ssrf_safe_connections()` context.
- Files: `sangyan/security/ssrf.py`

---

### D-008: Standard Library Socket-Level SSRF Interception without Mandatory External Dependencies
- Date / phase / commit: 2026-10-04, Phase 1, uncommitted
- Context: `urllib3` is not bundled in all Python environments or when HTTP clients like `httpx` or standard library `urllib` are used. Tight coupling to `urllib3.util.connection` caused collection errors when `urllib3` was absent.
- Decision: Intercept Python's standard library `socket.create_connection` in `sangyan.security.ssrf`, while conditionally hooking `urllib3.util.connection.create_connection` if `urllib3` is present.
- Why: Python standard library `socket.create_connection` is the root TCP connect call used by all HTTP clients (urllib, httpcore, httpx, urllib3). Intercepting it at standard library level provides universal DNS-rebinding protection without requiring `urllib3` as a mandatory dependency.
- Alternatives considered: Adding `urllib3` to dependencies (rejected: unnecessary extra dependency when standard library hook is cleaner and more universal).
- Consequences: All network fetches scoped within `ssrf_safe_connections()` are protected against SSRF and DNS rebinding across all HTTP libraries.
- Files: `sangyan/security/ssrf.py`
