"""Phase 11: Real-time investigation progress streaming (SSE) test suite.

Validates:
1. Event publication and strictly monotonic sequencing.
2. Persistence into `sangyan_investigation_events`.
3. Sequence replay via `Last-Event-ID` / `after_sequence`.
4. Multi-tenant isolation (cross-tenant replay/subscription isolation).
5. Bounded backpressure (slow consumers drop packets without blocking worker/publisher).
6. Heartbeat emission during connection idle periods.
7. Standard SSE wire protocol format (`id:`, `event:`, `data:`).
"""
import asyncio
import json
import pytest
import time

from sangyan.database.engine import SQLiteDatabaseEngine
from sangyan.database.migrations import MigrationRunner
from sangyan.realtime.broker import InvestigationEventBroker
from sangyan.realtime.models import InvestigationEvent, InvestigationEventType


@pytest.fixture
def db_engine(tmp_path):
    eng = SQLiteDatabaseEngine(tmp_path / "realtime_test.db")
    runner = MigrationRunner(eng)
    runner.migrate()
    yield eng
    eng.close()


@pytest.fixture
def broker(db_engine):
    return InvestigationEventBroker(engine=db_engine)


def test_event_models_and_sse_wire_format():
    event = InvestigationEvent(
        event_id="inv-100:1",
        investigation_id="inv-100",
        organization_id="org-acme",
        event_type=InvestigationEventType.INTAKE_STARTED.value,
        sequence=1,
        timestamp=1000.0,
        node_name="intake_node",
        payload={"item_count": 2},
    )

    d = event.to_dict()
    assert d["event_id"] == "inv-100:1"
    assert d["sequence"] == 1
    assert d["payload"]["item_count"] == 2

    # Wire protocol format check
    wire = event.to_sse_message()
    assert wire.startswith("id: inv-100:1\n")
    assert "event: INTAKE_STARTED\n" in wire
    assert 'data: {"event_id":"inv-100:1"' in wire
    assert wire.endswith("\n\n")

    # Roundtrip from_dict
    restored = InvestigationEvent.from_dict(d)
    assert restored.event_id == event.event_id
    assert restored.sequence == 1
    assert restored.node_name == "intake_node"


def test_broker_publishing_and_monotonic_sequencing(broker, db_engine):
    ev1 = broker.publish(
        investigation_id="inv-seq",
        organization_id="org-1",
        event_type=InvestigationEventType.INVESTIGATION_STARTED,
        node_name="start",
    )
    ev2 = broker.publish(
        investigation_id="inv-seq",
        organization_id="org-1",
        event_type=InvestigationEventType.INTAKE_STARTED,
        node_name="intake_node",
    )
    ev3 = broker.publish(
        investigation_id="inv-seq",
        organization_id="org-1",
        event_type=InvestigationEventType.INTAKE_COMPLETED,
        node_name="intake_node",
    )

    assert ev1.sequence == 1
    assert ev2.sequence == 2
    assert ev3.sequence == 3
    assert ev1.event_id == "inv-seq:1"
    assert ev2.event_id == "inv-seq:2"
    assert ev3.event_id == "inv-seq:3"

    # Database verification
    rows = db_engine.query_all(
        "SELECT * FROM sangyan_investigation_events WHERE investigation_id='inv-seq' ORDER BY sequence ASC"
    )
    assert len(rows) == 3
    assert [r["sequence"] for r in rows] == [1, 2, 3]
    assert [r["event_type"] for r in rows] == [
        "INVESTIGATION_STARTED",
        "INTAKE_STARTED",
        "INTAKE_COMPLETED",
    ]


def test_historical_replay_with_sequence_filter(broker):
    for i in range(1, 6):
        broker.publish(
            investigation_id="inv-replay",
            organization_id="org-1",
            event_type=f"STAGE_{i}",
            payload={"step": i},
        )

    # Replay all
    all_events = broker.get_events("inv-replay", "org-1", after_sequence=0)
    assert len(all_events) == 5
    assert [e.sequence for e in all_events] == [1, 2, 3, 4, 5]

    # Replay from sequence 3 (simulating client reconnect with Last-Event-ID: inv-replay:3)
    resumed_events = broker.get_events("inv-replay", "org-1", after_sequence=3)
    assert len(resumed_events) == 2
    assert [e.sequence for e in resumed_events] == [4, 5]


def test_multi_tenant_isolation_boundary(broker):
    # Org A publishes events
    broker.publish(
        investigation_id="inv-isolated",
        organization_id="tenant-a",
        event_type="INTAKE_COMPLETED",
    )

    # Org B attempts to read Org A's investigation events
    cross_read = broker.get_events("inv-isolated", "tenant-b", after_sequence=0)
    assert len(cross_read) == 0

    # Org A reads own events
    legit_read = broker.get_events("inv-isolated", "tenant-a", after_sequence=0)
    assert len(legit_read) == 1


@pytest.mark.asyncio
async def test_live_streaming_and_reconnection(broker):
    # Publish initial historical event
    broker.publish(
        investigation_id="inv-stream",
        organization_id="org-stream",
        event_type=InvestigationEventType.INVESTIGATION_STARTED,
    )

    received = []

    async def client():
        gen = broker.subscribe(
            investigation_id="inv-stream",
            organization_id="org-stream",
            last_event_id=None,
            heartbeat_interval=1.0,
        )
        async for ev in gen:
            received.append(ev)
            if ev.event_type == InvestigationEventType.INVESTIGATION_COMPLETED.value:
                break

    task = asyncio.create_task(client())
    await asyncio.sleep(0.05)

    # Publish live events while subscriber is connected
    broker.publish(
        investigation_id="inv-stream",
        organization_id="org-stream",
        event_type=InvestigationEventType.INTAKE_STARTED,
    )
    broker.publish(
        investigation_id="inv-stream",
        organization_id="org-stream",
        event_type=InvestigationEventType.INVESTIGATION_COMPLETED,
    )

    await asyncio.wait_for(task, timeout=2.0)
    assert len(received) == 3
    assert received[0].event_type == "INVESTIGATION_STARTED"
    assert received[1].event_type == "INTAKE_STARTED"
    assert received[2].event_type == "INVESTIGATION_COMPLETED"
    assert [e.sequence for e in received] == [1, 2, 3]


@pytest.mark.asyncio
async def test_heartbeat_emission_on_idle(broker):
    gen = broker.subscribe(
        investigation_id="inv-idle",
        organization_id="org-idle",
        last_event_id=None,
        heartbeat_interval=0.1,  # Short timeout for test
    )

    # Wait for first event which should be a heartbeat because no live events are published
    first_ev = await asyncio.wait_for(gen.__anext__(), timeout=1.0)
    assert first_ev.event_type == InvestigationEventType.HEARTBEAT.value
    assert first_ev.payload.get("type") == "ping"


def test_slow_consumer_bounded_backpressure(broker):
    # Register subscriber with queue maxsize=2
    q = asyncio.Queue(maxsize=2)
    broker._subscribers["inv-slow"] = {q}
    broker._subscriber_org[q] = "org-slow"

    # Push 5 events: worker must NOT block or raise exception
    for i in range(5):
        broker.publish(
            investigation_id="inv-slow",
            organization_id="org-slow",
            event_type=f"STEP_{i}",
        )

    # Queue contains 2 items (first 2), rest were gracefully dropped to protect worker throughput
    assert q.qsize() == 2
    item1 = q.get_nowait()
    assert item1.sequence == 1
    item2 = q.get_nowait()
    assert item2.sequence == 2
