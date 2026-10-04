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



