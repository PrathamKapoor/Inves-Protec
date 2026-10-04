# SANGYAN — Project Handoff

## 1. Current Phase
Phase 4 — Investigation Correlation, Scam-Chain Reconstruction & Safe Guidance (COMPLETED)

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

## 3. Files Changed / Created
- `sangyan/database/migrations.py` (Migration 002 statements and registration)
- `sangyan/domain/models.py`, `sangyan/domain/__init__.py` (Phase 4 domain models, enums, validation)
- `sangyan/tenancy/repository.py` (correlations, scam chain stages, grievance records CRUD)
- `sangyan/intelligence/signals.py` (refined guaranteed returns and withdrawal fee regexes)
- `sangyan/verification/trust_binding.py` (investigation PQC signing and verification)
- `sangyan/correlation/__init__.py`
- `sangyan/correlation/correlator.py` (InvestigationCorrelator)
- `sangyan/correlation/scam_chains.py` (ScamChainReconstructor)
- `sangyan/correlation/taxonomy.py` (ScamTaxonomyClassifier)
- `sangyan/correlation/guidance.py` (GuidanceEngine)
- `sangyan/correlation/grievance.py` (GrievanceRouter)
- `sangyan/correlation/explainer.py` (InvestigationExplainer)
- `sangyan/correlation/orchestrator.py` (InvestigationOrchestrator)
- `sangyan/api/app.py`, `sangyan/api/routes.py` (investigation endpoints)
- `tests/test_database.py` (Migration 002 verification)
- `tests/test_correlation.py` (20 comprehensive Phase 4 tests)
- `tests/test_api.py` (investigation REST endpoint tests)
- `decisions.md` (Architectural decisions D-030 through D-036)
- `flow.md` (Added Section 8 investigation flow and Session Changelog)
- `MODEL_CHANGES.md` (Documented Phase 4 domain contracts and migration tables)
- `handoff.md` (Updated project status and Phase 4 full completion)

## 4. Current Architecture / State
- Package: `sangyan` (installed in editable mode in Python 3.13 venv)
- Database: Migrations 001 and 002 create 19 core relational tables. SQLite WAL mode enabled.
- Cryptography: Pure-Python ML-DSA-65 (`dilithium-py`) + SHA3-256 canonical JSON.
- Security: Socket-level SSRF validation with private/loopback/link-local IP blocking.
- Tenancy: `TenantRepository` enforcing organization boundaries and RBAC permissions across all tables.
- Ingestion (`sangyan.ingest`): Text cleaning, URL extraction, bounded streaming fetcher.
- Content Intelligence (`sangyan.intelligence`): Multilingual identification, atomic claims, entity resolver, observable safety signals.
- Authoritative Verification (`sangyan.verification`): Source registry, snapshots, adapters (SEBI, MCA, Circulars, Domains, Market Infrastructure, Payment), conflict resolution, post-quantum trust receipts.
- Correlation & Guidance (`sangyan.correlation`): Graph correlator, 12-stage scam chains, 14-pattern taxonomy, safe guidance, grievance router, explainer with uncertainty abstentions, investigation orchestrator, and PQC investigation trust receipts.
- API (`sangyan.api`): FastAPI REST API and server-rendered HTML inspection views with Section 40 banners.

## 5. Decisions Made
- D-001 through D-029: Phase 1 to Phase 3 decisions.
- D-030: Graph Correlation Model & Strength Hierarchy (STRONG/MEDIUM/WEAK)
- D-031: 12-Stage Scam-Chain Reconstruction & Inferred Stage Semantics
- D-032: Multi-Label Controlled Scam Taxonomy Classification
- D-033: Non-Investment Conditional Safe Guidance & Incident Preservation Checklist
- D-034: Grievance Problem Classification & Official Institutional Routing
- D-035: Epistemic Explainability & Mandatory Uncertainty Abstention
- D-036: Investigation-Level ML-DSA-65 Post-Quantum Trust Binding

## 6. Requirements and Constraints
- Git authorship: strictly `PrathamKapoor <prathamkapoor027@gmail.com>`. Zero AI attribution.
- Preservation of PQC cryptography (`dilithium-py` ML-DSA-65, SHA3-256, canonical JSON).
- Strict non-investment advice guardrails: no price predictions, no buy/sell calls, no broker endorsements.
- Epistemic integrity: Never collapse determinations into binary percentages or single confidence scalars. Always state what remains unknown.
- Bounded graph complexity: max 5 hops, max 200 edges, max 25 related content items.

## 7. Testing and Verification
- Full test suite: **131 passed in 11.28s**, 0 failures, exit code 0 (`python -m pytest tests -v`).
- `tests/test_correlation.py`: 20 passed (Scenarios 1-5, graph limits, cycle avoidance, prompt injection as data defense, PQC signature verification, cross-tenant isolation, hard-negative suppression on regulatory warnings).
- `tests/test_api.py`: 8 passed (REST endpoints, batch investigation endpoint, HTML inspection views).
- `tests/test_verification_extended.py`: 10 passed (market infrastructure, payment VPAs, audit ledger).
- `tests/test_verification.py`: 28 passed.
- `tests/test_intelligence.py`: 19 passed.
- `tests/test_domain.py`: 22 passed.
- `tests/test_ingest.py`: 7 passed.
- `tests/test_database.py`: 4 passed.
- `tests/test_crypto.py`: 3 passed.
- `tests/test_security.py`: 3 passed.
- `tests/test_trust.py`: 2 passed.
- `tests/test_persistence.py`: 4 passed.

## 8. Known Issues / Risks
- None identified in Phase 1, Phase 2, Phase 3, or Phase 4.

## 9. Unfinished Work
- Phase 5: LangGraph Workflow & Cryptographic Trust Pipeline.
- Phase 6: REST API & Security.
- Phase 7: Next.js Frontend.

## 10. Next Subphase
Phase 5: LangGraph Workflow & Cryptographic Trust Pipeline (StateGraph definition, conditional edges, supervisor-worker routing, checkpointing, multi-turn human-in-the-loop review).

## 11. Critical Context
- Target environment uses Python 3.13 venv at `C:\Projects\SIH26\TRUST-SAT\.venv313repro`.
- All Git operations must maintain `PrathamKapoor <prathamkapoor027@gmail.com>`.
- Preserved zero AI attribution across all files and git logs.

## 12. Agent Instructions
- Ensure tests pass with real output before committing.
- Keep `decisions.md` and `flow.md` updated in the same step as code changes.
