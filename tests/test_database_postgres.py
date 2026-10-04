"""Unit and integration tests for PostgresDatabaseEngine."""
from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from sangyan.core.errors import DuplicateEntryError, StorageError
from sangyan.database.postgres import PostgresDatabaseEngine, _to_postgres_sql


def test_sql_placeholder_translation():
    sql = "SELECT * FROM sangyan_users WHERE id = ? AND status = ? AND age > ?"
    translated = _to_postgres_sql(sql)
    assert translated == "SELECT * FROM sangyan_users WHERE id = %s AND status = %s AND age > %s"
    assert "?" not in translated


def test_postgres_engine_initialization():
    engine = PostgresDatabaseEngine(
        dsn="postgresql://user:pass@localhost:5432/sangyandb",
        min_size=2,
        max_size=10,
        timeout=5.0,
    )
    assert engine.dialect == "postgresql"
    assert engine.min_size == 2
    assert engine.max_size == 10
    assert engine._pool is None


def test_postgres_engine_execute_returns_rowcount():
    engine = PostgresDatabaseEngine("postgresql://mock/db")
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 3
    mock_conn.execute.return_value = mock_cursor

    # Setup pool connection context manager
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    engine._pool = mock_pool

    count = engine.execute("UPDATE test_table SET col = ? WHERE id = ?", ("val", "123"))
    assert count == 3
    mock_conn.execute.assert_called_once_with(
        "UPDATE test_table SET col = %s WHERE id = %s",
        ("val", "123"),
    )


def test_postgres_engine_duplicate_key_error():
    engine = PostgresDatabaseEngine("postgresql://mock/db")
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = Exception("duplicate key value violates unique constraint 'idx_unique'")
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    engine._pool = mock_pool

    with pytest.raises(DuplicateEntryError) as excinfo:
        engine.execute("INSERT INTO test (id) VALUES (?)", ("1",))
    assert "duplicate key" in str(excinfo.value).lower()


def test_postgres_engine_thread_local_transaction_commit():
    engine = PostgresDatabaseEngine("postgresql://mock/db")
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_tx = MagicMock()

    mock_conn.transaction.return_value.__enter__.return_value = mock_tx
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    engine._pool = mock_pool

    with engine.transaction():
        # Inside transaction, _local.conn is bound
        assert getattr(engine._local, "conn", None) is mock_conn
        engine.execute("INSERT INTO audit (msg) VALUES (?)", ("test",))

    # Outside transaction, _local.conn is cleared
    assert getattr(engine._local, "conn", None) is None
    mock_conn.transaction.assert_called_once()


def test_postgres_engine_thread_local_transaction_rollback():
    engine = PostgresDatabaseEngine("postgresql://mock/db")
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_tx = MagicMock()

    # Emulate transaction context manager raising on exception
    class MockTxContext:
        def __enter__(self):
            return mock_tx
        def __exit__(self, exc_type, exc_val, exc_tb):
            return False  # Propagate exception

    mock_conn.transaction.return_value = MockTxContext()
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    engine._pool = mock_pool

    with pytest.raises(ValueError):
        with engine.transaction():
            engine.execute("INSERT INTO test VALUES (?)", ("1",))
            raise ValueError("Deliberate transaction failure")

    # Verify thread local connection was properly un-bound even on failure
    assert getattr(engine._local, "conn", None) is None


def test_postgres_engine_ping_and_pool_status():
    engine = PostgresDatabaseEngine("postgresql://mock/db")
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"alive": 1}
    mock_conn.execute.return_value = mock_cursor
    mock_pool.connection.return_value.__enter__.return_value = mock_conn
    engine._pool = mock_pool

    assert engine.ping() is True
    status = engine.get_pool_status()
    assert status["status"] == "open"
    assert status["min_size"] == 2
    assert status["max_size"] == 20
