"""Domain models for SANGYAN Investor Safety & Content Intelligence Platform.

Defines the 10 core domain records:
ContentItem, Claim, Entity, Source, Evidence, Signal, Finding,
ActionGuidance, Investigation, and Review.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from sangyan.domain.base import CURRENT_SCHEMA_VERSION, new_id, require, validate_enum

# ---------------------------------------------------------------------------
# Domain Enums & Constants
# ---------------------------------------------------------------------------

CONTENT_TYPES = ("text", "url", "document", "image")
PROCESSING_STATUSES = ("pending", "processing", "completed", "failed")

CLAIM_TYPES = ("factual", "regulatory", "return", "urgency", "payment", "affiliation", "other")

CLAIM_STATUSES = (
    "SUPPORTED",
    "CONTRADICTED",
    "PARTIALLY_SUPPORTED",
    "UNVERIFIED",
    "CONFLICTING",
    "OUTDATED",
    "INSUFFICIENT_EVIDENCE",
)

ENTITY_TYPES = (
    "BROKER",
    "INVESTMENT_ADVISER",
    "RESEARCH_ANALYST",
    "COMPANY",
    "APP",
    "WEBSITE",
    "PAYMENT_ACCOUNT",
    "UPI",
    "SCHEME",
    "REGULATOR",
    "EXCHANGE",
    "DEPOSITORY",
    "OTHER",
)

AUTHORITY_TIERS = (
    "T0_REGULATOR",           # SEBI, RBI, MCA, Cybercrime Portal, Government
    "T1_INFRASTRUCTURE",      # NSE, BSE, NSDL, CDSL
    "T2_REGISTERED_ENTITY",   # Registered intermediary / primary authoritative entity
    "T3_ESTABLISHED_SECONDARY",# Reputable news / financial press
    "T4_GENERAL_WEB",         # General internet source
    "T5_USER_GENERATED",      # Social media / WhatsApp / Telegram
)

EVIDENCE_STANCES = ("SUPPORTS", "CONTRADICTS", "PARTIAL", "NEUTRAL", "DISCUSSES")

SIGNAL_TYPES = (
    "GUARANTEED_RETURN",
    "HIGH_RETURN_PROMISE",
    "URGENCY",
    "SCARCITY",
    "AUTHORITY_IMPERSONATION",
    "UNREGISTERED_ENTITY",
    "SUSPICIOUS_URL",
    "UNVERIFIED_APP",
    "THIRD_PARTY_PAYMENT",
    "UPI_MISMATCH",
    "SOCIAL_MEDIA_SOLICITATION",
    "WITHDRAWAL_FEE",
    "FAKE_PROFIT",
    "OTP_REQUEST",
    "CREDENTIAL_REQUEST",
    "PRESSURE_LANGUAGE",
    "SECRECY_REQUEST",
    "SOCIAL_PROOF",
    "FEAR_APPEAL",
    "GREED_APPEAL",
)

GUIDANCE_CATEGORIES = (
    "OFFICIAL_VERIFICATION",
    "PRESERVE_EVIDENCE",
    "GRIEVANCE_SCORES",
    "CYBERCRIME_1930",
    "CREDENTIAL_SAFETY",
    "INVESTOR_AWARENESS",
    "WITHDRAWAL_SAFETY",
    "BANKING_PAYMENT_SAFETY",
    "CHAKSHU_REPORTING",
)

RELATIONSHIP_TYPES = (
    "SAME_ENTITY",
    "SAME_UPI",
    "SAME_PHONE",
    "SAME_DOMAIN",
    "SAME_URL",
    "SAME_REGISTRATION",
    "SAME_APP",
    "SHARED_INFRASTRUCTURE",
    "CLAIM_DEPENDENCY",
    "EVIDENCE_SUPPORTS",
    "EVIDENCE_CONTRADICTS",
    "TEMPORALLY_FOLLOWS",
    "PATTERN_MATCH",
)

RELATIONSHIP_STRENGTHS = ("STRONG", "MEDIUM", "WEAK")

SCAM_CHAIN_STAGES = (
    "INITIAL_CONTACT",
    "AUTHORITY_IMPERSONATION",
    "TRUST_BUILDING",
    "INVESTMENT_PROMISE",
    "DEPOSIT_REQUEST",
    "FAKE_PLATFORM",
    "FAKE_PROFIT",
    "WITHDRAWAL_BLOCK",
    "ADDITIONAL_PAYMENT",
    "CREDENTIAL_REQUEST",
    "OTP_REQUEST",
    "DISAPPEARANCE",
)

STAGE_STATUSES = (
    "OBSERVED",
    "SUPPORTED",
    "INFERRED",
    "NOT_OBSERVED",
    "UNKNOWN",
)

SCAM_TAXONOMY_PATTERNS = (
    "INVESTMENT_SCAM",
    "GUARANTEED_RETURN",
    "FAKE_ADVISER",
    "AUTHORITY_IMPERSONATION",
    "UNREGISTERED_INTERMEDIARY",
    "FAKE_TRADING_APP",
    "SOCIAL_MEDIA_SOLICITATION",
    "WITHDRAWAL_FEE_SCAM",
    "THIRD_PARTY_PAYMENT",
    "UPI_IMPERSONATION",
    "PHISHING_CREDENTIAL_THEFT",
    "OTP_THEFT",
    "PONZI_PYRAMID",
    "TASK_SCAM",
)

GRIEVANCE_CATEGORIES = (
    "BROKER_GRIEVANCE",
    "ADVISER_GRIEVANCE",
    "EXCHANGE_GRIEVANCE",
    "DEPOSITORY_GRIEVANCE",
    "BANKING_PAYMENT_ISSUE",
    "CYBER_FRAUD",
    "INVESTMENT_SCAM",
    "INFORMATION_REQUEST",
    "UNKNOWN",
)

INVESTIGATION_STATUSES = (
    "QUEUED",
    "INTAKE",
    "ANALYZING",
    "RETRIEVING",
    "VERIFYING",
    "CORRELATING",
    "AWAITING_REVIEW",
    "FINALIZING",
    "COMPLETED",
    "PARTIALLY_COMPLETED",
    "FAILED",
    "CANCELLED",
)

REVIEW_ACTIONS = ("CONFIRM", "DISMISS", "ESCALATE", "DEFER", "ANNOTATE")


# ---------------------------------------------------------------------------
# Confidence Vector
# ---------------------------------------------------------------------------

@dataclass
class ConfidenceVector:
    """Multi-dimensional confidence vector avoiding false precision."""

    analytical_support: float
    evidence_completeness: float
    source_authority_weight: float
    peer_agreement: Optional[float] = None

    @property
    def overall(self) -> float:
        components = [self.analytical_support, self.evidence_completeness, self.source_authority_weight]
        if self.peer_agreement is not None:
            components.append(self.peer_agreement)
        return round(min(components), 4)

    def validate(self) -> list[str]:
        errors: list[str] = []
        for name, val in [
            ("analytical_support", self.analytical_support),
            ("evidence_completeness", self.evidence_completeness),
            ("source_authority_weight", self.source_authority_weight),
        ]:
            if not (0.0 <= val <= 1.0):
                errors.append(f"{name} must be between 0.0 and 1.0")
        if self.peer_agreement is not None and not (0.0 <= self.peer_agreement <= 1.0):
            errors.append("peer_agreement must be between 0.0 and 1.0")
        return errors

    def to_dict(self) -> dict:
        return {
            "analytical_support": self.analytical_support,
            "evidence_completeness": self.evidence_completeness,
            "source_authority_weight": self.source_authority_weight,
            "peer_agreement": self.peer_agreement,
            "overall": self.overall,
        }

    @classmethod
    def from_dict(cls, d: Any) -> "ConfidenceVector":
        if isinstance(d, ConfidenceVector):
            return d
        return cls(
            analytical_support=float(d["analytical_support"]),
            evidence_completeness=float(d["evidence_completeness"]),
            source_authority_weight=float(d.get("source_authority_weight", 0.5)),
            peer_agreement=float(d["peer_agreement"]) if d.get("peer_agreement") is not None else None,
        )


# ---------------------------------------------------------------------------
# 1. ContentItem
# ---------------------------------------------------------------------------

@dataclass
class ContentItem:
    """The raw submitted material under investigation."""

    content_type: str  # text, url, document, image
    raw_content: str
    organization_id: str
    id: str = field(default_factory=lambda: new_id("content"))
    normalized_text: str = ""
    source_url: str = ""
    content_hash: str = ""
    language: str = "en"
    created_at: float = field(default_factory=time.time)
    processing_status: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.id), "id is required", errors)
        require(bool(self.organization_id), "organization_id is required", errors)
        require(bool(self.raw_content), "raw_content cannot be empty", errors)
        validate_enum(self.content_type, CONTENT_TYPES, "content_type", errors)
        validate_enum(self.processing_status, PROCESSING_STATUSES, "processing_status", errors)
        if self.content_type == "url":
            require(bool(self.source_url or self.raw_content), "source_url is required for URL content", errors)
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "content_type": self.content_type,
            "raw_content": self.raw_content,
            "normalized_text": self.normalized_text,
            "source_url": self.source_url,
            "content_hash": self.content_hash,
            "language": self.language,
            "created_at": self.created_at,
            "processing_status": self.processing_status,
            "metadata": dict(self.metadata),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ContentItem":
        return cls(
            content_type=d["content_type"],
            raw_content=d["raw_content"],
            organization_id=d["organization_id"],
            id=d.get("id") or new_id("content"),
            normalized_text=d.get("normalized_text", ""),
            source_url=d.get("source_url", ""),
            content_hash=d.get("content_hash", ""),
            language=d.get("language", "en"),
            created_at=float(d.get("created_at", time.time())),
            processing_status=d.get("processing_status", "pending"),
            metadata=dict(d.get("metadata", {})),
            schema_version=int(d.get("schema_version", CURRENT_SCHEMA_VERSION)),
        )


# ---------------------------------------------------------------------------
# 2. Claim
# ---------------------------------------------------------------------------

@dataclass
class Claim:
    """An independently evaluable assertion decomposed from submitted content."""

    content_item_id: str
    statement: str
    id: str = field(default_factory=lambda: new_id("claim"))
    claim_type: str = "factual"  # factual, regulatory, return, payment, urgency
    status: str = "UNVERIFIED"
    confidence: Optional[ConfidenceVector] = None
    extracted_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.id), "id is required", errors)
        require(bool(self.content_item_id), "content_item_id is required", errors)
        require(bool(self.statement.strip()), "statement cannot be empty", errors)
        validate_enum(self.status, CLAIM_STATUSES, "status", errors)
        if self.confidence is not None:
            errors.extend(self.confidence.validate())
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content_item_id": self.content_item_id,
            "statement": self.statement,
            "claim_type": self.claim_type,
            "status": self.status,
            "confidence": self.confidence.to_dict() if self.confidence else None,
            "extracted_at": self.extracted_at,
            "metadata": dict(self.metadata),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Claim":
        return cls(
            content_item_id=d["content_item_id"],
            statement=d["statement"],
            id=d.get("id") or new_id("claim"),
            claim_type=d.get("claim_type", "factual"),
            status=d.get("status", "UNVERIFIED"),
            confidence=ConfidenceVector.from_dict(d["confidence"]) if d.get("confidence") else None,
            extracted_at=float(d.get("extracted_at", time.time())),
            metadata=dict(d.get("metadata", {})),
            schema_version=int(d.get("schema_version", CURRENT_SCHEMA_VERSION)),
        )


# ---------------------------------------------------------------------------
# 3. Entity
# ---------------------------------------------------------------------------

@dataclass
class Entity:
    """An external or referenced entity (broker, adviser, company, app, UPI, etc.)."""

    name: str
    entity_type: str
    id: str = field(default_factory=lambda: new_id("entity"))
    aliases: list[str] = field(default_factory=list)
    registration_number: Optional[str] = None
    official_url: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.id), "id is required", errors)
        require(bool(self.name.strip()), "name cannot be empty", errors)
        validate_enum(self.entity_type, ENTITY_TYPES, "entity_type", errors)
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "aliases": list(self.aliases),
            "registration_number": self.registration_number,
            "official_url": self.official_url,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Entity":
        return cls(
            name=d["name"],
            entity_type=d["entity_type"],
            id=d.get("id") or new_id("entity"),
            aliases=list(d.get("aliases", [])),
            registration_number=d.get("registration_number"),
            official_url=d.get("official_url"),
            created_at=float(d.get("created_at", time.time())),
            metadata=dict(d.get("metadata", {})),
            schema_version=int(d.get("schema_version", CURRENT_SCHEMA_VERSION)),
        )


# ---------------------------------------------------------------------------
# 4. Source
# ---------------------------------------------------------------------------

@dataclass
class Source:
    """The origin of evidence with explicit authority tier and freshness timestamps."""

    name: str
    authority_tier: str
    id: str = field(default_factory=lambda: new_id("source"))
    url: Optional[str] = None
    publisher: Optional[str] = None
    published_at: Optional[float] = None
    retrieved_at: float = field(default_factory=time.time)
    valid_until: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.id), "id is required", errors)
        require(bool(self.name.strip()), "name cannot be empty", errors)
        validate_enum(self.authority_tier, AUTHORITY_TIERS, "authority_tier", errors)
        require(self.retrieved_at > 0, "retrieved_at must be positive timestamp", errors)
        if self.published_at is not None and self.valid_until is not None:
            require(self.valid_until >= self.published_at, "valid_until cannot be earlier than published_at", errors)
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "authority_tier": self.authority_tier,
            "url": self.url,
            "publisher": self.publisher,
            "published_at": self.published_at,
            "retrieved_at": self.retrieved_at,
            "valid_until": self.valid_until,
            "metadata": dict(self.metadata),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Source":
        return cls(
            name=d["name"],
            authority_tier=d["authority_tier"],
            id=d.get("id") or new_id("source"),
            url=d.get("url"),
            publisher=d.get("publisher"),
            published_at=float(d["published_at"]) if d.get("published_at") is not None else None,
            retrieved_at=float(d.get("retrieved_at", time.time())),
            valid_until=float(d["valid_until"]) if d.get("valid_until") is not None else None,
            metadata=dict(d.get("metadata", {})),
            schema_version=int(d.get("schema_version", CURRENT_SCHEMA_VERSION)),
        )


# ---------------------------------------------------------------------------
# 5. Evidence
# ---------------------------------------------------------------------------

@dataclass
class Evidence:
    """An observable piece of information supporting or contradicting a claim."""

    source_id: str
    claim_id: str
    excerpt: str
    id: str = field(default_factory=lambda: new_id("evid"))
    structured_fact: dict[str, Any] = field(default_factory=dict)
    stance: str = "NEUTRAL"
    relevance: float = 1.0
    content_hash: str = ""
    retrieved_at: float = field(default_factory=time.time)
    published_at: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = CURRENT_SCHEMA_VERSION

    @property
    def tenant_id(self) -> str:
        return self.metadata.get("tenant_id", "")

    @tenant_id.setter
    def tenant_id(self, val: str) -> None:
        self.metadata["tenant_id"] = val

    @property
    def source_record_id(self) -> str:
        return self.metadata.get("source_record_id", "")

    @source_record_id.setter
    def source_record_id(self, val: str) -> None:
        self.metadata["source_record_id"] = val

    @property
    def source_url(self) -> str:
        return self.metadata.get("source_url", "")

    @source_url.setter
    def source_url(self, val: str) -> None:
        self.metadata["source_url"] = val

    @property
    def effective_from(self) -> Optional[float]:
        return self.metadata.get("effective_from")

    @effective_from.setter
    def effective_from(self, val: Optional[float]) -> None:
        self.metadata["effective_from"] = val

    @property
    def effective_until(self) -> Optional[float]:
        return self.metadata.get("effective_until")

    @effective_until.setter
    def effective_until(self, val: Optional[float]) -> None:
        self.metadata["effective_until"] = val

    @property
    def evidence_type(self) -> str:
        return self.metadata.get("evidence_type", "REGISTRY_RECORD")

    @evidence_type.setter
    def evidence_type(self, val: str) -> None:
        self.metadata["evidence_type"] = val

    @property
    def provenance(self) -> str:
        return self.metadata.get("provenance", "STATUTORY_REGISTRY_SNAPSHOT")

    @provenance.setter
    def provenance(self, val: str) -> None:
        self.metadata["provenance"] = val

    @property
    def raw_value(self) -> str:
        return self.metadata.get("raw_value", "")

    @raw_value.setter
    def raw_value(self, val: str) -> None:
        self.metadata["raw_value"] = val

    @property
    def normalized_value(self) -> str:
        return self.metadata.get("normalized_value", "")

    @normalized_value.setter
    def normalized_value(self, val: str) -> None:
        self.metadata["normalized_value"] = val

    @property
    def verification_metadata(self) -> dict[str, Any]:
        return self.metadata

    @property
    def quality(self) -> dict[str, float]:
        """Multi-dimensional evidence quality: authority, freshness, directness, specificity, completeness."""
        return self.metadata.get(
            "quality",
            {
                "authority": 1.0 if self.source_id.startswith("src_sebi") or self.source_id.startswith("src_mca") else 0.9,
                "freshness": 0.95,
                "directness": 1.0 if self.stance in {"SUPPORTS", "CONTRADICTS"} else 0.5,
                "specificity": 0.95 if self.structured_fact else 0.8,
                "completeness": 0.9,
            },
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.id), "id is required", errors)
        require(bool(self.source_id), "source_id is required", errors)
        require(bool(self.claim_id), "claim_id is required", errors)
        require(bool(self.excerpt.strip()), "excerpt cannot be empty", errors)
        validate_enum(self.stance, EVIDENCE_STANCES, "stance", errors)
        require(0.0 <= self.relevance <= 1.0, "relevance must be between 0.0 and 1.0", errors)
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "claim_id": self.claim_id,
            "excerpt": self.excerpt,
            "structured_fact": dict(self.structured_fact),
            "stance": self.stance,
            "relevance": self.relevance,
            "content_hash": self.content_hash,
            "retrieved_at": self.retrieved_at,
            "published_at": self.published_at,
            "metadata": dict(self.metadata),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Evidence":
        return cls(
            source_id=d["source_id"],
            claim_id=d["claim_id"],
            excerpt=d["excerpt"],
            id=d.get("id") or new_id("evid"),
            structured_fact=dict(d.get("structured_fact", {})),
            stance=d.get("stance", "NEUTRAL"),
            relevance=float(d.get("relevance", 1.0)),
            content_hash=d.get("content_hash", ""),
            retrieved_at=float(d.get("retrieved_at", time.time())),
            published_at=float(d["published_at"]) if d.get("published_at") is not None else None,
            metadata=dict(d.get("metadata", {})),
            schema_version=int(d.get("schema_version", CURRENT_SCHEMA_VERSION)),
        )



# ---------------------------------------------------------------------------
# 6. Signal
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    """An observable property or persuasion signal (NOT standalone proof of fraud)."""

    content_item_id: str
    signal_type: str
    excerpt: str
    id: str = field(default_factory=lambda: new_id("sig"))
    detection_basis: str = ""
    confidence: float = 1.0
    observed_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.id), "id is required", errors)
        require(bool(self.content_item_id), "content_item_id is required", errors)
        validate_enum(self.signal_type, SIGNAL_TYPES, "signal_type", errors)
        require(bool(self.excerpt.strip()), "excerpt cannot be empty", errors)
        require(0.0 <= self.confidence <= 1.0, "confidence must be between 0.0 and 1.0", errors)
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content_item_id": self.content_item_id,
            "signal_type": self.signal_type,
            "excerpt": self.excerpt,
            "detection_basis": self.detection_basis,
            "confidence": self.confidence,
            "observed_at": self.observed_at,
            "metadata": dict(self.metadata),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Signal":
        return cls(
            content_item_id=d["content_item_id"],
            signal_type=d["signal_type"],
            excerpt=d["excerpt"],
            id=d.get("id") or new_id("sig"),
            detection_basis=d.get("detection_basis", ""),
            confidence=float(d.get("confidence", 1.0)),
            observed_at=float(d.get("observed_at", time.time())),
            metadata=dict(d.get("metadata", {})),
            schema_version=int(d.get("schema_version", CURRENT_SCHEMA_VERSION)),
        )


# ---------------------------------------------------------------------------
# 7. Finding
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """Structured analytical conclusion tied to evidence and claims."""

    claim_id: str
    statement: str
    status: str
    id: str = field(default_factory=lambda: new_id("find"))
    confidence: Optional[ConfidenceVector] = None
    evidence_refs: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    rationale: str = ""
    limitations: str = ""
    generated_at: float = field(default_factory=time.time)
    verification_version: str = "1.0"
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.id), "id is required", errors)
        require(bool(self.claim_id), "claim_id is required", errors)
        require(bool(self.statement.strip()), "statement cannot be empty", errors)
        validate_enum(self.status, CLAIM_STATUSES, "status", errors)
        if self.status in {"SUPPORTED", "CONTRADICTED"}:
            require(bool(self.evidence_refs), f"status {self.status} requires at least one evidence_ref", errors)
        if self.confidence is not None:
            errors.extend(self.confidence.validate())
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "claim_id": self.claim_id,
            "statement": self.statement,
            "status": self.status,
            "confidence": self.confidence.to_dict() if self.confidence else None,
            "evidence_refs": list(self.evidence_refs),
            "source_refs": list(self.source_refs),
            "rationale": self.rationale,
            "limitations": self.limitations,
            "generated_at": self.generated_at,
            "verification_version": self.verification_version,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        return cls(
            claim_id=d["claim_id"],
            statement=d["statement"],
            status=d["status"],
            id=d.get("id") or new_id("find"),
            confidence=ConfidenceVector.from_dict(d["confidence"]) if d.get("confidence") else None,
            evidence_refs=list(d.get("evidence_refs", [])),
            source_refs=list(d.get("source_refs", [])),
            rationale=d.get("rationale", ""),
            limitations=d.get("limitations", ""),
            generated_at=float(d.get("generated_at", time.time())),
            verification_version=d.get("verification_version", "1.0"),
            schema_version=int(d.get("schema_version", CURRENT_SCHEMA_VERSION)),
        )


# ---------------------------------------------------------------------------
# 8. ActionGuidance
# ---------------------------------------------------------------------------

@dataclass
class ActionGuidance:
    """Safe, non-investment next steps for investor protection and grievance escalation."""

    category: str
    title: str
    description: str
    id: str = field(default_factory=lambda: new_id("action"))
    official_url: Optional[str] = None
    priority: int = 1  # 1 (high/immediate) to 5 (educational)
    urgency: bool = False
    limitations: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.id), "id is required", errors)
        require(bool(self.title.strip()), "title cannot be empty", errors)
        require(bool(self.description.strip()), "description cannot be empty", errors)
        validate_enum(self.category, GUIDANCE_CATEGORIES, "category", errors)
        require(1 <= self.priority <= 5, "priority must be between 1 and 5", errors)
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "official_url": self.official_url,
            "priority": self.priority,
            "urgency": self.urgency,
            "limitations": self.limitations,
            "metadata": dict(self.metadata),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ActionGuidance":
        return cls(
            category=d["category"],
            title=d["title"],
            description=d["description"],
            id=d.get("id") or new_id("action"),
            official_url=d.get("official_url"),
            priority=int(d.get("priority", 1)),
            urgency=bool(d.get("urgency", False)),
            limitations=d.get("limitations", ""),
            metadata=dict(d.get("metadata", {})),
            schema_version=int(d.get("schema_version", CURRENT_SCHEMA_VERSION)),
        )


# ---------------------------------------------------------------------------
# 9. Investigation
# ---------------------------------------------------------------------------

@dataclass
class Investigation:
    """Aggregated lifecycle envelope binding claims, entities, signals, findings, and guidance."""

    organization_id: str
    user_id: str
    content_item_id: str
    id: str = field(default_factory=lambda: new_id("inv"))
    claim_ids: list[str] = field(default_factory=list)
    entity_ids: list[str] = field(default_factory=list)
    signal_ids: list[str] = field(default_factory=list)
    finding_ids: list[str] = field(default_factory=list)
    guidance_ids: list[str] = field(default_factory=list)
    status: str = "QUEUED"
    summary: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    trust_receipt_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.id), "id is required", errors)
        require(bool(self.organization_id), "organization_id is required", errors)
        require(bool(self.user_id), "user_id is required", errors)
        require(bool(self.content_item_id), "content_item_id is required", errors)
        validate_enum(self.status, INVESTIGATION_STATUSES, "status", errors)
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "content_item_id": self.content_item_id,
            "claim_ids": list(self.claim_ids),
            "entity_ids": list(self.entity_ids),
            "signal_ids": list(self.signal_ids),
            "finding_ids": list(self.finding_ids),
            "guidance_ids": list(self.guidance_ids),
            "status": self.status,
            "summary": self.summary,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "trust_receipt_id": self.trust_receipt_id,
            "metadata": dict(self.metadata),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Investigation":
        return cls(
            organization_id=d["organization_id"],
            user_id=d["user_id"],
            content_item_id=d["content_item_id"],
            id=d.get("id") or new_id("inv"),
            claim_ids=list(d.get("claim_ids", [])),
            entity_ids=list(d.get("entity_ids", [])),
            signal_ids=list(d.get("signal_ids", [])),
            finding_ids=list(d.get("finding_ids", [])),
            guidance_ids=list(d.get("guidance_ids", [])),
            status=d.get("status", "QUEUED"),
            summary=d.get("summary", ""),
            created_at=float(d.get("created_at", time.time())),
            completed_at=float(d["completed_at"]) if d.get("completed_at") is not None else None,
            trust_receipt_id=d.get("trust_receipt_id"),
            metadata=dict(d.get("metadata", {})),
            schema_version=int(d.get("schema_version", CURRENT_SCHEMA_VERSION)),
        )


# ---------------------------------------------------------------------------
# 10. Review
# ---------------------------------------------------------------------------

@dataclass
class Review:
    """Authenticated human review action over an investigation or specific finding."""

    investigation_id: str
    reviewer_id: str
    action: str
    id: str = field(default_factory=lambda: new_id("rev"))
    finding_id: Optional[str] = None
    reason: str = ""
    occurred_at: float = field(default_factory=time.time)
    previous_revision_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.id), "id is required", errors)
        require(bool(self.investigation_id), "investigation_id is required", errors)
        require(bool(self.reviewer_id), "reviewer_id is required", errors)
        validate_enum(self.action, REVIEW_ACTIONS, "action", errors)
        require(self.occurred_at > 0, "occurred_at must be positive timestamp", errors)
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "investigation_id": self.investigation_id,
            "reviewer_id": self.reviewer_id,
            "action": self.action,
            "finding_id": self.finding_id,
            "reason": self.reason,
            "occurred_at": self.occurred_at,
            "previous_revision_id": self.previous_revision_id,
            "metadata": dict(self.metadata),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Review":
        return cls(
            investigation_id=d["investigation_id"],
            reviewer_id=d["reviewer_id"],
            action=d["action"],
            id=d.get("id") or new_id("rev"),
            finding_id=d.get("finding_id"),
            reason=d.get("reason", ""),
            occurred_at=float(d.get("occurred_at", time.time())),
            metadata=dict(d.get("metadata", {})),
            schema_version=int(d.get("schema_version", CURRENT_SCHEMA_VERSION)),
        )


# ---------------------------------------------------------------------------
# 11. AuditEvent
# ---------------------------------------------------------------------------

@dataclass
class AuditEvent:
    """Tamper-evident record of a system, analyst, or verification operation."""

    event_id: str
    actor: str
    action: str
    resource: str
    result: str
    id: str = field(default_factory=lambda: new_id("audit"))
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    ledger_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "result": self.result,
            "metadata": dict(self.metadata),
            "ledger_hash": self.ledger_hash,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AuditEvent":
        return cls(
            event_id=d["event_id"],
            actor=d["actor"],
            action=d["action"],
            resource=d["resource"],
            result=d["result"],
            id=d.get("id") or new_id("audit"),
            timestamp=float(d.get("timestamp", time.time())),
            metadata=dict(d.get("metadata", {})),
            ledger_hash=d.get("ledger_hash", ""),
        )


# ---------------------------------------------------------------------------
# 12. CorrelationEdge
# ---------------------------------------------------------------------------

@dataclass
class CorrelationEdge:
    """Explicit, directional, and explainable relationship between investigative nodes."""

    organization_id: str
    investigation_id: str
    source_id: str
    source_type: str
    target_id: str
    target_type: str
    relationship_type: str
    strength: str
    rationale: str
    id: str = field(default_factory=lambda: new_id("corr"))
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.id), "id is required", errors)
        require(bool(self.organization_id), "organization_id is required", errors)
        require(bool(self.investigation_id), "investigation_id is required", errors)
        require(bool(self.source_id), "source_id is required", errors)
        require(bool(self.target_id), "target_id is required", errors)
        require(bool(self.rationale.strip()), "rationale cannot be empty", errors)
        validate_enum(self.relationship_type, RELATIONSHIP_TYPES, "relationship_type", errors)
        validate_enum(self.strength, RELATIONSHIP_STRENGTHS, "strength", errors)
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "investigation_id": self.investigation_id,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "target_id": self.target_id,
            "target_type": self.target_type,
            "relationship_type": self.relationship_type,
            "strength": self.strength,
            "rationale": self.rationale,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CorrelationEdge":
        return cls(
            organization_id=d["organization_id"],
            investigation_id=d["investigation_id"],
            source_id=d["source_id"],
            source_type=d["source_type"],
            target_id=d["target_id"],
            target_type=d["target_type"],
            relationship_type=d["relationship_type"],
            strength=d["strength"],
            rationale=d["rationale"],
            id=d.get("id") or new_id("corr"),
            metadata=dict(d.get("metadata", {})),
            created_at=float(d.get("created_at", time.time())),
        )


# ---------------------------------------------------------------------------
# 13. InvestigationStage
# ---------------------------------------------------------------------------

@dataclass
class InvestigationStage:
    """Scam-chain progression stage with strict evidentiary provenance."""

    organization_id: str
    investigation_id: str
    stage: str
    status: str
    id: str = field(default_factory=lambda: new_id("stg"))
    evidence_refs: list[str] = field(default_factory=list)
    signal_refs: list[str] = field(default_factory=list)
    details: str = ""
    sequence_order: int = 0
    created_at: float = field(default_factory=time.time)

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.id), "id is required", errors)
        require(bool(self.organization_id), "organization_id is required", errors)
        require(bool(self.investigation_id), "investigation_id is required", errors)
        validate_enum(self.stage, SCAM_CHAIN_STAGES, "stage", errors)
        validate_enum(self.status, STAGE_STATUSES, "status", errors)
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "investigation_id": self.investigation_id,
            "stage": self.stage,
            "status": self.status,
            "evidence_refs": list(self.evidence_refs),
            "signal_refs": list(self.signal_refs),
            "details": self.details,
            "sequence_order": self.sequence_order,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "InvestigationStage":
        return cls(
            organization_id=d["organization_id"],
            investigation_id=d["investigation_id"],
            stage=d["stage"],
            status=d["status"],
            id=d.get("id") or new_id("stg"),
            evidence_refs=list(d.get("evidence_refs", [])),
            signal_refs=list(d.get("signal_refs", [])),
            details=d.get("details", ""),
            sequence_order=int(d.get("sequence_order", 0)),
            created_at=float(d.get("created_at", time.time())),
        )


# ---------------------------------------------------------------------------
# 14. GrievanceRecord
# ---------------------------------------------------------------------------

@dataclass
class GrievanceRecord:
    """Official grievance routing determination with institutional channels and steps."""

    organization_id: str
    investigation_id: str
    category: str
    routing_channel: str
    id: str = field(default_factory=lambda: new_id("grv"))
    portal_url: Optional[str] = None
    helpline: Optional[str] = None
    guidance_steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.id), "id is required", errors)
        require(bool(self.organization_id), "organization_id is required", errors)
        require(bool(self.investigation_id), "investigation_id is required", errors)
        validate_enum(self.category, GRIEVANCE_CATEGORIES, "category", errors)
        require(bool(self.routing_channel.strip()), "routing_channel cannot be empty", errors)
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "investigation_id": self.investigation_id,
            "category": self.category,
            "routing_channel": self.routing_channel,
            "portal_url": self.portal_url,
            "helpline": self.helpline,
            "guidance_steps": list(self.guidance_steps),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GrievanceRecord":
        return cls(
            organization_id=d["organization_id"],
            investigation_id=d["investigation_id"],
            category=d["category"],
            routing_channel=d["routing_channel"],
            id=d.get("id") or new_id("grv"),
            portal_url=d.get("portal_url"),
            helpline=d.get("helpline"),
            guidance_steps=list(d.get("guidance_steps", [])),
            metadata=dict(d.get("metadata", {})),
            created_at=float(d.get("created_at", time.time())),
        )


# ---------------------------------------------------------------------------
# 15. InvestigationExplanation
# ---------------------------------------------------------------------------

@dataclass
class InvestigationExplanation:
    """Human-readable evidentiary explanation separating observable facts from explicit uncertainties."""

    why_flagged: list[str] = field(default_factory=list)
    what_we_do_not_know: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "why_flagged": list(self.why_flagged),
            "what_we_do_not_know": list(self.what_we_do_not_know),
            "limitations": list(self.limitations),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "InvestigationExplanation":
        return cls(
            why_flagged=list(d.get("why_flagged", [])),
            what_we_do_not_know=list(d.get("what_we_do_not_know", [])),
            limitations=list(d.get("limitations", [])),
        )


WORKFLOW_RUN_STATUSES = (
    "RUNNING",
    "AWAITING_REVIEW",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "PARTIALLY_COMPLETED",
)

# ---------------------------------------------------------------------------
# 16. WorkflowRun
# ---------------------------------------------------------------------------

@dataclass
class WorkflowRun:
    """Relational execution record of a LangGraph workflow instance."""

    organization_id: str
    investigation_id: str
    thread_id: str
    run_id: str
    id: str = field(default_factory=lambda: new_id("run"))
    status: str = "RUNNING"
    current_node: str = "intake_node"
    retry_count: int = 0
    checkpoint_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.id), "id is required", errors)
        require(bool(self.organization_id), "organization_id is required", errors)
        require(bool(self.investigation_id), "investigation_id is required", errors)
        require(bool(self.thread_id), "thread_id is required", errors)
        require(bool(self.run_id), "run_id is required", errors)
        validate_enum(self.status, WORKFLOW_RUN_STATUSES, "status", errors)
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "investigation_id": self.investigation_id,
            "thread_id": self.thread_id,
            "run_id": self.run_id,
            "status": self.status,
            "current_node": self.current_node,
            "retry_count": self.retry_count,
            "checkpoint_id": self.checkpoint_id,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WorkflowRun":
        return cls(
            organization_id=d["organization_id"],
            investigation_id=d["investigation_id"],
            thread_id=d["thread_id"],
            run_id=d["run_id"],
            id=d.get("id") or new_id("run"),
            status=d.get("status", "RUNNING"),
            current_node=d.get("current_node", "intake_node"),
            retry_count=int(d.get("retry_count", 0)),
            checkpoint_id=d.get("checkpoint_id"),
            metadata=dict(d.get("metadata", {})),
            created_at=float(d.get("created_at", time.time())),
            updated_at=float(d.get("updated_at", time.time())),
        )


