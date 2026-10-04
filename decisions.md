# SANGYAN — Architecture & Implementation Decisions

This file is an append-only record of architectural, domain, security, data, and implementation decisions made in the SANGYAN project. Historical decisions are never rewritten; any reversal must explicitly supersede an earlier decision entry.

---

### D-001: Standalone SANGYAN Repository Initialization & Packaging Architecture
- Date / phase / commit: 2026-10-04, Phase 1, 4dbd278
- Context: The project requires transforming prior supervisory (SAT-SA-with-PQC) and content analysis architectures into a shippable, production-ready, standalone investor-safety platform called SANGYAN. The root directory `C:\Projects\Sangyan` was an uninitialized workspace.
- Decision: Initialize a clean standalone Git repository in `C:\Projects\Sangyan` with Git author identity `PrathamKapoor <prathamkapoor027@gmail.com>`. Organize the core Python backend package under `sangyan/` with standard packaging via `pyproject.toml`, preserving clean modular separation (`sangyan.core`, `sangyan.crypto`, `sangyan.database`, `sangyan.domain`, `sangyan.tenancy`, `sangyan.security`, `sangyan.trust`).
- Why: SANGYAN is an independent investor-safety product for Indian retail investors, requiring clean separation from legacy SOC/MLOps telemetry. Clean packaging ensures standard installation, deployability, and dependency isolation.
- Alternatives considered: Developing in-place inside `C:\Projects\SIH26\TRUST-SAT` (rejected: would pollute prior research and violate repo isolation); mono-repo subfolder (rejected: active workspace is `C:\Projects\Sangyan`).
- Consequences: All code, migrations, tests, and documentation reside in `C:\Projects\Sangyan`. Python code will execute against the pre-equipped Python 3.13 environment.
- Files: `pyproject.toml`, `sangyan/__init__.py`, `.gitignore`

---

### D-002: Cryptographic Infrastructure Preservation (Pure Python ML-DSA-65 & SHA3-256)
- Date / phase / commit: 2026-10-04, Phase 1, 4dbd278
- Context: Investor investigation records require tamper-evident cryptographic provenance and receipts that resist both classical and quantum computing attacks, without introducing fragile C-extension dependencies on Windows.
- Decision: Port and reuse the post-quantum cryptographic primitives from SAT-SA (`dilithium-py` ML-DSA-65 and `kyber-py` ML-KEM-768) and standard library SHA3-256 (`hashlib.sha3_256`) along with deterministic canonical JSON serialization into `sangyan.crypto`.
- Why: `dilithium-py 1.4.0` and `kyber-py 1.2.0` are pure-Python, verified thread-safe via serialized lock (`_PQC_LOCK`), and already installed and tested in the environment. Canonical JSON ensures identical byte serialization across platforms.
- Alternatives considered: Using classical RSA/ECDSA (rejected: prompt mandates PQC ML-DSA-65 preserving SAT-SA trust layer); using liboqs C-bindings (rejected: difficult build dependencies on Windows).
- Consequences: Investigation receipts and finding digests will be signed with quantum-resistant ML-DSA-65 signatures.
- Files: `sangyan/crypto/hashing.py`, `sangyan/crypto/providers.py`

---

### D-003: Storage & Migration Architecture (Dual-Dialect DatabaseEngine SQLite/PostgreSQL)
- Date / phase / commit: 2026-10-04, Phase 1, 4dbd278
- Context: SANGYAN must operate both in local/air-gapped environments (using SQLite) and in multi-tenant hosted environments (using PostgreSQL 16), with deterministic schema versioning and transactional safety.
- Decision: Adopt the statement-level `DatabaseEngine` abstraction (`SQLiteDatabaseEngine` and `PostgresDatabaseEngine`) with `threading.RLock`, row-factories returning dicts, transactional context manager (`with engine.transaction():`), and linear migration tracking via `schema_migrations`.
- Why: The existing `DatabaseEngine` has been battle-tested in SAT-SA with over 1300 tests. It avoids heavy ORM overhead, eliminates dialect discrepancies, and enables zero-dependency offline SQLite operation.
- Alternatives considered: SQLAlchemy or Tortoise ORM (rejected: adds heavy runtime overhead and potential async session complexity; violates prompt instruction to reuse proven database abstraction).
- Consequences: All database operations use parameterized statements (`?` syntax with auto-translation to `%s` in Postgres).
- Files: `sangyan/database/engine.py`, `sangyan/database/migrations.py`

---

### D-004: Tenant Isolation & Multi-Tenancy Architecture
- Date / phase / commit: 2026-10-04, Phase 1, 4dbd278
- Context: Investigations may contain sensitive user submissions or organization-specific review workflows. Cross-tenant leakage must be structurally impossible.
- Decision: Implement mandatory `organization_id` tenancy scoping on all persisted investigation records (`sangyan_content_items`, `sangyan_investigations`, `sangyan_findings`, `sangyan_reviews`). Provide `TenantRepository` that binds caller identity and organization context, strictly validating permissions on every operation.
- Why: Public-good investor safety platforms handling suspicious messages or user grievances must guarantee privacy and strict isolation.
- Alternatives considered: Single-tenant schema (rejected: fails enterprise/institutional deployment requirement); row-level security in Postgres only (rejected: breaks parity with local SQLite offline mode).
- Consequences: Every repository query requires an active `organization_id` parameter.
- Files: `sangyan/tenancy/models.py`, `sangyan/tenancy/repository.py`

---

### D-005: SANGYAN Investor-Safety Domain Model Definition
- Date / phase / commit: 2026-10-04, Phase 1, 4dbd278
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
- Date / phase / commit: 2026-10-04, Phase 1, 4dbd278
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
- Date / phase / commit: 2026-10-04, Phase 1, 4dbd278
- Context: Future ingestion will fetch URLs provided by users (e.g., suspicious investment sites). This poses severe SSRF (Server-Side Request Forgery) and DNS-rebinding risks to internal networks and cloud metadata services.
- Decision: Port and integrate the dual-check SSRF protection module from the Sentiment system into `sangyan.security.ssrf`. It enforces scheme restrictions (`http`, `https`), blocked hostnames, private/loopback/link-local/multicast IP address rejections, and hooks socket connections to prevent DNS-rebinding time-of-check to time-of-use (TOCTOU) exploits.
- Why: Production investor safety systems must be hardened against malicious link submissions.
- Alternatives considered: Basic URL parse regex (rejected: completely vulnerable to DNS-rebinding and loopback tricks); external proxy only (rejected: creates an external operational dependency for local/air-gapped use).
- Consequences: Any network fetching in later phases must execute within `ssrf_safe_connections()` context.
- Files: `sangyan/security/ssrf.py`

---

### D-008: Standard Library Socket-Level SSRF Interception without Mandatory External Dependencies
- Date / phase / commit: 2026-10-04, Phase 1, 4dbd278
- Context: `urllib3` is not bundled in all Python environments or when HTTP clients like `httpx` or standard library `urllib` are used. Tight coupling to `urllib3.util.connection` caused collection errors when `urllib3` was absent.
- Decision: Intercept Python's standard library `socket.create_connection` in `sangyan.security.ssrf`, while conditionally hooking `urllib3.util.connection.create_connection` if `urllib3` is present.
- Why: Python standard library `socket.create_connection` is the root TCP connect call used by all HTTP clients (urllib, httpcore, httpx, urllib3). Intercepting it at standard library level provides universal DNS-rebinding protection without requiring `urllib3` as a mandatory dependency.
- Alternatives considered: Adding `urllib3` to dependencies (rejected: unnecessary extra dependency when standard library hook is cleaner and more universal).
- Consequences: All network fetches scoped within `ssrf_safe_connections()` are protected against SSRF and DNS rebinding across all HTTP libraries.
- Files: `sangyan/security/ssrf.py`

---

### D-009: Repository CRUD Expansion, ConfidenceVector Idempotency & SQLite WAL Concurrency
- Date / phase / commit: 2026-10-04, Phase 1 (Perfection Protocol), 42bbef2
- Context: Post-Phase 1 audit identified three opportunities for hardening before pipeline implementation:
  1. `TenantRepository` possessed persistence methods for `ContentItem`, `Claim`, `Signal`, `Investigation`, and `Review`, but lacked full tenant-scoped CRUD methods for `Entity`, `Source`, `Evidence`, `Finding`, `ActionGuidance`, and investigation updates/listings.
  2. `ConfidenceVector.from_dict` assumed dictionary inputs, which raised errors if an already-deserialized `ConfidenceVector` instance was passed.
  3. Default SQLite file locking can cause contention between concurrent reader and writer threads in multi-user/multi-worker workloads.
- Decision:
  1. Implemented complete CRUD coverage in `TenantRepository` for all domain models (`save_entity`, `get_entity`, `list_entities`, `save_source`, `get_source`, `list_sources`, `save_evidence`, `get_evidence`, `list_evidence_for_claim`, `save_finding`, `get_finding`, `list_findings_for_claim`, `save_guidance`, `get_guidance`, `list_guidance`, `list_investigations`, `update_investigation`, `list_reviews_for_investigation`), enforcing tenant isolation via foreign key joins back to `sangyan_content_items.organization_id`.
  2. Made `ConfidenceVector.from_dict()` idempotent so passing an existing `ConfidenceVector` returns it unchanged.
  3. Configured `PRAGMA journal_mode = WAL;` and `PRAGMA busy_timeout = 5000;` on all SQLite connections in `SQLiteDatabaseEngine`.
- Why: Ensures transactional robustness, concurrent access performance, and complete repository data-access methods for downstream analysis pipelines and API layers.
- Alternatives considered: Deferring entity/source repository methods to Phase 3 (rejected: violative of the Persistent Completion & Perfection Protocol).
- Consequences: All domain entities can be managed through the strictly scoped `TenantRepository` with validated domain rules and concurrency safety.
- Files: `sangyan/database/engine.py`, `sangyan/domain/models.py`, `sangyan/tenancy/repository.py`, `tests/test_persistence.py`

---

### D-010: Multilingual Text Normalization & Adversarial Evasion Architecture
- Date / phase / commit: 2026-10-04, Phase 2
- Context: Fraudulent financial content frequently uses adversarial formatting (zero-width spaces `\u200b` between keywords, fullwidth or mathematical alphanumeric homoglyphs, embedded HTML markup, and mixed Indic scripts/Hinglish) to bypass naive string matching and regex filters.
- Decision: Implemented a multi-stage text cleaning and language identification pipeline in `sangyan.ingest.cleaner` and `sangyan.intelligence.language`:
  1. Strips zero-width and bidirectional control characters before pattern matching.
  2. Extracts plain text from HTML while discarding script/style blocks and decoding entities.
  3. Normalizes Unicode via NFKC (canonical decomposition followed by canonical composition).
  4. Identifies scripts and languages across English, Hindi (Devanagari), Hinglish (Romanized Hindi), Marathi, Gujarati, Bengali, Tamil, Telugu, and Kannada.
  5. Implements an Indic combining-mark preserving tokenizer (`[^\w\s\u0900-\u0D7F]`) to prevent breaking Devanagari vowel signs/matras during vocabulary analysis.
- Why: Guarantees consistent canonical representations of submitted messages across diverse Indian languages and stops adversarial evasions.
- Alternatives considered: Using external heavy LLM for language identification (rejected: adds latency, non-deterministic outputs, and external runtime dependencies for a basic classification task).
- Consequences: Downstream intelligence extractors operate on normalized text with known language and script metadata.
- Files: `sangyan/ingest/cleaner.py`, `sangyan/intelligence/language.py`, `tests/test_ingest.py`, `tests/test_intelligence.py`

---

### D-011: Bounded SSRF-Safe HTTP Ingestion Service
- Date / phase / commit: 2026-10-04, Phase 2
- Context: User-submitted suspicious investment URLs must be fetched to inspect landing pages, but fetching arbitrary URLs poses critical SSRF risks (accessing cloud metadata `169.254.169.254`, internal services `10.0.0.0/8`, `127.0.0.1`, DNS rebinding) and denial-of-service risks (compression bombs, infinite streaming, redirect loops).
- Decision: Built `UrlFetcher` and `IngestionService` in `sangyan.ingest`:
  1. Integrates socket-level interception (`ssrf_safe_connections()`) and preflight URL validation (`validate_url_ssrf`).
  2. Bounded HTTP streaming with a hard limit of 2 MB (`MAX_SIZE_BYTES = 2097152`).
  3. Strict timeouts (connect 3.0s, read 5.0s).
  4. Manual redirect resolution verifying each redirect target against SSRF policy with a maximum of 3 hops.
  5. Automatic extraction of page title, meta description, and plain text.
  6. Computes SHA3-256 canonical hash over fetched content and stores a validated `ContentItem` through `TenantRepository`.
- Why: Provides secure web crawling capabilities with rock-solid defense in depth against network boundary attacks.
- Alternatives considered: Calling standard `requests.get(url, allow_redirects=True)` (rejected: vulnerable to TOCTOU DNS-rebinding and redirect SSRF bypasses).
- Consequences: Content from suspicious links can be safely ingested into the platform without exposing host infrastructure.
- Files: `sangyan/ingest/fetcher.py`, `sangyan/ingest/service.py`, `tests/test_ingest.py`

---

### D-012: Deterministic Financial Entity Resolution & Atomic Claim Decomposition
- Date / phase / commit: 2026-10-04, Phase 2
- Context: Compound promotional messages join multiple independent claims (e.g. regulatory license assertions, return promises, payment demands, urgency tactics). Conflating them prevents independent verification against authoritative registries.
- Decision:
  1. `ClaimExtractor` splits compound sentences on clause boundaries and conjunctions, categorizing each into `regulatory`, `return`, `urgency`, `payment`, `affiliation`, or `other`, with default status `UNVERIFIED` and context pointer metadata.
  2. `EntityResolver` extracts SEBI registration formats (`INZ`, `INA`, `INH`, `INP`, `INM`, `IN-DP`, `MF`), Corporate CIN (`[LU][0-9]{5}...`), Indian UPI VPAs (`@okhdfcbank`, `@paytm`, `@ybl`, etc.), Telegram handles/invite links, WhatsApp invite links, statutory regulators (SEBI, RBI, IRDAI, MCA), market infrastructure (NSE, BSE, MCX, NSDL, CDSL), and recognized retail brokers.
- Why: Decomposing content into discrete entities and claims enables 1-to-1 evidence mapping in Phase 3 verification.
- Alternatives considered: Single binary classification of messages as "safe" vs "unsafe" (rejected: violates product design requirement to verify atomic assertions with transparent provenance).
- Consequences: Every message yields granular claims and entities ready for registry lookups and evidence graph construction.
- Files: `sangyan/intelligence/claims.py`, `sangyan/intelligence/entities.py`, `tests/test_intelligence.py`

---

### D-013: Contextual Negation & Hard-Negative Disclaimer Suppression in Signal Detection
- Date / phase / commit: 2026-10-04, Phase 2
- Context: Pattern-matching signal detection easily generates severe false positives on regulatory warnings, investor education, and statutory disclaimers. For instance, "SEBI warns investors against guaranteed returns" or "Never share your OTP" contain high-risk keywords but are protective advisories rather than predatory solicitations.
- Decision: Implemented two-tier negation and context handling in `SignalDetector`:
  1. Sentence-level warning detection (`WARNING_CONTEXT_PATTERNS` covering `beware`, `warns`, `advises`, `regulatory warning`, `do not share`, `never`, `subject to market risks`, `धोखाधड़ी से बचें`, `सावधान`). Sentences matching protective advisory intent suppress signal emission.
  2. Immediate preceding negation detection (`NEGATION_PREFIXES` covering `not`, `never`, `no`, `without`, `don't`, `nahi`, `mat`).
  3. Detects 20+ observable, factual signals (GUARANTEED_RETURN, HIGH_RETURN_PROMISE, URGENCY, SCARCITY, AUTHORITY_IMPERSONATION, WITHDRAWAL_FEE, OTP_REQUEST, CREDENTIAL_REQUEST, FAKE_PROFIT, SOCIAL_MEDIA_SOLICITATION, PRESSURE_LANGUAGE, SUSPICIOUS_URL, UNVERIFIED_APP, THIRD_PARTY_PAYMENT, UPI_MISMATCH).
  4. `ContentIntelligenceEngine` computes a diminishing-returns risk score from signal severity weights and generates an evidence-grounded summary.
- Why: Prevents the platform from falsely flagging genuine SEBI advisories or mutual fund statutory disclaimers as scams.
- Alternatives considered: Simple regex matching without negation (rejected: unacceptably high false-positive rate on legitimate educational content).
- Consequences: High signal precision with rigorous verification against hard negative test cases.
- Files: `sangyan/intelligence/signals.py`, `sangyan/intelligence/pipeline.py`, `tests/test_intelligence.py`

---

### D-014: Authoritative Source Registry Architecture
- Date / phase / commit: 2026-10-04, Phase 3
- Context: Financial claim verification must ground all assessments strictly in curated, authoritative institutional sources rather than open-ended LLM knowledge or untrusted web crawling. Sources must have explicit trust tiers (T0 Regulator to T5 User-generated), reliability scores, update frequencies, and schema identifiers.
- Decision: Implemented `AuthoritativeSourceRegistry` (`sangyan/verification/sources.py`) initialized with curated Indian financial market seed sources:
  1. `src_sebi_intermediaries`: Tier 0 SEBI Intermediaries Registry (Brokers, Investment Advisers, Research Analysts, Depositories, Mutual Funds).
  2. `src_sebi_circulars`: Tier 0 Official SEBI Circulars & Regulatory Advisories.
  3. `src_mca_registry`: Tier 0 Ministry of Corporate Affairs Registry (Company CIN & LLP verification).
  4. `src_nse_members`: Tier 1 NSE Member Directory.
  5. `src_bse_members`: Tier 1 BSE Member Directory.
  6. `src_official_domains`: Tier 0 Curated Financial Domain & Phishing List.
  7. `src_rbi_entities`: Tier 0 Reserve Bank of India Regulated Entities.
- Why: Provides an auditable, controlled registry preventing arbitrary external references from influencing verification findings.
- Alternatives considered: Dynamic ad-hoc web searches for verification (rejected: vulnerable to SEO-manipulated scam pages, phishing domains, and non-authoritative forums).
- Consequences: All verification adapters query registered authoritative sources with deterministic provenance.
- Files: `sangyan/verification/sources.py`, `tests/test_verification.py`

---

### D-015: Controlled Multi-Source Verification Adapters
- Date / phase / commit: 2026-10-04, Phase 3
- Context: Claim verification requires domain-specific adapters capable of parsing and querying heterogeneous authoritative records (SEBI registration certificates, MCA CIN corporate records, regulatory circular bans, and official domain registries).
- Decision: Implemented abstract base adapter `VerificationAdapter` and 4 concrete verification adapters in `sangyan/verification/adapters/`:
  1. `SEBIVerificationAdapter`: Validates SEBI registration numbers (INZ, INA, INH, INM, INP, IN-DP, MF) and intermediary names. Correctly distinguishes active, expired, cancelled, suspended, and bogus registrations. Exact registration mismatches strictly override name-similarity lookups to defeat brand-spoofing attacks.
  2. `MCAVerificationAdapter`: Validates 21-character Corporate Identification Numbers (CINs) and company names, verifying status (ACTIVE, STRUCK_OFF, DISSOLVED, UNREGISTERED).
  3. `CircularsVerificationAdapter`: Matches claims and signals against official regulatory circulars (e.g. SEBI prohibition of guaranteed returns under SEBI/HO/MIRSD, prohibition of OTP/credential solicitation under SEBI/HO/ISD, fraudulent fee demands, and statutory disclaimers).
  4. `OfficialDomainsVerificationAdapter`: Performs domain-level verification, authenticating genuine financial domains, blocking lookalike/phishing domains (`zerodha-profit.cc`, `sebi-approval.xyz`), and flagging high-risk TLDs (.xyz, .top, .vip).
- Why: Modular, single-responsibility adapters provide deterministic verification logic with zero hallucination.
- Alternatives considered: A single monolithic verification class (rejected: brittle, difficult to test and maintain).
- Consequences: Each adapter produces structured `AdapterResult` records with explicit stance, confidence, and evidence payloads.
- Files: `sangyan/verification/adapters/base.py`, `sangyan/verification/adapters/sebi.py`, `sangyan/verification/adapters/mca.py`, `sangyan/verification/adapters/circulars.py`, `sangyan/verification/adapters/official_domains.py`, `tests/test_verification.py`

---

### D-016: Versioned Registry Snapshots with SHA3-256 Integrity
- Date / phase / commit: 2026-10-04, Phase 3
- Context: Institutional registries update continuously (brokers get suspended, new circulars are issued). To ensure investigations remain reproducible and legally verifiable over time, the system must support versioned snapshots with cryptographic integrity verification.
- Decision: Implemented `RegistrySnapshot` and `SnapshotManager` (`sangyan/verification/snapshots.py`):
  1. Snapshots contain source ID, semantic version (e.g. `2026.03.01`), entry count, data payload, and a canonical SHA3-256 integrity hash.
  2. `verify_integrity()` recalculates canonical JSON SHA3-256 hash over snapshot entries and raises `VerificationIntegrityError` if any entry has been altered.
  3. Default seed snapshots are bundled for SEBI intermediaries, MCA companies, regulatory circulars, and official domains.
- Why: Guarantees immutable, reproducible investigation baselines that can withstand court scrutiny or compliance audits.
- Alternatives considered: Querying live unversioned remote endpoints without caching snapshots (rejected: tests and verification reproducibility would break when upstream websites change).
- Consequences: Investigations link findings to exact snapshot versions and integrity hashes.
- Files: `sangyan/verification/snapshots.py`, `tests/test_verification.py`

---

### D-017: Epistemic Stances & Temporal Verification (Active vs Outdated)
- Date / phase / commit: 2026-10-04, Phase 3
- Context: Financial claims cannot be evaluated on a simplistic true/false binary. Registrations expire or are cancelled; regulatory rules evolve; evidence may be conflicting or insufficient.
- Decision: Standardized on 5 mutually exclusive verification stances:
  1. `SUPPORTED`: Claim is directly corroborated by active authoritative records (e.g., active SEBI registration matching intermediary name).
  2. `CONTRADICTED`: Claim is explicitly refuted by authoritative records (e.g., bogus registration number, struck-off company, or guaranteed return promise prohibited by circular).
  3. `CONFLICTING`: Multiple authoritative sources or valid records present contradictory evidence.
  4. `OUTDATED`: Claim was valid in the past but has expired or been cancelled/suspended (e.g. expired SEBI broker registration `INZ000999999` valid 2018-2022 but expired).
  5. `INSUFFICIENT_EVIDENCE`: No authoritative records exist to definitively support or contradict the claim.
- Why: Provides nuanced, legally defensible, and actionable intelligence to investors and investigators.
- Alternatives considered: Binary boolean `is_valid` flag (rejected: conflates expired licenses with active scams, and unverified entities with confirmed fraudulent ones).
- Consequences: Downstream guidance engines can distinguish between active fraud and administrative expiry.
- Files: `sangyan/domain/models.py`, `sangyan/verification/adapters/`, `sangyan/verification/engine.py`, `tests/test_verification.py`

---

### D-018: Multi-Source Conflict Resolution & Transparency
- Date / phase / commit: 2026-10-04, Phase 3
- Context: When verifying claims across multiple adapters or registries, sources may yield opposing stances (e.g. one source indicates support while another indicates contradiction). Suppressing one source or taking an arbitrary average misleads investigators.
- Decision: Implemented deterministic conflict resolution in `ClaimVerificationEngine` (`sangyan/verification/engine.py`):
  1. If adapters yield both `SUPPORTED` and `CONTRADICTED` outcomes without an overriding authoritative contradiction, the claim stance resolves to `CONFLICTING`.
  2. Dual contradictory evidence items are persisted to the database, explicitly recording opposing claims and findings.
  3. Adversarial precedence rule: In entity registration verification, an explicit contradictory registration check strictly overrides a fuzzy name similarity match to defeat brand spoofing.
- Why: Total transparency ensures investigators see both sides of conflicting records rather than an artificial consensus.
- Alternatives considered: Majority voting among adapters (rejected: a scammer could register a bogus MCA name to outvote a genuine SEBI cancellation).
- Consequences: Investigators receive full visibility into conflicting claims with complete provenance.
- Files: `sangyan/verification/engine.py`, `tests/test_verification.py`

---

### D-019: Traceable Evidence & Finding Provenance
- Date / phase / commit: 2026-10-04, Phase 3
- Context: Every claim verification must produce an immutable chain of custody linking the user content, atomic claim, extracted entity, authoritative source, raw retrieved excerpt, evaluation stance, and resulting finding.
- Decision: In `ClaimVerificationEngine`:
  1. For every adapter result, a domain `Evidence` entity is created, populated with source ID, title, excerpt, URL/identifier, canonical SHA3-256 content hash, and confidence vector.
  2. A domain `Finding` entity is created summarizing the factual determination, stance, confidence vector, and reasoning.
  3. All entities are tenant-scoped and persisted atomically through `TenantRepository`.
  4. Cross-tenant isolation is strictly maintained; verification results cannot leak across tenant boundaries.
- Why: Enables complete auditability and defensibility of every assertion made by the platform.
- Alternatives considered: Persisting only the final finding without intermediate evidence objects (rejected: destroys evidentiary chain of custody).
- Consequences: Every finding in SANGYAN can be traced back to exact authoritative evidence records.
- Files: `sangyan/verification/engine.py`, `sangyan/domain/models.py`, `tests/test_verification.py`

---

### D-020: ML-DSA-65 Post-Quantum Trust Binding for Verification Findings
- Date / phase / commit: 2026-10-04, Phase 3
- Context: Findings and evidence must be tamper-evident. If a database record or investigation report is altered after the fact, the system must cryptographically detect and reject the tampering.
- Decision: Implemented `TrustBindingService` (`sangyan/verification/trust_binding.py`):
  1. Assembles a canonical JSON verification payload containing `finding_id`, `claim_id`, `stance`, `finding_statement`, `confidence_vector`, `evidence_hashes`, `verified_at`, and `tenant_id`.
  2. Signs the canonical payload using pure-Python ML-DSA-65 (`dilithium-py`) post-quantum digital signature.
  3. Generates a signed `TrustReceipt` linking the verification event to the investigator or system identity.
  4. `verify_finding_integrity()` recalculates the canonical payload and verifies the ML-DSA-65 signature against the public key, immediately detecting any payload or statement tampering.
- Why: Provides quantum-resistant, non-repudiable proof of verification determinations.
- Alternatives considered: Traditional ECDSA/RSA signatures (rejected: vulnerable to Shor's algorithm; project standard mandates ML-DSA-65 post-quantum cryptography).
- Consequences: Any modification to a finding's stance, statement, or evidence invalidates its post-quantum signature.
- Files: `sangyan/verification/trust_binding.py`, `tests/test_verification.py`

---

### D-021: Verification Caching & Upstream Rate Limiting
- Date / phase / commit: 2026-10-04, Phase 3
- Context: Authoritative registries and APIs have rate limits, and redundant verification of popular entities (e.g. checking Zerodha's SEBI registration thousands of times) exhausts network and compute resources.
- Decision: Implemented in-memory caching and sliding-window rate limiting (`sangyan/verification/cache.py`):
  1. `VerificationCache`: Thread-safe, TTL-based caching keyed by canonical SHA3-256 hash of `(source_id, query_type, query_val)`.
  2. `RateLimiter`: Sliding-window rate limiter per source with exponential backoff on retryable upstream failures.
- Why: Protects authoritative sources from request spikes while maintaining sub-second verification response times for frequently verified entities.
- Alternatives considered: Unbounded caching without TTL (rejected: stale data risks) or no caching (rejected: upstream rate limits exceeded).
- Consequences: Fast, resilient verification lookups with configurable TTL and rate limit governance.
- Files: `sangyan/verification/cache.py`, `tests/test_verification.py`

---

### D-022: Multi-Domain Threat Precedence, Disclaimer Evasion Defense, and Engine Fault Resilience
- Date / phase / commit: 2026-10-04, Phase 3
- Context: Adversarial testing revealed evasion patterns:
  1. Attackers prepending official regulator links (e.g. `https://sebi.gov.in`) before phishing links (`http://zerodha-profit.cc`) to trick naive single-URL parsers into reporting `SUPPORTED`.
  2. Attackers appending statutory risk disclaimers ("mutual funds are subject to market risks") to illegal guaranteed return schemes to trigger disclaimer hard-negative suppression.
  3. External network or parsing exceptions in custom adapters could crash the entire batch verification workflow.
  4. Non-atomic database writes could persist orphan evidence if an exception occurred midway through saving findings.
- Decision: Implemented multi-tier hardening across the verification subsystem:
  1. `OfficialDomainsVerificationAdapter` scans all URLs and bare domains in claims; if ANY domain is malicious, lookalike, or utilizes high-risk TLDs (.top, .vip, .cc, .xyz), `CONTRADICTED` is immediately emitted, defeating prepended regulator URLs.
  2. `SnapshotManager.lookup_official_domain` symmetrically normalizes hostnames, stripping ports, trailing dots, and `www.` prefixes.
  3. `CircularsVerificationAdapter` evaluates affirmative prohibited practices (guaranteed returns, OTP demands, advance fee solicitations) prior to disclaimers. Disclaimers only yield `SUPPORTED` when no affirmative prohibited promises exist.
  4. `SEBIVerificationAdapter` and `MCAVerificationAdapter` normalize whitespace and hyphens in registration numbers and CINs.
  5. `ClaimVerificationEngine` contains adapter execution exceptions in `try...except`, logging degraded `source_unavailable` results while allowing surviving adapters to complete.
  6. Rate-limited adapter attempts are recorded as explicit `rate_limited` adapter results rather than silently discarded.
  7. In-memory `VerificationCache` and `RateLimiter` utilize `threading.Lock` for complete thread safety.
  8. Evidence and Finding persistence in `ClaimVerificationEngine` executes inside atomic database transactions (`repository._db.transaction()`).
- Why: Provides defense-in-depth against sophisticated evasion techniques and ensures enterprise-grade operational stability.
- Alternatives considered: Single-URL parsing and blind disclaimer suppression (rejected: trivially bypassable by real-world fraudsters).
- Consequences: Rock-solid verification engine with 26 comprehensive verification tests covering adversarial, resilience, and concurrency scenarios.
- Files: `sangyan/verification/engine.py`, `sangyan/verification/snapshots.py`, `sangyan/verification/cache.py`, `sangyan/verification/adapters/`, `tests/test_verification.py`

---

### D-023: End-to-End Investigation Orchestration & Regex Clause Splitting Preservation
- Date / phase / commit: 2026-10-04, Phase 3
- Context: Two systemic integration issues were identified during end-to-end verification pipeline testing:
  1. Clause splitting regex `[\.\!\?।|;]\s*` was greedily matching dot characters in URLs (e.g. `https://zerodha.com` became split into `https://zerodha` and `com`), numeric floating points, and abbreviations because `\s*` matched zero whitespace immediately following a period.
  2. While `ContentIntelligenceEngine` and `ClaimVerificationEngine` operated independently, there was no unified orchestration method to ingest raw content, extract intelligence, verify all extracted claims, synthesize post-quantum trust receipts, compute an overall risk posture, and persist an `Investigation` audit envelope.
  3. `persist_analysis()` in `ContentIntelligenceEngine` did not execute inside a database transaction, posing atomicity hazards if entity persistence failed after claims were written.
- Decision:
  1. Updated `CLAUSE_SPLIT_REGEX` in `sangyan/intelligence/claims.py` to use positive lookbehind `(?<=[.!?।|;])\s+`. Sentence splits now require at least one whitespace character after punctuation, preserving embedded dots in URLs (`zerodha.com`), financial metrics (`10.5%`), and abbreviations.
  2. Wrapped `persist_analysis()` in `sangyan/intelligence/pipeline.py` in `with repository._db.transaction():` to ensure atomicity.
  3. Implemented `verify_content_item(content_item, repository, user_id)` and `InvestigationReport` in `ClaimVerificationEngine`:
     - Analyzes content with `ContentIntelligenceEngine`.
     - Atomically persists extracted claims, entities, and safety signals.
     - Verifies all atomic claims using registered authoritative adapters.
     - Binds ML-DSA-65 post-quantum trust receipts.
     - Derives holistic `overall_status` (`HIGH_RISK` if prohibited/contradicted claims exist, `SUSPICIOUS` if unverified claims or signals exist, `SAFE` if supported without high-risk signals).
     - Generates and persists the `Investigation` record linking all findings and evidence.
  4. Added statutory disclosure keywords (`market risks`, `scheme related`, `disclaimer`, `regulatory warning`) to `CircularsVerificationAdapter` to correctly support legitimate risk disclosures.
- Why: Bridges Phase 2 Content Intelligence and Phase 3 Authoritative Verification into a seamless, atomic, production-ready investigation workflow while eliminating URL corruption.
- Alternatives considered: Separate manual invocation of intelligence and verification in user controllers (rejected: duplicates pipeline wiring and risks inconsistent persistence).
- Consequences: Full end-to-end investigation pipeline executable via a single call, verified by 2 comprehensive end-to-end integration tests. Total test suite reaches 92 passed tests.
- Files: `sangyan/intelligence/claims.py`, `sangyan/intelligence/pipeline.py`, `sangyan/verification/adapters/circulars.py`, `sangyan/verification/engine.py`, `tests/test_verification.py`

---

### D-024: Authoritative Source Registry Metadata Expansion & Indian Infrastructure
- Date / phase / commit: 2026-10-04, Phase 3
- Context: Prompt Section 7 requires authoritative source governance metadata explicitly tracking `source_type`, `authority`, and `provenance_policy`, and Section 8 requires expanding coverage across Indian financial infrastructure (MCX, NSDL, CDSL, NPCI, IRDAI).
- Decision:
  1. Expanded `AuthoritativeSourceMetadata` with `source_type` (`REGULATOR_REGISTRY`, `EXCHANGE_DIRECTORY`, `CORPORATE_REGISTRY`, `STATUTORY_CIRCULAR`, `OFFICIAL_DOMAINS`, `PAYMENT_DIRECTORY`, `DEPOSITORY_REGISTRY`), `authority` (`SEBI`, `MCA`, `RBI`, `NSE`, `BSE`, `MCX`, `NSDL`, `CDSL`, `NPCI`, `IRDAI`), and `provenance_policy` (`STATUTORY_MANDATE`, `REGULATORY_FILING`, `CRYPTOGRAPHIC_SNAPSHOT`, `OFFICIAL_GAZETTE`).
  2. Registered seed sources for `src_mcx_members` (MCX), `src_nsdl_depositories` (NSDL), `src_cdsl_depositories` (CDSL), `src_upis_official` (NPCI), and `src_irdai_insurers` (IRDAI).
  3. Added multi-attribute filtering by `source_type` and `authority` in `AuthoritativeSourceRegistry.list_sources()`.
- Why: Provides complete governance tracking, domain allowlisting, and provenance policies for Indian capital market regulators and market infrastructure entities.
- Alternatives considered: Dynamic schema dictionaries (rejected: lacks static type guarantees and validation).
- Consequences: All authoritative sources possess strict governance metadata and explicit authority tiers.
- Files: `sangyan/verification/sources.py`, `tests/test_api.py`

---

### D-025: Market Infrastructure & Depository Participant Verification (NSE, BSE, MCX, NSDL, CDSL)
- Date / phase / commit: 2026-10-04, Phase 3
- Context: Fraudulent investment solicitations frequently impersonate recognized stock exchange members, clearing members, or depository participants (e.g. claiming fake member IDs on NSE or BSE). The system must deterministically verify these assertions against official member directories.
- Decision: Implemented `MarketInfrastructureVerificationAdapter` (`sangyan/verification/adapters/market_infrastructure.py`) backed by `src_market_infrastructure` versioned snapshots:
  1. Verifies exchange member IDs and DP IDs across NSE, BSE, MCX, NSDL, and CDSL.
  2. Distinguishes active, expired, suspended, and expelled/defaulter statuses.
  3. Enforces epistemic precedence: Disciplinary expulsion/defaulter orders (e.g. Karvy NSE ID `08035`) strictly yield `CONTRADICTED` prior to natural date expiry (`OUTDATED`).
  4. Bogus claimed member IDs not present in directories yield `CONTRADICTED` with `not_found` status.
  5. Distinguishes legitimate market infrastructure advisories (hard-negative suppression on "NSE cautions...").
- Why: Directly fulfills prompt Section 8 for market infrastructure verification and prevents expelled or unregistered brokers from operating under legitimate exchange banners.
- Alternatives considered: Merging market infrastructure lookups into `SEBIVerificationAdapter` (rejected: violates single-responsibility principle; exchange member IDs differ from statutory SEBI registration formats).
- Consequences: Trading member and DP claims are evaluated against authoritative market infrastructure directories.
- Files: `sangyan/verification/adapters/market_infrastructure.py`, `sangyan/verification/snapshots.py`, `tests/test_verification_extended.py`

---

### D-026: UPI Payment Destination & Corporate Mismatch Verification
- Date / phase / commit: 2026-10-04, Phase 3
- Context: Real-world investment scams solicit funds into personal UPI accounts (e.g. `@paytm`, `@ybl`) while masquerading as registered corporate brokers or SEBI advisers. Prompt Section 34 mandates verifying payment identifiers, detecting mismatches, and returning `INSUFFICIENT_EVIDENCE` for unfamiliar VPAs without falsely declaring fraud.
- Decision: Implemented `UPIPaymentVerificationAdapter` (`sangyan/verification/adapters/payment.py`):
  1. Validates payment VPAs against `src_upis_official` verified merchant registry.
  2. Identifies official corporate VPAs for registered brokers (e.g. `zerodha.pay@okhdfcbank`, `groww@icici`) and emits `SUPPORTED`.
  3. Matches against blacklisted fraudulent/cybercrime-reported VPAs (e.g. `fastprofit24@paytm`) and emits `CONTRADICTED`.
  4. Detects corporate mismatch: When content mentions a recognized broker brand (e.g. Zerodha, Groww) or statutory authority (SEBI) but requests payment to a personal VPA pattern, emits `CONTRADICTED` citing SEBI circular bans on personal fund transfers.
  5. Safe epistemic default: An unfamiliar VPA with no contradiction or impersonation returns `INSUFFICIENT_EVIDENCE`, ensuring absence of evidence is not conflated with fraud.
- Why: Protects retail investors from unauthorized third-party payment diversions while adhering to supervisory epistemic standards.
- Alternatives considered: Regex-only VPA format checking (rejected: cannot detect legitimate corporate vs personal account mismatches).
- Consequences: Clear, defensible determinations on payment solicitation claims.
- Files: `sangyan/verification/adapters/payment.py`, `sangyan/verification/snapshots.py`, `tests/test_verification_extended.py`

---

### D-027: Evidence Provenance, Quality Dimensions, and Value Normalization
- Date / phase / commit: 2026-10-04, Phase 3
- Context: Prompt Section 11, 14, and 36 require Evidence domain models to track tenant ownership, source record IDs, source URLs, effective validity intervals, evidence types, provenance policies, raw vs normalized values, and multi-dimensional quality scores without breaking existing database schemas.
- Decision: Enhanced `Evidence` domain dataclass (`sangyan/domain/models.py`) with typed accessors:
  1. Added `tenant_id`, `source_record_id`, `source_url`, `effective_from`, `effective_until`, `evidence_type`, and `provenance`.
  2. Preserved original assertion as `raw_value` while capturing canonical registry entry as `normalized_value`.
  3. Structured multi-dimensional `quality` vector capturing `authority`, `freshness`, `directness`, `specificity`, and `completeness`.
  4. Retained 100% backward compatibility with database schema and existing test suites via JSON metadata mapping.
- Why: Provides full cryptographic and evidentiary traceability from user assertion to verbatim registry certificate.
- Alternatives considered: Modifying SQL migration schema (rejected: would force breaking changes onto existing databases when metadata encapsulation cleanly satisfies the requirement).
- Consequences: Every evidence item carries rich audit and quality provenance.
- Files: `sangyan/domain/models.py`, `sangyan/verification/engine.py`

---

### D-028: Authoritative Verification Audit Logging & Chained SHA3-256 Ledger
- Date / phase / commit: 2026-10-04, Phase 3
- Context: Prompt Section 38 mandates producing audit events for all verification operations, recording tenant, claim, source, adapter, timestamp, result, evidence, and failure without logging secrets.
- Decision:
  1. Defined `AuditEvent` domain model (`sangyan/domain/models.py`).
  2. Implemented `record_audit_event()` and `list_audit_events()` on `TenantRepository` backed by `sangyan_audit_events`.
  3. Chained consecutive audit events with canonical SHA3-256 ledger hashes (`prev_hash:event_id:actor:action:resource:result:timestamp`), making audit log tampering or deletion cryptographically detectable.
  4. Automated audit event emission inside `ClaimVerificationEngine.verify_claim()` and `verify_content_item()`.
  5. Enforced tenant isolation on all audit queries.
- Why: Guarantees immutable, tamper-evident forensic records of all platform determinations.
- Alternatives considered: Standard Python logger only (rejected: ephemeral, not queryable by tenants, lacks cryptographic chaining).
- Consequences: Institutional investigators can inspect a verifiable audit ledger of all verification actions.
- Files: `sangyan/domain/models.py`, `sangyan/tenancy/repository.py`, `sangyan/verification/engine.py`, `tests/test_verification_extended.py`

---

### D-029: Verification REST API & Human Audit Inspection Views
- Date / phase / commit: 2026-10-04, Phase 3
- Context: Prompt Sections 39, 40, and 41 require exposing verification capabilities through clean REST APIs and lightweight, human-auditable inspection views without overbuilding a complex frontend.
- Decision: Created `sangyan.api` module (`sangyan/api/app.py`, `sangyan/api/routes.py`, `sangyan/api/views.py`):
  1. REST API endpoints:
     - `POST /api/v1/verify/claim`: Single atomic assertion verification.
     - `POST /api/v1/verify/content`: Full intelligence, multi-adapter verification, and trust receipt pipeline.
     - `GET /api/v1/investigations/{id}`: Investigation envelope with claims, entities, signals, and findings.
     - `GET /api/v1/claims/{id}/evidence`: List authoritative evidence items.
     - `GET /api/v1/claims/{id}/findings`: List synthesized findings.
     - `GET /api/v1/sources`: Registered institutional registries and allowlists.
     - `GET /api/v1/audit/events`: Query tenant audit events.
  2. HTML Inspection Views (`/inspect/claim/{id}` and `/inspect/investigation/{id}`):
     - Renders claim text, epistemic stance badges, and verbatim evidence excerpts with SHA3-256 hashes.
     - Mandatory Section 40 Banner: Prominently displays "INSUFFICIENT EVIDENCE: No authoritative record was found. This does NOT establish that the claim is false."
     - Conflicting Display: Renders side-by-side cards comparing opposing authoritative evidence (Source A vs Source B) when discrepancies exist.
     - Anchored by ML-DSA-65 post-quantum trust receipt status.
- Why: Empowers human analysts and institutional regulators to review, understand, and audit machine determinations with total transparency.
- Alternatives considered: Heavy React/Next.js dashboard (rejected: prompt Section 41 explicitly forbids overbuilding UI during Phase 3).
- Consequences: Ready-to-deploy FastAPI application providing both machine-readable JSON contracts and human-readable audit views.
- Files: `sangyan/api/app.py`, `sangyan/api/routes.py`, `sangyan/api/views.py`, `tests/test_api.py`

---

### D-030: Graph Correlation Model & Strength Hierarchy (STRONG/MEDIUM/WEAK)
- Date / phase / commit: 2026-10-04, Phase 4
- Context: Phase 4 mandates transforming atomic claims, resolved entities, and safety signals across multiple content items into a connected investigation graph without false linkages or unbounded memory/cycle expansion.
- Decision: Implemented `InvestigationCorrelator` (`sangyan/correlation/correlator.py`):
  1. Standardized relationship types (`SHARED_ENTITY`, `SHARED_PAYMENT`, `SHARED_CONTACT`, `SHARED_INFRASTRUCTURE`, `COMMON_PATTERN`, `TEMPORAL_SEQUENCE`, `CLAIM_LINK`, `ENTITY_LINK`) and strength tiers (`STRONG`, `MEDIUM`, `WEAK`).
  2. Defined explicit strength rules: Direct shared payment VPAs, registration numbers, domains, phone numbers, or mutual contradictions establish `STRONG` edges; fuzzy aliases or claim corroboration establish `MEDIUM` edges; co-occurrence or loose pattern overlaps establish `WEAK` edges.
  3. Enforced bounded traversal safeguards: Maximum 5 hops depth, 200 edges per investigation subgraph, and 25 related content items limit.
  4. Cycle avoidance: DFS/BFS traversal tracks visited vertex sets, preventing infinite recursion on self-referential or cyclic graph structures.
  5. Canonical normalizers: Dedicated canonicalizers for phone numbers (E.164-like stripped digits), UPI VPAs (lowercase stripped), domains (fqdn lowercase), and registration numbers (alphanumeric uppercase).
- Why: Provides a deterministic, mathematically bounded correlation network representing multi-content syndicate links while preventing DoS via cyclic or dense graphs.
- Alternatives considered: External graph database like Neo4j (rejected: introduces heavy operational dependency for tenant-scoped relational queries; in-memory/SQLite relational model is self-contained and reproducible).
- Consequences: Investigations cleanly link related content items and cross-entity networks with explicit evidentiary strength.
- Files: `sangyan/correlation/correlator.py`, `sangyan/domain/models.py`, `tests/test_correlation.py`

---

### D-031: 12-Stage Scam-Chain Reconstruction & Inferred Stage Semantics
- Date / phase / commit: 2026-10-04, Phase 4
- Context: Financial fraud follows an observable lifecycle (lure -> platform access -> credential harvesting -> withdrawal fee/block). Phase 4 requires reconstructing this lifecycle across 12 discrete stages with explicit epistemic statuses (`OBSERVED`, `SUPPORTED`, `INFERRED`, `NOT_OBSERVED`, `UNKNOWN`) and avoiding false accusations on regulatory warnings.
- Decision: Implemented `ScamChainReconstructor` (`sangyan/correlation/scam_chains.py`):
  1. Reconstructs 12 stages: `LURE_FIRST_CONTACT`, `PLATFORM_ACCESS`, `TRUST_BUILDING`, `GROUP_INDOCCTRINATION`, `CREDENTIAL_HARVESTING`, `INITIAL_DEPOSIT`, `FICTITIOUS_RETURNS`, `ESCALATION_COERCION`, `WITHDRAWAL_ATTEMPT`, `FEE_EXTORTION`, `COMMUNICATION_TERMINATION`, `SECONDARY_RECOVERY_SCAM`.
  2. Status semantics:
     - `OBSERVED`: Direct observable signal or claim matches stage indicators.
     - `SUPPORTED`: Validated by corroborating authoritative evidence or regulatory findings.
     - `INFERRED`: Logical prerequisite or downstream consequence of observed stages (e.g. withdrawal fee extortion implies prior fictitious returns and deposit stages).
     - `NOT_OBSERVED`: No indicators present for this stage in analyzed materials.
     - `UNKNOWN`: Incomplete or ambiguous data.
  3. Hard-negative suppression: When content contains legitimate regulatory warnings (e.g. SEBI caution circulars, broker advisories), all 12 stages are explicitly evaluated as `NOT_OBSERVED` to prevent treating the warning itself as scam progression.
- Why: Gives victims and investigators a transparent visual breakdown of where the interaction stands in the scam lifecycle without hallucinating unobserved events.
- Alternatives considered: Linear state machine requiring every prior stage to be observed before advancing (rejected: real-world reporting often begins at later stages such as withdrawal blockage or fee demands).
- Consequences: Clear chronological and causal mapping of fraudulent schemes.
- Files: `sangyan/correlation/scam_chains.py`, `sangyan/domain/models.py`, `tests/test_correlation.py`

---

### D-032: Multi-Label Controlled Scam Taxonomy Classification
- Date / phase / commit: 2026-10-04, Phase 4
- Context: Financial frauds frequently exhibit overlapping characteristics (e.g. a fake IPO scheme operating via an impersonated Telegram channel demanding personal UPI transfers). Systems that force single-label classification lose critical operational intelligence.
- Decision: Implemented `ScamTaxonomyClassifier` (`sangyan/correlation/taxonomy.py`):
  1. Implemented a controlled 14-pattern taxonomy: `UNAUTHORIZED_ADVISORY`, `GUARANTEED_RETURN_SCHEME`, `REGULATOR_IMPERSONATION`, `BROKER_IMPERSONATION`, `DIGITAL_ARREST_EXTORTION`, `PUMP_AND_DUMP`, `TASK_BASED_INVESTMENT_FRAUD`, `FAKE_TRADING_PLATFORM`, `UNREGISTERED_PMS_AIF`, `RECOVERY_ROOM_FRAUD`, `ALGO_TRADING_PONZI`, `OFFSHORE_FOREX_CRYPTO_SOLICITATION`, `PRE_IPO_UNLISTED_SHARE_FRAUD`, `PONZI_MULTI_TIER_REFERRAL`.
  2. Multi-label coexistence: Multiple patterns can be active simultaneously if their distinct signal and evidence requirements are satisfied.
  3. Zero bare-keyword triggering: Every pattern requires a combination of detected signals, resolved entity types, and/or authoritative contradiction findings (e.g. `REGULATOR_IMPERSONATION` requires statutory authority mention + contradiction/impersonation signal).
  4. Safe fallback: Returns an empty pattern set if no pattern meets the rigorous multi-signal threshold, avoiding speculative categorization.
- Why: Provides institutional investigators with accurate, multi-faceted fraud classifications grounded strictly in verified signals and registry contradictions.
- Alternatives considered: Monolithic single-label classification or keyword-bag matching (rejected: produces severe false positives and obscures multi-vector attack tactics).
- Consequences: Rich, multi-dimensional pattern attribution with deterministic explainability.
- Files: `sangyan/correlation/taxonomy.py`, `sangyan/domain/models.py`, `tests/test_correlation.py`

---

### D-033: Non-Investment Conditional Safe Guidance & Incident Preservation Checklist
- Date / phase / commit: 2026-10-04, Phase 4
- Context: Retail investors in distress require clear, non-speculative, actionable steps to safeguard funds and preserve evidence. However, SANGYAN must never offer financial, trading, or investment advice (buy/sell/hold/broker endorsements).
- Decision: Implemented `GuidanceEngine` (`sangyan/correlation/guidance.py`):
  1. Strict non-investment scope: Guidance is exclusively operational, security, and legal/regulatory protection.
  2. Conditional next-step guidance:
     - Urgent financial freeze: Immediate recommendation to dial 1930 / visit cybercrime.gov.in and request banking golden-hour freeze if funds were transferred.
     - Device & credential hygiene: Revocation of remote access tools (AnyDesk, TeamViewer), changing banking credentials, and enabling hardware 2FA.
     - Communication cessation: Cease all dialogue with solicitants; never pay secondary "clearance" or "tax" fees.
  3. Forensic incident preservation checklist:
     - Systematic instructions to preserve unedited chat exports, payment transaction IDs (UTR, VPA, bank statements), app APKs/URLs, and caller phone numbers.
- Why: Empowers users to mitigate immediate financial loss and secure admissible digital evidence without violating regulatory advisory prohibitions.
- Alternatives considered: Generic "be careful" warnings (rejected: unhelpful during active fraud) or automated payment reversals (rejected: technically impossible without direct banking switch integration).
- Consequences: Actionable, legally compliant, victim-centric safety directives.
- Files: `sangyan/correlation/guidance.py`, `sangyan/domain/models.py`, `tests/test_correlation.py`

---

### D-034: Grievance Problem Classification & Official Institutional Routing
- Date / phase / commit: 2026-10-04, Phase 4
- Context: When an investor experiences fraud or malfeasance, filing a grievance with the wrong regulatory authority (e.g. filing a banking cyber-theft with SEBI instead of Cybercrime/1930, or filing an unlisted share grievance with RBI) causes critical delays and administrative rejections.
- Decision: Implemented `GrievanceRouter` (`sangyan/correlation/grievance.py`):
  1. Categorizes user situations into 9 distinct grievance classes: `UNREGISTERED_INTERMEDIARY_SEBI`, `INVESTOR_FRAUD_CYBERCRIME`, `BANKING_PAYMENT_FAILURE_RBI`, `TELECOM_SPAM_PHISHING_CHAKSHU`, `UNAUTHORIZED_PMS_AIF_SEBI`, `MARKET_MANIPULATION_SEBI`, `BROKER_DEFICIENCY_SEBI_EXCHANGE`, `FAKE_PLATFORM_CYBERCRIME`, `GENERAL_INQUIRY`.
  2. Maps directly to authoritative Indian regulatory grievance portals:
     - Cybercrime Portal (`cybercrime.gov.in` / Helpline 1930): Financial cyber-fraud, digital arrest, fake trading apps.
     - SEBI SCORES 2.0 (`scores.sebi.gov.in`): Unregistered investment advisors, research analysts, fraudulent stock tips.
     - RBI CMS (`cms.rbi.org.in`): Banking transaction unauthorized debits, payment system operator failures.
     - DoT Chakshu (`sancharsaathi.gov.in`): Suspected telecom fraud, spoofed SMS, scam WhatsApp/Telegram numbers.
  3. No automated external submission: Formulates structured filing dossiers and checklists for the user while leaving final submission strictly in human hands.
- Why: Directs aggrieved investors to the exact statutory authority with legal jurisdiction over their specific grievance, accelerating remedial action.
- Alternatives considered: Direct API submission to SCORES/Cybercrime (rejected: requires institutional API keys, OTPs, and personal victim affidavits).
- Consequences: Accurate, multi-agency routing guidance tailored to the specific evidentiary findings.
- Files: `sangyan/correlation/grievance.py`, `sangyan/domain/models.py`, `tests/test_correlation.py`

---

### D-035: Epistemic Explainability & Mandatory Uncertainty Abstention
- Date / phase / commit: 2026-10-04, Phase 4
- Context: Black-box AI risk scores undermine user and regulator trust. An investor-safety platform must explain exactly why a conclusion was reached, link directly to authoritative evidence, and explicitly state what remains unknown or unverified.
- Decision: Implemented `InvestigationExplainer` (`sangyan/correlation/explainer.py`):
  1. "Why was this flagged?" synthesis: Assembles bullet-pointed rationales tied directly to observable signals, contradictory regulatory evidence, unregistered entities, and unverified payment channels.
  2. Direct evidentiary linkage: Each explanation item includes references to the supporting evidence IDs and registry sources.
  3. Mandatory "What we don't know" abstentions: Systematically enumerates unverified entities, claims with `INSUFFICIENT_EVIDENCE`, missing transaction proofs, and unconfirmed beneficial ownership.
  4. Preserves epistemic humility: Never emits definitive fraud conclusions when evidence is absent; labels such states as unverified rather than safe or fraudulent.
- Why: Complies with high-stakes financial transparency standards and prevents both false positives and dangerous false assurances.
- Alternatives considered: Free-form LLM-generated summaries without evidence bounds (rejected: prone to hallucinations, false certainty, and ungrounded speculation).
- Consequences: Defensible, human-auditable explanations for every investigation report.
- Files: `sangyan/correlation/explainer.py`, `sangyan/domain/models.py`, `tests/test_correlation.py`

---

### D-036: Investigation-Level ML-DSA-65 Post-Quantum Trust Binding
- Date / phase / commit: 2026-10-04, Phase 4
- Context: Correlated investigation reports aggregate findings, scam stages, guidance, and grievance records. To be forensically admissible and tamper-evident across organizational boundaries, the unified investigation dossier must be cryptographically signed using post-quantum cryptography.
- Decision: Extended `TrustService` (`sangyan/verification/trust_binding.py`):
  1. Built canonical investigation payload generator `build_investigation_payload()` combining investigation ID, tenant ID, content hashes, correlation graph digest, scam patterns, chain stages, guidance, and grievance records.
  2. Applied NIST FIPS 204 ML-DSA-65 post-quantum digital signature to the canonical investigation payload.
  3. Integrated `bind_investigation()` and `verify_investigation_integrity()` into the `InvestigationOrchestrator` workflow.
  4. Encapsulated signatures in standard `TrustReceipt` objects, maintaining seamless compatibility with the Phase 1 trust layer.
- Why: Guarantees post-quantum cryptographic immutability and non-repudiation for entire multi-content investigative dossiers.
- Alternatives considered: Classical RSA or ECDSA signatures (rejected: vulnerable to future quantum cryptanalysis; ML-DSA-65 is the established SANGYAN platform standard).
- Consequences: Legally and forensically robust investigation records verifiable by third-party auditors.
- Files: `sangyan/verification/trust_binding.py`, `sangyan/correlation/orchestrator.py`, `tests/test_correlation.py`

---

### D-037: LangGraph StateGraph Architecture & Workflow State Model
- Date / phase / commit: 2026-10-04, Phase 5
- Context: Phase 5 mandates orchestrating the complete SANGYAN investigation lifecycle using LangGraph StateGraph without duplicating existing business logic from intelligence, verification, correlation, or guidance subsystems.
- Decision: Implemented `InvestigationWorkflow` (`sangyan/workflow/graph.py`) and `InvestigationWorkflowState` (`sangyan/workflow/state.py`):
  1. Defined typed orchestration state `InvestigationWorkflowState` holding explicit identifiers (`investigation_id`, `organization_id`, `user_id`, `run_id`, `thread_id`), stage outputs, error/warning lists, and lifecycle flags. Large binary assets and raw secrets are strictly omitted from the state.
  2. Established explicit node boundaries that delegate exclusively to underlying domain services:
     - `intake_node`: Ingests and registers `ContentItem` instances in tenant scope.
     - `intelligence_node`: Invokes `ContentIntelligenceEngine` for atomic claims, entities, and observable signals.
     - `verification_node`: Invokes `ClaimVerificationEngine` across claims and authoritative adapters.
     - `correlation_node`: Invokes `InvestigationCorrelator` for cross-entity graph construction.
     - `scam_chain_node`: Invokes `ScamChainReconstructor` and `ScamTaxonomyClassifier`.
     - `guidance_node`: Invokes `GuidanceEngine` and `GrievanceRouter`.
     - `explanation_node`: Invokes `InvestigationExplainer` and evaluates review necessity.
     - `review_gate_node`: Handles durable human-in-the-loop review pause/resume via LangGraph `interrupt()`.
     - `trust_finalization_node`: Canonicalizes dossier and signs with ML-DSA-65 post-quantum cryptography.
     - `completion_node`: Atomically marks the investigation as `COMPLETED` and emits audit events.
     - `failure_node`: Handles unrecoverable errors, preserves partial evidence, and records failure status.
  3. Preserved strict separation: Nodes orchestrate domain services and update workflow state, but implement zero ad-hoc business rules or duplicate detection heuristics.
- Why: Provides clear architectural separation between deterministic domain engines and stateful execution orchestration.
- Alternatives considered: Monolithic node architecture or embedding business rules directly into graph conditionals (rejected: violates SANGYAN core architectural principles and creates duplicate ungrounded logic).
- Consequences: Maintainable, declarative workflow graph with transparent node contracts.
- Files: `sangyan/workflow/graph.py`, `sangyan/workflow/state.py`, `sangyan/workflow/nodes.py`

---

### D-038: Durable SQLite Checkpointing & Tenant-Scoped Thread Identity (`org:inv:run`)
- Date / phase / commit: 2026-10-04, Phase 5
- Context: Workflows must survive worker restarts, process crashes, and prolonged human review pauses without losing in-flight state. Checkpoint storage must be durable, tenant-isolated, and thread-safe.
- Decision: Implemented `WorkflowCheckpointer` and checkpoint manager (`sangyan/workflow/checkpointer.py`):
  1. Integrated LangGraph `SqliteSaver` backed by durable SQLite storage with WAL mode enabled.
  2. Enforced canonical composite thread identity format: `<organization_id>:<investigation_id>:<run_id>`.
  3. Enforced strict tenant pre-validation: Any request to load, inspect, resume, or cancel a checkpoint must verify that the caller belongs to the `<organization_id>` prefix of the `thread_id`.
  4. Added Migration 003 table `sangyan_workflow_runs` to provide a queryable relational ledger of workflow runs, thread IDs, statuses, and retry metrics alongside the binary checkpoint store.
- Why: Prevents cross-tenant state leakage while ensuring persistent, crash-resilient workflow checkpoints across process lifecycles.
- Alternatives considered: In-memory checkpointer only (rejected: does not survive process restart; cannot support real human review pauses) or pure Redis state (rejected: unnecessary infrastructure dependency).
- Consequences: Durable, restart-proof execution state with deterministic tenant isolation.
- Files: `sangyan/workflow/checkpointer.py`, `sangyan/database/migrations.py`

---

### D-039: Human-in-the-Loop Durable Interruption & Resume Semantics
- Date / phase / commit: 2026-10-04, Phase 5
- Context: High-stakes financial determinations with conflicting authoritative evidence or suspicious signals require supervisory human review. The workflow must physically pause, persist to disk, allow process restart, and resume seamlessly once an authorized analyst submits a decision.
- Decision: Implemented human-in-the-loop review mechanism (`sangyan/workflow/nodes.py`, `sangyan/workflow/service.py`):
  1. Review gate criteria: Triggered if `risk_posture == "SUSPICIOUS"`, if any claim resolves to `CONFLICTING`, if unverified high-risk signals are present, or if explicitly requested.
  2. Durable pause: `review_gate_node` executes LangGraph `interrupt({"investigation_id": inv_id, "reason": review_reason, "posture": risk_posture})`. The graph execution halts immediately and serializes current state to SQLite.
  3. Relational status tracking: `sangyan_investigations` and `sangyan_workflow_runs` are updated to `status="AWAITING_REVIEW"`.
  4. Resume execution: An analyst with `investigation:review` permission invokes `resume_investigation()`. The service validates caller authorization, applies `Command(resume=review_payload)` to the checkpointer thread, records the `Review` domain entity in `sangyan_reviews`, and resumes the graph directly into `trust_finalization_node`.
  5. Facts immutability: The reviewer's decision (`CONFIRM`, `DISMISS`, `ESCALATE`, `ANNOTATE`) is recorded as a supervisory layer on top of the investigation; it cannot delete, overwrite, or forge historical evidence or registry certificates.
- Why: Satisfies regulatory oversight mandates while ensuring human intervention never alters underlying factual evidence.
- Alternatives considered: Ephemeral function callbacks or boolean in-memory flags (rejected: cannot survive server restarts and fails multi-tenant security requirements).
- Consequences: Real, durable human-in-the-loop governance for ambiguous or high-consequence investigations.
- Files: `sangyan/workflow/nodes.py`, `sangyan/workflow/service.py`, `tests/test_workflow.py`

---

### D-040: Fault Resilience, Bounded Retry Policy & Error Classification
- Date / phase / commit: 2026-10-04, Phase 5
- Context: Unhandled exceptions during upstream network fetches, transient database lock contention, or adapter execution must not crash the orchestrator or leave investigations in an undefined state.
- Decision: Implemented structured error classification and retry policies (`sangyan/workflow/errors.py`, `sangyan/workflow/nodes.py`):
  1. Classified errors into retryable vs non-retryable categories:
     - Retryable: `TransientNetworkError`, `UpstreamUnavailableError`, `DatabaseBusyError`.
     - Non-retryable: `DomainValidationError`, `PermissionDeniedError`, `SecurityViolationError`, `ContradictoryEvidenceError`.
  2. Bounded retries: Enforced maximum retry limit (default 3 attempts) with exponential backoff and jitter. Non-retryable errors immediately route to `failure_node`.
  3. Node-level exception boundaries: Every node wraps execution in try/except blocks, recording errors into the `errors` state list and updating run retry counters.
  4. Failure isolation: Failure in downstream nodes (e.g. guidance or trust signing) retains all previously gathered content items, claims, entities, and evidence intact.
- Why: Prevents infinite retry loops while maintaining high operational resilience against transient infrastructure disruptions.
- Alternatives considered: Uncaught exception bubbling (rejected: causes process crashes and lost state) or blanket catch-all retries (rejected: causes futile retries on logic/validation errors).
- Consequences: Robust, self-healing execution with clear diagnostic audit logs.
- Files: `sangyan/workflow/errors.py`, `sangyan/workflow/nodes.py`, `tests/test_workflow.py`

---

### D-041: Workflow Cancellation Semantics & Partial State Preservation
- Date / phase / commit: 2026-10-04, Phase 5
- Context: Operators must be able to cancel in-flight or awaiting-review investigations. Cancellation must cleanly halt execution, preserve all already-persisted evidence, and prevent corrupted resumption.
- Decision: Implemented `cancel_investigation()` in `WorkflowService` (`sangyan/workflow/service.py`):
  1. Authorization: Only users with `investigation:create` or `tenant:manage` within the owning organization may cancel an investigation.
  2. State transition: Updates `sangyan_investigations` and `sangyan_workflow_runs` to `status="CANCELLED"`.
  3. Immutability protection: Completed investigations cannot be cancelled (`CannotCancelCompletedInvestigationError`).
  4. Partial preservation: All evidence, claims, entities, and findings accumulated prior to cancellation remain queryable in the repository for forensic reference.
  5. Resumption blocking: Attempting to resume a cancelled investigation is strictly rejected.
- Why: Provides administrative operational control while safeguarding evidentiary integrity.
- Alternatives considered: Dropping or rolling back all database tables on cancellation (rejected: destroys valuable forensic evidence gathered up to the cancellation point).
- Consequences: Clean, auditable cancellation lifecycle with evidence preservation.
- Files: `sangyan/workflow/service.py`, `sangyan/domain/models.py`, `tests/test_workflow.py`

---

### D-042: Epistemic Review Concurrency & Multi-Tenant Authorization Guardrails
- Date / phase / commit: 2026-10-04, Phase 5
- Context: Simultaneous review submissions by multiple analysts must be handled deterministically without silent overwrites, and tenant boundaries must be strictly enforced.
- Decision: Implemented concurrency controls and RBAC validation (`sangyan/workflow/service.py`):
  1. Concurrency policy: "First valid review decision wins". Uses investigation-level threading locks and database status verification (`status == 'AWAITING_REVIEW'`). Once a review is accepted and the status advances to `FINALIZING` / `COMPLETED`, subsequent review attempts raise `ReviewConflictError`.
  2. Role enforcement:
     - `sangyan_viewer`: Denied access to review submission (`PermissionDeniedError`).
     - `sangyan_analyst` / `sangyan_admin`: Permitted to submit reviews within their organization.
  3. Cross-tenant isolation: Calling `resume_investigation()` or `get_workflow_state()` with an organization ID differing from the investigation's owning organization raises `PermissionDeniedError` before reading any state.
  4. Decision replay defense: Review decisions contain unique IDs, timestamps, and target investigation IDs; attempting to replay a decision against a different investigation is rejected.
- Why: Enforces institutional audit standards and eliminates race conditions in collaborative investigation environments.
- Alternatives considered: Last-write-wins (rejected: allows accidental overwriting of supervisory decisions).
- Consequences: Deterministic review resolution and strict multi-tenant confidentiality.
- Files: `sangyan/workflow/service.py`, `tests/test_workflow.py`

---

### D-043: Post-Quantum Trust Finalization & Idempotent Dossier Signing
- Date / phase / commit: 2026-10-04, Phase 5
- Context: Final investigation dossiers must be cryptographically sealed with post-quantum digital signatures. Trust finalization must occur only after all required stages and human reviews are complete, and repeated finalization requests must be idempotent.
- Decision: Implemented `trust_finalization_node` and trust binding lifecycle (`sangyan/workflow/nodes.py`, `sangyan/workflow/service.py`):
  1. Finalization timing: Positioned strictly after `review_gate_node`. If human review was required, signing only executes after an authorized decision is committed.
  2. Idempotency: If `trust_receipt_id` already exists on the state/investigation and verifies against the public key, the existing `TrustReceipt` is reused without generating redundant signatures.
  3. Signing failure resilience: If the PQC cryptographic provider fails (e.g. key unavailable), the investigation is marked `trust_status="FAILED"`, the analytical report remains readable, and an explicit audit event is recorded without destroying the investigation data.
  4. Integrity verification: Signed receipts bind `investigation_id`, `organization_id`, content hashes, findings, evidence hashes, and scam patterns under NIST FIPS 204 ML-DSA-65.
- Why: Guarantees cryptographic non-repudiation and post-quantum tamper evidence for completed investigations while preserving availability if signing fails.
- Alternatives considered: Signing transient intermediate node states (rejected: creates noisy receipts for incomplete or mutable data).
- Consequences: Tamper-evident, audit-ready investigation dossiers with post-quantum security guarantees.
- Files: `sangyan/workflow/nodes.py`, `sangyan/workflow/service.py`, `tests/test_workflow.py`

---

### D-044: Multi-Scheme External Authentication Boundary (JWT & API Key) & Canonical Principal Model
- Date / phase / commit: 2026-10-04, Phase 6
- Context: External callers must be authenticated before accessing investigation or workflow services. The system must clearly distinguish unauthenticated (401), authenticated, and authorized (403) states. Both interactive user sessions (JWT) and automated institutional integrations (API keys) are required. Conflicting or ambiguous credentials presented in a single request must be deterministically rejected.
- Decision: Implemented external authentication boundary and `Principal` model (`sangyan/security/models.py`, `sangyan/security/auth.py`):
  1. Built immutable `Principal` dataclass carrying `principal_id`, `organization_id`, `roles`, `scopes`, `auth_method`, `credential_id`, `issued_at`, and `expires_at`.
  2. Implemented dual authentication extraction: `Authorization: Bearer <token>` (JWT) and `X-API-Key: <key>` (API key).
  3. Enforced mutual exclusivity: if both Bearer and X-API-Key headers are present, the request is rejected with HTTP 400 (`AmbiguousAuthenticationError`) to prevent credential confusion or privilege substitution.
  4. Enforced fail-closed behavior: invalid or expired credentials fail with HTTP 401 and standard `WWW-Authenticate` header.
  5. Clean downstream context: authentication is resolved once at the API boundary and attached to `request.state.principal`.
- Why: Provides a single, unambiguous identity representation for downstream authorization while eliminating credential-juggling attacks.
- Alternatives considered: Allowing JWT to override API key silently (rejected: creates security confusion and masks misconfigured automated clients).
- Consequences: Transparent, auditable identity resolution across all endpoints.
- Files: `sangyan/security/models.py`, `sangyan/security/auth.py`, `sangyan/api/app.py`

---

### D-045: Cryptographic JWT Validation, Allowed Algorithms & Key Lifecycle
- Date / phase / commit: 2026-10-04, Phase 6
- Context: Untrusted JWTs must be strictly validated against signature, algorithm, issuer, audience, and time validity before any claims are trusted. `alg=none`, unsigned tokens, and algorithm confusion attacks must be definitively prevented.
- Decision: Implemented `JwtValidator` (`sangyan/security/jwt.py`):
  1. Cryptographic validation using PyJWT (`jwt.decode`) against configured secret (symmetric HS256) or public key (asymmetric RS256/ES256/EdDSA).
  2. Strict algorithm allowlist (`HS256`, `RS256`, `ES256`, `EdDSA`). Explicit rejection of `none` or unexpected algorithms.
  3. Mandatory claims enforcement: validates `exp` (expiry), `nbf` (not-before), `iat` (issued-at), `iss` (issuer match), `aud` (audience match), `sub` (principal identity), and `org_id` (tenant boundary).
  4. Explicit clock skew tolerance bounded to 30 seconds (`leeway=30`).
  5. No remote JWKS fetching without caching and domain validation; rejects untrusted `kid` parameters.
  6. Environment separation: production mode strictly requires configured non-default verification keys (`SANGYAN_JWT_SECRET` or `SANGYAN_JWT_PUBLIC_KEY`), failing startup if missing or weak.
- Why: Defends against signature forgery, replay of expired tokens, and cross-issuer/cross-tenant token replay attacks.
- Alternatives considered: Inspecting unverified payload claims prior to signature check (rejected: creates critical spoofing vulnerabilities).
- Consequences: Provably sound JWT validation adhering to RFC 7519 standards.
- Files: `sangyan/security/jwt.py`, `tests/test_security_phase6.py`

---

### D-046: Hashed API Key Storage, Key Generation & Prefixed Lookup (Migration 004)
- Date / phase / commit: 2026-10-04, Phase 6
- Context: Automated clients and server-to-server integrations require API key authentication. Storing plaintext API keys in relational storage creates critical database compromise risks. Keys must be queryable in O(1) without leaking hash timing information.
- Decision: Implemented prefixed hashed API keys and Migration 004 (`sangyan/security/api_keys.py`, `sangyan/database/migrations.py`):
  1. Key structure: `sgy_<prefix>_<secret>` where `prefix` is 8 hex characters (for indexed lookup) and `secret` is 32 secure hex characters (entropy >= 128 bits).
  2. Secure hash storage: stores SHA-256 hash of `prefix:secret` in `sangyan_api_keys.key_hash`. Plaintext secret is never persisted and only displayed once upon generation.
  3. Added Migration 004 table `sangyan_api_keys` with columns: `id`, `organization_id`, `user_id`, `name`, `key_prefix`, `key_hash`, `role`, `scopes`, `expires_at`, `revoked_at`, `last_used_at`, `created_at`.
  4. Prefixed constant-time verification: lookup by `key_prefix`, compute SHA-256 over submitted secret, verify hash with `hmac.compare_digest`, check `revoked_at is None` and `expires_at > now()`, and atomically update `last_used_at`.
  5. Lifecycle operations: supports creation, revocation (`revoked_at`), expiration checks, and scoped listing in `TenantRepository`.
- Why: Prevents database credential dumps from yielding active API keys while maintaining high lookup performance without full-table scans.
- Alternatives considered: Storing raw API keys (rejected: catastrophic failure mode on database breach) or unindexed bcrypt over whole key (rejected: O(N) database scan on every request).
- Consequences: Secure, high-performance API key authentication with instant revocation.
- Files: `sangyan/security/api_keys.py`, `sangyan/database/migrations.py`, `sangyan/tenancy/repository.py`

---

### D-047: Strict Multi-Tenant Isolation, IDOR/BOLA Protection & Contextual RBAC Matrix
- Date / phase / commit: 2026-10-04, Phase 6
- Context: External callers must never be able to access another tenant's investigations, claims, evidence, correlations, workflows, or audit logs by manipulating `organization_id` in request payloads, query strings, or path parameters.
- Decision: Implemented tenant boundary enforcement and RBAC matrix (`sangyan/security/auth.py`, `sangyan/api/routes.py`):
  1. Zero-trust parameter policy: `organization_id` is resolved exclusively from `principal.organization_id`. Any request body or query parameter claiming a different `organization_id` raises HTTP 403 `TenantMismatchError`.
  2. IDOR/BOLA defense: every resource access (`get_investigation`, `get_workflow_state`, `list_workflow_runs`, `cancel_investigation`) enforces ownership against `principal.organization_id`. Non-existent or foreign-tenant resources return HTTP 404 (or 403) consistently to prevent cross-tenant ID enumeration.
  3. Centralized RBAC enforcement:
     - `sangyan_viewer`: read-only access to own tenant investigations and receipts.
     - `sangyan_analyst`: create investigations, start workflows, review/resume workflows, cancel workflows.
     - `sangyan_admin`: all analyst permissions + tenant management and API key lifecycle.
  4. LangGraph thread identity protection: `<organization_id>:<investigation_id>:<run_id>` validated before any checkpointer interaction.
- Why: Prevents horizontal and vertical privilege escalation and eliminates cross-tenant data leaks.
- Alternatives considered: Trusting user-supplied `organization_id` with a database check (rejected: prone to parameter tampering and developer omission).
- Consequences: Bulletproof tenant isolation enforced uniformly at the API gateway layer.
- Files: `sangyan/security/auth.py`, `sangyan/api/routes.py`, `tests/test_security_phase6.py`

---

### D-048: Token-Bucket Rate Limiting Middleware & Failed-Authentication Throttling
- Date / phase / commit: 2026-10-04, Phase 6
- Context: The API must be protected against credential stuffing, denial-of-service, and resource exhaustion without introducing heavy external infrastructure like Redis for local single-node deployments.
- Decision: Implemented in-memory sliding `TokenBucketRateLimiter` (`sangyan/security/rate_limiter.py`):
  1. Multi-dimensional scoping: rate limits keyed by `(principal_id, endpoint_class)` for authenticated callers, and `(client_ip, endpoint_class)` for unauthenticated callers.
  2. Endpoint classes:
     - `auth`: 10 req/min (brute-force defense)
     - `investigation`: 30 req/min (CPU-heavy content analysis)
     - `workflow_mutate`: 20 req/min (start, resume, cancel)
     - `read`: 120 req/min (query state, runs, inspection)
     - `default`: 60 req/min
  3. Failed-authentication throttling: tracks consecutive auth failures per client IP (threshold: 5 failures/min); locks out further attempts with HTTP 429 for a 60-second backoff window.
  4. Standards-compliant response: returns HTTP 429 with `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers.
  5. Clean in-memory concurrency: thread-safe with lock, bounded memory cleanup of inactive buckets.
- Why: Protects CPU-intensive cryptographic verification and LLM pipelines from exhaustion while stopping credential brute-force attacks.
- Alternatives considered: Global rate limiter across all endpoints (rejected: allows read bursts to starve critical workflow operations).
- Consequences: Fine-grained traffic shaping with zero external infrastructure dependencies.
- Files: `sangyan/security/rate_limiter.py`, `tests/test_security_phase6.py`

---

### D-049: Hardened HTTP Security Headers, Restricted CORS & Request Body Bounds
- Date / phase / commit: 2026-10-04, Phase 6
- Context: Production APIs must protect against MIME-type sniffing, clickjacking, browser caching of financial data, cross-origin abuse, and unbounded payload denial-of-service.
- Decision: Implemented `SecurityHeadersMiddleware`, restricted CORS, and request bounds (`sangyan/security/middleware.py`, `sangyan/api/app.py`):
  1. Security Headers: Injects `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: geolocation=(), camera=(), microphone=()`, and `Content-Security-Policy: default-src 'self'`.
  2. Strict Cache-Control: Injects `Cache-Control: no-store, no-cache, must-revalidate` on all `/api/v1/*` routes to prevent client/proxy caching of sensitive evidence and investigation dossiers.
  3. Hardened CORS: Eliminates `allow_origins=["*"]` when credentials are supported; requires explicitly configured allowed origins (`SANGYAN_ALLOWED_ORIGINS`).
  4. Request body bounding: Enforces maximum request body size of 2 MB (`MAX_REQUEST_BODY_BYTES`) before parsing payload; returns HTTP 413 Payload Too Large on oversized inputs.
  5. Payload limits: Enforces max 25 content items per batch, max 100,000 characters per content item, max 2048 characters per URL.
- Why: Hardens the HTTP transport layer against standard web vulnerabilities and memory exhaustion attacks.
- Alternatives considered: Relying solely on reverse-proxy headers (rejected: application must be secure-by-default even if deployed without an edge proxy).
- Consequences: Defense-in-depth protection across all incoming and outgoing HTTP interactions.
- Files: `sangyan/security/middleware.py`, `sangyan/api/app.py`

---

### D-050: Low-Cardinality Telemetry, Prometheus Metrics, Request Correlation & Structured Redacted Logging
- Date / phase / commit: 2026-10-04, Phase 6
- Context: Observability must monitor API performance, workflow lifecycles, and security events without leaking sensitive investor content, credentials, or creating high-cardinality memory leaks.
- Decision: Implemented telemetry, Prometheus metrics exporter, and sensitive-data redaction (`sangyan/security/telemetry.py`):
  1. Request correlation: Injects or propagates `X-Request-ID` across HTTP requests, workflow executions, and audit records.
  2. Prometheus metrics at `/metrics`:
     - `sangyan_http_requests_total(method, route, status_code)`
     - `sangyan_http_request_duration_seconds(method, route)`
     - `sangyan_security_events_total(event_type, status)`
     - `sangyan_workflow_runs_total(status)`
     - `sangyan_rate_limit_exceeded_total(endpoint_class)`
     - `sangyan_pqc_trust_signatures_total(status)`
  3. Strict cardinality bounding: Routes are normalized to route templates (e.g. `/api/v1/workflow/{id}/resume`). Explicitly forbids `user_id`, `investigation_id`, `claim_text`, or raw URLs in Prometheus labels.
  4. Sensitive log redaction: Regex-based redaction filters redact Bearer tokens, API keys (`sgy_*`), passwords, OTPs, and private keys from all structured log output.
  5. Chained audit ledger integration: Material security events (auth failure, tenant mismatch, key revocation) link into the tamper-evident SHA3-256 audit ledger.
- Why: Provides complete operational visibility and auditability without exposing PII, secrets, or exploding monitoring system memory.
- Alternatives considered: Logging full request bodies for debugging (rejected: leaks sensitive financial grievances and credentials into log aggregators).
- Consequences: Production-ready observability compliant with privacy and security mandates.
- Files: `sangyan/security/telemetry.py`, `sangyan/api/app.py`

---

### D-051: Minimal Multi-Stage Container Packaging, Non-Root Runtime & Read-Only Root Filesystem
- Date / phase / commit: 2026-10-04, Phase 7
- Context: Deploying SANGYAN into production requires a minimal, reproducible, and secure container image. Running as root or permitting mutable root filesystems exposes the host and cluster to privilege escalation, container escapes, and unauthorized code mutation. Build-time secrets or test dependencies must never leak into production layers.
- Decision: Implemented a hardened multi-stage Dockerfile:
  1. Base Image: `python:3.13-slim` (matching repository Python 3.13 runtime, Debian Bookworm minimal).
  2. Multi-Stage Build: Builder stage compiles wheels and installs dependencies; runtime stage copies only pre-built wheels and application source code, omitting compilers (`gcc`, `make`) and test fixtures.
  3. Non-Root Identity: Dedicated system user and group `sangyan` (UID `10001`, GID `10001`) with no shell access (`/sbin/nologin`). All processes run under UID 10001.
  4. Filesystem Boundary: Read-only root filesystem (`readOnlyRootFilesystem: true`). Application source at `/app` is owned by `root:root` and mode `0555` (read-only to runtime user).
  5. Explicit Writable Storage: Only dedicated, explicitly mounted runtime paths are writable:
     - `/app/data` (mode `0750`, owned by `10001:10001`) for SQLite database (if used).
     - `/app/checkpoints` (mode `0750`, owned by `10001:10001`) for LangGraph SQLite WAL checkpoint storage.
     - `/app/keys` (mode `0700`, owned by `10001:10001`) for ML-DSA-65 post-quantum signing keys.
     - `/app/backups` (mode `0750`, owned by `10001:10001`) for local backup dumps.
     - `/tmp` (mounted as `emptyDir` tmpfs).
  6. Signal Handling & Entrypoint: Exec-form entrypoint `["python", "-m", "sangyan.cli", "serve"]` ensuring PID 1 forwards `SIGTERM` and `SIGINT` cleanly to Uvicorn for graceful shutdown without shell swallowing.
  7. Build Context Hygiene: Comprehensive `.dockerignore` excluding `.git`, `.venv`, `__pycache__`, `tests/`, local `.db` files, credentials, `.env*`, and research/paper artifacts.
- Why: Eliminates privilege escalation, prevents in-container source modification by attackers, minimizes image attack surface, and ensures deterministic container builds.
- Alternatives considered: Distroless Python images (rejected: lacks necessary standard library shared objects and SQLite binary bindings required for LangGraph WAL checkpointer).
- Consequences: Production container passes strict CIS Docker benchmarks and runs under Kubernetes `restricted` Pod Security Standards.
- Files: `Dockerfile`, `.dockerignore`

---

### D-052: Single-Replica Deployment Topology, Worker Concurrency & In-Process State Isolation
- Date / phase / commit: 2026-10-04, Phase 7
- Context: SANGYAN relies on in-memory sliding token-bucket rate limiting (`TokenBucketRateLimiter`), per-investigation in-memory execution thread locks (`_investigation_locks`), and an embedded SQLite WAL checkpointer (`WorkflowCheckpointer`) for LangGraph state persistence. Naively scaling the API to multiple horizontal replicas (e.g. via HPA) without distributed coordination would lead to split-brain rate limits, concurrent review-gate race conditions, and SQLite multi-node write lock corruption.
- Decision: Formally establish a Single-Replica Deployment Topology (`replicas: 1`) per tenant/environment:
  1. Pod Count: `replicaCount: 1` enforced in Helm values and Docker Compose. Autoscaling (HPA) is explicitly disabled.
  2. Process Model: Single-worker Uvicorn process (`--workers 1`) to preserve in-process mutual exclusion across concurrent investigation threads and SQLite write transactions.
  3. Vertical Scaling: Performance scaling is achieved vertically by adjusting CPU and memory requests/limits (`resources.requests` and `resources.limits`).
  4. Concurrency Safety: Python's `asyncio` event loop handles high-concurrency I/O for API requests, while background CPU-intensive verification and graph operations run in bounded threadpools with re-entrant locking.
- Why: Prevents distributed state inconsistencies, eliminates file lock contention on SQLite WAL checkpoints, and guarantees absolute correctness of investigation review gates without requiring heavy distributed infrastructure (Redis, ZooKeeper, etcd).
- Alternatives considered: Introducing Redis for distributed rate limiting and PostgreSQL checkpointer (rejected: Phase 7 is infrastructure stabilization; adding distributed backends violates simplicity guardrails and introduces unnecessary architectural complexity).
- Consequences: Rock-solid state consistency and reliable review gates. Horizontal scale-out is deferred to a future phase requiring distributed lock managers.
- Files: `deploy/helm/sangyan/values.yaml`, `docker-compose.yml`, `sangyan/workflow/service.py`

---

### D-053: Fail-Closed Environment Configuration, Secret Injection & Production Boundary Validation
- Date / phase / commit: 2026-10-04, Phase 7
- Context: Production deployments must not bake credentials, signing keys, or database passwords into container images or Git repositories. Insecure development defaults (such as default JWT secrets or wildcard CORS) must be strictly forbidden in production mode.
- Decision: Implemented centralized configuration management and fail-closed startup validation (`sangyan/config.py`):
  1. Environment Layering: Three explicit environments (`development`, `test`, `production`), controlled via `SANGYAN_ENV`.
  2. Configuration Parameters:
     - `SANGYAN_ENV`: Runtime mode (default: `development`).
     - `SANGYAN_DATABASE_URL`: Connection string (`sqlite:////app/data/sangyan.db` or `postgresql://...`).
     - `SANGYAN_CHECKPOINT_DB_PATH`: Filesystem path to SQLite checkpoint database (`/app/checkpoints/workflow_checkpoints.db`).
     - `SANGYAN_JWT_SECRET`: Symmetric signing secret (minimum 32 bytes with high entropy).
     - `SANGYAN_JWT_PUBLIC_KEY` / `SANGYAN_JWT_PRIVATE_KEY`: Asymmetric verification keys.
     - `SANGYAN_REQUIRE_AUTH`: Enforces authentication on all API routes.
     - `SANGYAN_ALLOWED_ORIGINS`: Explicit comma-separated CORS allowed origins.
     - `SANGYAN_BACKUP_ENCRYPTION_KEY`: Symmetric key for database backup encryption.
  3. Fail-Closed Production Validation (`validate_production_config`):
     - When `SANGYAN_ENV == "production"`, startup fails immediately (raising `ConfigurationError`) if:
       - Default test JWT secret is present (`sangyan-insecure-test-secret...`).
       - JWT secret is shorter than 32 characters or lacks entropy.
       - `SANGYAN_REQUIRE_AUTH` is disabled or set to `false`.
       - `SANGYAN_ALLOWED_ORIGINS` contains wildcard `*` with credentials enabled.
       - Database URL is missing or empty.
       - Writable directories are inaccessible.
  4. Secret Injection: Secrets are injected exclusively via environment variables from Kubernetes `Secret` objects or Docker Compose env files, never stored in ConfigMaps or Helm values.
- Why: Eliminates the possibility of accidental deployment with insecure development settings or leaked test credentials.
- Alternatives considered: Allowing development fallbacks in production with log warnings (rejected: insecure-by-default; warnings are routinely ignored in production).
- Consequences: The application will not start unless all production security prerequisites are completely and correctly satisfied.
- Files: `sangyan/config.py`, `sangyan/api/app.py`, `tests/test_config.py`

---

### D-054: Operational Health Semantics (Liveness, Readiness, Startup) & Safe Information Exposure
- Date / phase / commit: 2026-10-04, Phase 7
- Context: Kubernetes and container orchestrators require distinct health probes to manage pod lifecycles. Conflating liveness and readiness causes unnecessary container restarts during transient dependency delays. Furthermore, health endpoints must not leak internal paths, connection strings, or system secrets to attackers.
- Decision: Implemented decoupled operational health endpoints with strict information-disclosure boundaries (`sangyan/api/app.py`):
  1. Liveness Probe (`/health/live`):
     - Answers: "Is the process event loop alive and accepting TCP connections?"
     - Checks process responsiveness and memory sanity. Does not query external or transient dependencies.
     - Returns HTTP 200 with `{"status": "live", "uptime_seconds": float}`.
  2. Readiness Probe (`/health/ready`):
     - Answers: "Can this instance safely process user traffic?"
     - Checks database engine connectivity (`SELECT 1`).
     - Checks database migration state (verifies all schema migrations 001..004 are applied).
     - Checks checkpoint persistence storage accessibility.
     - Returns HTTP 200 with `{"status": "ready", "database": "connected", "migrations": "current"}` when healthy; returns HTTP 503 Service Unavailable when degraded.
  3. System Health Summary (`/health`):
     - Preserved for backward compatibility with Phase 3–6 integration tests, returning service name, version, and registered sources count.
  4. Information-Disclosure Defense:
     - Health responses never expose database credentials, hostnames, filesystem paths, JWT configuration, or stack traces.
     - Failed readiness returns standardized error codes without sensitive diagnostic traces.
- Why: Prevents cascading container restarts while giving orchestrators precise signals for traffic routing and automated self-healing.
- Alternatives considered: Checking external regulatory APIs (SEBI, MCA) in readiness probe (rejected: external third-party network blips would falsely take the SANGYAN API offline).
- Consequences: Reliable container orchestration with zero information leakage.
- Files: `sangyan/api/app.py`, `tests/test_health_probes.py`

---

### D-055: Durable SQLite Checkpointing in Production, WAL Lifecycle & Crash Recovery
- Date / phase / commit: 2026-10-04, Phase 7
- Context: Phase 5 established LangGraph StateGraph orchestration and human-in-the-loop review gates (`review_gate_node`). In development, checkpointers frequently default to in-memory mode. In production, container restarts or worker crashes must not destroy in-flight investigation workflows or lose human review interrupt states.
- Decision: Implemented production checkpoint persistence and lifecycle management:
  1. Persistent Checkpoint Path: `WorkflowCheckpointer` is initialized with a persistent database file located on a mounted volume (`/app/checkpoints/workflow_checkpoints.db`).
  2. SQLite WAL Configuration: The checkpoint database operates with `PRAGMA journal_mode = WAL`, `PRAGMA synchronous = NORMAL`, and `PRAGMA busy_timeout = 10000`.
  3. Composite Tenant Identity: Thread identities strictly follow `<organization_id>:<investigation_id>:<run_id>`, guaranteeing complete multi-tenant checkpoint isolation.
  4. Graceful Shutdown & WAL Checkpoint: On receiving `SIGTERM`, FastAPI lifespan context closes the SQLite connection, triggering an orderly SQLite WAL checkpoint (`PRAGMA wal_checkpoint(TRUNCATE)`), ensuring zero pending journal entries remain in temporary files.
  5. Recovery Verification: On container restart, the checkpointer connects to the existing database file; pending review states (`interrupted`) are immediately reloaded, allowing authorized analysts to resume investigations seamlessly.
- Why: Satisfies the core durability requirement: `container restart != workflow state loss`.
- Alternatives considered: Storing workflow state in the primary relational database (rejected: LangGraph SQLite saver schema is specialized and changing checkpointer architecture in Phase 7 would violate Phase 5 contracts).
- Consequences: Durable workflow recovery verified across crashes, restarts, and interruptions.
- Files: `sangyan/workflow/checkpointer.py`, `sangyan/api/app.py`, `tests/test_workflow.py`

---

### D-056: Controlled Database Migration Lifecycle, Concurrency Locking & Pre-Deployment Execution
- Date / phase / commit: 2026-10-04, Phase 7
- Context: Executing database migrations automatically on application pod startup can cause concurrency race conditions, table lock contention, and schema corruption if multiple pods or jobs execute DDL statements simultaneously.
- Decision: Implemented controlled migration execution and concurrency locking (`sangyan/database/migrations.py`, `sangyan/cli.py`):
  1. Concurrency Locking:
     - SQLite: Writes are protected via `BEGIN IMMEDIATE` transaction semantics, acquiring exclusive database write locks.
     - PostgreSQL: `MigrationRunner` acquires a PostgreSQL session-level advisory lock (`SELECT pg_advisory_lock(837192)`) before inspecting or applying migrations, releasing it in a `finally` block (`SELECT pg_advisory_unlock(837192)`).
  2. Dedicated Migration CLI: `sangyan migrate` command enables operators and deployment pipelines to execute migrations independently of the API server process.
  3. Kubernetes Deployment Architecture: Migrations are decoupled from the application Deployment and executed via a pre-install / pre-upgrade Kubernetes `Job` (Helm hook `pre-install,pre-upgrade`). The API pod only starts after the migration Job completes successfully.
  4. Inspection Commands: `sangyan migrate-status` provides CLI visibility into applied versus pending migrations without modifying database state.
- Why: Eliminates DDL race conditions during rollouts and ensures zero-downtime, orderly schema progression.
- Alternatives considered: Allowing API pods to run `migrate()` during startup in production (rejected: violates production deployment best practices and risks race conditions).
- Consequences: Safe, locked, auditable schema migrations across SQLite and PostgreSQL.
- Files: `sangyan/database/migrations.py`, `sangyan/cli.py`, `deploy/helm/sangyan/templates/job-migration.yaml`

---

### D-057: Automated Cryptographic Database Backup, AES-256-GCM Encryption, SHA-256 Verification & Isolated Restore
- Date / phase / commit: 2026-10-04, Phase 7
- Context: SANGYAN holds critical investor-safety data, evidence provenance records, post-quantum trust receipts, and audit ledgers. Unverified or plaintext backups stored in untrusted locations create disaster recovery and confidentiality risks. A backup is unproven until a complete restore has been verified in an isolated environment.
- Decision: Implemented a comprehensive backup, verification, and restore engine (`sangyan/database/backup.py`, `sangyan/cli.py`):
  1. Consistent Snapshot Creation:
     - SQLite: Utilizes SQLite's online backup API or `VACUUM INTO` to create transactionally consistent point-in-time snapshots of relational and checkpoint databases even under active concurrent writes.
     - PostgreSQL: Leverages streaming SQL dumps or table exports.
  2. Multi-Artifact Packaging: Bundles primary relational database, workflow checkpoints database, and cryptographic key metadata into a versioned tarball (`sangyan_backup_<timestamp>.tar.gz`).
  3. Cryptographic Integrity: Computes SHA-256 digest of the backup archive, storing it alongside the archive as `<backup>.sha256`.
  4. Strong Encryption: Optional symmetric encryption using AES-256-GCM (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`) with a 12-byte random nonce and authenticated tag, keyed from `SANGYAN_BACKUP_ENCRYPTION_KEY`.
  5. Automated Pruning & Retention: `prune_backups()` retains the last $N$ backups (default: 7 daily backups) and cleans up orphaned checksum and metadata files.
  6. Verified Restore Procedure: `restore_backup()` validates archive checksum, decrypts ciphertext, unpacks into an isolated target directory, and runs `PRAGMA integrity_check` and schema verification.
  7. Disaster Recovery Metrics: Initial operational targets established: RPO <= 24 hours (with daily scheduled backup) or RPO <= 1 hour (with hourly cron); RTO <= 5 minutes (measured restore execution < 1 second locally).
- Why: Guarantees complete data recoverability without data leakage or undetected backup corruption.
- Alternatives considered: Simple file copy of SQLite databases (rejected: copying active SQLite databases with WAL files corrupts the copy if a write occurs mid-copy).
- Consequences: Verifiable, encrypted disaster recovery runbook and automated scheduled backup routines.
- Files: `sangyan/database/backup.py`, `sangyan/cli.py`, `tests/test_backup.py`

---

### D-058: Hardened Kubernetes / Helm Manifest Architecture, Pod Security Standards & Ingress Boundary
- Date / phase / commit: 2026-10-04, Phase 7
- Context: Deploying SANGYAN onto Kubernetes clusters requires production-grade Helm templates adhering to Kubernetes Pod Security Standards (Restricted profile), strict resource bounding, and controlled ingress exposure.
- Decision: Implemented standardized Helm chart (`deploy/helm/sangyan`):
  1. Pod Security Standards (Restricted Profile):
     - `runAsNonRoot: true`, `runAsUser: 10001`, `runAsGroup: 10001`, `fsGroup: 10001`.
     - `allowPrivilegeEscalation: false`.
     - `readOnlyRootFilesystem: true`.
     - `capabilities.drop: ["ALL"]`.
     - `seccompProfile.type: "RuntimeDefault"`.
  2. Resource Allocation Defaults:
     - Requests: `cpu: "250m"`, `memory: "512Mi"`.
     - Limits: `cpu: "1000m"`, `memory: "1Gi"`.
  3. Persistent Storage (PVC): Dedicated PersistentVolumeClaims for relational data (`/app/data`), LangGraph checkpoints (`/app/checkpoints`), and cryptographic keys (`/app/keys`).
  4. Ingress Boundary & Metrics Isolation:
     - Ingress routes `/` and `/api` to the Service on port 8000 with TLS termination.
     - Route `/metrics` is explicitly excluded from the public Ingress and restricted to cluster-internal scraping via Prometheus `ServiceMonitor` or NetworkPolicy.
  5. NetworkPolicy: Enforces default-deny ingress with explicit allows for ingress controller traffic on port 8000 and cluster-internal Prometheus scrapers.
  6. Operational Decoupling: Migration Job (`job-migration.yaml`) and scheduled Backup CronJob (`cronjob-backup.yaml`) are packaged with appropriate RBAC and Volume mounts.
- Why: Implements defense-in-depth at the container, pod, network, and orchestrator boundaries.
- Alternatives considered: Permitting default root permissions and permissive ingress (rejected: violates zero-trust principles).
- Consequences: Safe, standard-compliant Kubernetes deployment templates validated statically via Helm lint and schema checks.
- Files: `deploy/helm/sangyan/`









