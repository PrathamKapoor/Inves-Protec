# SANGYAN — Project Handoff

## 1. Current Phase
Phase 1 — Foundation Setup, Repository Migration & Investor-Safety Domain Model (COMPLETED)

## 2. Work Completed
- Successfully completed Phase 0 reconnaissance of SAT-SA-with-PQC and Sentiment Analysis codebases.
- Initialized standalone SANGYAN Git repository in `C:\Projects\Sangyan` under author `PrathamKapoor <prathamkapoor027@gmail.com>`.
- Established project documentation system (`decisions.md` with D-001..D-008, `flow.md`, `handoff.md`, `README.md`).
- Ported and verified post-quantum cryptographic primitives (`dilithium-py` ML-DSA-65, SHA3-256 canonical hashing, keypair generation, and verification) in `sangyan.crypto`.
- Implemented statement-level `DatabaseEngine` (`SQLiteDatabaseEngine`, `PostgresDatabaseEngine`) with transactional locking (`RLock`), dict row factories, and linear migration runner in `sangyan.database`.
- Created Migration 001 (`create_sangyan_core_tables`) covering all 16 relational tables and indexes across SQLite and PostgreSQL.
- Implemented complete 10-object investor-safety domain model in `sangyan.domain` (`ContentItem`, `Claim`, `Entity`, `Source`, `Evidence`, `Signal`, `Finding`, `ActionGuidance`, `Investigation`, `Review`) with explicit validation, enums, confidence vectors, and serialization.
- Implemented multi-tenancy models, roles (`sangyan_admin`, `sangyan_analyst`, `sangyan_viewer`), and `TenantRepository` enforcing tenant isolation and permission checks in `sangyan.tenancy`.
- Ported and hardened DNS-rebinding-safe SSRF URL validation in `sangyan.security.ssrf` with universal standard-library socket-level connect interception.
- Implemented `TrustService` and `TrustReceipt` in `sangyan.trust` binding investigation digests to post-quantum ML-DSA-65 signatures.
- Created and executed comprehensive 37-test suite (`tests/test_*.py`) passing cleanly in 2.44 seconds.

## 3. Files Changed
- `.gitignore` (Python, Node, databases, and paper/tex guardrails)
- `README.md` (Product concept, guardrails, architecture, getting started)
- `pyproject.toml` (Build configuration, dependencies, script entrypoint)
- `decisions.md` (Architectural decisions D-001 through D-008)
- `flow.md` (Execution diagrams and session change log)
- `handoff.md` (Current state and phase handoff)
- `sangyan/__init__.py`
- `sangyan/core/__init__.py`, `errors.py`, `logging.py`
- `sangyan/crypto/__init__.py`, `hashing.py`, `providers.py`
- `sangyan/database/__init__.py`, `engine.py`, `migrations.py`, `postgres.py`
- `sangyan/domain/__init__.py`, `base.py`, `models.py`
- `sangyan/security/__init__.py`, `ssrf.py`
- `sangyan/tenancy/__init__.py`, `models.py`, `repository.py`
- `sangyan/trust/__init__.py`, `receipt.py`, `service.py`
- `tests/test_crypto.py`
- `tests/test_database.py`
- `tests/test_domain.py`
- `tests/test_persistence.py`
- `tests/test_security.py`
- `tests/test_trust.py`

## 4. Current Architecture / State
The repository has a working, tested, standalone foundation:
- Package: `sangyan` (installed in editable mode in Python 3.13 venv)
- Database: Migration 001 creates 16 core relational tables for tenancy, content items, claims, entities, sources, evidence, signals, findings, guidance, investigations, reviews, and trust receipts.
- Cryptography: Pure-Python ML-DSA-65 (`dilithium-py`) + SHA3-256 canonical JSON.
- Security: Socket-level SSRF validation with private/loopback/link-local IP blocking.
- Tenancy: `TenantRepository` enforcing organization boundaries and RBAC permissions.

## 5. Decisions Made
- D-001: Standalone SANGYAN Repository Initialization & Packaging Architecture
- D-002: Cryptographic Infrastructure Preservation (Pure Python ML-DSA-65 & SHA3-256)
- D-003: Storage & Migration Architecture (Dual-Dialect DatabaseEngine SQLite/PostgreSQL)
- D-004: Tenant Isolation & Multi-Tenancy Architecture
- D-005: SANGYAN Investor-Safety Domain Model Definition
- D-006: Schema Migrations & Storage Primitives for Phase 1
- D-007: SSRF Protection & Network Boundary Foundation
- D-008: Standard Library Socket-Level SSRF Interception without Mandatory External Dependencies

## 6. Requirements and Constraints
- Git authorship: strictly `PrathamKapoor <prathamkapoor027@gmail.com>`. No AI/model attribution.
- Preservation of PQC cryptography (`dilithium-py` ML-DSA-65, SHA3-256, canonical JSON).
- Strict non-investment advice guardrails: no price predictions, no buy/sell calls, no broker endorsements.
- Authoritative evidence hierarchy (T0 Regulator to T5 User-generated).
- Explicit multi-valued claim statuses (SUPPORTED, CONTRADICTED, PARTIALLY_SUPPORTED, UNVERIFIED, CONFLICTING, OUTDATED, INSUFFICIENT_EVIDENCE).
- Do not commit paper/, research/, *.tex.

## 7. Testing and Verification
- Full test suite: **37 passed in 2.44s**, 0 failures, exit code 0 (`C:\Projects\SIH26\TRUST-SAT\.venv313repro\Scripts\python.exe -m pytest tests -v`).
- `tests/test_crypto.py`: 3 passed (canonical JSON key sorting, SHA3-256 digest, ML-DSA-65 keygen/sign/verify/tamper detection).
- `tests/test_database.py`: 4 passed (connect, query, duplicate entry, transaction rollback, migration runner idempotency).
- `tests/test_domain.py`: 22 passed (all 10 domain models, enums, confidence vectors, validation error reporting).
- `tests/test_persistence.py`: 3 passed (tenant isolation, permission enforcement, investigation & review lifecycle).
- `tests/test_security.py`: 3 passed (unsafe IP detection, URL shape validation, loopback blocking).
- `tests/test_trust.py`: 2 passed (keypair persistence, document signing and post-quantum verification).
- Editable installation: `pip install -e . --no-deps` completed successfully.

## 8. Known Issues / Risks
- None currently identified in Phase 1 foundation.

## 9. Unfinished Work
- Phase 2: Ingestion & Content Intelligence Engine (multilingual language detection, claim decomposition, entity extraction, signal & persuasion extraction).
- Phase 3: Authoritative Verification Adapters (SEBI registry queries, official circulars, URL reputation).
- Phase 4: Investigation Correlation, Scam-Chain Reconstruction & Safe Guidance.
- Phase 5: LangGraph Workflow & Cryptographic Trust Pipeline.
- Phase 6: REST API & Security.
- Phase 7: Next.js Frontend.

## 10. Next Subphase
Phase 2: Ingestion & Content Intelligence Engine (Text/URL ingestion, Language identification, Claim decomposition, Financial entity normalization, Observable signal detection).

## 11. Critical Context
- Target environment uses Python 3.13 venv at `C:\Projects\SIH26\TRUST-SAT\.venv313repro`.
- All Git operations must maintain `PrathamKapoor <prathamkapoor027@gmail.com>`.

## 12. Agent Instructions
- Ensure tests pass with real output before committing.
- Keep `decisions.md` and `flow.md` updated in the same step as code changes.
