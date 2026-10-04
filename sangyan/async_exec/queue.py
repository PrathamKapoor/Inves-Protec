"""Asynchronous task queue abstractions and Redis Streams implementation with consumer groups."""
from __future__ import annotations

import json
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from sangyan.async_exec.models import AsyncTask
from sangyan.core.errors import StorageError
from sangyan.core.logging import get_logger

logger = get_logger("sangyan.async_exec.queue")


class TaskQueue(ABC):
    """Abstract interface for task streaming, leasing, and consumer group operations."""

    @abstractmethod
    def enqueue(self, task: AsyncTask) -> str:
        """Enqueue task into the stream. Returns broker message identifier."""
        ...

    @abstractmethod
    def claim_tasks(
        self,
        consumer_name: str,
        batch_size: int = 1,
        block_ms: int = 1000,
    ) -> list[tuple[str, AsyncTask]]:
        """Read and lease unacknowledged tasks for the given consumer.

        Returns list of (stream_message_id, AsyncTask).
        """
        ...

    @abstractmethod
    def ack(self, stream_message_id: str) -> None:
        """Acknowledge completed task in the broker stream."""
        ...

    @abstractmethod
    def dead_letter(
        self,
        task: AsyncTask,
        reason: str,
        stream_message_id: Optional[str] = None,
    ) -> str:
        """Move task to the dead-letter stream and acknowledge original stream message."""
        ...

    @abstractmethod
    def reclaim_expired(
        self,
        consumer_name: str,
        min_idle_time_ms: int = 60000,
        batch_size: int = 10,
    ) -> list[tuple[str, AsyncTask]]:
        """Claim tasks that have been pending longer than min_idle_time_ms."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release underlying connections."""
        ...

    def pending_count(self) -> int:
        """Number of delivered-but-unacknowledged entries (stream backlog telemetry)."""
        return 0


class RedisStreamTaskQueue(TaskQueue):
    """Production task queue implementation backed by Redis Streams (XADD, XREADGROUP, XACK, XCLAIM)."""

    def __init__(
        self,
        redis_url: str,
        stream_name: str = "sangyan:tasks:stream",
        group_name: str = "sangyan:task_workers",
        dead_letter_stream: str = "sangyan:tasks:dead_letter",
        redis_client: Optional[Any] = None,
    ) -> None:
        self.stream_name = stream_name
        self.group_name = group_name
        self.dead_letter_stream = dead_letter_stream
        self._redis = redis_client
        self._redis_url = redis_url
        self._ensure_client()
        self._ensure_group()

    def _ensure_client(self) -> None:
        if self._redis is None:
            import redis
            self._redis = redis.Redis.from_url(self._redis_url, decode_responses=True)

    def _ensure_group(self) -> None:
        try:
            self._redis.xgroup_create(self.stream_name, self.group_name, id="0", mkstream=True)
        except Exception as exc:
            msg = str(exc).lower()
            if "busygroup" in msg or "already exists" in msg:
                pass  # Group already initialized
            else:
                logger.warning("Could not create Redis consumer group %s: %s", self.group_name, exc)

    def enqueue(self, task: AsyncTask) -> str:
        msg_payload = {
            "task_id": task.task_id,
            "organization_id": task.organization_id,
            "user_id": task.user_id,
            "investigation_id": task.investigation_id,
            "task_type": task.task_type,
            "status": task.status,
            "payload": json.dumps(task.payload),
            "retry_count": str(task.retry_count),
            "max_retries": str(task.max_retries),
            "created_at": str(task.created_at),
        }
        msg_id = self._redis.xadd(self.stream_name, msg_payload)
        return str(msg_id)

    def claim_tasks(
        self,
        consumer_name: str,
        batch_size: int = 1,
        block_ms: int = 1000,
    ) -> list[tuple[str, AsyncTask]]:
        try:
            entries = self._redis.xreadgroup(
                self.group_name,
                consumer_name,
                {self.stream_name: ">"},
                count=batch_size,
                block=block_ms,
            )
        except Exception as exc:
            logger.error("Failed to read from Redis Stream %s: %s", self.stream_name, exc)
            return []

        results: list[tuple[str, AsyncTask]] = []
        if not entries:
            return results

        for stream_key, msgs in entries:
            for msg_id, fields in msgs:
                try:
                    task = AsyncTask(
                        task_id=fields["task_id"],
                        organization_id=fields["organization_id"],
                        user_id=fields["user_id"],
                        investigation_id=fields["investigation_id"],
                        task_type=fields["task_type"],
                        status=fields.get("status", "QUEUED"),
                        payload=json.loads(fields.get("payload", "{}")),
                        retry_count=int(fields.get("retry_count", 0)),
                        max_retries=int(fields.get("max_retries", 3)),
                        created_at=float(fields.get("created_at", time.time())),
                    )
                    results.append((str(msg_id), task))
                except Exception as parse_err:
                    logger.error("Failed to deserialize task from stream msg %s: %s", msg_id, parse_err)
        return results

    def ack(self, stream_message_id: str) -> None:
        try:
            self._redis.xack(self.stream_name, self.group_name, stream_message_id)
        except Exception as exc:
            logger.error("Failed to ACK stream message %s: %s", stream_message_id, exc)

    def dead_letter(
        self,
        task: AsyncTask,
        reason: str,
        stream_message_id: Optional[str] = None,
    ) -> str:
        dl_payload = {
            "task_id": task.task_id,
            "organization_id": task.organization_id,
            "investigation_id": task.investigation_id,
            "task_type": task.task_type,
            "reason": reason,
            "retry_count": str(task.retry_count),
            "payload": json.dumps(task.payload),
            "failed_at": str(time.time()),
        }
        dl_id = self._redis.xadd(self.dead_letter_stream, dl_payload)
        if stream_message_id:
            self.ack(stream_message_id)
        return str(dl_id)

    def reclaim_expired(
        self,
        consumer_name: str,
        min_idle_time_ms: int = 60000,
        batch_size: int = 10,
    ) -> list[tuple[str, AsyncTask]]:
        """Reclaim pending messages idle longer than min_idle_time_ms via xautoclaim or xpending+xclaim."""
        results: list[tuple[str, AsyncTask]] = []
        try:
            # First try xautoclaim if supported (Redis >= 6.2)
            if hasattr(self._redis, "xautoclaim"):
                res = self._redis.xautoclaim(
                    self.stream_name,
                    self.group_name,
                    consumer_name,
                    min_idle_time=min_idle_time_ms,
                    start_id="0-0",
                    count=batch_size,
                )
                # res is (next_start_id, [(msg_id, fields), ...], [deleted_ids])
                messages = res[1] if isinstance(res, (list, tuple)) and len(res) > 1 else []
                for msg_id, fields in messages:
                    if fields:
                        t = AsyncTask(
                            task_id=fields["task_id"],
                            organization_id=fields["organization_id"],
                            user_id=fields["user_id"],
                            investigation_id=fields["investigation_id"],
                            task_type=fields["task_type"],
                            status=fields.get("status", "QUEUED"),
                            payload=json.loads(fields.get("payload", "{}")),
                            retry_count=int(fields.get("retry_count", 0)),
                            max_retries=int(fields.get("max_retries", 3)),
                            created_at=float(fields.get("created_at", time.time())),
                        )
                        results.append((str(msg_id), t))
                return results

            # Fallback for older redis clients: xpending and xclaim
            pending_res = self._redis.xpending_range(
                self.stream_name,
                self.group_name,
                min="-",
                max="+",
                count=batch_size,
            )
            for item in pending_res:
                idle = item.get("idle", 0)
                msg_id = item.get("message_id")
                if idle >= min_idle_time_ms and msg_id:
                    claimed = self._redis.xclaim(
                        self.stream_name,
                        self.group_name,
                        consumer_name,
                        min_idle_time=min_idle_time_ms,
                        message_ids=[msg_id],
                    )
                    for c_id, c_fields in claimed:
                        if c_fields:
                            t = AsyncTask(
                                task_id=c_fields["task_id"],
                                organization_id=c_fields["organization_id"],
                                user_id=c_fields["user_id"],
                                investigation_id=c_fields["investigation_id"],
                                task_type=c_fields["task_type"],
                                status=c_fields.get("status", "QUEUED"),
                                payload=json.loads(c_fields.get("payload", "{}")),
                                retry_count=int(c_fields.get("retry_count", 0)),
                                max_retries=int(c_fields.get("max_retries", 3)),
                                created_at=float(c_fields.get("created_at", time.time())),
                            )
                            results.append((str(c_id), t))
        except Exception as exc:
            logger.warning("Error during reclaim_expired: %s", exc)
        return results

    def pending_count(self) -> int:
        """Broker pending-entries count via XPENDING for this consumer group."""
        try:
            info = self._redis.xpending(self.stream_name, self.group_name)
            if isinstance(info, dict):
                return int(info.get("pending", 0))
            return int(info[0]) if info else 0
        except Exception:
            return 0

    def close(self) -> None:
        if self._redis is not None:
            try:
                self._redis.close()
            except Exception:
                pass


class InMemoryTaskQueue(TaskQueue):
    """Thread-safe in-memory stream task queue for deterministic testing and local emulation."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._messages: list[tuple[str, AsyncTask, float]] = []  # (id, task, added_at)
        self._pending: dict[str, tuple[str, AsyncTask, str, float]] = {}  # msg_id -> (consumer, task, id, leased_at)
        self._dead_letter_stream: list[tuple[str, AsyncTask, str, float]] = []
        self._seq = 0

    def enqueue(self, task: AsyncTask) -> str:
        with self._lock:
            self._seq += 1
            msg_id = f"{int(time.time() * 1000)}-{self._seq}"
            self._messages.append((msg_id, task, time.time()))
            return msg_id

    def claim_tasks(
        self,
        consumer_name: str,
        batch_size: int = 1,
        block_ms: int = 1000,
    ) -> list[tuple[str, AsyncTask]]:
        with self._lock:
            claimed: list[tuple[str, AsyncTask]] = []
            while self._messages and len(claimed) < batch_size:
                msg_id, task, added_at = self._messages.pop(0)
                self._pending[msg_id] = (consumer_name, task, msg_id, time.time())
                claimed.append((msg_id, task))
            return claimed

    def ack(self, stream_message_id: str) -> None:
        with self._lock:
            self._pending.pop(stream_message_id, None)

    def dead_letter(
        self,
        task: AsyncTask,
        reason: str,
        stream_message_id: Optional[str] = None,
    ) -> str:
        with self._lock:
            self._seq += 1
            dl_id = f"dl-{int(time.time() * 1000)}-{self._seq}"
            self._dead_letter_stream.append((dl_id, task, reason, time.time()))
            if stream_message_id:
                self.ack(stream_message_id)
            return dl_id

    def reclaim_expired(
        self,
        consumer_name: str,
        min_idle_time_ms: int = 60000,
        batch_size: int = 10,
    ) -> list[tuple[str, AsyncTask]]:
        with self._lock:
            now = time.time()
            min_idle_sec = min_idle_time_ms / 1000.0
            reclaimed: list[tuple[str, AsyncTask]] = []
            for msg_id, (prev_consumer, task, _, leased_at) in list(self._pending.items()):
                if now - leased_at >= min_idle_sec:
                    self._pending[msg_id] = (consumer_name, task, msg_id, now)
                    reclaimed.append((msg_id, task))
                    if len(reclaimed) >= batch_size:
                        break
            return reclaimed

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def close(self) -> None:
        with self._lock:
            self._messages.clear()
            self._pending.clear()
