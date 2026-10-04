"""Tests for migration runner status, pending inspection, and multi-thread concurrency safety."""
from __future__ import annotations

import concurrent.futures
import tempfile
from pathlib import Path

import pytest

from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MIGRATIONS, MigrationRunner


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "mig_concurrency_test.db"
        engine = SQLiteDatabaseEngine(db_path)
        yield engine
        engine.close()


def test_migration_status_and_pending_inspection(temp_db):
    runner = MigrationRunner(temp_db)
    # Before migration
    status = runner.status()
    assert status["is_current"] is False
    assert status["current_version"] == 0
    assert status["latest_version"] == 6
    assert len(status["pending_versions"]) == 6

    pending = runner.pending_migrations()
    assert len(pending) == 6
    assert [m.version for m in pending] == [1, 2, 3, 4, 5, 6]

    # Apply migration
    applied = runner.migrate()
    assert len(applied) == 6

    # After migration
    status_after = runner.status()
    assert status_after["is_current"] is True
    assert status_after["current_version"] == 6
    assert status_after["pending_versions"] == []
    assert runner.pending_migrations() == []
    assert runner.is_up_to_date() is True


def test_concurrent_migration_execution(temp_db):
    # Simulate multiple replicas / workers starting simultaneously and calling migrate()
    def run_migrate():
        r = MigrationRunner(temp_db)
        return r.migrate()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_migrate) for _ in range(5)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # Exactly one thread applies the 5 migrations; all others receive empty list []
    all_applied = [m for res in results for m in res]
    assert len(all_applied) == 6

    # Verify final state is completely consistent
    runner = MigrationRunner(temp_db)
    assert runner.is_up_to_date() is True
    assert runner.applied_versions() == [1, 2, 3, 4, 5, 6]
