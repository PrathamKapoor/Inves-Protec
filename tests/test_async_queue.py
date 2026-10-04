"""Tests for asynchronous task queue implementations: InMemoryTaskQueue and RedisStreamTaskQueue."""
import time
import uuid
import pytest
import redis

from sangyan.async_exec.models import AsyncTask, TaskStatus, TaskType
from sangyan.async_exec.queue import InMemoryTaskQueue, RedisStreamTaskQueue


def test_in_memory_task_queue_lifecycle():
    queue = InMemoryTaskQueue()

    task1 = AsyncTask(
        task_id="task-q1",
        organization_id="org-sebi",
        user_id="analyst-1",
        investigation_id="inv-001",
        task_type=TaskType.WORKFLOW_START,
        payload={"query": "first"},
    )
    task2 = AsyncTask(
        task_id="task-q2",
        organization_id="org-sebi",
        user_id="analyst-1",
        investigation_id="inv-002",
        task_type=TaskType.WORKFLOW_START,
        payload={"query": "second"},
    )

    msg1 = queue.enqueue(task1)
    msg2 = queue.enqueue(task2)
    assert msg1 is not None
    assert msg2 is not None

    # Claim one task
    claimed = queue.claim_tasks("worker-a", batch_size=1)
    assert len(claimed) == 1
    stream_id, task = claimed[0]
    assert stream_id == msg1
    assert task.task_id == "task-q1"

    # Ack first task
    queue.ack(stream_id)

    # Claim second task
    claimed2 = queue.claim_tasks("worker-b", batch_size=1)
    assert len(claimed2) == 1
    stream_id2, task_b = claimed2[0]
    assert stream_id2 == msg2
    assert task_b.task_id == "task-q2"

    # Dead letter second task
    dl_id = queue.dead_letter(task_b, reason="Exhausted retries", stream_message_id=stream_id2)
    assert dl_id.startswith("dl-")

    # Queue should now be empty
    claimed_empty = queue.claim_tasks("worker-c", batch_size=1)
    assert len(claimed_empty) == 0

    queue.close()


def test_in_memory_task_queue_reclaim_expired():
    queue = InMemoryTaskQueue()

    task = AsyncTask(
        task_id="task-reclaim",
        organization_id="org-1",
        user_id="user-1",
        investigation_id="inv-rec",
        task_type=TaskType.WORKFLOW_START,
    )

    msg_id = queue.enqueue(task)
    claimed = queue.claim_tasks("crashed-worker", batch_size=1)
    assert len(claimed) == 1

    # Immediate reclaim should find nothing (not expired)
    reclaimed_none = queue.reclaim_expired("active-worker", min_idle_time_ms=500)
    assert len(reclaimed_none) == 0

    # Wait for expiration
    time.sleep(0.6)
    reclaimed = queue.reclaim_expired("active-worker", min_idle_time_ms=500)
    assert len(reclaimed) == 1
    assert reclaimed[0][0] == msg_id
    assert reclaimed[0][1].task_id == "task-reclaim"

    queue.ack(msg_id)
    queue.close()


def _is_redis_available() -> bool:
    try:
        r = redis.Redis.from_url("redis://localhost:6379", socket_timeout=1)
        r.ping()
        r.close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _is_redis_available(), reason="Redis is not reachable on localhost:6379")
def test_redis_stream_task_queue_live():
    uid = uuid.uuid4().hex[:8]
    stream_name = f"test:sangyan:tasks:{uid}"
    group_name = f"test:grp:{uid}"
    dl_stream = f"test:sangyan:dl:{uid}"
    redis_url = "redis://localhost:6379"

    client = redis.Redis.from_url(redis_url, decode_responses=True)
    try:
        queue = RedisStreamTaskQueue(
            redis_url=redis_url,
            stream_name=stream_name,
            group_name=group_name,
            dead_letter_stream=dl_stream,
            redis_client=client,
        )

        task = AsyncTask(
            task_id=f"task-redis-{uid}",
            organization_id="org-sebi",
            user_id="analyst-99",
            investigation_id="inv-redis-001",
            task_type=TaskType.WORKFLOW_START,
            payload={"stock_symbol": "ABC_CORP", "priority": "HIGH"},
        )

        # 1. Enqueue
        msg_id = queue.enqueue(task)
        assert msg_id is not None
        assert "-" in msg_id  # Redis stream ID format: <timestamp>-<sequence>

        # 2. Claim
        claimed = queue.claim_tasks(consumer_name="worker-1", batch_size=1, block_ms=1000)
        assert len(claimed) == 1
        c_msg_id, c_task = claimed[0]
        assert c_msg_id == msg_id
        assert c_task.task_id == task.task_id
        assert c_task.organization_id == "org-sebi"
        assert c_task.payload["stock_symbol"] == "ABC_CORP"

        # 3. ACK
        queue.ack(c_msg_id)

        # 4. Dead letter testing
        dl_task = AsyncTask(
            task_id=f"task-dl-{uid}",
            organization_id="org-sebi",
            user_id="analyst-99",
            investigation_id="inv-redis-002",
            task_type=TaskType.WORKFLOW_START,
        )
        dl_msg_id = queue.enqueue(dl_task)
        claimed_dl = queue.claim_tasks(consumer_name="worker-1", batch_size=1, block_ms=500)
        assert len(claimed_dl) == 1

        dl_res = queue.dead_letter(dl_task, reason="Max retries exceeded", stream_message_id=dl_msg_id)
        assert dl_res is not None

        # Verify DL stream received message
        dl_entries = client.xrange(dl_stream)
        assert len(dl_entries) == 1
        assert dl_entries[0][1]["task_id"] == dl_task.task_id
        assert dl_entries[0][1]["reason"] == "Max retries exceeded"

        queue.close()
    finally:
        client.delete(stream_name, dl_stream)
        client.close()
