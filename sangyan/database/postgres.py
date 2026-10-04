"""PostgreSQL engine implementation using psycopg 3 bounded connection pool."""
from __future__ import annotations

import re
import threading
from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any, Optional

from sangyan.core.errors import DuplicateEntryError, StorageError
from sangyan.database.engine import DatabaseEngine


def _to_postgres_sql(sql: str) -> str:
    """Translate ? placeholders to %s for psycopg."""
    return re.sub(r"\?", "%s", sql)


class PostgresDatabaseEngine(DatabaseEngine):
    """PostgreSQL implementation backed by psycopg 3 connection pool with thread-local transaction isolation."""

    def __init__(
        self,
        dsn: str,
        min_size: int = 2,
        max_size: int = 20,
        timeout: float = 10.0,
    ) -> None:
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self.timeout = timeout
        self._pool = None
        self._local = threading.local()

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
                min_size=self.min_size,
                max_size=self.max_size,
                timeout=self.timeout,
                kwargs={"row_factory": dict_row, "autocommit": True},
            )
            self._pool.open()
        except ImportError as exc:
            raise StorageError("psycopg and psycopg_pool are required for PostgreSQL") from exc
        except Exception as exc:
            raise StorageError(f"PostgreSQL connection pool failed to open: {exc}") from exc

    @contextmanager
    def _conn_scope(self):
        """Yield the active transactional connection for this thread, or borrow a pool connection."""
        self.connect()
        active = getattr(self._local, "conn", None)
        if active is not None:
            yield active
        else:
            with self._pool.connection(timeout=self.timeout) as conn:
                yield conn

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        self.connect()
        pg_sql = _to_postgres_sql(sql)
        try:
            with self._conn_scope() as conn:
                cur = conn.execute(pg_sql, tuple(params))
                return cur.rowcount
        except Exception as exc:
            msg = str(exc).lower()
            if "unique constraint" in msg or "duplicate key" in msg:
                raise DuplicateEntryError(str(exc)) from exc
            raise StorageError(str(exc)) from exc

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> dict | None:
        self.connect()
        pg_sql = _to_postgres_sql(sql)
        try:
            with self._conn_scope() as conn:
                cur = conn.execute(pg_sql, tuple(params))
                row = cur.fetchone()
                return dict(row) if row is not None else None
        except Exception as exc:
            raise StorageError(str(exc)) from exc

    def query_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        self.connect()
        pg_sql = _to_postgres_sql(sql)
        try:
            with self._conn_scope() as conn:
                cur = conn.execute(pg_sql, tuple(params))
                return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            raise StorageError(str(exc)) from exc

    @contextmanager
    def transaction(self):
        """Thread-local transaction context manager.
        
        Statements executed inside this block run on a single borrowed connection
        and commit or roll back together.
        """
        self.connect()
        active = getattr(self._local, "conn", None)
        if active is not None:
            # Re-entrant / nested transaction block on the same connection
            with active.transaction():
                yield
            return

        with self._pool.connection(timeout=self.timeout) as conn:
            self._local.conn = conn
            try:
                with conn.transaction():
                    yield
            finally:
                self._local.conn = None

    def ping(self) -> bool:
        """Check database liveness."""
        try:
            res = self.query_one("SELECT 1 AS alive")
            return res is not None and res.get("alive") == 1
        except Exception:
            return False

    def get_pool_status(self) -> dict[str, Any]:
        """Return diagnostic metrics about connection pool utilization."""
        if self._pool is None:
            return {"status": "closed", "min_size": self.min_size, "max_size": self.max_size}
        try:
            return {
                "status": "open",
                "min_size": self.min_size,
                "max_size": self.max_size,
                "pool_size": getattr(self._pool, "get_size", lambda: None)(),
            }
        except Exception:
            return {"status": "open", "min_size": self.min_size, "max_size": self.max_size}

    def close(self) -> None:
        if self._pool is not None:
            try:
                self._pool.close()
            except Exception:
                pass
            self._pool = None
