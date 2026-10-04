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
 ├─ 6. Scoped Atomic Persistence                sangyan/tenancy/repository.py
 │   └─ stores Evidence, Findings, and Receipts inside tenant isolation boundary
 └─ 7. End-to-End Investigation Orchestration   verify_content_item()
     ├─ executes ContentIntelligenceEngine      atomic claims, entities, observable safety signals
     ├─ persists analysis atomically            database transaction guarantees integrity
     ├─ executes ClaimVerificationEngine        multi-adapter evaluation across all extracted claims
     ├─ binds post-quantum TrustReceipts        all findings cryptographically sealed
      ├─ synthesizes holistic posture            SAFE, HIGH_RISK, SUSPICIOUS, or UNVERIFIED
      └─ returns InvestigationReport             comprehensive investigation bundle with Investigation record
```

---

## 8. Investigation Correlation, Scam-Chain Reconstruction & Safe Guidance Execution Flow

```text
InvestigationOrchestrator.investigate(...)      sangyan/correlation/orchestrator.py
 ├─ 1. Content Verification Execution           sangyan/verification/engine.py
 │   ├─ verifies multiple content items (text/URLs) in tenant scope
 │   ├─ extracts claims, entities, observable safety signals per item
 │   └─ evaluates authoritative adapters (SEBI, MCA, Exchanges, Circulars, Domains, Payment)
 ├─ 2. Multi-Content & Cross-Entity Correlation sangyan/correlation/correlator.py
 │   ├─ canonical normalizers: phone (E.164-like), UPI VPA, domain FQDN, registration
 │   ├─ evaluates relationship types: SHARED_ENTITY, SHARED_PAYMENT, SHARED_CONTACT, etc.
 │   ├─ assigns relationship strength: STRONG, MEDIUM, WEAK based on deterministic criteria
 │   ├─ bounded graph exploration: max 5 hops, max 200 edges, max 25 content items
 │   └─ cycle avoidance: visited vertex tracking prevents infinite loops
 ├─ 3. Scam-Chain Reconstruction                sangyan/correlation/scam_chains.py
 │   ├─ reconstructs 12 stages: LURE_FIRST_CONTACT -> PLATFORM_ACCESS -> ... -> FEE_EXTORTION -> RECOVERY
 │   ├─ assigns status: OBSERVED, SUPPORTED, INFERRED, NOT_OBSERVED, UNKNOWN
 │   ├─ inferred progression: withdrawal blockage/fee implies prior deposit & fictitious returns
 │   └─ hard-negative suppression: regulatory warning/caution texts evaluate all stages to NOT_OBSERVED
 ├─ 4. Controlled 14-Pattern Scam Taxonomy      sangyan/correlation/taxonomy.py
 │   ├─ multi-label pattern assignment: UNAUTHORIZED_ADVISORY, REGULATOR_IMPERSONATION, etc.
 │   ├─ requires observable signal + entity type / registry contradiction combinations
 │   └─ zero bare-keyword triggers; returns empty list if evidence threshold unmet
 ├─ 5. Safe Next-Step Guidance & Preservation   sangyan/correlation/guidance.py
 │   ├─ strictly non-investment advice: security, legal, and operational actions only
 │   ├─ urgent freeze: cybercrime 1930 / banking golden-hour alert for financial loss
 │   ├─ device & account hygiene: credential reset, 2FA, remote desktop software revocation
 │   └─ forensic preservation checklist: raw chat logs, UTR/VPA transaction receipts, APKs
 ├─ 6. Grievance Classification & Routing       sangyan/correlation/grievance.py
 │   ├─ 9-category problem classification: UNREGISTERED_INTERMEDIARY, INVESTOR_FRAUD, etc.
 │   ├─ official institutional routing: Cybercrime 1930, SEBI SCORES 2.0, RBI CMS, DoT Chakshu
 │   └─ user-facing filing checklist with zero automated external submissions
 ├─ 7. Epistemic Explainability & Abstention     sangyan/correlation/explainer.py
 │   ├─ "Why was this flagged?": concise factual points tied directly to evidence IDs
 │   └─ "What we don't know": explicit uncertainty statements on unverified claims & entities
 ├─ 8. Post-Quantum Investigation Trust Binding sangyan/verification/trust_binding.py
 │   ├─ canonical investigation payload: hashes, correlations, taxonomy, stages, guidance
 │   ├─ signs payload using NIST FIPS 204 ML-DSA-65 post-quantum digital signature
 │   └─ anchors complete investigation dossier with signed TrustReceipt
 ├─ 9. Scoped Atomic Persistence                sangyan/tenancy/repository.py
 │   └─ persists correlations, chain stages, grievances, and receipts in tenant transaction
 └─ 10. Returns CorrelatedInvestigationReport
```

---

## 9. LangGraph Investigation Workflow Pipeline (`sangyan/workflow/`)

```text
Investigation Initiation / Resume
 └─ WorkflowService.start_investigation() / resume_investigation()
     │
     ├─ Thread Identity & Access Validation
     │   └─ Canonical thread: <org_id>:<investigation_id>:<run_id>
     │   └─ Validates caller tenant matches org_id prefix
     │   └─ Creates WorkflowRun record in sangyan_workflow_runs
     │
     └─ InvestigationWorkflow.invoke() (Compiled LangGraph StateGraph)
         │
         ├─ Node 1: intake_node
         │   ├─ validates raw ContentItem list
         │   └─ saves items and initiates Investigation record in tenant scope
         │
         ├─ Node 2: intelligence_node
         │   ├─ invokes ContentIntelligenceEngine
         │   └─ extracts atomic claims, resolved entities, and observable signals
         │
         ├─ Node 3: verification_node
         │   ├─ invokes ClaimVerificationEngine with bounded exponential retry (3 attempts)
         │   ├─ queries authoritative adapters (SEBI, MCA, Market Infra, Payment)
         │   └─ emits findings, evidence, and records transient retry audit events
         │
         ├─ Node 4: correlation_node
         │   ├─ invokes InvestigationCorrelator
         │   └─ builds bounded cross-entity and multi-content graph with STRONG/MEDIUM/WEAK tiers
         │
         ├─ Node 5: scam_chain_node
         │   ├─ invokes ScamChainReconstructor (12-stage lifecycle)
         │   ├─ invokes ScamTaxonomyClassifier (14-pattern multi-label taxonomy)
         │   └─ synthesizes risk posture and evaluates human review requirement
         │
         ├─ Node 6: guidance_node
         │   ├─ invokes GuidanceEngine (non-investment safety directives & incident checklist)
         │   └─ invokes GrievanceRouter (institutional routing to Cybercrime, SCORES, CMS, Chakshu)
         │
         ├─ Node 7: explanation_node
         │   ├─ invokes InvestigationExplainer ("Why flagged?" + "What we don't know" abstentions)
         │   └─ finalizes explainability dossier
         │
         ├─ Conditional Edge: should_review_condition
         │   ├─ if review_required and not review_decision:
         │   │   └─ routes to Node 8: review_gate_node
         │   └─ else:
         │       └─ routes to Node 9: trust_finalization_node
         │
         ├─ Node 8: review_gate_node (Human-in-the-Loop Interruption)
         │   ├─ updates sangyan_investigations & workflow_runs to AWAITING_REVIEW
         │   ├─ calls LangGraph interrupt() -> serializes execution state to SQLite checkpointer
         │   ├─ [PROCESS CAN CRASH / RESTART HERE]
         │   ├─ resumed via WorkflowService.resume_investigation(Command(resume=decision))
         │   ├─ verifies reviewer RBAC permissions (viewer denied; analyst/admin allowed)
         │   ├─ records supervisory Review record in sangyan_reviews
         │   └─ flows to Node 9: trust_finalization_node
         │
         ├─ Node 9: trust_finalization_node
         │   ├─ checks receipt idempotency (reuses existing TrustReceipt if present)
         │   ├─ canonicalizes full investigation dossier
         │   ├─ signs dossier with NIST FIPS 204 ML-DSA-65 post-quantum digital signature
         │   └─ records TrustReceipt in sangyan_trust_receipts
         │
         ├─ Node 10: completion_node
         │   ├─ atomically marks Investigation and WorkflowRun as COMPLETED
         │   ├─ records workflow_completed audit event in chained ledger
         │   └─ ends pipeline (END)
         │
         └─ Node 11: failure_node (Error Boundary & Evidence Preservation)
             ├─ captures irrecoverable error, preserves prior collected claims/entities/evidence
             ├─ marks investigation as PARTIALLY_COMPLETED or FAILED
             ├─ updates sangyan_workflow_runs with current_node=failure_node and error details
             ├─ records workflow_failed audit event
             └─ ends pipeline (END)
```

---

## 10. Phase 6 Production API, Authentication, Authorization & Security Hardening

Phase 6 hardens SANGYAN for production operation by establishing an external authentication gateway, strict multi-tenant boundary guardrails, contextual RBAC enforcement, token-bucket traffic shaping, HTTP transport security, and low-cardinality observability.

```text
                                INCOMING HTTP REQUEST
                                          │
                  ┌───────────────────────┴───────────────────────┐
                  ▼                                               ▼
         [X-Request-ID Header]                           [Content-Length Check]
       Inject / propagate trace id                     Reject > 2 MB with 413
                  │                                               │
                  └───────────────────────┬───────────────────────┘
                                          │
                                          ▼
                         [Defensive Security Headers]
                 nosniff, DENY, CSP, Referrer-Policy, no-store
                                          │
                                          ▼
                            [Token-Bucket Rate Limiter]
               IP failed-auth lockout (5 strikes -> 429 Retry-After)
               Multi-dimensional endpoint categories:
               auth (10), investigate (30), mutate (20), read (120)
                                          │
                                          ▼
                          [External Gateway Authenticator]
                                          │
            ┌─────────────────────────────┴─────────────────────────────┐
            ▼                                                           ▼
     [Bearer JWT Token]                                        [X-API-Key Header]
   - Allowlist: HS256, RS256, ES256, EdDSA                    - Format: sgy_<8hex>_<32hex>
   - Reject alg=none immediately                              - O(1) prefix indexed lookup
   - Claims: iss, aud, exp, nbf, iat, sub, org_id             - Constant-time HMAC comparison
   - 30s clock skew tolerance                                 - Active / expiry / revocation check
   - Build canonical Principal                                - Update last_used_at timestamp
            │                                                           │
            └─────────────────────────────┬─────────────────────────────┘
                                          │
                     (Ambiguous: Both Bearer & Key -> 400 Bad Request)
                     (Missing / Expired / Invalid -> 401 Unauthorized)
                                          │
                                          ▼
                         [Contextual Multi-Tenant RBAC]
            - Enforce caller tenant: principal.org_id == req.org_id (403 on mismatch)
            - Prevent IDOR/BOLA: foreign tenant resources return 404 (zero enumeration)
            - sangyan_viewer: read-only investigations and receipts (create/mutate -> 403)
            - sangyan_analyst: create, investigate, workflow start/resume/cancel
            - sangyan_admin: all analyst capabilities + API key provisioning & revocation
                                          │
                                          ▼
                            [Core REST & Workflow Handlers]
            - Verify claims, verify content, multi-content investigate batch
            - Durable LangGraph start, review/resume, cancel, state snapshot, runs ledger
            - Admin API key generation (raw key returned once), listing, instant revocation
                                          │
                                          ▼
                           [Low-Cardinality Observability]
            - Prometheus /metrics: requests_total, latency, security_events, workflow_runs
            - Route normalizer: /api/v1/investigations/{id} bounds label cardinality
            - Sensitive-data redaction: auto-scrub JWTs, sgy_* keys, private keys, secrets
```

---

## 11. Production Runtime Architecture, Deployment Rollout & Disaster Recovery Flow

```text
+====================================================================================================+
|                    SANGYAN PRODUCTION RUNTIME ARCHITECTURE & TOPOLOGY                             |
+====================================================================================================+

              [Internet / Client Requests]
                           │
                           ▼
            [Kubernetes Ingress (TLS Termination)]
            - Strict TLS (TLS 1.3 / 1.2 modern ciphers)
            - 2 MB client_max_body_size
            - Location /metrics -> 404 Not Found (Internal Cluster-Only)
            - Location / -> Forward to sangyan-api ClusterIP Service (8000)
                           │
                           ▼
           [NetworkPolicy & Pod Security Context Boundary]
            - Ingress allowed only from ingress controller & Prometheus scraper
            - Egress restricted to DNS (53), HTTPS (443), and DB (5432 if PostgreSQL)
            - Pod Security: non-root UID 10001 (sangyan), drop ALL capabilities
            - Read-only root filesystem (readOnlyRootFilesystem: true)
            - Dedicated writable volumes: /app/data, /app/checkpoints, /app/keys, /tmp
                           │
                           ▼
              [Single-Replica SANGYAN API Pod (replicas: 1)]
            - Container Entrypoint: python -m sangyan.cli serve
            - Async Lifespan Startup:
                1. load_config() & validate_production_config(strict=True)
                2. Initialize DatabaseEngine (/app/data/sangyan.db, WAL mode)
                3. Verify pending_migrations() == 0 (Fail fast if unapplied)
                4. Initialize SqliteSaver checkpointer (/app/checkpoints/workflow_checkpoints.db)
                5. Mark app.state.is_ready = True
            - Uvicorn Single-Worker (1 process) to guarantee:
                * In-memory token bucket rate limiter coherence
                * Investigation thread-locking without distributed lock manager
                * SQLite WAL single-writer safety

                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
[Automated Pre-Rollout Hook]      [Daily Scheduled Backup CronJob]
- Job: sangyan-migration         - CronJob: sangyan-backup (0 2 * * *)
- Command: python -m sangyan.cli migrate - Command: python -m sangyan.cli backup create
- Concurrency Lock:               - AES-256-GCM encryption + PBKDF2 key derivation
  * SQLite: BEGIN IMMEDIATE       - Online snapshot (VACUUM INTO) + WAL flush
  * Postgres: pg_advisory_lock   - SHA-256 integrity digest manifest
- Runs to completion before API   - Automatic retention pruning (--keep-days 30)
```

### Container Startup & Lifespan Execution Sequence

```text
Container Init (UID 10001)
 └─ CLI: python -m sangyan.cli serve --host 0.0.0.0 --port 8000
     ├─ 1. Configuration Validation:
     │   └─ validate_production_config(strict=True)
     │       ├─ Check entropy >= 32 bytes for JWT_SECRET
     │       ├─ Reject default/insecure secret tokens ("sangyan-default-secret", etc.)
     │       ├─ Ensure ALLOWED_ORIGINS does not contain wildcard "*"
     │       └─ Ensure AUTH_REQUIRED is True
     │       (Any violation raises SystemExit(1) -> Container terminates immediately)
     ├─ 2. Database & Persistence Boot:
     │   ├─ Engine connection test
     │   ├─ Check schema migrations: runner.pending_migrations()
     │   │   └─ If unapplied migrations exist -> log warning, readiness probe returns 503
     │   └─ SqliteSaver checkpointer initialized in WAL mode at /app/checkpoints/
     ├─ 3. Lifespan Ready:
     │   ├─ Set app.state.is_ready = True
     │   ├─ Liveness probe (/health/live) -> 200 OK (Process responsive)
     │   └─ Readiness probe (/health/ready) -> 200 OK (DB connected, migrations applied)
     └─ 4. Graceful Termination (SIGTERM / SIGINT):
         ├─ FastAPI lifespan catches cancellation
         ├─ Set app.state.is_ready = False (Readiness immediately 503)
         ├─ Wait for in-flight requests to complete (within 30s terminationGracePeriod)
         ├─ Close workflow checkpointer connection
         ├─ Close DatabaseEngine connection pool
         └─ Exit 0 cleanly
```

### Cryptographic Backup & Disaster Recovery Sequence

```text
Backup Creation:
 └─ BackupManager.create_backup(encrypt_password=...)
     ├─ 1. Flush SQLite WAL via VACUUM INTO temporary snapshot file
     ├─ 2. Snapshot workflow checkpointer database (VACUUM INTO)
     ├─ 3. Snapshot signing keys and active configuration files
     ├─ 4. Assemble unencrypted tarball with manifest (timestamp, schema version)
     ├─ 5. Compute SHA-256 integrity checksum over data package
     ├─ 6. Derive 256-bit AES key via PBKDF2 (HMAC-SHA256, 100,000 rounds, 16-byte salt)
     ├─ 7. Encrypt payload via AES-256-GCM (12-byte random nonce, 16-byte auth tag)
     ├─ 8. Write binary container: MAGIC ('SGYBKP1\0') + Salt + Nonce + Tag + Ciphertext
     ├─ 9. Write backup_manifest.json with backup_id, timestamp, SHA-256, and metadata
     └─ 10. Prune backups older than retention policy (retention_days)

Isolated Disaster Recovery Verification:
 └─ BackupManager.restore_backup(backup_id, restore_dir, decrypt_password=...)
     ├─ 1. Read archive header, verify MAGIC ('SGYBKP1\0')
     ├─ 2. PBKDF2 key derivation using stored salt and operator password
     ├─ 3. AES-256-GCM authenticated decryption (verifies authentication tag)
     ├─ 4. Compute SHA-256 on decrypted tarball and verify match with manifest
     ├─ 5. Extract tarball using safe extraction filter (rejection of directory traversal)
     ├─ 6. Validate restored database integrity: PRAGMA integrity_check == 'ok'
     ├─ 7. Validate schema version matches manifest expectation
     └─ 8. Restore databases into production paths atomically
```

---

## 12. Distributed Runtime Architecture, Checkpoint Durability, Redis Rate Limiting & Cloud Resilience Flow

```text
Multi-Replica Kubernetes Ingress / Cluster Traffic
                   ↓
   +---------------+---------------+
   |               |               |
[Pod A (API)]   [Pod B (API)]   [Pod N (API)]
   |               |               |
   +-------+-------+-------+-------+
           |               |
           ↓               ↓
   [Redis Cluster]   [PostgreSQL Pool]
   - Token Bucket     - Relational DB
   - Auth Throttle    - PostgresSaver
                      - Advisory Locks
```

1. Distributed Rate Limiting & Cluster-Wide Failed-Auth Throttling:
  └─ RateLimiterMiddleware.dispatch()                     sangyan/security/middleware.py
      ├─ 1. Identify client: principal ID or IP           identifier = f"principal:{p.id}" or f"ip:{host}"
      ├─ 2. RedisFailedAuthTracker.is_throttled()         sangyan/security/redis_limiter.py
      │   ├─ ZREMRANGEBYSCORE sangyan:authfail:<ip>       prune failures older than sliding window
      │   ├─ ZCARD key                                    count active failures
      │   └─ if count >= threshold: return 429           cluster-wide lockout across all API pods
      ├─ 3. RedisRateLimiter.check_rate_limit()           sangyan/security/redis_limiter.py
      │   └─ EVALSHA LUA_TOKEN_BUCKET_SCRIPT              atomic token replenishment & deduction
      │       ├─ capacity, refill_rate, now, requested
      │       ├─ tokens = min(cap, tokens + elapsed*rate)
      │       ├─ if tokens >= requested: decrement & allow (200)
      │       └─ else: calculate retry_after & reject (429)
      └─ Failure Mode Resilience:
          ├─ fail_closed_mutations: mutations fail 429/503; reads fail open
          ├─ fail_open: allow all requests on Redis failure
          └─ local_fallback: transparent in-memory TokenBucket fallback

2. PostgreSQL Connection Pooling & Thread-Local Transaction Isolation:
  └─ PostgresDatabaseEngine                               sangyan/database/postgres.py
      ├─ psycopg_pool.ConnectionPool(min_size=2, max_size=20)
      ├─ thread-local connection binding in transaction()
      ├─ autocommit=False with BEGIN / COMMIT / ROLLBACK guarantees
      └─ execute() returns affected rowcount (cur.rowcount)

3. Workflow Checkpoint Durability (PostgresSaver):
  └─ WorkflowCheckpointer(backend="postgres")             sangyan/workflow/checkpointer.py
      ├─ PostgresSaver(sync_connection)
      ├─ saver.setup() idempotently provisions checkpoints schema
      └─ thread_id: `<org_id>:<investigation_id>:<run_id>` prevents cross-tenant access

4. Review Concurrency & Database-Level Mutex:
  └─ WorkflowService.resume_investigation()               sangyan/workflow/service.py
      ├─ TenantRepository.transition_investigation_status()
      │   └─ UPDATE sangyan_investigations
      │      SET status = 'FINALIZING'
      │      WHERE id = ? AND status = 'AWAITING_REVIEW'
      ├─ If rowcount == 1: winning pod claims review, invokes workflow runner
      └─ If rowcount == 0: losing pod raises ReviewConflictError (409 Conflict)

5. Chained Audit Ledger Advisory Locking:
  └─ TenantRepository.record_audit_event()                sangyan/tenancy/repository.py
      ├─ pg_advisory_xact_lock(918273) serializes audit chain writes per-tenant
      ├─ SELECT prev_hash FROM sangyan_audit_ledger ORDER BY sequence_number DESC LIMIT 1
      ├─ compute entry_hash = SHA3_256(prev_hash + tenant_id + payload)
      └─ INSERT INTO sangyan_audit_ledger (entry_hash, prev_hash, seq)

6. Offsite Cloud Backup Replication & Remote Restore:
  └─ BackupManager + S3BackupStorage                      sangyan/database/cloud_backup.py
      ├─ 1. Local backup creation: VACUUM snapshot + tarball
      ├─ 2. Pre-upload encryption enforcement: requires AES-256-GCM (.enc extension)
      ├─ 3. S3 upload with exponential backoff & jitter (max_retries=3)
      ├─ 4. SHA-256 integrity verification against remote object
      ├─ 5. Download remote archive into isolated temporary directory
      ├─ 6. Authenticated decryption, SHA-256 match, and safe tarball extraction
      ├─ 7. PRAGMA integrity_check on restored relational & checkpoint databases
      └─ 8. Remote retention pruning: keep newest N, never prune latest verified backup

7. OpenTelemetry Distributed Tracing & Privacy Guardrails:
  └─ TracingMiddleware + trace_span                       sangyan/security/tracing.py
      ├─ Propagate W3C traceparent headers across distributed boundaries
      ├─ Sanitize span attributes: reject raw claims, message bodies, tokens, and PII
      ├─ Record low-cardinality metadata: status_code, http.route, organization_id
      └─ Fallback to NoOpTracer when tracing is disabled
```

---

## 13. Asynchronous Execution, Stream Leasing, HITL Decoupling & Multi-Region Disaster Recovery Flow

```text
Client Submission (POST /workflow/start?async_exec=true)
                       ↓
   [API Gateway / Route: 202 Accepted with task_id & poll_url]
                       ↓
       +---------------+---------------+
       |                               |
       ↓                               ↓
[sangyan_async_tasks]        [Redis Streams: XADD]
(Relational Outbox Ledger)   (sangyan:tasks:stream)
                                       ↓
                        [Consumer Group: XREADGROUP]
                                       ↓
                     [AsyncInvestigationWorker]
                     ├─ 1. Atomic Lease Acquisition (UPDATE lease_owner)
                     ├─ 2. Background Heartbeat Thread (renew_lease)
                     ├─ 3. Execution Dispatch
                     │   ├─ WORKFLOW_START
                     │   │   ├─ Stage 1 executes until review_gate_node
                     │   │   └─ HITL Decoupling: AWAITING_REVIEW completes stage;
                     │   │      capacity freed immediately; no lease held!
                     │   ├─ WORKFLOW_RESUME
                     │   │   └─ Resumes LangGraph checkpoint, completes graph,
                     │   │      and signs ML-DSA-65 trust receipt
                     │   └─ WORKFLOW_CANCEL
                     │       └─ Cancels investigation preserving evidence
                     ├─ 4. Success: UPDATE status=SUCCEEDED & XACK
                     └─ 5. Failure Handling:
                         ├─ Transient: RETRY_WAIT + backoff with jitter + XACK + re-enqueue
                         └─ Fatal / Max Retries: DEAD_LETTERED + XADD dead-letter stream
```

### Multi-Region Active-Passive Disaster Recovery & Split-Brain Fencing

```text
       Primary Region (Active)                      Standby Region (Ready)
   [primary-south-1 | Epoch 1]                 [standby-north-1 | Epoch 1]
               │                                            │
               │ (verify_write_authority: OK)               │ (verify_write_authority: REJECT)
               ▼                                            ▼
       [Active Writes Allowed]                      [StaleRegionError: 409]
               │
               │   CATASTROPHIC OUTAGE / DRILL
               │   ───────────────────────────► Disaster Recovery Manager
               │                                ├─ Promote target (Epoch = 2)
               │                                └─ Demote & Fence source
               ▼                                            ▼
   [primary-south-1 | FENCED]                  [standby-north-1 | Epoch 2]
               │                                            │
               │ (verify_write_authority: REJECT)           │ (verify_write_authority: OK)
               ▼                                            ▼
   [StaleRegionError: Split-Brain Blocked]          [Active Writes Allowed]
               │                                            │
               └──────────────────────┬─────────────────────┘
                                      ▼
                   [Continuous Linear SHA3-256 Audit Chain]
                   (verify_audit_continuity: Unbroken Cryptographic Hash)
```

1. Asynchronous Task Lifecycle & Stream Architecture:
  └─ AsyncInvestigationWorker + RedisStreamTaskQueue      sangyan/async_exec/
      ├─ 1. Client submits async investigation: receives HTTP 202 Accepted with task_id and poll_url
      ├─ 2. Relational outbox record created in sangyan_async_tasks with status QUEUED
      ├─ 3. Broker stream publication: XADD to sangyan:tasks:stream
      ├─ 4. Consumer group dequeue: XREADGROUP sangyan:task_workers with consumer ID
      ├─ 5. Relational lease acquisition: UPDATE sangyan_async_tasks SET lease_owner, lease_expires_at
      ├─ 6. Background lease heartbeat: thread periodically extends lease_expires_at while active
      └─ 7. Expired lease discovery: find_expired_leases() recovers abandoned tasks for execution

2. Human-in-the-Loop (HITL) Decoupling Semantic:
  └─ AsyncInvestigationWorker._execute_task_payload()     sangyan/async_exec/worker.py
      ├─ Workflow executes up to review_gate_node (AWAITING_REVIEW)
      ├─ Worker completes task stage: status SUCCEEDED with result.status = 'AWAITING_REVIEW'
      ├─ Worker immediately frees execution capacity and ACKs broker message
      ├─ Worker NEVER sleeps, blocks, or holds leases while awaiting human deliberation
      └─ Resumption occurs via independent WORKFLOW_RESUME task upon supervisor decision

3. Bounded Retry Backoff & Dead-Letter Handling:
  └─ AsyncTask.compute_backoff_delay() + queue.dead_letter() sangyan/async_exec/
      ├─ Transient errors increment retry_count and transition task to RETRY_WAIT
      ├─ Exponential backoff with decorrelated jitter: delay = uniform(base * 0.5, min(max_sec, base * 2^retry))
      ├─ Re-enqueue into broker stream after backoff delay
      ├─ If retry_count >= max_retries: task transitions to DEAD_LETTERED in DB and dead_letter stream
      └─ Administrative recovery: CLI/API retry command resets retry_count=0 and re-queues task

4. Multi-Region Disaster Recovery & Split-Brain Fencing:
  └─ DisasterRecoveryManager                              sangyan/dr/manager.py
      ├─ Active-Passive topology: PRIMARY_ACTIVE vs STANDBY_READY
      ├─ Region Authority Epoch tracked in sangyan_region_fencing
      ├─ Pre-write validation: verify_write_authority() enforced across all TenantRepository mutations
      ├─ Fenced or standby regions reject write mutations with StaleRegionError (HTTP 409 Conflict)
      ├─ Idempotent promotion: promote_region() advances global epoch and fences prior primary
      ├─ Split-brain defense: demoted primary attempting writes rejected due to stale epoch / fence
      └─ Cryptographic audit continuity: verify_audit_continuity() verifies unbroken SHA3-256 chain

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
| Verification Adapters | SEBI intermediary, MCA CIN, Circulars, and Official Domains adapters | `sangyan/verification/adapters/` | 3ecb832 | D-015, D-017 |
| Post-Quantum Trust Binding | ML-DSA-65 digital signing of findings, claims, and evidence digests | `sangyan/verification/trust_binding.py` | 3ecb832 | D-020 |
| Claim Verification Engine | Orchestration, conflict resolution, epistemic stances, and repository persistence | `sangyan/verification/engine.py` | 3ecb832 | D-018, D-019 |
| Phase 3 Verification Test Suite | 18 verification tests (adapters, conflict resolution, PQC trust, cross-tenant isolation, adversarial evasion) | `tests/test_verification.py` | 3ecb832 | D-014..D-021 |
| Phase 3 Hardening & Evasion Defense | Multi-domain threat precedence, disclaimer evasion defense, adapter fault resilience, thread safety, and 8 new tests (total 90 tests) | `sangyan/verification/`, `tests/test_verification.py` | d60429c | D-022 |
| End-to-End Investigation Orchestration | Lookbehind clause splitting regex, transactional persistence, verify_content_item(), InvestigationReport, and 2 E2E tests (total 92 tests) | `sangyan/intelligence/`, `sangyan/verification/`, `tests/test_verification.py` | 8754f62 | D-023 |
| Market Infrastructure Verification | Verify NSE, BSE, MCX trading members and NSDL, CDSL depositories with disciplinary status handling | `sangyan/verification/adapters/market_infrastructure.py`, `sangyan/verification/snapshots.py` | a0766f5 | D-024 |
| Payment Destination Verification | UPI VPA verification against official broker directories, scam registries, and mismatch detection | `sangyan/verification/adapters/payment.py`, `sangyan/verification/snapshots.py` | a0766f5 | D-025 |
| Evidentiary Provenance & Quality Metrics | Multi-dimensional quality metrics, raw/normalized values, and immutable SHA3-256 digests in Evidence | `sangyan/domain/models.py`, `sangyan/verification/engine.py` | a0766f5 | D-026 |
| Chained Audit Ledger | Tamper-evident SHA3-256 chained audit trail with cryptographic log integrity and tenant scoping | `sangyan/domain/models.py`, `sangyan/tenancy/repository.py`, `sangyan/verification/engine.py` | a0766f5 | D-027 |
| Verification REST API & Routes | FastAPI endpoints for claims, content verification, investigations, sources, and audit logs | `sangyan/api/routes.py`, `sangyan/api/app.py` | a0766f5 | D-028 |
| Human Inspection HTML Views | Server-rendered audit views with side-by-side conflicting evidence and Section 40 banner | `sangyan/api/views.py` | a0766f5 | D-029 |
| Correlation Engine & Graph Correlator | Bounded multi-content entity/claim/signal graph with STRONG/MEDIUM/WEAK hierarchy and cycle avoidance | `sangyan/correlation/correlator.py`, `sangyan/domain/models.py` | d6694d6 | D-030 |
| 12-Stage Scam-Chain Reconstruction | Lifecycle reconstruction with OBSERVED/INFERRED semantics and regulatory hard-negative suppression | `sangyan/correlation/scam_chains.py`, `sangyan/domain/models.py` | d6694d6 | D-031 |
| Controlled Scam Taxonomy | Multi-label 14-pattern scam classifier requiring signal and contradiction combinations | `sangyan/correlation/taxonomy.py`, `sangyan/domain/models.py` | d6694d6 | D-032 |
| Safe Guidance & Incident Preservation | Non-investment conditional action guidance and forensic incident preservation checklist | `sangyan/correlation/guidance.py`, `sangyan/domain/models.py` | d6694d6 | D-033 |
| Grievance Classification & Routing | 9-category problem classification and institutional routing to SCORES, Cybercrime 1930, RBI CMS, Chakshu | `sangyan/correlation/grievance.py`, `sangyan/domain/models.py` | d6694d6 | D-034 |
| Epistemic Explainability & Abstention | "Why was this flagged?" with evidence links and mandatory "What we don't know" explicit uncertainty | `sangyan/correlation/explainer.py`, `sangyan/domain/models.py` | d6694d6 | D-035 |
| Investigation Post-Quantum Trust Binding | NIST ML-DSA-65 digital signing of canonical multi-content investigation dossiers | `sangyan/verification/trust_binding.py`, `sangyan/correlation/orchestrator.py` | d6694d6 | D-036 |
| Phase 4 REST API & Migration 002 | Batch investigation API endpoints and Migration 002 tables (correlations, stages, grievances) | `sangyan/api/`, `sangyan/database/migrations.py` | d6694d6 | D-030..D-036 |
| Phase 4 Test Suite | 21 new tests covering correlation, scam chains, guidance, grievance, explainability, PQC signing, API (total 131 tests) | `tests/test_correlation.py`, `tests/test_api.py` | d6694d6 | D-030..D-036 |
| Migration 003 & Workflow Runs Schema | sangyan_workflow_runs table with scoped tenant indexes, retry tracking, and checkpoint pointers | `sangyan/database/migrations.py`, `tests/test_database.py` | aca648c | D-038 |
| Workflow State & Models | InvestigationWorkflowState TypedDict, WorkflowRun domain model, and expanded investigation statuses | `sangyan/workflow/state.py`, `sangyan/domain/models.py` | aca648c | D-037 |
| Durable SQLite Checkpointing | SqliteSaver checkpointer wrapper with tenant-scoped thread identity (org:inv:run) and crash recovery | `sangyan/workflow/checkpointer.py` | aca648c | D-038 |
| Node Suite & Domain Delegation | 11 orchestration nodes delegating to intelligence, verification, correlation, guidance, explainer, trust | `sangyan/workflow/nodes.py` | aca648c | D-037 |
| Human-in-the-Loop Review Gate | Durable interrupt() pause, restart recovery, resume_investigation(), first-valid-review wins, and viewer denial | `sangyan/workflow/nodes.py`, `sangyan/workflow/service.py` | aca648c | D-039, D-042 |
| Bounded Retry & Error Boundary | Exponential backoff for transient failures, audit logging, failure_node with partial evidence preservation | `sangyan/workflow/nodes.py`, `sangyan/workflow/service.py`, `sangyan/workflow/errors.py` | aca648c | D-040 |
| Cancellation & Concurrency | cancel_investigation() preserving prior evidence, per-investigation thread locks, race condition guardrails | `sangyan/workflow/service.py` | aca648c | D-041, D-042 |
| PQC Trust Finalization | Post-review NIST FIPS 204 ML-DSA-65 investigation dossier signing with receipt idempotency | `sangyan/workflow/nodes.py`, `sangyan/workflow/service.py` | aca648c | D-043 |
| Workflow REST API Endpoints | /api/v1/workflow/start, /resume, /cancel, /state, /runs with full RBAC and tenant scoping | `sangyan/api/routes.py`, `sangyan/api/app.py`, `tests/test_api.py` | aca648c | D-037..D-043 |
| Phase 5 Workflow Test Suite | 14 new comprehensive tests (12 workflow scenarios + 2 API lifecycle tests, total 145 tests) | `tests/test_workflow.py`, `tests/test_api.py` | aca648c | D-037..D-043 |
| Migration 004 & API Keys Schema | sangyan_api_keys table with prefix indexing, tenant scoping, revocation, and last_used tracking | `sangyan/database/migrations.py`, `tests/test_database.py` | 28d9fbc | D-046 |
| External Authentication Boundary | Multi-scheme JWT Bearer and hashed API key authentication with mutual exclusivity (400 on conflict) | `sangyan/security/models.py`, `sangyan/security/auth.py` | 28d9fbc | D-044 |
| Cryptographic JWT Validation | Strict algorithm allowlist (HS256/RS256/ES256/EdDSA), RFC 7519 claims check, 30s clock skew | `sangyan/security/jwt.py` | 28d9fbc | D-045 |
| Hashed API Key Management | Constant-time prefixed lookup, key generation, SHA-256 storage, and Admin CRUD endpoints | `sangyan/security/api_keys.py`, `sangyan/tenancy/repository.py`, `sangyan/api/routes.py` | 28d9fbc | D-046 |
| Multi-Tenant RBAC & IDOR Defense | Zero-trust tenant parameter verification, sangyan_viewer/analyst/admin RBAC matrix, IDOR protection | `sangyan/security/auth.py`, `sangyan/api/routes.py` | 28d9fbc | D-047 |
| Token-Bucket Rate Limiter | Sliding token bucket across 5 endpoint categories and failed-auth IP lockout middleware | `sangyan/security/rate_limiter.py`, `sangyan/security/middleware.py` | 28d9fbc | D-048 |
| HTTP Transport Security Hardening | Defensive headers (nosniff, DENY, CSP), Cache-Control: no-store on API, 2 MB body bound, X-Request-ID | `sangyan/security/middleware.py`, `sangyan/api/app.py` | 28d9fbc | D-049 |
| Low-Cardinality Telemetry & Redaction | Bounded Prometheus /metrics exporter, route normalizer, and sensitive credential log redaction | `sangyan/security/telemetry.py` | 28d9fbc | D-050 |
| Phase 6 Security Test Suite | 32 new tests covering JWT, API keys, RBAC, IDOR, rate limiting, security headers, metrics (total 177 tests) | `tests/test_security_phase6.py`, `tests/test_database.py` | 28d9fbc | D-044..D-050 |
| Container Packaging & Hardening | Non-root UID 10001 multi-stage Docker build, read-only rootfs, dedicated volumes, no secrets | `Dockerfile`, `.dockerignore` | a7b6504 | D-051 |
| Single-Replica Production Topology | Enforced replicas: 1 model for token buckets, SQLite WAL, and thread locks; zero multi-replica drift | `deploy/helm/`, `docker-compose.yml` | a7b6504 | D-052 |
| Production Configuration Validation | Fail-closed validate_production_config (entropy >= 32, no defaults, no wildcard CORS, auth required) | `sangyan/config.py` | a7b6504 | D-053 |
| Decoupled Health Semantics | Explicit /health/live (process), /health/ready (DB/migrations), /health with zero secret disclosure | `sangyan/api/app.py`, `sangyan/cli.py` | a7b6504 | D-054 |
| Durable Workflow Checkpointing | File-backed SQLite WAL SqliteSaver checkpointer persisted in /app/checkpoints across restarts | `sangyan/api/app.py` | a7b6504 | D-055 |
| Migration Lifecycle & Concurrency | Transactional double-check lock for SQLite, pg_advisory_lock for Postgres, pre-rollout Job hook | `sangyan/database/migrations.py`, `deploy/helm/` | a7b6504 | D-056 |
| Cryptographic Backup & Safe Restore | Online VACUUM snapshot, AES-256-GCM + PBKDF2 encryption, SHA-256 manifest, traversal-safe restore | `sangyan/database/backup.py`, `sangyan/cli.py` | a7b6504 | D-057 |
| Production Kubernetes & Helm Deployment | Helm chart with non-root securityContext, Ingress TLS, NetworkPolicy, Job, and CronJob | `deploy/helm/sangyan/` | a7b6504 | D-058 |
| Phase 7 Verification Suite | 28 new tests covering config, health, backups, migrations, container and k8s manifests (total 205 tests) | `tests/test_*.py` | a7b6504 | D-051..D-058 |
| Distributed Relational Engine | PostgreSQL connection pooling with psycopg_pool, thread-local transactions, and rowcount reporting | `sangyan/database/postgres.py`, `sangyan/database/engine.py` | e6aaea5 | D-059 |
| Durable Workflow Checkpointing | PostgresSaver checkpointer with pooled connections, schema initialization, and tenant thread isolation | `sangyan/workflow/checkpointer.py` | e6aaea5 | D-060 |
| Distributed Rate Limiting | Atomic Redis token bucket via Lua script and shared sliding-window failed-auth lockout across pods | `sangyan/security/redis_limiter.py`, `sangyan/security/middleware.py` | e6aaea5 | D-061 |
| Review Race Concurrency | Database-level atomic conditional transition (AWAITING_REVIEW -> FINALIZING) preventing double-finalization | `sangyan/tenancy/repository.py`, `sangyan/workflow/service.py` | e6aaea5 | D-062 |
| Chained Audit Serialization | PostgreSQL advisory transaction locking (pg_advisory_xact_lock) for unbroken cryptographic hash chains | `sangyan/tenancy/repository.py` | e6aaea5 | D-063 |
| Cloud Backup Replication | S3/GCS-compatible offsite replication with strict pre-upload encryption enforcement (.enc) and isolated restore | `sangyan/database/cloud_backup.py`, `sangyan/cli.py` | e6aaea5 | D-064 |
| OpenTelemetry Distributed Tracing | W3C trace propagation with privacy boundary rejecting raw claims, tokens, and PII from span attributes | `sangyan/security/tracing.py`, `sangyan/api/app.py` | e6aaea5 | D-065 |
| Distributed Topology & Scaling | Multi-replica Helm values, HPA, NetworkPolicy with Redis egress, and distributed docker-compose | `deploy/helm/sangyan/`, `docker-compose.distributed.yml` | e6aaea5 | D-066 |
| Phase 8 Distributed Test Suite | 34 comprehensive tests across 15 scenarios covering concurrency, cloud backup, tracing, Redis, and Postgres (total 239 tests) | `tests/test_*.py` | e6aaea5 | D-059..D-066 |
| Migration 005 Schema | Add sangyan_async_tasks relational outbox and sangyan_region_fencing multi-region split-brain tables | `sangyan/database/migrations.py` | 5d014e4 | D-067, D-071 |
| Asynchronous Task Domain & State Machine | Implement AsyncTask, TaskStatus, TaskType, VALID_TASK_TRANSITIONS, and decorrelated jitter backoff | `sangyan/async_exec/models.py` | 5d014e4 | D-067 |
| Outbox Repository & Relational Leasing | Implement AsyncTaskRepository with atomic leasing, lease renewals, retries, and dead-lettering | `sangyan/async_exec/repository.py` | 5d014e4 | D-067 |
| Redis Streams & Consumer Groups | Implement TaskQueue ABC, RedisStreamTaskQueue (XADD, XREADGROUP, XACK, XCLAIM), and InMemoryTaskQueue | `sangyan/async_exec/queue.py` | 5d014e4 | D-067 |
| Asynchronous Investigation Worker | Implement AsyncInvestigationWorker with bounded leasing, lease heartbeat, expired lease recovery, and SIGTERM shutdown | `sangyan/async_exec/worker.py` | 5d014e4 | D-067, D-068 |
| HITL Decoupling Semantic | Stage pause at review_gate_node marks task stage complete and releases capacity; resume via WORKFLOW_RESUME | `sangyan/async_exec/worker.py` | 5d014e4 | D-068 |
| Active-Passive DR & Split-Brain Fencing | DisasterRecoveryManager with epoch progression, write authority fencing, and StaleRegionError enforcement | `sangyan/dr/manager.py`, `sangyan/dr/models.py` | 5d014e4 | D-071, D-072 |
| Cryptographic Audit Continuity | SHA3-256 linear hash chain verification across failover boundaries and tamper detection | `sangyan/dr/manager.py` | 5d014e4 | D-073 |
| Pre-Write Authority Assertion | TenantRepository asserts region write authority on all write mutations; rejects writes if fenced or stale | `sangyan/tenancy/repository.py` | 5d014e4 | D-071 |
| Phase 9 CLI & REST Endpoints | Add worker, dr status/promote/simulate, task list/inspect/dead-letter/retry commands and REST routes | `sangyan/cli.py`, `sangyan/api/routes.py`, `sangyan/api/app.py` | 5d014e4 | D-069, D-072 |
| Phase 9 Comprehensive Test Suite | 36 new tests covering models, queues, worker, DR failover, API, and failure scenarios A-G (total 275 tests) | `tests/test_async_*.py`, `tests/test_dr_failover.py`, `tests/test_phase9_failure_scenarios.py` | 5d014e4 | D-067..D-073 |











