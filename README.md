# SANGYAN (संज्ञान)
### Investor Safety & Content Intelligence Platform

> **INVESTIGATE → VERIFY → EXPLAIN → PROTECT → GUIDE**

SANGYAN is an evidence-grounded investor safety and content intelligence platform designed to protect Indian retail investors from digital fraud, misleading financial promotions, unregistered entities, and high-risk schemes.

---

## What SANGYAN Does

1. **Intake & Normalization**: Accepts suspicious text, URLs, forwarded messages, screenshots, and documents.
2. **Decomposition**: Breaks compound messages into discrete, independently testable claims.
3. **Signal Detection**: Identifies 20+ observable financial persuasion and scam signals (guaranteed returns, urgency, authority impersonation, withdrawal fees, etc.).
4. **Authoritative Verification**: Queries official regulatory registries (SEBI, recognized exchanges, official circulars) rather than hallucinating status.
5. **Evidence Grounding**: Constructs a transparent evidence graph with explicit multi-valued statuses (`SUPPORTED`, `CONTRADICTED`, `PARTIALLY_SUPPORTED`, `UNVERIFIED`, `CONFLICTING`, `OUTDATED`, `INSUFFICIENT_EVIDENCE`).
6. **Explainability ("Why Flagged")**: Explains the exact observed facts, evidence citations, authority tiers, and explicit limitations.
7. **Safe Action Guidance**: Recommends non-investment next steps (grievance filing via SCORES, 1930 Cybercrime escalation, evidence preservation).
8. **Cryptographic Integrity**: Employs Post-Quantum Cryptography (ML-DSA-65 / Dilithium) and SHA3-256 canonical digests to produce verifiable investigation receipts.

---

## Core Guardrails — What SANGYAN Never Does

- **NO investment advice**: Never recommends buying, selling, or holding any security.
- **NO price predictions**: Never forecasts market moves or stock targets.
- **NO broker/scheme promotion**: Does not promote any financial product, intermediary, or commission-earning opportunity.
- **NO black-box fraud scores**: Avoids arbitrary "97% scam probability" numbers; exposes concrete claims and observable signals.
- **NO regulatory hallucinations**: Never invents SEBI registration numbers or legal status; distinguishes authoritative facts from model interpretations.

---

## Authority Tier Hierarchy

- **T0**: Regulator / Government / Official authority (SEBI, RBI, MCA, Cybercrime Portal)
- **T1**: Exchange / Depository / Official infrastructure (NSE, BSE, NSDL, CDSL)
- **T2**: Registered intermediary / primary authoritative entity
- **T3**: Established secondary source / financial press
- **T4**: General web source
- **T5**: Social media / user-generated content (evidence to investigate, not truth)

---

## Repository Structure

```text
C:\Projects\Sangyan/
├── sangyan/                    # Core Python application package
│   ├── core/                   # Errors, logging, identifiers
│   ├── crypto/                 # Post-quantum cryptography (ML-DSA-65, SHA3-256)
│   ├── database/               # DatabaseEngine (SQLite / PostgreSQL) & migrations
│   ├── domain/                 # 10 investor-safety domain records & validation
│   ├── security/               # SSRF protection, rate limiting, security headers
│   ├── tenancy/                # Multi-tenancy, memberships, sessions
│   └── trust/                  # PQC receipts & verification service
├── tests/                      # Comprehensive test suite
├── decisions.md                # Append-only architectural decision log
├── flow.md                     # Runtime execution and call flows
├── handoff.md                  # Development phase state & handoff record
└── pyproject.toml              # Project manifest and script entrypoints
```

---

## Getting Started

### Prerequisites
- Python >= 3.10 (tested on Python 3.13)
- Node.js >= 20 (for web frontend)

### Installation
```bash
pip install -e .
```

### Running Tests
```bash
pytest tests/ -v
```
