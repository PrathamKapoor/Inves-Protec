# SANGYAN — Project Handoff

## 1. Current Phase
Phase 1 — Foundation Setup, Repository Migration & Investor-Safety Domain Model

## 2. Work Completed
- Completed Phase 0 reconnaissance of SAT-SA-with-PQC and Sentiment Analysis reference codebases.
- Initialized standalone Git repository in `C:\Projects\Sangyan` under author `PrathamKapoor <prathamkapoor027@gmail.com>`.
- Established project documentation system (`decisions.md` with D-001..D-007, `flow.md`, `handoff.md`).

## 3. Files Changed
- `decisions.md` (initial architecture and domain decisions D-001..D-007)
- `flow.md` (runtime flows and session change log)
- `handoff.md` (handoff document)

## 4. Current Architecture / State
Clean standalone repository prepared for porting verified cryptographic (ML-DSA-65, SHA3-256), storage (`DatabaseEngine`), tenancy, and SSRF security primitives, and implementing the new 10-object investor-safety domain model.

## 5. Decisions Made
- D-001: Standalone SANGYAN Repository Initialization & Packaging Architecture
- D-002: Cryptographic Infrastructure Preservation (Pure Python ML-DSA-65 & SHA3-256)
- D-003: Storage & Migration Architecture (Dual-Dialect DatabaseEngine SQLite/PostgreSQL)
- D-004: Tenant Isolation & Multi-Tenancy Architecture
- D-005: SANGYAN Investor-Safety Domain Model Definition
- D-006: Schema Migrations & Storage Primitives for Phase 1
- D-007: SSRF Protection & Network Boundary Foundation

## 6. Requirements and Constraints
- Git authorship: strictly `PrathamKapoor <prathamkapoor027@gmail.com>`. No AI/model attribution.
- Preservation of PQC cryptography (`dilithium-py` ML-DSA-65, SHA3-256, canonical JSON).
- Strict non-investment advice guardrails: no price predictions, no buy/sell calls, no broker endorsements.
- Authoritative evidence hierarchy (T0 Regulator to T5 User-generated).
- Explicit multi-valued claim statuses (SUPPORTED, CONTRADICTED, PARTIALLY_SUPPORTED, UNVERIFIED, CONFLICTING, OUTDATED, INSUFFICIENT_EVIDENCE).

## 7. Testing and Verification
- Environment inspection: Python 3.13.14, Node.js v24.19.0, npm 12.0.2 verified.
- Git config: `user.name` = PrathamKapoor, `user.email` = prathamkapoor027@gmail.com verified.
- Unit tests for domain, crypto, database, and security will run via `pytest` in the Python 3.13 venv.

## 8. Known Issues / Risks
- None currently identified in Phase 1 setup.

## 9. Unfinished Work
- Implement `sangyan/` package modules (crypto, database, domain, tenancy, security, trust).
- Implement database migration 001.
- Implement comprehensive test suite and verify test execution.

## 10. Next Subphase
Subphase 1.1: Core package files, packaging manifests, crypto, and database engine porting.

## 11. Critical Context
- Use Python environment at `C:\Projects\SIH26\TRUST-SAT\.venv313repro\Scripts\python.exe`.
- Do not commit paper/, research/, *.tex.
- Every architectural choice requires an entry in `decisions.md`.

## 12. Agent Instructions
- Ensure tests pass with real output before committing.
- Keep documentation in sync in the same step as code changes.
