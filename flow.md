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

## 5. Content Ingestion & Normalization Flow

```text
User / WhatsApp / Web / API Submission
 ├─ IngestionService.ingest_text(raw_text)   sangyan/ingest/service.py
 │   ├─ clean_text(raw_text)                 sangyan/ingest/cleaner.py
 │   │   ├─ ZERO_WIDTH_PATTERN.sub()         strips evasion characters (\u200b, \ufeff)
 │   │   ├─ _HTMLTextExtractor               parses and extracts plain text from HTML
 │   │   ├─ html.unescape()                  decodes entities (&#8377; -> ₹)
 │   │   └─ unicodedata.normalize('NFKC')    canonical composition/decomposition
 │   ├─ extract_urls(raw_text)               finds nested HTTP/HTTPS links
 │   ├─ sha3_256_text(cleaned)               computes canonical content hash
 │   └─ repo.save_content_item(item)         persists ContentItem in sangyan_content_items
 └─ IngestionService.ingest_url(url)         sangyan/ingest/service.py
     └─ UrlFetcher.fetch(url)                sangyan/ingest/fetcher.py
         ├─ validate_url_ssrf(url)           pre-flight SSRF and scheme validation
         ├─ with ssrf_safe_connections():    hooks socket.create_connection
         │   └─ httpx.Client(stream=True)    bounded streaming (2MB limit, timeouts)
         │       └─ redirect validation      each redirect hop checked against SSRF
         ├─ _TitleExtractor                  parses HTML title
         ├─ clean_text(raw_content)          strips HTML scripts/styles
         └─ repo.save_content_item(item)     persists ContentItem
```

---

## 6. Content Intelligence Pipeline Execution Flow

```text
ContentIntelligenceEngine.analyze(item)      sangyan/intelligence/pipeline.py
 ├─ 1. LanguageDetector.detect(text)         sangyan/intelligence/language.py
 │   ├─ Unicode script frequency distribution (Deva, Latn, Gujr, Beng, Taml, Telu, Knda)
 │   ├─ Devanagari Hindi vs Marathi: Indic combining-mark preserving tokenizer
 │   │   └─ checks distinct MARATHI_MARKERS vs HINDI_MARKERS
 │   └─ Latin script Hinglish: matches high-frequency HINGLISH_MARKERS
 ├─ 2. ClaimExtractor.extract_claims(text)   sangyan/intelligence/claims.py
 │   ├─ CLAUSE_SPLIT_REGEX.split()           breaks compound clauses on conjunctions
 │   ├─ _classify_claim_type()               maps to regulatory, return, urgency, payment, affiliation
 │   └─ emits list[Claim] with UNVERIFIED status and context_pointers in metadata
 ├─ 3. EntityResolver.resolve_entities(text) sangyan/intelligence/entities.py
 │   ├─ SEBI registration patterns           INZ, INA, INH, INP, INM, IN-DP, MF
 │   ├─ CIN pattern                          [LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}
 │   ├─ Indian UPI VPAs                      handle@okhdfcbank, @paytm, @ybl, etc.
 │   ├─ Telegram & WhatsApp links            t.me/..., chat.whatsapp.com/...
 │   └─ Known regulators & brokers           SEBI, RBI, MCA, NSE, BSE, Zerodha, Groww, etc.
 ├─ 4. SignalDetector.detect_signals(text)   sangyan/intelligence/signals.py
 │   ├─ WARNING_CONTEXT_PATTERNS check       suppresses signals on regulatory warnings & advisories
 │   ├─ NEGATION_PREFIXES check              suppresses negated phrases ("not guaranteed")
 │   └─ evaluates 20+ observable signals     GUARANTEED_RETURN, URGENCY, WITHDRAWAL_FEE, etc.
 ├─ 5. _compute_risk_score(signals)          weighted diminishing-returns risk aggregation
 └─ 6. _generate_summary(...)                synthesizes human-readable findings summary
```

---

## 7. Authoritative Verification & Trust Binding Execution Flow

```text
ClaimVerificationEngine.verify_claims(...)      sangyan/verification/engine.py
 ├─ 1. Cache Check                              sangyan/verification/cache.py
 │   └─ SHA3-256(source_id + query_type + val)  avoids repeated upstream lookups
 ├─ 2. Adapter Execution Pipeline
 │   ├─ SEBIVerificationAdapter                 sangyan/verification/adapters/sebi.py
 │   │   ├─ queries SEBI snapshot               INZ, INA, INH, INP, INM, IN-DP, MF
 │   │   ├─ validates registration status       ACTIVE vs EXPIRED vs CANCELLED vs BOGUS
 │   │   └─ adversarial override                exact bogus registration overrides brand name match
 │   ├─ MCAVerificationAdapter                  sangyan/verification/adapters/mca.py
 │   │   ├─ queries MCA snapshot                21-character CIN validation
 │   │   └─ validates corporate status          ACTIVE vs STRUCK_OFF vs DISSOLVED vs UNREGISTERED
 │   ├─ CircularsVerificationAdapter            sangyan/verification/adapters/circulars.py
 │   │   ├─ evaluates prohibited assertions     guaranteed returns (SEBI/HO/MIRSD), OTP solicitation
 │   │   └─ maps regulatory bans                returns CONTRADICTED + authoritative circular excerpt
 │   └─ OfficialDomainsVerificationAdapter      sangyan/verification/adapters/official_domains.py
 │       ├─ checks official registry            legitimate financial infrastructure
 │       ├─ evaluates phishing blacklist        lookalike domains (e.g. zerodha-profit.cc)
 │       └─ checks suspicious TLDs              high-risk TLD warnings (.xyz, .top, .vip)
 ├─ 3. Deterministic Conflict Resolution
 │   ├─ Opposing outcomes (SUPPORTED + CONTRADICTED) -> resolves to CONFLICTING
 │   └─ Persists dual opposing evidence items with complete provenance
 ├─ 4. Stance & Finding Synthesis
 │   ├─ maps to 5 epistemic stances             SUPPORTED, CONTRADICTED, CONFLICTING, OUTDATED, INSUFFICIENT_EVIDENCE
 │   ├─ constructs domain Evidence objects      canonical SHA3-256 hashes, source links, confidence
 │   └─ synthesizes domain Finding objects      factual determination, reasoning, and context
 ├─ 5. Post-Quantum Trust Binding               sangyan/verification/trust_binding.py
 │   ├─ builds canonical verification payload   finding_id, claim_id, stance, statement, evidence_hashes
 │   ├─ signs payload with ML-DSA-65            pure Python dilithium-py post-quantum digital signature
 │   └─ generates signed TrustReceipt           cryptographically anchors verification determination
 └─ 6. Scoped Atomic Persistence                sangyan/tenancy/repository.py
     └─ stores Evidence, Findings, and Receipts inside tenant isolation boundary
```

---

## Session Changelog

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
| Concurrency & Persistence | Enable SQLite WAL mode, ConfidenceVector idempotency, and full CRUD in TenantRepository | `sangyan/database/engine.py`, `sangyan/domain/models.py`, `sangyan/tenancy/repository.py`, `tests/test_persistence.py` | 42bbef2 | D-009 |
| Ingestion & Text Normalization | Implement zero-width stripping, HTML cleaning, NFKC normalization, URL extraction | `sangyan/ingest/cleaner.py` | d395cfe | D-010 |
| SSRF-Safe Fetching | Implement bounded streaming HTTP fetcher with redirect re-verification | `sangyan/ingest/fetcher.py`, `sangyan/ingest/service.py` | d395cfe | D-011 |
| Multilingual Identification | Script analysis and Devanagari Hindi/Marathi + Hinglish identification with combining-mark tokenizer | `sangyan/intelligence/language.py` | d395cfe | D-010 |
| Claim & Entity Extraction | Atomic claim decomposition and SEBI/CIN/UPI/Channel entity extraction | `sangyan/intelligence/claims.py`, `sangyan/intelligence/entities.py` | d395cfe | D-012 |
| Safety Signals & Hard Negatives | 20+ signal detectors with disclaimer/warning contextual suppression | `sangyan/intelligence/signals.py`, `sangyan/intelligence/pipeline.py` | d395cfe | D-013 |
| Phase 2 Test Suite | 27 new tests (ingest, language, claims, entities, signals, stress tests) bringing total to 64 tests | `tests/test_ingest.py`, `tests/test_intelligence.py` | d395cfe | D-010..D-013 |
| Authoritative Source Registry | Seed registry of SEBI, MCA, Exchanges, Circulars, Domains with trust tiers | `sangyan/verification/sources.py` | 3ecb832 | D-014 |
| Versioned Snapshots | SHA3-256 verified registry snapshots and SnapshotManager | `sangyan/verification/snapshots.py` | 3ecb832 | D-016 |
| Verification Caching & Rate Limiting | In-memory SHA3-256 TTL caching and sliding-window rate limiting | `sangyan/verification/cache.py` | 3ecb832 | D-021 |
| Verification Adapters | SEBI intermediary, MCA CIN, Circulars, and Official Domain adapters | `sangyan/verification/adapters/` | 3ecb832 | D-015, D-017 |
| Post-Quantum Trust Binding | ML-DSA-65 digital signing of findings, claims, and evidence digests | `sangyan/verification/trust_binding.py` | 3ecb832 | D-020 |
| Claim Verification Engine | Orchestration, conflict resolution, epistemic stances, and repository persistence | `sangyan/verification/engine.py` | 3ecb832 | D-018, D-019 |
| Phase 3 Verification Test Suite | 18 verification tests (adapters, conflict resolution, PQC trust, cross-tenant isolation, adversarial evasion) | `tests/test_verification.py` | 3ecb832 | D-014..D-021 |
| Phase 3 Hardening & Evasion Defense | Multi-domain threat precedence, disclaimer evasion defense, adapter fault resilience, thread safety, and 8 new tests (total 90 tests) | `sangyan/verification/`, `tests/test_verification.py` | d60429c | D-022 |





