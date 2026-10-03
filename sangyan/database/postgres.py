"""PostgreSQL engine implementation using psycopg 3 pool."""
from __future__ import annotations

import re
from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any

from sangyan.core.errors import DuplicateEntryError, StorageError
from sangyan.database.engine import DatabaseEngine


def _to_postgres_sql(sql: str) -> str:
    """Translate ? placeholders to %s for psycopg."""
    return re.sub(r"\?", "%s", sql)


class PostgresDatabaseEngine(DatabaseEngine):
    """PostgreSQL implementation backed by psycopg connection pool."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._pool = None

    @property
    def dialect(self) -> str:
        return "postgresql"

    def connect(self) -> None:
        if self._pool is not None:
            return
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool

            self._pool = ConnectionPool(
                self.dsn,
                min_size=1,
                max_size=10,
                kwargs={"row_factory": dict_row, "autocommit": True},
            )
            self._pool.open()
        except ImportError as exc:
            raise StorageError("psycopg and psycopg_pool are required for PostgreSQL") from exc
        except Exception as exc:
            raise StorageError(f"PostgreSQL connection failed: {exc}") from exc

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        self.connect()
        pg_sql = _to_postgres_sql(sql)
        try:
            with self._pool.connection() as conn:
                conn.execute(pg_sql, tuple(params))
        except Exception as exc:
            msg = str(exc).lower()
            if "unique constraint" in msg or "duplicate key" in msg:
                raise DuplicateEntryError(str(exc)) from exc
            raise StorageError(str(exc)) from exc

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> dict | None:
        self.connect()
        pg_sql = _to_postgres_sql(sql)
        try:
            with self._pool.connection() as conn:
                cur = conn.execute(pg_sql, tuple(params))
                row = cur.fetchone()
                return dict(row) if row is not None else None
        except Exception as exc:
            raise StorageError(str(exc)) from exc

    def query_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        self.connect()
        pg_sql = _to_postgres_sql(sql)
        try:
            with self._pool.connection() as conn:
                cur = conn.execute(pg_sql, tuple(params))
                return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            raise StorageError(str(exc)) from exc

    @contextmanager
    def transaction(self):
        self.connect()
        with self._pool.connection() as conn:
            with conn.transaction():
                yield

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None
