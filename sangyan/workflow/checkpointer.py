"""Durable SQLite checkpointing and tenant-scoped thread identity management."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from sangyan.workflow.errors import TenantMismatchError


def format_thread_id(organization_id: str, investigation_id: str, run_id: str) -> str:
    """Format canonical composite thread ID: <organization_id>:<investigation_id>:<run_id>."""
    return f"{organization_id}:{investigation_id}:{run_id}"


def parse_thread_id(thread_id: str) -> tuple[str, str, str]:
    """Parse canonical composite thread ID into (organization_id, investigation_id, run_id)."""
    parts = thread_id.split(":")
    if len(parts) != 3:
        raise ValueError(
            f"Invalid thread_id format '{thread_id}'; expected '<organization_id>:<investigation_id>:<run_id>'"
        )
    return parts[0], parts[1], parts[2]


def validate_thread_access(thread_id: str, caller_organization_id: str) -> None:
    """Verify that caller organization matches the thread's tenant prefix."""
    org_id, _, _ = parse_thread_id(thread_id)
    if org_id != caller_organization_id:
        raise TenantMismatchError(
            f"Access denied: thread '{thread_id}' belongs to organization '{org_id}', "
            f"not caller '{caller_organization_id}'."
        )


class WorkflowCheckpointer:
    """Manages creation and lifecycle of durable LangGraph checkpointers."""

    def __init__(self, db_path: Optional[str | Path] = None, in_memory: bool = False) -> None:
        self.in_memory = in_memory
        self.db_path = Path(db_path) if db_path else None
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._saver: Optional[BaseCheckpointSaver] = None

    def get_saver(self) -> BaseCheckpointSaver:
        """Return initialized, thread-safe checkpointer instance."""
        with self._lock:
            if self._saver is not None:
                return self._saver

            if self.in_memory or self.db_path is None or str(self.db_path) == ":memory:":
                # If path is :memory: or in_memory flag set, create in-memory SqliteSaver with shared connection
                conn = sqlite3.connect(":memory:", check_same_thread=False)
                saver = SqliteSaver(conn)
                saver.setup()
                self._conn = conn
                self._saver = saver
                return self._saver

            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA busy_timeout = 10000")
            saver = SqliteSaver(conn)
            saver.setup()
            self._conn = conn
            self._saver = saver
            return self._saver

    def close(self) -> None:
        """Close underlying SQLite connection."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
            self._saver = None
