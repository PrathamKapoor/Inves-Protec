"""Database engine abstraction supporting SQLite and PostgreSQL.

Provides thread-safe connections, dict row-factories, transactional context
management, and uniform statement execution.
"""
from __future__ import annotations

import sqlite3
import threading
from abc import ABC, abstractmethod
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sangyan.core.errors import DuplicateEntryError, StorageError


def parse_database_url(url: str) -> tuple[str, Path | str]:
    """Split database URL into dialect and connection target."""
    if url.startswith("sqlite:///"):
        return "sqlite", Path(url[len("sqlite:///") :])
    if url.startswith(("postgresql://", "postgres://")):
        return "postgresql", url
    raise StorageError("unsupported database URL; expected sqlite:///<file> or postgresql://...")


class DatabaseEngine(ABC):
    """Minimal statement-level database interface."""

    @property
    @abstractmethod
    def dialect(self) -> str: ...

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        """Execute write statement and commit (or enlist in transaction). Returns affected rowcount."""
        ...

    @abstractmethod
    def query_one(self, sql: str, params: Sequence[Any] = ()) -> dict | None: ...

    @abstractmethod
    def query_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict]: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def transaction(self):
        """Context manager: statements executed inside block commit or roll back together."""
        ...


class SQLiteDatabaseEngine(DatabaseEngine):
    """SQLite implementation with re-entrant serialized writes and dict row-factories."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        self._in_transaction = False

    @property
    def dialect(self) -> str:
        return "sqlite"

    def connect(self) -> None:
        with self._lock:
            if self._conn is not None:
                return
            if str(self.db_path) != ":memory:":
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                str(self.db_path), check_same_thread=False, isolation_level=None
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 10000")
            if str(self.db_path) != ":memory:":
                conn.execute("PRAGMA journal_mode = WAL")
            self._conn = conn

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self.connect()
        assert self._conn is not None
        return self._conn

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        with self._lock:
            conn = self._get_connection()
            try:
                if not self._in_transaction:
                    conn.execute("BEGIN IMMEDIATE")
                cur = conn.execute(sql, tuple(params))
                rowcount = cur.rowcount
                if not self._in_transaction:
                    conn.execute("COMMIT")
                return rowcount
            except sqlite3.IntegrityError as exc:
                if not self._in_transaction:
                    conn.execute("ROLLBACK")
                msg = str(exc).lower()
                if "unique" in msg or "primary key" in msg:
                    raise DuplicateEntryError(str(exc)) from exc
                raise StorageError(str(exc)) from exc
            except Exception as exc:
                if not self._in_transaction:
                    conn.execute("ROLLBACK")
                raise StorageError(str(exc)) from exc

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> dict | None:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(sql, tuple(params))
                row = cur.fetchone()
                return dict(row) if row is not None else None
            except Exception as exc:
                raise StorageError(str(exc)) from exc

    def query_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(sql, tuple(params))
                return [dict(row) for row in cur.fetchall()]
            except Exception as exc:
                raise StorageError(str(exc)) from exc

    @contextmanager
    def transaction(self):
        with self._lock:
            conn = self._get_connection()
            if self._in_transaction:
                yield
                return
            conn.execute("BEGIN IMMEDIATE")
            self._in_transaction = True
            try:
                yield
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            finally:
                self._in_transaction = False

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None


def create_engine(url_or_path: str | Path) -> DatabaseEngine:
    """Factory creating appropriate DatabaseEngine from URL or filesystem path."""
    if isinstance(url_or_path, Path):
        return SQLiteDatabaseEngine(url_or_path)
    dialect, target = parse_database_url(url_or_path)
    if dialect == "sqlite":
        return SQLiteDatabaseEngine(target)
    if dialect == "postgresql":
        from sangyan.database.postgres import PostgresDatabaseEngine
        return PostgresDatabaseEngine(str(target))
    raise StorageError(f"unsupported database dialect: {dialect}")
