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





