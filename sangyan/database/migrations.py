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

MIGRATION_004_STATEMENTS: tuple[str, ...] = (
    # Hashed API Keys & Machine Credentials
    """
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
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_api_keys_org_prefix ON sangyan_api_keys(organization_id, key_prefix)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_api_keys_prefix ON sangyan_api_keys(key_prefix)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_api_keys_org ON sangyan_api_keys(organization_id)",
)

MIGRATION_005_STATEMENTS: tuple[str, ...] = (
    # Asynchronous Tasks (Task ledger & outbox)
    """
    CREATE TABLE IF NOT EXISTS sangyan_async_tasks (
        task_id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        investigation_id TEXT NOT NULL,
        task_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'QUEUED',
        payload TEXT NOT NULL DEFAULT '{}',
        result TEXT,
        error_message TEXT,
        retry_count INTEGER NOT NULL DEFAULT 0,
        max_retries INTEGER NOT NULL DEFAULT 3,
        lease_owner TEXT,
        lease_expires_at REAL,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        completed_at REAL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_tasks_org ON sangyan_async_tasks(organization_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_tasks_status ON sangyan_async_tasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_tasks_inv ON sangyan_async_tasks(investigation_id)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_tasks_lease ON sangyan_async_tasks(lease_owner, lease_expires_at)",
    # Disaster Recovery Region Epoch & Fencing
    """
    CREATE TABLE IF NOT EXISTS sangyan_region_fencing (
        region_id TEXT PRIMARY KEY,
        cluster_epoch INTEGER NOT NULL DEFAULT 1,
        role TEXT NOT NULL DEFAULT 'STANDBY_READY',
        is_fenced INTEGER NOT NULL DEFAULT 0,
        fence_reason TEXT,
        last_heartbeat_at REAL NOT NULL,
        promoted_at REAL,
        updated_at REAL NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_fencing_role ON sangyan_region_fencing(role)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_fencing_epoch ON sangyan_region_fencing(cluster_epoch)",
)

MIGRATION_006_STATEMENTS: tuple[str, ...] = (
    # Crash-safe retry scheduling: explicit earliest-retry timestamp so retry
    # re-enqueue can be driven by a relational sweeper instead of blocking a
    # worker inline or relying on in-process timers that die with the worker.
    "ALTER TABLE sangyan_async_tasks ADD COLUMN next_attempt_at REAL",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_tasks_retry_due ON sangyan_async_tasks(status, next_attempt_at)",
)

MIGRATION_007_STATEMENTS: tuple[str, ...] = (
    # Real-time investigation event stream buffer: durable operational projection
    # enabling SSE / WebSocket client reconnect replay via Last-Event-ID.
    """
    CREATE TABLE IF NOT EXISTS sangyan_investigation_events (
        id TEXT PRIMARY KEY,
        investigation_id TEXT NOT NULL,
        workflow_run_id TEXT NOT NULL,
        organization_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        sequence INTEGER NOT NULL,
        timestamp REAL NOT NULL,
        status TEXT NOT NULL,
        stage TEXT NOT NULL DEFAULT '',
        progress_pct INTEGER NOT NULL DEFAULT 0,
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_inv_events_inv_seq ON sangyan_investigation_events(investigation_id, sequence)",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_inv_events_org ON sangyan_investigation_events(organization_id)",
    # Physical PostgreSQL replication & multi-node health tracking
    """
    CREATE TABLE IF NOT EXISTS sangyan_replication_state (
        node_id TEXT PRIMARY KEY,
        role TEXT NOT NULL DEFAULT 'STANDBY',
        cluster_epoch INTEGER NOT NULL DEFAULT 1,
        wal_lsn TEXT,
        replay_lsn TEXT,
        lag_bytes INTEGER NOT NULL DEFAULT 0,
        lag_seconds REAL NOT NULL DEFAULT 0.0,
        last_heartbeat_at REAL NOT NULL,
        is_healthy INTEGER NOT NULL DEFAULT 1,
        metadata TEXT NOT NULL DEFAULT '{}'
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sangyan_repl_role ON sangyan_replication_state(role)",
    # Cryptographic key rotation: track signing key identifier on trust receipts
    "ALTER TABLE sangyan_trust_receipts ADD COLUMN signing_key_id TEXT NOT NULL DEFAULT 'default'",
    "CREATE INDEX IF NOT EXISTS idx_sangyan_trust_key_id ON sangyan_trust_receipts(signing_key_id)",
)

MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "create_sangyan_core_tables", MIGRATION_001_STATEMENTS),
    Migration(2, "create_sangyan_correlation_and_guidance_tables", MIGRATION_002_STATEMENTS),
    Migration(3, "create_sangyan_workflow_runs_table", MIGRATION_003_STATEMENTS),
    Migration(4, "create_sangyan_api_keys_table", MIGRATION_004_STATEMENTS),
    Migration(5, "create_sangyan_async_tasks_and_dr_tables", MIGRATION_005_STATEMENTS),
    Migration(6, "add_task_retry_scheduling_column", MIGRATION_006_STATEMENTS),
    Migration(7, "create_phase11_realtime_events_and_replication_tables", MIGRATION_007_STATEMENTS),
)



class MigrationRunner:
    """Manages idempotent linear schema migrations across SQLite and PostgreSQL with concurrency locking."""

    MIGRATION_LOCK_ID = 837192  # 32-bit integer for pg_advisory_lock

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

    def _acquire_migration_lock(self) -> None:
        if self.engine.dialect == "postgresql":
            try:
                self.engine.execute(f"SELECT pg_advisory_lock({self.MIGRATION_LOCK_ID})")
            except Exception:
                pass  # Fall back to transactional locks if advisory unavailable

    def _release_migration_lock(self) -> None:
        if self.engine.dialect == "postgresql":
            try:
                self.engine.execute(f"SELECT pg_advisory_unlock({self.MIGRATION_LOCK_ID})")
            except Exception:
                pass

    def applied_versions(self) -> list[int]:
        self.engine.connect()
        self._ensure_table()
        rows = self.engine.query_all(
            f"SELECT version FROM {MIGRATION_TABLE} ORDER BY version ASC"
        )
        return [int(r["version"]) for r in rows]

    def pending_migrations(self) -> list[Migration]:
        applied = set(self.applied_versions())
        return [m for m in sorted(MIGRATIONS, key=lambda m: m.version) if m.version not in applied]

    def is_up_to_date(self) -> bool:
        return len(self.pending_migrations()) == 0

    def status(self) -> dict[str, Any]:
        applied = self.applied_versions()
        pending = [m.version for m in self.pending_migrations()]
        current_ver = applied[-1] if applied else 0
        latest_ver = max((m.version for m in MIGRATIONS), default=0)
        return {
            "applied_versions": applied,
            "pending_versions": pending,
            "is_current": len(pending) == 0,
            "total_migrations": len(MIGRATIONS),
            "current_version": current_ver,
            "latest_version": latest_ver,
        }

    def migrate(self) -> list[str]:
        """Apply all pending migrations; returns list of newly applied migration identifiers."""
        self.engine.connect()
        self._acquire_migration_lock()
        try:
            self._ensure_table()
            result: list[str] = []
            for migration in sorted(MIGRATIONS, key=lambda m: m.version):
                if migration.version in set(self.applied_versions()):
                    continue
                with self.engine.transaction():
                    # Double-check inside transaction lock
                    if migration.version in set(self.applied_versions()):
                        continue
                    for stmt in migration.statements:
                        self.engine.execute(stmt)
                    self.engine.execute(
                        f"INSERT INTO {MIGRATION_TABLE} (version, name, applied_at) VALUES (?,?,?)",
                        (migration.version, migration.name, time.time()),
                    )
                result.append(f"{migration.version:03d}_{migration.name}")
            return result
        finally:
            self._release_migration_lock()

