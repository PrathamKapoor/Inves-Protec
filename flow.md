# SANGYAN — Architecture & Execution Flow

This document details the actual runtime execution and data flows across SANGYAN subsystems. Function names, classes, files, and schemas documented here reflect real repository code.

---

## 1. Domain Model Instantiation & Validation Flow

```text
User / Parser / Integration
 └─ DomainRecord.from_dict(data)             sangyan/domain/models.py
     ├─ Construct dataclass instance          fields populated with typed inputs
     └─ record.validate()                     sangyan/domain/models.py
         ├─ require(field, msg, errors)       sangyan/domain/base.py
         └─ returns list[str] of problems     empty list = valid
```
- **Rationale**: Validation never raises internally; it returns explicit validation error strings so callers can log, reject, or request human attention without fragile try/catch blocks.

---

## 2. Persistence & Migration Flow

```text
Application Startup / CLI Migrate
 └─ MigrationRunner(engine).migrate()        sangyan/database/migrations.py
     ├─ engine.connect()                     sangyan/database/engine.py
     ├─ _ensure_table()                      verifies 'schema_migrations' exists
     ├─ applied_versions()                   queries applied versions
     └─ for migration in pending:
         └─ with engine.transaction():        transactional commit or rollback
             ├─ engine.execute(statement)    executes DDL statements
             └─ records version in ledger    INSERT INTO schema_migrations
```
- **Rationale**: Ordered idempotent migrations ensure any fresh or existing database (SQLite or PostgreSQL) deterministically reaches the target schema.

---

## 3. Cryptographic Provenance & Receipt Flow

```text
Investigation Finalization / Review
 └─ TrustService.sign_investigation()        sangyan/trust/service.py
     ├─ canonical_json(investigation_dict)   sangyan/crypto/hashing.py
     ├─ sha3_hex(canonical_bytes)            SHA3-256 digest
     ├─ SignatureProvider.sign(sk, digest)   ML-DSA-65 post-quantum signing
     └─ TrustReceipt(...)                    persisted in sangyan_trust_receipts
```
- **Rationale**: Eliminates tampering risk by binding the complete investigation graph (claims, signals, evidence, review) to an ML-DSA-65 post-quantum digital signature.

---

## 4. SSRF Validation Flow

```text
URL Ingestion / Fetch
 └─ validate_url_ssrf(url)                   sangyan/security/ssrf.py
     ├─ validate_url_shape(url)              format, scheme (http/https), host check
     ├─ socket.getaddrinfo(host, None)       resolves DNS
     └─ for each sockaddr:
         └─ _is_unsafe_ip(ip)                rejects private/loopback/link-local/multicast
 └─ with ssrf_safe_connections():            hooks socket.create_connection
     └─ requests.get(url)                    guarantees no DNS-rebinding bypass
```
- **Rationale**: Prevents internal network scanning or cloud credential exposure when users submit URLs to suspicious financial sites.

---

## Changes in this session (Phase 1 — Foundation Setup & Domain Migration)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Packaging & Repository | Initialize standalone repository and pyproject.toml | `pyproject.toml`, `.gitignore` | 4dbd278 | D-001 |
| Cryptography | Port PQC ML-DSA-65 and SHA3-256 canonical hashing | `sangyan/crypto/hashing.py`, `sangyan/crypto/providers.py` | 4dbd278 | D-002 |
| Database Engine | Port dual SQLite/PostgreSQL DatabaseEngine and transaction manager | `sangyan/database/engine.py` | 4dbd278 | D-003 |
| Tenancy | Implement tenant/organization models and repository scoping | `sangyan/tenancy/models.py`, `sangyan/tenancy/repository.py` | 4dbd278 | D-004 |
| Domain Models | Define 10 investor-safety domain dataclasses with validation | `sangyan/domain/base.py`, `sangyan/domain/models.py` | 4dbd278 | D-005 |
| Migrations | Implement Migration 001 core tables and runner | `sangyan/database/migrations.py` | 4dbd278 | D-006 |
| Security | Implement DNS-rebinding-safe SSRF URL validator | `sangyan/security/ssrf.py` | 4dbd278 | D-007 |
| Security Hook | Universal socket-level connect hook without urllib3 dependency | `sangyan/security/ssrf.py` | 4dbd278 | D-008 |
| Trust Service | Implement TrustReceipt and ML-DSA-65 signing/verification service | `sangyan/trust/receipt.py`, `sangyan/trust/service.py` | 4dbd278 | D-002, D-005 |
| Test Suite | Implement comprehensive 37 unit and integration tests | `tests/test_*.py` | 4dbd278 | D-001..D-008 |
