# SANGYAN — Domain Model & Verification Contracts Documentation

## 1. Overview

This document specifies the domain model interactions, schema contracts, and epistemic stance semantics implemented in SANGYAN during **Phase 3: Authoritative Verification & Evidence Retrieval**.

The verification subsystem grounds all factual evaluations in curated authoritative institutional registries (SEBI, MCA, Exchanges, Circulars, Official Domains) with complete evidentiary provenance and post-quantum cryptographic trust binding.

---

## 2. Core Domain Models in Verification

The verification subsystem interacts with six core domain entities defined in `sangyan.domain.models`:

### 2.1 `Claim`
- **Purpose**: Represents an atomic assertion extracted from investor-facing content.
- **Key Fields**:
  - `claim_id`: Unique identifier (UUID4 format).
  - `content_id`: Foreign key linking to parent `ContentItem`.
  - `claim_text`: Normalized text of the atomic assertion.
  - `claim_type`: `regulatory`, `return`, `urgency`, `payment`, `affiliation`, or `other`.
  - `status`: Epistemic verification stance (`ClaimStatus` enum). Default is `UNVERIFIED`.
  - `confidence_vector`: Multi-dimensional confidence vector (`factual_grounding`, `source_authority`, `linguistic_certainty`, `consensus_level`).
  - `tenant_id`: Multi-tenant organization boundary identifier.

### 2.2 `Entity`
- **Purpose**: A recognized financial entity extracted from content.
- **Key Fields**:
  - `entity_id`: Unique identifier.
  - `content_id`: Foreign key linking to parent `ContentItem`.
  - `entity_type`: `sebi_reg`, `cin`, `upi_vpa`, `telegram_channel`, `whatsapp_group`, `regulator`, `exchange`, `broker`, `bank`, or `domain`.
  - `name`: Extracted or canonical name.
  - `identifier`: Extracted unique identifier (e.g. `INZ000000123`, `L67120MH1995PLC089632`, `zerodha.com`).
  - `verification_status`: Status of the entity in authoritative registries (`ACTIVE`, `EXPIRED`, `CANCELLED`, `SUSPENDED`, `UNREGISTERED`).

### 2.3 `Source`
- **Purpose**: An authoritative registry, database, or institutional repository.
- **Key Fields**:
  - `source_id`: Unique string identifier (e.g. `src_sebi_intermediaries`, `src_mca_registry`, `src_sebi_circulars`, `src_official_domains`).
  - `name`: Human-readable name.
  - `source_tier`: `SourceTier` enum (`T0_REGULATOR`, `T1_SRO_EXCHANGE`, `T2_DEPOSITORY`, `T3_LISTED_ENTITY`, `T4_REPUTABLE_MEDIA`, `T5_USER_SUBMITTED`).
  - `reliability_score`: Float between 0.0 and 1.0 (Tier 0 = 1.0).
  - `is_authoritative`: Boolean flag (True for T0-T2).

### 2.4 `Evidence`
- **Purpose**: An immutable piece of factual data retrieved from an authoritative source.
- **Key Fields**:
  - `evidence_id`: Unique identifier (UUID4 format).
  - `claim_id`: Linked claim identifier.
  - `source_id`: Authoritative source identifier.
  - `title`: Descriptive evidence heading.
  - `excerpt`: Verbatim text or structured record retrieved from the authoritative registry.
  - `url_or_identifier`: Source URL, circular reference, or registry certificate number.
  - `content_hash`: SHA3-256 canonical hash of the excerpt and metadata.
  - `confidence_vector`: Multi-dimensional confidence vector.
  - `tenant_id`: Scoped tenant identifier.
  - `source_record_id`: Registry record ID (e.g., member code, DP ID, VPA, certificate number).
  - `source_url`: URL or snapshot reference where the evidence was acquired.
  - `effective_from`: ISO date or timestamp when the record became valid.
  - `effective_until`: ISO date or timestamp when the record expires or was revoked.
  - `evidence_type`: Classification of evidence (`registry_record`, `circular_text`, `whois_record`, `payment_directory`).
  - `provenance`: Dict capturing `source_authority`, `snapshot_version`, `snapshot_hash`, and `retrieved_at`.
  - `raw_value`: Original excerpt string or record dictionary prior to normalization.
  - `normalized_value`: Normalized, canonicalized representation (e.g. lowercase VPA, uppercase CIN).
  - `quality`: Multi-dimensional quality metrics dict (`freshness`, `completeness`, `extraction_confidence`, `authority_tier`).

### 2.5 `Finding`
- **Purpose**: Synthesized factual determination concluding the verification of a claim.
- **Key Fields**:
  - `finding_id`: Unique identifier.
  - `claim_id`: Linked claim identifier.
  - `statement`: Human-readable, evidence-grounded factual determination.
  - `stance`: Final resolved stance (`SUPPORTED`, `CONTRADICTED`, `CONFLICTING`, `OUTDATED`, `INSUFFICIENT_EVIDENCE`).
  - `reasoning`: Detailed explanation linking evidence excerpts to the determination.
  - `confidence_vector`: Composite multi-dimensional confidence.
  - `verification_version`: Schema and engine version (default `"1.0"`).
  - `tenant_id`: Scoped tenant identifier.

### 2.6 `TrustReceipt`
- **Purpose**: Cryptographic proof anchoring verification findings to an ML-DSA-65 post-quantum digital signature.
- **Key Fields**:
  - `receipt_id`: Unique receipt identifier (`tr_...`).
  - `target_id`: Linked finding identifier.
  - `target_type`: `"finding_verification"`.
  - `payload_digest`: SHA3-256 digest of the canonical verification JSON payload.
  - `signature_algorithm`: `"ML-DSA-65"`.
  - `signature_bytes`: Post-quantum digital signature.
  - `public_key_bytes`: Public verification key.
  - `signed_at`: ISO 8601 UTC timestamp.
  - `tenant_id`: Scoped tenant identifier.

---

## 3. Subsystem Contracts & Data Structures

The verification subsystem defines two high-level data contracts in `sangyan.verification`:

### 3.1 `AdapterResult` (`sangyan.verification.adapters.base`)
Returned by individual verification adapters:
```python
@dataclass(frozen=True)
class AdapterResult:
    source_id: str
    stance: ClaimStatus
    confidence: float
    title: str
    excerpt: str
    url_or_identifier: str
    metadata: dict[str, Any] = field(default_factory=dict)
```

### 3.2 `VerificationOutcome` (`sangyan.verification.engine`)
Returned by `ClaimVerificationEngine.verify_claims()`:
```python
@dataclass
class VerificationOutcome:
    claim_id: str
    status: str  # SUPPORTED, CONTRADICTED, CONFLICTING, OUTDATED, INSUFFICIENT_EVIDENCE
    finding: Finding
    evidence_items: list[Evidence] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    trust_receipt_id: Optional[str] = None
    adapter_results: list[AdapterResult] = field(default_factory=list)
```

### 3.3 `InvestigationReport` (`sangyan.verification.engine`)
Returned by `ClaimVerificationEngine.verify_content_item()`:
```python
@dataclass
class InvestigationReport:
    content_item: ContentItem
    analysis: AnalysisResult
    outcomes: list[VerificationOutcome]
    investigation: Investigation
    overall_status: str  # "SAFE", "HIGH_RISK", "SUSPICIOUS", "UNVERIFIED"
```


---

## 4. Epistemic Verification Taxonomy

Financial claim verification uses five mutually exclusive stances (`ClaimStatus` enum):

| Stance | Semantic Meaning | Example Trigger |
|---|---|---|
| `SUPPORTED` | Directly corroborated by active authoritative institutional records. | Intermediary registration number matches active broker name in SEBI Intermediaries Registry. |
| `CONTRADICTED` | Explicitly refuted by authoritative records or regulatory circulars. | Registration number not found in registry; claim promises guaranteed returns prohibited by SEBI circular `SEBI/HO/MIRSD/DOS3/CIR/P/2018/140`. |
| `CONFLICTING` | Opposing authoritative sources or records present irreconcilable determinations. | One official registry marks entity as compliant while another issues an active enforcement order. |
| `OUTDATED` | Record was legitimate in the past but has expired, lapsed, or been revoked. | Broker registration `INZ000999999` was valid 2018-2022 but expired without renewal. |
| `INSUFFICIENT_EVIDENCE` | No authoritative records exist to definitively support or contradict the claim. | Generic claims with no identifiable entities, registration numbers, or regulatory assertions. |

---

## 5. Security & Isolation Guarantees

1. **Adversarial Brand-Spoofing Override**:
   If content mentions a recognized broker brand (e.g. "Zerodha") but specifies an invalid or bogus registration number (e.g. `INZ000000000`), the adapter strictly marks the claim as `CONTRADICTED`. Exact registration refutation overrides fuzzy name matches.

2. **Tamper-Evident Post-Quantum Signatures**:
   The verification payload canonicalizes `finding_id`, `claim_id`, `stance`, `finding_statement`, `confidence_vector`, `evidence_hashes`, `verified_at`, and `tenant_id`. Any alteration of finding statements or evidence invalidates the ML-DSA-65 signature.

3. **Multi-Tenant Isolation**:
   All database writes for `Evidence`, `Finding`, and `TrustReceipt` enforce tenant scoping through `TenantRepository`. Queries across tenants are strictly rejected.

4. **Multi-Domain Threat Precedence**:
   When content contains multiple URLs or domains (e.g. an attacker prepending `https://sebi.gov.in` before a phishing URL `http://zerodha-profit.cc`), the domain adapter evaluates all candidates and gives malicious lookalike domains and suspicious TLDs strict precedence, emitting `CONTRADICTED`.

5. **Disclaimer Evasion Defense**:
   Prohibited practice evaluations (guaranteed returns, OTP demands, fee demands) take precedence over general statutory disclaimers. A scammer cannot bypass regulatory prohibition simply by appending "subject to market risks".

6. **Fault-Resilient Adapter Isolation**:
   Exceptions thrown during adapter execution are contained per adapter, logging `source_unavailable` or `error` outcomes without crashing the pipeline. In-memory caching and rate limiting are fully thread-safe.

7. **Tamper-Evident Chained Audit Ledger**:
   All verification actions automatically append to a tenant-scoped audit ledger. Each `AuditEvent` links to its predecessor via SHA3-256 hash chaining. Any retrospective deletion, modification, or reordering of audit events breaks the cryptographic chain and is immediately detectable.

8. **Section 40 Mandatory Absence-of-Evidence Safeguard**:
   For claims resolved as `INSUFFICIENT_EVIDENCE`, human inspection views prominently render the mandatory statutory notice:
   *"Absence of evidence is not proof of fraud or non-compliance. Verification was unable to locate authoritative regulatory records for the specified identifiers within available registries."*

---

## 6. Phase 4 Investigation Correlation & Guidance Models

Phase 4 introduces multi-content correlation, scam-chain lifecycle reconstruction, grievance classification, and explainability contracts.

### 6.1 `CorrelationEdge` (`sangyan.domain.models`)
- **Purpose**: Represents a typed, weighted relationship connecting two nodes (entities, claims, signals, or content items) within an investigation graph.
- **Key Fields**:
  - `edge_id`: Unique identifier (`edge_...`).
  - `investigation_id`: Parent investigation ID.
  - `source_node_id` & `target_node_id`: Connected node identifiers.
  - `relationship_type`: `SHARED_ENTITY`, `SHARED_PAYMENT`, `SHARED_CONTACT`, `SHARED_INFRASTRUCTURE`, `COMMON_PATTERN`, `TEMPORAL_SEQUENCE`, `CLAIM_LINK`, `ENTITY_LINK`.
  - `strength`: `STRONG`, `MEDIUM`, `WEAK`.
  - `evidence_ids`: List of supporting evidence IDs justifying the link.
  - `confidence`: Confidence float (0.0 to 1.0).
  - `tenant_id`: Multi-tenant boundary.

### 6.2 `InvestigationStage` (`sangyan.domain.models`)
- **Purpose**: Represents the status and evidence for one of the 12 lifecycle stages in a scam chain.
- **Key Fields**:
  - `stage_id`: Unique identifier (`stg_...`).
  - `investigation_id`: Parent investigation ID.
  - `stage_name`: One of the 12 canonical stages (`LURE_FIRST_CONTACT` through `SECONDARY_RECOVERY_SCAM`).
  - `status`: `OBSERVED`, `SUPPORTED`, `INFERRED`, `NOT_OBSERVED`, `UNKNOWN`.
  - `observed_at`: ISO timestamp when detected.
  - `evidence_ids`: Authoritative evidence identifiers corroborating the stage.
  - `notes`: Human-readable context and rationale.
  - `tenant_id`: Multi-tenant boundary.

### 6.3 `GrievanceRecord` (`sangyan.domain.models`)
- **Purpose**: Tracks an investor's problem classification and authoritative institutional filing guidance.
- **Key Fields**:
  - `grievance_id`: Unique identifier (`grv_...`).
  - `investigation_id`: Parent investigation ID.
  - `category`: Problem category (`UNREGISTERED_INTERMEDIARY_SEBI`, `INVESTOR_FRAUD_CYBERCRIME`, `BANKING_PAYMENT_FAILURE_RBI`, `TELECOM_SPAM_PHISHING_CHAKSHU`, etc.).
  - `target_portal`: Official statutory destination (`Cybercrime Portal (cybercrime.gov.in / 1930)`, `SEBI SCORES 2.0 (scores.sebi.gov.in)`, `RBI CMS (cms.rbi.org.in)`, `DoT Chakshu (sancharsaathi.gov.in)`).
  - `status`: Lifecycle state (`DRAFT`, `READY`, `FILED`, `RESOLVED`).
  - `filing_checklist`: Structured list of documents and forensic artifacts required for submission.
  - `filing_dossier`: Pre-filled JSON payload containing incident facts and evidence references.
  - `tenant_id`: Multi-tenant boundary.

### 6.4 `InvestigationExplanation` (`sangyan.domain.models`)
- **Purpose**: Epistemic explanation answering "Why was this flagged?" with mandatory uncertainty disclosure.
- **Key Fields**:
  - `explanation_id`: Unique identifier.
  - `investigation_id`: Parent investigation ID.
  - `overall_narrative`: Comprehensive summary of findings.
  - `why_flagged`: Bullet-pointed list of observable signals, contradictory evidence, and syndicate links.
  - `evidence_links`: Dict mapping finding/claim IDs to authoritative evidence citations.
  - `what_we_dont_know`: Explicit list of unverified assertions, missing evidence, and unconfirmed entities.
  - `abstention_reasons`: Explicit justifications for why certain conclusions could not be drawn.

### 6.5 `CorrelatedInvestigationReport` (`sangyan.correlation.orchestrator`)
- **Purpose**: End-to-end multi-content investigative dossier signed with post-quantum cryptography.
- **Key Fields**:
  - `investigation`: Root `Investigation` domain object.
  - `content_items`: List of analyzed `ContentItem` objects.
  - `outcomes`: List of claim-level `VerificationOutcome` objects.
  - `correlations`: List of `CorrelationEdge` objects.
  - `scam_patterns`: List of matched `SCAM_TAXONOMY_PATTERNS`.
  - `scam_chain_stages`: List of `InvestigationStage` objects.
  - `guidance`: `SafeGuidanceResponse` containing urgent actions, checklists, and safe next steps.
  - `grievance_record`: Generated `GrievanceRecord` for official portal submission.
  - `explanation`: `InvestigationExplanation` with explicit abstentions.
  - `trust_receipt`: Cryptographically signed `TrustReceipt` using ML-DSA-65.

---

## 7. Database Migration 002 Schema Expansion

Migration 002 (`sangyan/database/migrations.py`) registers three dedicated tables:

1. `sangyan_correlations`:
   - `edge_id` (PK, TEXT)
   - `investigation_id` (TEXT, NOT NULL)
   - `organization_id` (TEXT, NOT NULL)
   - `source_node_id` (TEXT, NOT NULL)
   - `target_node_id` (TEXT, NOT NULL)
   - `relationship_type` (TEXT, NOT NULL)
   - `strength` (TEXT, NOT NULL)
   - `confidence` (REAL, NOT NULL)
   - `evidence_ids` (TEXT, JSON array)
   - `metadata` (TEXT, JSON object)
   - `created_at` (TEXT, ISO-8601)
   - Scoped indexes on `(organization_id, investigation_id)` and `(organization_id, target_node_id)`.

2. `sangyan_scam_chain_stages`:
   - `stage_id` (PK, TEXT)
   - `investigation_id` (TEXT, NOT NULL)
   - `organization_id` (TEXT, NOT NULL)
   - `stage_name` (TEXT, NOT NULL)
   - `status` (TEXT, NOT NULL)
   - `observed_at` (TEXT)
   - `evidence_ids` (TEXT, JSON array)
   - `notes` (TEXT)
   - `metadata` (TEXT, JSON object)
   - `created_at` (TEXT, ISO-8601)
   - Scoped index on `(organization_id, investigation_id)`.

3. `sangyan_grievance_records`:
   - `grievance_id` (PK, TEXT)
   - `investigation_id` (TEXT, NOT NULL)
   - `organization_id` (TEXT, NOT NULL)
   - `category` (TEXT, NOT NULL)
   - `target_portal` (TEXT, NOT NULL)
   - `status` (TEXT, NOT NULL)
   - `filing_checklist` (TEXT, JSON array)
   - `filing_dossier` (TEXT, JSON object)
   - `created_at` (TEXT, ISO-8601)
   - `updated_at` (TEXT, ISO-8601)
   - Scoped index on `(organization_id, investigation_id)`.

---

## 8. Phase 5 Workflow Orchestration, State & Checkpoint Models

Phase 5 introduces LangGraph StateGraph durable orchestration, human-in-the-loop supervisory review gates, and Migration 003 workflow execution tracking.

### 8.1 `InvestigationWorkflowState` (`sangyan.workflow.state`)
Typed orchestration state dictionary tracking execution progression without duplicating or replacing relational persistence:
- **Core Identifiers**: `organization_id`, `investigation_id`, `user_id`, `run_id`, `thread_id` (`<org>:<inv>:<run>`).
- **Domain State Collections**:
  - `content_items` & `content_item_ids`
  - `claims` & `claim_ids`
  - `entities` & `entity_ids`
  - `signals` & `signal_ids`
  - `findings` & `finding_ids`
  - `evidence_items` & `evidence_ids`
  - `correlations` & `correlation_ids`
  - `scam_chain`
  - `scam_patterns`
  - `guidance` & `guidance_ids`
  - `grievance`
  - `explanation`
- **Epistemic & Execution Flags**:
  - `risk_posture`: `SAFE`, `HIGH_RISK`, `SUSPICIOUS`, `UNVERIFIED`.
  - `is_educational_warning`: Boolean suppressing false positives on regulatory caution circulars.
  - `review_required`: Boolean indicating whether human supervisory review is necessary.
  - `review_reason`: Justification for pausing at the review gate.
  - `review_decision`: Supervisor decision payload committed during resumption.
  - `trust_receipt_id`: Post-quantum ML-DSA-65 signed receipt pointer.
  - `trust_status`: `FINALIZED`, `FAILED`, `PENDING`.
  - `status`: `INTAKE`, `ANALYZING`, `VERIFYING`, `CORRELATING`, `AWAITING_REVIEW`, `FINALIZING`, `COMPLETED`, `PARTIALLY_COMPLETED`, `FAILED`, `CANCELLED`.
  - `current_stage`: Current graph node name.
  - `errors` & `warnings`: Diagnostic execution messages.

### 8.2 `WorkflowRun` (`sangyan.domain.models`)
Relational execution ledger representing one execution of a StateGraph for an investigation:
```python
@dataclass
class WorkflowRun:
    id: str = field(default_factory=lambda: new_id("wfr"))
    organization_id: str
    investigation_id: str
    thread_id: str                          # Canonical: <org_id>:<investigation_id>:<run_id>
    run_id: str
    status: str = "RUNNING"                 # RUNNING, AWAITING_REVIEW, COMPLETED, FAILED, CANCELLED, PARTIALLY_COMPLETED
    current_node: str = "intake_node"
    retry_count: int = 0
    checkpoint_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    schema_version: int = CURRENT_SCHEMA_VERSION
```

### 8.3 Migration 003 Schema Expansion
Migration 003 (`sangyan/database/migrations.py`) registers the `sangyan_workflow_runs` relational table:
```sql
CREATE TABLE IF NOT EXISTS sangyan_workflow_runs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    investigation_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    status TEXT NOT NULL,
    current_node TEXT NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    checkpoint_id TEXT,
    metadata TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (investigation_id) REFERENCES sangyan_investigations(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_org_inv ON sangyan_workflow_runs(organization_id, investigation_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_thread ON sangyan_workflow_runs(organization_id, thread_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON sangyan_workflow_runs(organization_id, status);
```

### 8.4 Checkpointing & Tenant Boundary Semantics
- **Durable Checkpointing**: Powered by LangGraph `SqliteSaver` in WAL mode, ensuring execution state survives abrupt worker termination, process crashes, and prolonged review interruptions.
- **Thread Identity Validation**: Canonical format `<organization_id>:<investigation_id>:<run_id>` prevents cross-tenant state access; attempts to read, resume, or cancel across tenants raise `TenantMismatchError` prior to checkpoint deserialization.
- **Human-in-the-Loop Interruption**: Triggered at `review_gate_node` via `interrupt(...)`. The graph halts, serializing in-flight state to SQLite while setting investigation and run status to `AWAITING_REVIEW`.
- **Epistemic Concurrency**: First valid review decision wins under investigation locks. Conflicting concurrent review submissions raise `ReviewConflictError`.
- **Role Enforcement**: `sangyan_viewer` role is strictly denied review submission (`PermissionDeniedError`).
- **Post-Quantum Trust Finalization**: ML-DSA-65 post-quantum signing executes after the review gate commits. Re-invoking trust finalization idempotently returns the existing `TrustReceipt`.

---

## 9. Phase 6 Production Security, Authentication & Observability Models

Phase 6 introduces external authentication schemes, hashed machine credentials, multi-tenant RBAC boundaries, token-bucket traffic shaping, and low-cardinality Prometheus telemetry.

### 9.1 `Principal` (`sangyan.security.models`)
Canonical representation of an authenticated calling identity bound at the API gateway layer:
```python
@dataclass(frozen=True)
class Principal:
    principal_id: str                   # User ID or machine client ID
    organization_id: str                # Tenant boundary
    roles: tuple[str, ...] = ("sangyan_viewer",)
    scopes: tuple[str, ...] = ()
    auth_method: str = "jwt"            # jwt | api_key | session | development
    credential_id: Optional[str] = None # API Key ID or JWT JTI
    issued_at: Optional[float] = None
    expires_at: Optional[float] = None

    @property
    def primary_role(self) -> str: ...
    def has_role(self, role: str) -> bool: ...
    def has_permission(self, permission: str) -> bool: ...
```

### 9.2 `ApiKey` (`sangyan.security.models`)
Relational model for hashed machine-to-machine API credentials:
```python
@dataclass
class ApiKey:
    organization_id: str
    user_id: str
    name: str
    key_prefix: str                     # 8-hex character prefix for indexed O(1) lookup
    key_hash: str                       # SHA-256 digest of prefix:secret
    role: str = "sangyan_analyst"       # sangyan_admin | sangyan_analyst | sangyan_viewer
    scopes: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: new_id("key"))
    expires_at: Optional[float] = None
    revoked_at: Optional[float] = None
    last_used_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    schema_version: int = CURRENT_SCHEMA_VERSION

    def is_active(self, now: Optional[float] = None) -> bool: ...
```

### 9.3 `SecurityConfig` (`sangyan.security.models`)
Production configuration for cryptographic JWT validation, allowed algorithms, key lifecycles, and bounds:
```python
@dataclass
class SecurityConfig:
    jwt_secret: str = "..."
    jwt_public_key: Optional[str] = None
    jwt_private_key: Optional[str] = None
    jwt_algorithms: list[str] = field(default_factory=lambda: ["HS256"])  # HS256, RS256, ES256, EdDSA
    jwt_issuer: str = "sangyan-auth"
    jwt_audience: str = "sangyan-api"
    jwt_leeway: int = 30                # RFC 7519 clock skew leeway in seconds
    api_key_prefix: str = "sgy_"
    max_request_body_bytes: int = 2 * 1024 * 1024  # 2 MB request bound
    allowed_origins: list[str] = field(default_factory=lambda: ["*"])
    rate_limit_enabled: bool = True
```

### 9.4 Migration 004 Schema Expansion
Migration 004 (`sangyan/database/migrations.py`) registers the `sangyan_api_keys` relational ledger:
```sql
CREATE TABLE IF NOT EXISTS sangyan_api_keys (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    scopes TEXT NOT NULL DEFAULT '[]',
    expires_at REAL,
    revoked_at REAL,
    last_used_at REAL,
    created_at REAL NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_sangyan_api_keys_org_prefix ON sangyan_api_keys(organization_id, key_prefix);
CREATE INDEX IF NOT EXISTS idx_sangyan_api_keys_prefix ON sangyan_api_keys(key_prefix);
CREATE INDEX IF NOT EXISTS idx_sangyan_api_keys_org ON sangyan_api_keys(organization_id);
```

### 9.5 Gateway Security & Observability Guarantees
1. **Dual External Authentication**: Supports both interactive user sessions (JWT Bearer) and institutional integrations (prefixed hashed API keys: `sgy_<8hex>_<32hex>`).
2. **Mutual Exclusivity**: Presenting both Bearer token and X-API-Key in a single request is rejected with HTTP 400 (`AmbiguousAuthenticationError`).
3. **Cryptographic JWT Hardening**: Enforces RFC 7519 standard claims (`iss`, `aud`, `exp`, `nbf`, `iat`, `sub`, `org_id`), explicit algorithm allowlist, immediate rejection of `alg=none`, and bounded 30s clock skew tolerance.
4. **Hashed API Key Storage**: The plaintext secret is never written to persistent disk; verification uses constant-time HMAC comparison (`hmac.compare_digest`) against SHA-256 digests.
5. **Multi-Tenant Isolation & IDOR Defense**: The caller tenant `principal.organization_id` strictly binds repository operations. Attempts to access foreign-tenant investigations return HTTP 404/403 with zero cross-tenant enumeration.
6. **Token-Bucket Rate Limiting**: Multi-dimensional token buckets per endpoint category (`auth`: 10 req/min, `investigation`: 30 req/min, `workflow_mutate`: 20 req/min, `read`: 120 req/min). Failed authentication attempts trigger IP-level backoff lockout (5 failures -> 429 Retry-After).
7. **Transport Security & Bounds**: Emits defensive headers (`nosniff`, `DENY`, `strict-origin-when-cross-origin`, `CSP`, `Cache-Control: no-store` on API routes), limits body payloads to 2 MB (HTTP 413), and correlates requests via `X-Request-ID`.
8. **Low-Cardinality Prometheus Observability**: Routes are normalized to route templates (`/api/v1/investigations/{id}`) to prevent label explosion. Logs and traces automatically scrub JWT tokens, API keys, private keys, passwords, and OTPs via `redact_sensitive_text`.

---

## 10. Phase 7 Deployment, Configuration & Backup Models

### 10.1 `SangyanConfig` (`sangyan.config`)
Unified production configuration model loading environment variables with strict fail-closed validation:
```python
@dataclass
class SangyanConfig:
    # Environment
    environment: str = "production"     # production | staging | development | test
    debug: bool = False

    # Database & Storage
    database_url: str = "sqlite:////app/data/sangyan.db"
    database_pool_size: int = 5
    database_timeout_seconds: float = 30.0
    checkpoint_db_path: str = "/app/checkpoints/workflow_checkpoints.db"
    backup_dir: str = "/app/backups"
    keys_dir: str = "/app/keys"

    # Server Runtime
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1                    # Strictly 1 in production (single-replica invariant)
    log_level: str = "INFO"

    # Security & Auth
    jwt_secret: str = ""
    jwt_issuer: str = "sangyan-auth"
    jwt_audience: str = "sangyan-api"
    jwt_algorithms: list[str] = field(default_factory=lambda: ["HS256"])
    auth_required: bool = True
    allowed_origins: list[str] = field(default_factory=lambda: [])
    max_request_body_bytes: int = 2 * 1024 * 1024
    rate_limit_enabled: bool = True

    # Backup & Retention
    backup_encryption_password: Optional[str] = None
    backup_retention_days: int = 30

    def validate_production(self, strict: bool = True) -> list[str]: ...
```

**Production Validation Invariants (`validate_production_config`)**:
- **Secret Entropy**: `jwt_secret` must have >= 32 characters (256-bit equivalent).
- **Insecure Secret Rejection**: Known placeholder secrets (`sangyan-dev-secret`, `sangyan-default-secret`, `secret`, `changeme`, `password`) raise immediate validation failure.
- **CORS Boundary**: `allowed_origins` must NOT contain wildcard `*` in production mode.
- **Mandatory Authentication**: `auth_required` cannot be set to `False` in production.
- **Worker Bound**: If SQLite is used as primary or checkpoint DB, `workers` must equal 1.

### 10.2 `BackupMetadata` (`sangyan.database.backup`)
Tamper-evident metadata document generated with each backup snapshot and stored inside `backup_manifest.json`:
```python
@dataclass
class BackupMetadata:
    backup_id: str                      # Format: sangyan_bkp_YYYYMMDD_HHMMSS_ffffff_XXXXXX
    timestamp: str                      # ISO-8601 UTC timestamp
    schema_version: int                 # Active database schema migration version
    checksum_sha256: str                # SHA-256 digest of unencrypted payload
    file_size_bytes: int                # Size in bytes of final archive
    is_encrypted: bool                  # True if AES-256-GCM encrypted
    encryption_algorithm: Optional[str] # "AES-256-GCM" or None
    kdf_algorithm: Optional[str]        # "PBKDF2-HMAC-SHA256" (100,000 iterations)
    kdf_iterations: int = 100000
    files_included: list[str] = field(default_factory=list)
    sangyan_version: str = "0.7.0"

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> "BackupMetadata": ...
```

**Cryptographic Archive Packaging Format (`.enc` container)**:
```text
+-------------------------------------------------------------------------+
| Header (8 bytes): MAGIC 'SGYBKP1\0'                                     |
+-------------------------------------------------------------------------+
| Salt (16 bytes): PBKDF2 cryptographic salt                              |
+-------------------------------------------------------------------------+
| Nonce (12 bytes): AES-256-GCM initialization vector                     |
+-------------------------------------------------------------------------+
| Tag (16 bytes): GCM authentication tag                                  |
+-------------------------------------------------------------------------+
| Ciphertext (variable length): Tarball payload (.tar.gz)                 |
+-------------------------------------------------------------------------+
```

### 10.3 Helm Values Schema Contract (`deploy/helm/sangyan/values.yaml`)
Formally specified in `deploy/helm/sangyan/values.schema.json`:
- `replicaCount`: Integer enum `[1]`. Disallows scaling beyond 1 due to SQLite single-writer semantics and in-process rate limiting.
- `podSecurityContext`: `runAsNonRoot: true`, `runAsUser: 10001`, `runAsGroup: 10001`, `fsGroup: 10001`, `seccompProfile.type: RuntimeDefault`.
- `securityContext`: `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities.drop: ["ALL"]`.
- `persistence`: ReadWriteOnce PVC specifications for `data` (10Gi), `checkpoints` (5Gi), `keys` (1Gi), and `backups` (50Gi).
- `probes`:
  * `livenessProbe`: `httpGet.path: /health/live`, `port: http`, `periodSeconds: 15`.
  * `readinessProbe`: `httpGet.path: /health/ready`, `port: http`, `periodSeconds: 10`.
  * `startupProbe`: `httpGet.path: /health`, `port: http`, `failureThreshold: 30`, `periodSeconds: 2`.
- `backup`: `enabled: true`, `schedule: "0 2 * * *"`, `retentionDays: 30`, `existingSecret: "sangyan-secrets"`.
- `ingress`: TLS enabled, annotations for 2 MB max body size, and location configuration blocking `/metrics` (returns 404).
- `networkPolicy`: `enabled: true`, strictly permits ingress from ingress-controller & Prometheus scraper; limits egress to DNS (53), HTTPS (443), and optional Postgres (5432).

---

## 11. Phase 8 Distributed Production Architecture & Resilience Models

Phase 8 elevates SANGYAN from a single-replica system to a horizontally scalable distributed system with PostgreSQL connection pooling, LangGraph `PostgresSaver` checkpointing, Redis-backed atomic rate limiting and shared failed-auth lockout, offsite encrypted cloud backup replication, and OpenTelemetry distributed tracing.

### 11.1 PostgreSQL Connection Pooling (`PostgresDatabaseEngine`)
Located in `sangyan/database/postgres.py`, backed by `psycopg_pool.ConnectionPool`:
- `min_size`: 2 connections
- `max_size`: 20 connections
- `timeout`: 10.0 seconds
- `max_idle`: 300.0 seconds
- `transaction()`: thread-local connection binding via `threading.local()`, ensuring multi-threaded safety and explicit `COMMIT` / `ROLLBACK`.
- `execute()`: Returns integer rowcount (`cur.rowcount`) for atomic conditional transitions.
- Advisory lock serialization for audit trail: `pg_advisory_xact_lock(918273)` ensures sequential hash chaining.

### 11.2 Distributed Rate Limiter & Failed-Auth Models (`sangyan.security.redis_limiter`)
- **`RedisRateLimiter`**:
  * Distributed token bucket governed by atomic Redis Lua script (`LUA_TOKEN_BUCKET_SCRIPT`).
  * Key namespace: `sangyan:ratelimit:{identifier}:{endpoint_class}`
  * TTL calculation: `max(120, int(capacity / refill_rate * 2))`
  * Failure modes: `fail_closed_mutations` (mutations rejected, reads allowed), `fail_open` (all allowed), `local_fallback` (transparent in-memory fallback).
- **`RedisFailedAuthTracker`**:
  * Sliding-window lockout backed by Redis sorted sets (`ZADD`, `ZREMRANGEBYSCORE`, `ZCARD`).
  * Key namespace: `sangyan:authfail:{client_ip}`
  * Cross-pod lockout: a client locked out on Pod A is immediately throttled across all API pods.

### 11.3 Cloud Backup Replication Models (`sangyan.database.cloud_backup`)
- **`CloudBackupManifest`**:
  * `backup_id`: format `sangyan_bkp_YYYYMMDD_HHMMSS_ffffff_XXXXXX`
  * `cloud_key`: S3 object key (e.g. `backups/sangyan_bkp_...tar.gz.enc`)
  * `sha256`: SHA-256 checksum of the uploaded ciphertext
  * `size_bytes`: length in bytes
  * `encrypted`: boolean (must be `True`)
  * `uploaded_at`: UTC timestamp
  * `dialect`: relational database dialect
- **Pre-Upload Encryption Invariant**:
  * Unencrypted uploads (missing `.enc` suffix or `encrypted=False`) raise immediate `SecurityViolationError` / `ValueError`. Plaintext backups are strictly prohibited from touching cloud object stores.
- **Remote Restore Isolation**:
  * Remote archives downloaded to isolated tempdir, pre-verified against remote checksum, decrypted via AES-256-GCM, unpacked safely with path-traversal guards, and tested with `PRAGMA integrity_check`.

### 11.4 Distributed Tracing & Privacy Guardrails (`sangyan.security.tracing`)
- **`TracingMiddleware`**:
  * Propagates W3C `traceparent` headers across HTTP hops.
  * Sanitizes span attributes (`sanitize_span_attributes`): rejects raw message content, claims, auth tokens, passwords, and PII.
  * Captures only low-cardinality metadata: `http.method`, `http.route`, `http.status_code`, `organization_id`, and `trace_id`.
- **`NoOpTracer`**:
  * Transparent zero-overhead fallback when `tracing_enabled = False`.

### 11.5 Helm Multi-Replica Schema & Manifests
- `deploy/helm/sangyan/values.schema.json`: `replicaCount` relaxed to `minimum: 1` (no upper bound constraint).
- `deploy/helm/sangyan/values-distributed.yaml`: Multi-replica defaults (`replicaCount: 3`, `autoscaling.enabled: true`, `minReplicas: 2`, `maxReplicas: 10`, `targetCPUUtilizationPercentage: 75`).
- `deploy/helm/sangyan/templates/hpa.yaml`: Kubernetes HorizontalPodAutoscaler template.
- `deploy/helm/sangyan/templates/networkpolicy.yaml`: Added egress on port 6379 for Redis cluster access.
- `docker-compose.distributed.yml`: Multi-replica cluster topology with `sangyan-api-1`, `sangyan-api-2`, `sangyan-postgres`, and `sangyan-redis`.





