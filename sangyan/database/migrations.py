"""SANGYAN database schema migrations framework and linear version runners."""
from __future__ import annotations

import time
from dataclasses import dataclass

from sangyan.database.engine import DatabaseEngine

MIGRATION_TABLE = "schema_migrations"


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]


MIGRATION_001_STATEMENTS: tuple[str, ...] = (
    # Tenancy & Identities
    """
    CREATE TABLE IF NOT EXISTS sangyan_organizations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_at REAL NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_org_status ON sangyan_organizations(status)",
    """
    CREATE TABLE IF NOT EXISTS sangyan_users (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_at REAL NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_usr_email ON sangyan_users(email)",
    """
    CREATE TABLE IF NOT EXISTS sangyan_memberships (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_at REAL NOT NULL,
        UNIQUE(organization_id, user_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_mem_org ON sangyan_memberships(organization_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_mem_usr ON sangyan_memberships(user_id)",
    """
    CREATE TABLE IF NOT EXISTS sangyan_sessions (
        token_digest TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        auth_key_id TEXT NOT NULL DEFAULT '',
        expires_at REAL NOT NULL,
        created_at REAL NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_sess_usr ON sangyan_sessions(user_id)",
    # Ingestion & Content
    """
    CREATE TABLE IF NOT EXISTS sangyan_content_items (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        content_type TEXT NOT NULL,
        raw_content TEXT NOT NULL,
        normalized_text TEXT NOT NULL DEFAULT '',
        source_url TEXT NOT NULL DEFAULT '',
        content_hash TEXT NOT NULL DEFAULT '',
        language TEXT NOT NULL DEFAULT 'en',
        created_at REAL NOT NULL,
        processing_status TEXT NOT NULL DEFAULT 'pending',
        metadata TEXT NOT NULL DEFAULT '{}',
        schema_version INTEGER NOT NULL DEFAULT 1
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_content_org ON sangyan_content_items(organization_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_content_hash ON sangyan_content_items(content_hash)",
    # Claims & Decomposition
    """
    CREATE TABLE IF NOT EXISTS sangyan_claims (
        id TEXT PRIMARY KEY,
        content_item_id TEXT NOT NULL,
        statement TEXT NOT NULL,
        claim_type TEXT NOT NULL DEFAULT 'factual',
        status TEXT NOT NULL DEFAULT 'UNVERIFIED',
        confidence TEXT,
        extracted_at REAL NOT NULL,
        metadata TEXT NOT NULL DEFAULT '{}',
        schema_version INTEGER NOT NULL DEFAULT 1
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_claims_item ON sangyan_claims(content_item_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_claims_status ON sangyan_claims(status)",
    # Entities
    """
    CREATE TABLE IF NOT EXISTS sangyan_entities (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        aliases TEXT NOT NULL DEFAULT '[]',
        registration_number TEXT,
        official_url TEXT,
        created_at REAL NOT NULL,
        metadata TEXT NOT NULL DEFAULT '{}',
        schema_version INTEGER NOT NULL DEFAULT 1
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_ent_type ON sangyan_entities(entity_type)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_ent_name ON sangyan_entities(name)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_ent_reg ON sangyan_entities(registration_number)",
    # Sources & Authority
    """
    CREATE TABLE IF NOT EXISTS sangyan_sources (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        authority_tier TEXT NOT NULL,
        url TEXT,
        publisher TEXT,
        published_at REAL,
        retrieved_at REAL NOT NULL,
        valid_until REAL,
        metadata TEXT NOT NULL DEFAULT '{}',
        schema_version INTEGER NOT NULL DEFAULT 1
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_src_tier ON sangyan_sources(authority_tier)",
    # Evidence
    """
    CREATE TABLE IF NOT EXISTS sangyan_evidence (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL,
        claim_id TEXT NOT NULL,
        excerpt TEXT NOT NULL,
        structured_fact TEXT NOT NULL DEFAULT '{}',
        stance TEXT NOT NULL DEFAULT 'NEUTRAL',
        relevance REAL NOT NULL DEFAULT 1.0,
        content_hash TEXT NOT NULL DEFAULT '',
        retrieved_at REAL NOT NULL,
        published_at REAL,
        metadata TEXT NOT NULL DEFAULT '{}',
        schema_version INTEGER NOT NULL DEFAULT 1
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_evid_claim ON sangyan_evidence(claim_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_evid_src ON sangyan_evidence(source_id)",
    # Signals
    """
    CREATE TABLE IF NOT EXISTS sangyan_signals (
        id TEXT PRIMARY KEY,
        content_item_id TEXT NOT NULL,
        signal_type TEXT NOT NULL,
        excerpt TEXT NOT NULL,
        detection_basis TEXT NOT NULL DEFAULT '',
        confidence REAL NOT NULL DEFAULT 1.0,
        observed_at REAL NOT NULL,
        metadata TEXT NOT NULL DEFAULT '{}',
        schema_version INTEGER NOT NULL DEFAULT 1
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_sig_item ON sangyan_signals(content_item_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_sig_type ON sangyan_signals(signal_type)",
    # Findings
    """
    CREATE TABLE IF NOT EXISTS sangyan_findings (
        id TEXT PRIMARY KEY,
        claim_id TEXT NOT NULL,
        statement TEXT NOT NULL,
        status TEXT NOT NULL,
        confidence TEXT,
        evidence_refs TEXT NOT NULL DEFAULT '[]',
        source_refs TEXT NOT NULL DEFAULT '[]',
        rationale TEXT NOT NULL DEFAULT '',
        limitations TEXT NOT NULL DEFAULT '',
        generated_at REAL NOT NULL,
        verification_version TEXT NOT NULL DEFAULT '1.0',
        schema_version INTEGER NOT NULL DEFAULT 1
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_find_claim ON sangyan_findings(claim_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_find_status ON sangyan_findings(status)",
    # Safe Action Guidance
    """
    CREATE TABLE IF NOT EXISTS sangyan_action_guidance (
        id TEXT PRIMARY KEY,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        official_url TEXT,
        priority INTEGER NOT NULL DEFAULT 1,
        urgency INTEGER NOT NULL DEFAULT 0,
        limitations TEXT NOT NULL DEFAULT '',
        metadata TEXT NOT NULL DEFAULT '{}',
        schema_version INTEGER NOT NULL DEFAULT 1
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_act_cat ON sangyan_action_guidance(category)",
    # Investigations
    """
    CREATE TABLE IF NOT EXISTS sangyan_investigations (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        content_item_id TEXT NOT NULL,
        claim_ids TEXT NOT NULL DEFAULT '[]',
        entity_ids TEXT NOT NULL DEFAULT '[]',
        signal_ids TEXT NOT NULL DEFAULT '[]',
        finding_ids TEXT NOT NULL DEFAULT '[]',
        guidance_ids TEXT NOT NULL DEFAULT '[]',
        status TEXT NOT NULL DEFAULT 'QUEUED',
        summary TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        completed_at REAL,
        trust_receipt_id TEXT,
        metadata TEXT NOT NULL DEFAULT '{}',
        schema_version INTEGER NOT NULL DEFAULT 1
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_inv_org ON sangyan_investigations(organization_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_inv_status ON sangyan_investigations(status)",
    # Reviews
    """
    CREATE TABLE IF NOT EXISTS sangyan_reviews (
        id TEXT PRIMARY KEY,
        investigation_id TEXT NOT NULL,
        reviewer_id TEXT NOT NULL,
        action TEXT NOT NULL,
        finding_id TEXT,
        reason TEXT NOT NULL DEFAULT '',
        occurred_at REAL NOT NULL,
        previous_revision_id TEXT,
        metadata TEXT NOT NULL DEFAULT '{}',
        schema_version INTEGER NOT NULL DEFAULT 1
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_rev_inv ON sangyan_reviews(investigation_id)",
    # Trust Receipts (PQC ML-DSA-65)
    """
    CREATE TABLE IF NOT EXISTS sangyan_trust_receipts (
        id TEXT PRIMARY KEY,
        subject_type TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        algorithm_id TEXT NOT NULL,
        public_key_b64 TEXT NOT NULL,
        content_digest TEXT NOT NULL,
        signature_b64 TEXT NOT NULL,
        created_at REAL NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_tr_subj ON sangyan_trust_receipts(subject_type, subject_id)",
    # Audit Events
    """
    CREATE TABLE IF NOT EXISTS sangyan_audit_events (
        id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL UNIQUE,
        timestamp REAL NOT NULL,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        resource TEXT NOT NULL,
        result TEXT NOT NULL,
        metadata TEXT NOT NULL DEFAULT '{}',
        ledger_hash TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_audit_action ON sangyan_audit_events(action)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_audit_time ON sangyan_audit_events(timestamp)",
)

MIGRATION_002_STATEMENTS: tuple[str, ...] = (
    # Investigation Correlations & Relationships
    """
    CREATE TABLE IF NOT EXISTS sangyan_correlations (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        investigation_id TEXT NOT NULL,
        source_id TEXT NOT NULL,
        source_type TEXT NOT NULL,
        target_id TEXT NOT NULL,
        target_type TEXT NOT NULL,
        relationship_type TEXT NOT NULL,
        strength TEXT NOT NULL,
        rationale TEXT NOT NULL,
        metadata TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_corr_org ON sangyan_correlations(organization_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_corr_inv ON sangyan_correlations(investigation_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_corr_src ON sangyan_correlations(source_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_corr_tgt ON sangyan_correlations(target_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_corr_type ON sangyan_correlations(relationship_type)",
    # Scam Chain Stages
    """
    CREATE TABLE IF NOT EXISTS sangyan_scam_chain_stages (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        investigation_id TEXT NOT NULL,
        stage TEXT NOT NULL,
        status TEXT NOT NULL,
        evidence_refs TEXT NOT NULL DEFAULT '[]',
        signal_refs TEXT NOT NULL DEFAULT '[]',
        details TEXT NOT NULL DEFAULT '',
        sequence_order INTEGER NOT NULL DEFAULT 0,
        created_at REAL NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_sc_org ON sangyan_scam_chain_stages(organization_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_sc_inv ON sangyan_scam_chain_stages(investigation_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_sc_stage ON sangyan_scam_chain_stages(stage)",
    # Grievance Records
    """
    CREATE TABLE IF NOT EXISTS sangyan_grievance_records (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        investigation_id TEXT NOT NULL,
        category TEXT NOT NULL,
        routing_channel TEXT NOT NULL,
        portal_url TEXT,
        helpline TEXT,
        guidance_steps TEXT NOT NULL DEFAULT '[]',
        metadata TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_grv_org ON sangyan_grievance_records(organization_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_grv_inv ON sangyan_grievance_records(investigation_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_grv_cat ON sangyan_grievance_records(category)",
)

MIGRATION_003_STATEMENTS: tuple[str, ...] = (
    # Workflow Runs & Execution Ledger
    """
    CREATE TABLE IF NOT EXISTS sangyan_workflow_runs (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        investigation_id TEXT NOT NULL,
        thread_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'RUNNING',
        current_node TEXT NOT NULL DEFAULT 'intake_node',
        retry_count INTEGER NOT NULL DEFAULT 0,
        checkpoint_id TEXT,
        metadata TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_wf_org ON sangyan_workflow_runs(organization_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_wf_inv ON sangyan_workflow_runs(investigation_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_wf_thread ON sangyan_workflow_runs(thread_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_wf_status ON sangyan_workflow_runs(status)",
)

MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "create_sangyan_core_tables", MIGRATION_001_STATEMENTS),
    Migration(2, "create_sangyan_correlation_and_guidance_tables", MIGRATION_002_STATEMENTS),
    Migration(3, "create_sangyan_workflow_runs_table", MIGRATION_003_STATEMENTS),
)



class MigrationRunner:
    """Manages idempotent linear schema migrations across SQLite and PostgreSQL."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self.engine = engine

    def _ensure_table(self) -> None:
        self.engine.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {MIGRATION_TABLE} (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at REAL NOT NULL
            )
            """
        )

    def applied_versions(self) -> list[int]:
        self.engine.connect()
        self._ensure_table()
        rows = self.engine.query_all(
            f"SELECT version FROM {MIGRATION_TABLE} ORDER BY version ASC"
        )
        return [int(r["version"]) for r in rows]

    def migrate(self) -> list[str]:
        """Apply all pending migrations; returns list of newly applied migration identifiers."""
        self.engine.connect()
        self._ensure_table()
        applied = set(self.applied_versions())
        result: list[str] = []
        for migration in sorted(MIGRATIONS, key=lambda m: m.version):
            if migration.version in applied:
                continue
            with self.engine.transaction():
                for stmt in migration.statements:
                    self.engine.execute(stmt)
                self.engine.execute(
                    f"INSERT INTO {MIGRATION_TABLE} (version, name, applied_at) VALUES (?,?,?)",
                    (migration.version, migration.name, time.time()),
                )
            result.append(f"{migration.version:03d}_{migration.name}")
        return result
