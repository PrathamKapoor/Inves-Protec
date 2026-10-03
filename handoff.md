# SANGYAN — Project Handoff

## 1. Current Phase
Phase 3 — Authoritative Verification, Evidence Retrieval, Findings, Conflict Resolution, and Trust Binding (COMPLETED)

## 2. Work Completed
- Completed Phase 0 reconnaissance of SAT-SA-with-PQC and Sentiment Analysis codebases.
- Completed Phase 1 Foundation Setup & Domain Migration (PQC crypto, database engine, migrations, domain models, multi-tenancy, SSRF protection, trust receipts, 37 tests).
- Completed Phase 2 Ingestion, Text Cleaning, Multilingual Classification, Atomic Claims, Entity Resolution, Observable Safety Signals, and Content Intelligence Pipeline (64 tests).
- Completed Phase 3 Authoritative Verification, Evidence Retrieval, Findings, Conflict Resolution, and Trust Binding:
  - Established Controlled Authoritative Source Registry (`AuthoritativeSourceRegistry`) with Indian financial market seed sources (SEBI Intermediaries, Circulars, MCA, NSE, BSE, Official Domains, RBI Regulated Entities) across explicit trust tiers (T0 Regulator to T5 User-generated).
  - Implemented versioned, reproducible `RegistrySnapshot` with SHA3-256 integrity verification and `SnapshotManager` bundled with seed snapshots for SEBI intermediaries, MCA companies, regulatory circulars, and official domains.
  - Implemented thread-safe in-memory `VerificationCache` (SHA3-256 TTL cache) and sliding-window `RateLimiter` with exponential backoff.
  - Implemented modular `VerificationAdapter` architecture with 4 concrete adapters:
    - `SEBIVerificationAdapter`: Verifies intermediary registration numbers (INZ, INA, INH, INM, INP, IN-DP, MF) and intermediary names against active, expired, cancelled, suspended, and bogus statuses. Enforces adversarial brand-spoofing overrides (bogus registration numbers strictly override name-match similarity).
    - `MCAVerificationAdapter`: Verifies 21-character Corporate Identification Numbers (CINs) and company names (ACTIVE, STRUCK_OFF, DISSOLVED, UNREGISTERED).
    - `CircularsVerificationAdapter`: Matches claims and signals against official regulatory circulars (e.g. SEBI prohibition of guaranteed returns under SEBI/HO/MIRSD, prohibition of OTP/credential solicitation under SEBI/HO/ISD, fraudulent fee demands, and statutory disclaimers).
    - `OfficialDomainsVerificationAdapter`: Authenticates official financial infrastructure domains, flags high-risk suspicious TLDs, and detects known phishing/lookalike domains.
  - Standardized on 5 epistemic verification stances (`SUPPORTED`, `CONTRADICTED`, `CONFLICTING`, `OUTDATED`, `INSUFFICIENT_EVIDENCE`).
  - Implemented deterministic conflict resolution handling opposing authoritative records, persisting dual evidence, and emitting `CONFLICTING` stances.
  - Implemented `TrustBindingService` cryptographically binding findings, claims, and evidence hashes into canonical verification payloads signed with pure-Python ML-DSA-65 post-quantum digital signatures (`TrustReceipt`).
  - Implemented `ClaimVerificationEngine` orchestrating adapters, conflict resolution, stance resolution, and tenant persistence.
  - Expanded test suite with 18 comprehensive verification tests (`tests/test_verification.py`), covering registry lookups, snapshot integrity, caching, rate limiting, all adapters, conflict resolution, ML-DSA-65 tamper detection, cross-tenant isolation, and adversarial evasion. Total test suite: 82 passed in 5.85s.

## 3. Files Changed / Created
- `sangyan/verification/__init__.py`
- `sangyan/verification/sources.py`
- `sangyan/verification/snapshots.py`
- `sangyan/verification/cache.py`
- `sangyan/verification/adapters/__init__.py`
- `sangyan/verification/adapters/base.py`
- `sangyan/verification/adapters/sebi.py`
- `sangyan/verification/adapters/mca.py`
- `sangyan/verification/adapters/circulars.py`
- `sangyan/verification/adapters/official_domains.py`
- `sangyan/verification/trust_binding.py`
- `sangyan/verification/engine.py`
- `tests/test_verification.py`
- `decisions.md` (Architectural decisions D-014 through D-021)
- `flow.md` (Added Section 7 and updated Session Changelog)
- `handoff.md` (Updated project status and Phase 3 completion)
- `MODEL_CHANGES.md` (Domain model relationships, schema contracts, and VerificationOutcome specifications)

## 4. Current Architecture / State
The repository has a working, tested, standalone foundation, complete Content Intelligence Pipeline, and complete Authoritative Verification Engine:
- Package: `sangyan` (installed in editable mode in Python 3.13 venv)
- Database: Migration 001 creates 16 core relational tables for tenancy, content items, claims, entities, sources, evidence, signals, findings, guidance, investigations, reviews, and trust receipts. SQLite WAL mode enabled.
- Cryptography: Pure-Python ML-DSA-65 (`dilithium-py`) + SHA3-256 canonical JSON.
- Security: Socket-level SSRF validation with private/loopback/link-local IP blocking.
- Tenancy: `TenantRepository` enforcing organization boundaries and RBAC permissions with full CRUD coverage.
- Ingestion (`sangyan.ingest`): Text cleaning (zero-width character stripping, HTML extraction, Unicode NFKC, whitespace normalization), link extraction, and SSRF-safe bounded HTTP retrieval (`UrlFetcher`).
- Content Intelligence (`sangyan.intelligence`):
  - Multilingual identification (`LanguageDetector`) across English, Hindi, Hinglish, Marathi, Gujarati, Bengali, Tamil, Telugu, and Kannada with Indic combining-mark preserving tokenization.
  - Atomic claim decomposition (`ClaimExtractor`) splitting compound clauses into regulatory, return, urgency, payment, affiliation, or other claims with UNVERIFIED default status and context pointers.
  - Financial entity resolution (`EntityResolver`) extracting SEBI registration numbers, Corporate CINs, Indian UPI VPAs, Telegram/WhatsApp solicitations, statutory regulators, market infrastructure, and recognized brokers.
  - Observable safety signals (`SignalDetector`) identifying 20+ signals with robust contextual negation and regulatory warning/disclaimer suppression.
  - Pipeline orchestration (`ContentIntelligenceEngine`) computing weighted risk scores, generating summaries, and persisting analysis outputs to `TenantRepository`.
- Authoritative Verification (`sangyan.verification`):
  - Source Registry (`AuthoritativeSourceRegistry`): Controlled institutional registries with trust tiers T0-T5.
  - Versioned Snapshots (`SnapshotManager`): SHA3-256 integrity-verified data snapshots ensuring reproducible investigations.
  - Caching & Rate Limiting (`VerificationCache`, `RateLimiter`): TTL caching and sliding-window rate limiting.
  - Verification Adapters (`sangyan.verification.adapters`): SEBI, MCA, Circulars, and Official Domains adapters producing structured `AdapterResult` records.
  - Conflict Resolution: Deterministic resolution of opposing authoritative outcomes into `CONFLICTING` stances with dual evidence persistence.
  - Post-Quantum Trust Binding (`TrustBindingService`): ML-DSA-65 signing of canonical verification payloads into verifiable `TrustReceipt` objects.
  - Claim Verification Engine (`ClaimVerificationEngine`): Orchestrates verification of claims against resolved entities and signals, persists `Evidence` and `Finding` records within tenant boundaries.

## 5. Decisions Made
- D-001: Standalone SANGYAN Repository Initialization & Packaging Architecture
- D-002: Cryptographic Infrastructure Preservation (Pure Python ML-DSA-65 & SHA3-256)
- D-003: Storage & Migration Architecture (Dual-Dialect DatabaseEngine SQLite/PostgreSQL)
- D-004: Tenant Isolation & Multi-Tenancy Architecture
- D-005: SANGYAN Investor-Safety Domain Model Definition
- D-006: Schema Migrations & Storage Primitives for Phase 1
- D-007: SSRF Protection & Network Boundary Foundation
- D-008: Standard Library Socket-Level SSRF Interception without Mandatory External Dependencies
- D-009: Repository CRUD Expansion, ConfidenceVector Idempotency & SQLite WAL Concurrency
- D-010: Multilingual Text Normalization & Adversarial Evasion Architecture
- D-011: Bounded SSRF-Safe HTTP Ingestion Service
- D-012: Deterministic Financial Entity Resolution & Atomic Claim Decomposition
- D-013: Contextual Negation & Hard-Negative Disclaimer Suppression in Signal Detection
- D-014: Authoritative Source Registry Architecture
- D-015: Controlled Multi-Source Verification Adapters
- D-016: Versioned Registry Snapshots with SHA3-256 Integrity
- D-017: Epistemic Stances & Temporal Verification (Active vs Outdated)
- D-018: Multi-Source Conflict Resolution & Transparency
- D-019: Traceable Evidence & Finding Provenance
- D-020: ML-DSA-65 Post-Quantum Trust Binding for Verification Findings
- D-021: Verification Caching & Upstream Rate Limiting
- D-022: Multi-Domain Threat Precedence, Disclaimer Evasion Defense, and Engine Fault Resilience

## 6. Requirements and Constraints
- Git authorship: strictly `PrathamKapoor <prathamkapoor027@gmail.com>`. No AI/model attribution.
- Preservation of PQC cryptography (`dilithium-py` ML-DSA-65, SHA3-256, canonical JSON).
- Strict non-investment advice guardrails: no price predictions, no buy/sell calls, no broker endorsements.
- Authoritative evidence hierarchy (T0 Regulator to T5 User-generated).
- Explicit multi-valued claim statuses (SUPPORTED, CONTRADICTED, PARTIALLY_SUPPORTED, UNVERIFIED, CONFLICTING, OUTDATED, INSUFFICIENT_EVIDENCE).
- Do not commit paper/, research/, *.tex.

## 7. Testing and Verification
- Full test suite: **90 passed in 9.62s**, 0 failures, exit code 0 (`C:\Projects\SIH26\TRUST-SAT\.venv313repro\Scripts\python.exe -m pytest tests -v`).
- `tests/test_crypto.py`: 3 passed (canonical JSON key sorting, SHA3-256 digest, ML-DSA-65 keygen/sign/verify/tamper detection).
- `tests/test_database.py`: 4 passed (connect, query, duplicate entry, transaction rollback, migration runner idempotency).
- `tests/test_domain.py`: 22 passed (all 10 domain models, enums, confidence vectors, validation error reporting).
- `tests/test_ingest.py`: 7 passed (zero-width character stripping, HTML extraction, NFKC normalization, URL extraction, SSRF blocking, mocked HTTP fetch, IngestionService workflow).
- `tests/test_intelligence.py`: 19 passed (English, Hindi, Marathi, Hinglish, Gujarati, Bengali, Tamil, empty text, claim decomposition, SEBI reg nos, CIN, UPI VPAs, channels/regulators, predatory signals, hard negatives on regulatory warnings, OTP advice, disclaimers, personal savings warnings, adversarial evasion countermeasures, large content throughput, and end-to-end pipeline persistence).
- `tests/test_persistence.py`: 4 passed (tenant isolation, permission enforcement, investigation & review lifecycle, full repository CRUD).
- `tests/test_security.py`: 3 passed (unsafe IP detection, URL shape validation, loopback blocking).
- `tests/test_trust.py`: 2 passed (keypair persistence, document signing and post-quantum verification).
- `tests/test_verification.py`: 26 passed (registry lookups, snapshot integrity, snapshot tampering detection, verification caching, rate limiting, SEBI active/expired/cancelled/bogus lookups, MCA active/struck-off/bogus CIN lookups, regulatory circular prohibited returns and OTP demands, official domain authentication, phishing lookalike detection, suspicious TLD detection, multi-source conflict resolution, end-to-end ClaimVerificationEngine orchestration, ML-DSA-65 trust binding & tamper detection, cross-tenant isolation, adversarial brand spoofing override, phishing prepended with official domain override, guaranteed return disclaimer evasion defense, adapter exception containment, explicit rate limit recording, www and dot domain normalization, hyphenated/spaced registration numbers, precise entity matching without bleed, multithreaded caching and rate limiter concurrency).


## 8. Known Issues / Risks
- None identified in Phase 1, Phase 2, or Phase 3.

## 9. Unfinished Work
- Phase 4: Investigation Correlation, Scam-Chain Reconstruction & Safe Guidance.
- Phase 5: LangGraph Workflow & Cryptographic Trust Pipeline.
- Phase 6: REST API & Security.
- Phase 7: Next.js Frontend.

## 10. Next Subphase
Phase 4: Investigation Correlation, Scam-Chain Reconstruction & Safe Guidance (Entity-claim graph correlation, scam taxonomy mapping, grievance guidance routing to SCORES / Chakshu / Cybercrime, safe next-step generators).

## 11. Critical Context
- Target environment uses Python 3.13 venv at `C:\Projects\SIH26\TRUST-SAT\.venv313repro`.
- All Git operations must maintain `PrathamKapoor <prathamkapoor027@gmail.com>`.
- Preserved zero AI attribution across all files and git logs.

## 12. Agent Instructions
- Ensure tests pass with real output before committing.
- Keep `decisions.md` and `flow.md` updated in the same step as code changes.
