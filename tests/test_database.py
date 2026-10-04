"""Unit tests for SQLite DatabaseEngine and MigrationRunner."""
import tempfile
from pathlib import Path

import pytest

from sangyan.core.errors import DuplicateEntryError
from sangyan.database.engine import SQLiteDatabaseEngine, create_engine
from sangyan.database.migrations import MigrationRunner


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sangyan.db"
        engine = SQLiteDatabaseEngine(db_path)
        yield engine
        engine.close()


class TestDatabaseEngine:
    def test_connect_and_query(self, temp_db):
        temp_db.connect()
        assert temp_db.dialect == "sqlite"
        temp_db.execute("CREATE TABLE items (id TEXT PRIMARY KEY, val INTEGER)")
        temp_db.execute("INSERT INTO items (id, val) VALUES (?, ?)", ("item_1", 42))

        row = temp_db.query_one("SELECT * FROM items WHERE id=?", ("item_1",))
        assert row is not None
        assert row["id"] == "item_1"
        assert row["val"] == 42

        rows = temp_db.query_all("SELECT * FROM items")
        assert len(rows) == 1

    def test_duplicate_entry_error(self, temp_db):
        temp_db.execute("CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT UNIQUE)")
        temp_db.execute("INSERT INTO users VALUES (?, ?)", ("u1", "test@example.com"))
        with pytest.raises(DuplicateEntryError):
            temp_db.execute("INSERT INTO users VALUES (?, ?)", ("u2", "test@example.com"))

    def test_transaction_rollback(self, temp_db):
        temp_db.execute("CREATE TABLE counter (id TEXT PRIMARY KEY, count INTEGER)")
        temp_db.execute("INSERT INTO counter VALUES (?, ?)", ("c1", 10))

        with pytest.raises(ValueError):
            with temp_db.transaction():
                temp_db.execute("UPDATE counter SET count = 20 WHERE id='c1'")
                raise ValueError("Simulated failure inside transaction")

        # Must have rolled back to 10
        row = temp_db.query_one("SELECT count FROM counter WHERE id='c1'")
        assert row["count"] == 10


class TestMigrations:
    def test_migration_runner_applies_tables(self, temp_db):
        runner = MigrationRunner(temp_db)
        applied = runner.migrate()
        assert len(applied) == 4
        assert "001_create_sangyan_core_tables" in applied[0]
        assert "002_create_sangyan_correlation_and_guidance_tables" in applied[1]
        assert "003_create_sangyan_workflow_runs_table" in applied[2]
        assert "004_create_sangyan_api_keys_table" in applied[3]

        # Check that core tables exist
        content_table = temp_db.query_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sangyan_content_items'"
        )
        assert content_table is not None

        investigations_table = temp_db.query_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sangyan_investigations'"
        )
        assert investigations_table is not None

        correlations_table = temp_db.query_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sangyan_correlations'"
        )
        assert correlations_table is not None

        runs_table = temp_db.query_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sangyan_workflow_runs'"
        )
        assert runs_table is not None

        api_keys_table = temp_db.query_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sangyan_api_keys'"
        )
        assert api_keys_table is not None

        # Re-running migration must be idempotent (zero new migrations applied)
        second_run = runner.migrate()
        assert second_run == []
