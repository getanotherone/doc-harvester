"""Redis-backed document processing queue.

FIFO queue using Redis Lists (RPUSH/BLPOP). Task metadata in Redis Hashes.
Progress tracking via lightweight HSET.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

import redis.asyncio as aioredis

from doc_proc.config import settings
from doc_proc.db.enums import QueueTaskStatus

logger = logging.getLogger(__name__)

QUEUE_KEY = "doc_proc:queue:documents"
PROCESSING_KEY = "doc_proc:queue:processing"
TASK_PREFIX = "doc_proc:task:"
STATS_KEY = "doc_proc:stats"
TASK_TTL = 604800  # 7 days


@dataclass
class QueueTask:
    task_id: str = ""
    document_id: str = ""
    filename: str = ""
    file_path: str = ""
    status: str = QueueTaskStatus.queued
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    error: str = ""
    retry_count: int = 0
    max_retries: int = 3
    metadata: dict = field(default_factory=dict)
    progress_percent: int = 0
    current_step: str = ""
    steps_detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, str]:
        d = asdict(self)
        d["metadata"] = json.dumps(d["metadata"])
        d["steps_detail"] = json.dumps(d["steps_detail"])
        d["retry_count"] = str(d["retry_count"])
        d["max_retries"] = str(d["max_retries"])
        d["progress_percent"] = str(d["progress_percent"])
        return d

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> QueueTask:
        return cls(
            task_id=d.get("task_id", ""),
            document_id=d.get("document_id", ""),
            filename=d.get("filename", ""),
            file_path=d.get("file_path", ""),
            status=d.get("status", QueueTaskStatus.queued),
            created_at=d.get("created_at", ""),
            started_at=d.get("started_at", ""),
            completed_at=d.get("completed_at", ""),
            error=d.get("error", ""),
            retry_count=int(d.get("retry_count", 0)),
            max_retries=int(d.get("max_retries", 3)),
            metadata=json.loads(d.get("metadata", "{}")),
            progress_percent=int(d.get("progress_percent", 0)),
            current_step=d.get("current_step", ""),
            steps_detail=json.loads(d.get("steps_detail", "{}")),
        )


class DocumentQueueService:
    def __init__(self):
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.redis_url)
        return self._redis

    async def enqueue(
        self,
        document_id: str,
        filename: str,
        file_path: str,
        metadata: dict | None = None,
    ) -> QueueTask:
        redis = await self._get_redis()
        task = QueueTask(
            task_id=str(uuid.uuid4()),
            document_id=document_id,
            filename=filename,
            file_path=file_path,
            created_at=datetime.now(UTC).isoformat(),
            metadata=metadata or {},
        )
        task_key = f"{TASK_PREFIX}{task.task_id}"
        await redis.hset(task_key, mapping=task.to_dict())
        await redis.expire(task_key, TASK_TTL)
        await redis.rpush(QUEUE_KEY, task.task_id)
        await redis.hincrby(STATS_KEY, "total_enqueued", 1)
        return task

    async def dequeue(self, timeout: int = 5) -> QueueTask | None:
        redis = await self._get_redis()
        result = await redis.blpop(QUEUE_KEY, timeout=timeout)
        if result is None:
            return None

        task_id = result[1].decode() if isinstance(result[1], bytes) else result[1]
        task_key = f"{TASK_PREFIX}{task_id}"
        data = await redis.hgetall(task_key)
        if not data:
            return None

        decoded = {
            (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
            for k, v in data.items()
        }
        task = QueueTask.from_dict(decoded)
        task.status = QueueTaskStatus.processing
        task.started_at = datetime.now(UTC).isoformat()
        await redis.hset(task_key, mapping={"status": task.status, "started_at": task.started_at})
        await redis.sadd(PROCESSING_KEY, task_id)
        return task

    async def complete(self, task_id: str) -> None:
        redis = await self._get_redis()
        now = datetime.now(UTC).isoformat()
        await redis.hset(
            f"{TASK_PREFIX}{task_id}",
            mapping={
                "status": QueueTaskStatus.completed,
                "completed_at": now,
                "progress_percent": "100",
            },
        )
        await redis.srem(PROCESSING_KEY, task_id)
        await redis.hincrby(STATS_KEY, "total_completed", 1)

    async def fail(self, task_id: str, error: str, permanent: bool = False) -> None:
        redis = await self._get_redis()
        task_key = f"{TASK_PREFIX}{task_id}"
        data = await redis.hgetall(task_key)
        decoded = {
            (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
            for k, v in data.items()
        }
        task = QueueTask.from_dict(decoded)

        if not permanent and task.retry_count < task.max_retries:
            task.retry_count += 1
            task.status = QueueTaskStatus.retrying
            task.error = error
            await redis.hset(task_key, mapping={
                "status": task.status,
                "error": error,
                "retry_count": str(task.retry_count),
            })
            await redis.rpush(QUEUE_KEY, task_id)
        else:
            now = datetime.now(UTC).isoformat()
            await redis.hset(task_key, mapping={
                "status": QueueTaskStatus.failed,
                "error": error,
                "completed_at": now,
            })
            await redis.hincrby(STATS_KEY, "total_failed", 1)

        await redis.srem(PROCESSING_KEY, task_id)

    async def update_progress(
        self, task_id: str, percent: int, step: str, detail: dict | None = None
    ) -> None:
        redis = await self._get_redis()
        mapping: dict[str, str] = {
            "progress_percent": str(max(0, min(100, percent))),
            "current_step": step,
        }
        if detail:
            mapping["steps_detail"] = json.dumps(detail)
        await redis.hset(f"{TASK_PREFIX}{task_id}", mapping=mapping)

    async def cancel(self, task_id: str) -> None:
        redis = await self._get_redis()
        now = datetime.now(UTC).isoformat()
        await redis.hset(
            f"{TASK_PREFIX}{task_id}",
            mapping={
                "status": QueueTaskStatus.failed,
                "error": "Cancelled by user",
                "completed_at": now,
            },
        )
        await redis.lrem(QUEUE_KEY, 0, task_id)
        await redis.srem(PROCESSING_KEY, task_id)

    async def get_task(self, task_id: str) -> QueueTask | None:
        redis = await self._get_redis()
        data = await redis.hgetall(f"{TASK_PREFIX}{task_id}")
        if not data:
            return None
        decoded = {
            (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
            for k, v in data.items()
        }
        return QueueTask.from_dict(decoded)

    async def get_stats(self) -> dict:
        redis = await self._get_redis()
        stats = await redis.hgetall(STATS_KEY)
        queue_len = await redis.llen(QUEUE_KEY)
        processing = await redis.scard(PROCESSING_KEY)
        decoded = {
            (k.decode() if isinstance(k, bytes) else k): int(
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in stats.items()
        }
        decoded["queue_length"] = queue_len
        decoded["processing"] = processing
        return decoded

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
            self._redis = None
