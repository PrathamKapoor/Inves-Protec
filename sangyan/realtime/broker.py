"""Investigation event broker managing persistence, pub/sub, replay, and SSE streaming."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

from sangyan.realtime.models import InvestigationEvent, InvestigationEventType

logger = logging.getLogger(__name__)


class InvestigationEventBroker:
    """Manages publishing, database persistence, and SSE subscriber distribution of investigation events."""

    def __init__(self, engine=None):
        self._engine = engine
        self._lock = threading.Lock()
        # investigation_id -> next sequence number
        self._sequences: Dict[str, int] = {}
        # investigation_id -> set of asyncio.Queue
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        # subscriber queue -> organization_id for tenant boundary check
        self._subscriber_org: Dict[asyncio.Queue, str] = {}

    def _get_next_sequence(self, investigation_id: str) -> int:
        with self._lock:
            if investigation_id in self._sequences:
                self._sequences[investigation_id] += 1
                return self._sequences[investigation_id]

            # Query database for highest sequence if available
            next_seq = 1
            if self._engine is not None:
                try:
                    row = self._engine.query_one(
                        "SELECT MAX(sequence) as max_seq FROM sangyan_investigation_events WHERE investigation_id = ?",
                        (investigation_id,),
                    )
                    if row and row.get("max_seq") is not None:
                        next_seq = int(row["max_seq"]) + 1
                except Exception as exc:
                    logger.warning("Could not query max sequence from DB: %s", exc)

            self._sequences[investigation_id] = next_seq
            return next_seq

    def publish(
        self,
        investigation_id: str,
        organization_id: str,
        event_type: str | InvestigationEventType,
        node_name: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> InvestigationEvent:
        """Publish an event, persist to database, and push to active subscribers without blocking."""
        seq = self._get_next_sequence(investigation_id)
        event_type_str = event_type.value if isinstance(event_type, InvestigationEventType) else str(event_type)
        event_id = f"{investigation_id}:{seq}"
        payload_dict = payload or {}

        event = InvestigationEvent(
            event_id=event_id,
            investigation_id=investigation_id,
            organization_id=organization_id,
            event_type=event_type_str,
            sequence=seq,
            timestamp=time.time(),
            node_name=node_name,
            payload=payload_dict,
        )

        # 1. Persist to database if engine is configured
        if self._engine is not None:
            try:
                self._engine.execute(
                    """
                    INSERT INTO sangyan_investigation_events (
                        id, investigation_id, workflow_run_id, organization_id,
                        event_type, sequence, timestamp, status, stage,
                        progress_pct, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.investigation_id,
                        str(event.payload.get("run_id") or "run_default"),
                        event.organization_id,
                        event.event_type,
                        event.sequence,
                        event.timestamp,
                        str(event.payload.get("status") or "IN_PROGRESS"),
                        event.node_name or "",
                        int(event.payload.get("progress_pct") or 0),
                        json.dumps(event.payload),
                        event.timestamp,
                    ),
                )
            except Exception as exc:
                logger.error("Failed to persist investigation event %s: %s", event_id, exc)

        # 2. Dispatch to memory queues non-blockingly
        with self._lock:
            queues = list(self._subscribers.get(investigation_id, set()))

        for q in queues:
            org = self._subscriber_org.get(q)
            # Strict tenant isolation
            if org and org != organization_id:
                continue
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Bounded backpressure: slow consumer drops latest or drops without stalling workers
                logger.warning(
                    "Subscriber queue full for investigation %s; dropping event to protect worker throughput",
                    investigation_id,
                )
            except Exception as exc:
                logger.debug("Failed to put event into subscriber queue: %s", exc)

        return event

    def get_events(
        self,
        investigation_id: str,
        organization_id: str,
        after_sequence: int = 0,
        limit: int = 1000,
    ) -> List[InvestigationEvent]:
        """Fetch historical events with tenant isolation and sequence replay."""
        if self._engine is None:
            return []

        rows = self._engine.query_all(
            """
            SELECT id, investigation_id, workflow_run_id, organization_id,
                   event_type, sequence, timestamp, status, stage,
                   progress_pct, payload_json, created_at
            FROM sangyan_investigation_events
            WHERE investigation_id = ? AND organization_id = ? AND sequence > ?
            ORDER BY sequence ASC
            LIMIT ?
            """,
            (investigation_id, organization_id, after_sequence, limit),
        )

        events: List[InvestigationEvent] = []
        for r in rows:
            events.append(
                InvestigationEvent(
                    event_id=r["id"],
                    investigation_id=r["investigation_id"],
                    organization_id=r["organization_id"],
                    event_type=r["event_type"],
                    sequence=r["sequence"],
                    timestamp=r["timestamp"],
                    node_name=r["stage"] if r.get("stage") else None,
                    payload=json.loads(r["payload_json"]) if r.get("payload_json") else {},
                )
            )
        return events

    def parse_sequence_from_event_id(self, last_event_id: Optional[str]) -> int:
        """Parse numeric sequence from Last-Event-ID header (e.g., 'inv-123:4' -> 4)."""
        if not last_event_id:
            return 0
        try:
            if ":" in last_event_id:
                return int(last_event_id.split(":")[-1])
            return int(last_event_id)
        except (ValueError, TypeError):
            return 0

    async def subscribe(
        self,
        investigation_id: str,
        organization_id: str,
        last_event_id: Optional[str] = None,
        heartbeat_interval: float = 15.0,
        queue_maxsize: int = 500,
    ) -> AsyncGenerator[InvestigationEvent, None]:
        """Async generator yielding historical replayed events followed by real-time stream."""
        q: asyncio.Queue[InvestigationEvent] = asyncio.Queue(maxsize=queue_maxsize)
        after_seq = self.parse_sequence_from_event_id(last_event_id)

        # 1. Replay historical events
        past_events = self.get_events(investigation_id, organization_id, after_sequence=after_seq)
        last_yielded_seq = after_seq
        for ev in past_events:
            yield ev
            last_yielded_seq = max(last_yielded_seq, ev.sequence)

        # 2. Register for live events
        with self._lock:
            if investigation_id not in self._subscribers:
                self._subscribers[investigation_id] = set()
            self._subscribers[investigation_id].add(q)
            self._subscriber_org[q] = organization_id

        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=heartbeat_interval)
                    # Deduplicate in case event was already replayed
                    if event.sequence > last_yielded_seq:
                        yield event
                        last_yielded_seq = event.sequence
                except asyncio.TimeoutError:
                    # Emit heartbeat to prevent connection timeout
                    yield InvestigationEvent(
                        event_id=f"{investigation_id}:hb",
                        investigation_id=investigation_id,
                        organization_id=organization_id,
                        event_type=InvestigationEventType.HEARTBEAT.value,
                        sequence=last_yielded_seq,
                        timestamp=time.time(),
                        node_name=None,
                        payload={"type": "ping"},
                    )
        finally:
            with self._lock:
                if investigation_id in self._subscribers:
                    self._subscribers[investigation_id].discard(q)
                    if not self._subscribers[investigation_id]:
                        del self._subscribers[investigation_id]
                self._subscriber_org.pop(q, None)


# Module-level singleton
_EVENT_BROKER: Optional[InvestigationEventBroker] = None
_BROKER_LOCK = threading.Lock()


def get_event_broker(engine=None) -> InvestigationEventBroker:
    """Return the global InvestigationEventBroker instance."""
    global _EVENT_BROKER
    with _BROKER_LOCK:
        if _EVENT_BROKER is None:
            _EVENT_BROKER = InvestigationEventBroker(engine=engine)
        elif engine is not None and _EVENT_BROKER._engine is None:
            _EVENT_BROKER._engine = engine
        return _EVENT_BROKER


def reset_event_broker() -> None:
    """Reset broker for testing."""
    global _EVENT_BROKER
    with _BROKER_LOCK:
        _EVENT_BROKER = None
