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
  - `evidence_id`: Unique identifier.
  - `claim_id`: Linked claim identifier.
  - `source_id`: Authoritative source identifier.
  - `title`: Descriptive evidence heading.
  - `excerpt`: Verbatim text or structured record retrieved from the authoritative registry.
  - `url_or_identifier`: Source URL, circular reference, or registry certificate number.
  - `content_hash`: SHA3-256 canonical hash of the excerpt and metadata.
  - `confidence_vector`: Multi-dimensional confidence vector.
  - `tenant_id`: Scoped tenant identifier.

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

