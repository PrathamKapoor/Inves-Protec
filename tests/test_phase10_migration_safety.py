"""Phase 10: database migration safety across schema generations.

Covers:
1. Empty database reaches schema version 6 with all tables and retry column.
2. Phase 9 schema (migrations 1-5) upgrades to 6 preserving existing task rows.
3. Idempotent re-run applies nothing and stays current.
4. Concurrent migrate() on a fresh database applies exactly once (regression guard).
5. Readiness probe reports current after migration.
"""
import concurrent.futures

import pytest

from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import (
    MIGRATIONS,
    MIGRATION_006_STATEMENTS,
    MigrationRunner,
)


@pytest.fixture
def engine(tmp_path):
    eng = SQLiteDatabaseEngine(tmp_path / "migration_safety.db")
    yield eng
    eng.close()


def _apply_partial(engine, up_to_version: int) -> None:
    """Apply only migrations 1..N (simulates an older schema generation)."""
    runner = MigrationRunner(engine)
    runner._ensure_table()
    import time

    for migration in sorted(MIGRATIONS, key=lambda m: m.version):
        if migration.version > up_to_version:
            break
        with engine.transaction():
            for stmt in migration.statements:
                engine.execute(stmt)
            engine.execute(
                f"INSERT INTO schema_migrations (version, name, applied_at) VALUES (?,?,?)",
                (migration.version, migration.name, time.time()),
            )


def test_empty_database_reaches_version_6(engine):
    runner = MigrationRunner(engine)
    applied = runner.migrate()
    assert len(applied) == 6
    assert runner.status()["current_version"] == 6
    assert runner.is_up_to_date()

    # New retry scheduling column and index exist
    cols = engine.query_all("PRAGMA table_info(sangyan_async_tasks)")
    names = {c["name"] for c in cols}
    assert "next_attempt_at" in names
    indexes = engine.query_all("PRAGMA index_list(sangyan_async_tasks)")
    idx_names = {i["name"] for i in indexes}
    assert "idx_sangyan_tasks_retry_due" in idx_names


def test_phase9_schema_upgrades_preserving_rows(engine):
    # 1. Build Phase 9 schema (migrations 1-5) with an existing task row
    _apply_partial(engine, 5)
    cols = engine.query_all("PRAGMA table_info(sangyan_async_tasks)")
    assert "next_attempt_at" not in {c["name"] for c in cols}
    engine.execute(
        """
        INSERT INTO sangyan_async_tasks (
            task_id, organization_id, user_id, investigation_id, task_type,
            status, payload, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        ("tsk-legacy", "org-1", "usr-1", "inv-1", "WORKFLOW_START", "QUEUED", "{}", 1.0, 1.0),
    )

    # 2. Run the real migration runner: only 006 applies
    runner = MigrationRunner(engine)
    applied = runner.migrate()
    assert applied == ["006_add_task_retry_scheduling_column"]
    assert runner.is_up_to_date()

    # 3. Legacy row preserved with NULL next_attempt_at and remains queryable
    row = engine.query_one("SELECT * FROM sangyan_async_tasks WHERE task_id='tsk-legacy'")
    assert row is not None
    assert row["status"] == "QUEUED"
    assert row["next_attempt_at"] is None


def test_migration_rerun_is_idempotent(engine):
    runner = MigrationRunner(engine)
    runner.migrate()
    again = runner.migrate()
    assert again == []
    assert runner.status()["current_version"] == 6


def test_migration_statements_are_ordered_and_newest_is_006():
    versions = [m.version for m in MIGRATIONS]
    assert versions == sorted(versions)
    assert versions == [1, 2, 3, 4, 5, 6]
    # DDL in migration 6 must be additive (never rewrites historical tables)
    joined = " ".join(MIGRATION_006_STATEMENTS)
    assert "ALTER TABLE sangyan_async_tasks ADD COLUMN next_attempt_at REAL" in joined
    assert "DROP" not in joined.upper()


def test_concurrent_migrate_applies_exactly_once(tmp_path):
    eng = SQLiteDatabaseEngine(tmp_path / "concurrent_safety.db")
    try:
        def run():
            return MigrationRunner(eng).migrate()

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = [f.result() for f in [pool.submit(run) for _ in range(4)]]

        total_applied = sum(len(r) for r in results)
        assert total_applied == 6  # no double-apply
        runner = MigrationRunner(eng)
        assert runner.applied_versions() == [1, 2, 3, 4, 5, 6]
    finally:
        eng.close()
