"""Detached SSE producers backed by replayable Redis Streams."""

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from loguru import logger
from redis.asyncio import Redis

from app.config import config


ProducerFactory = Callable[[], AsyncIterator[dict[str, Any]]]


class ResumableStreamService:
    def __init__(
        self,
        redis_client: Any | None = None,
        namespace: str = "aiops:sse",
        ttl_seconds: int = 86400,
        block_ms: int = 5000,
    ):
        self.redis = redis_client or Redis.from_url(config.redis_url, decode_responses=True)
        self.namespace = namespace
        self.ttl_seconds = ttl_seconds
        self.block_ms = block_ms
        self.running_key = f"{namespace}:running"
        self._tasks: dict[str, asyncio.Task] = {}

    def meta_key(self, stream_id: str) -> str:
        return f"{self.namespace}:{stream_id}:meta"

    def events_key(self, stream_id: str) -> str:
        return f"{self.namespace}:{stream_id}:events"

    def active_key(self, kind: str, session_id: str) -> str:
        return f"{self.namespace}:active:{kind}:{session_id}"

    async def startup(self) -> None:
        await self.redis.ping()
        orphaned = await self.redis.smembers(self.running_key)
        for stream_id in orphaned:
            meta = await self.metadata(stream_id)
            if meta.get("status") != "running":
                await self.redis.srem(self.running_key, stream_id)
                continue
            await self._append(
                stream_id,
                {
                    "type": "error",
                    "stage": "stream_interrupted",
                    "message": "服务重启导致流任务中断，请重新发起请求",
                },
            )
            await self._set_status(stream_id, "failed")
        logger.info("resumable_sse_ready orphaned_streams={}", len(orphaned))

    async def start(
        self,
        kind: str,
        session_id: str,
        producer_factory: ProducerFactory,
    ) -> str:
        stream_id = uuid.uuid4().hex
        now = str(time.time())
        await self.redis.hset(
            self.meta_key(stream_id),
            mapping={
                "stream_id": stream_id,
                "kind": kind,
                "session_id": session_id,
                "status": "running",
                "created_at": now,
                "updated_at": now,
            },
        )
        await self.redis.expire(self.meta_key(stream_id), self.ttl_seconds)
        await self.redis.set(self.active_key(kind, session_id), stream_id, ex=self.ttl_seconds)
        await self.redis.sadd(self.running_key, stream_id)
        await self._append(
            stream_id,
            {
                "type": "stream_start",
                "stream_id": stream_id,
                "kind": kind,
                "session_id": session_id,
            },
        )
        task = asyncio.create_task(
            self._run(stream_id, producer_factory),
            name=f"resumable-{kind}-{stream_id}",
        )
        self._tasks[stream_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(stream_id, None))
        return stream_id

    async def _run(self, stream_id: str, producer_factory: ProducerFactory) -> None:
        terminal = False
        try:
            async for event in producer_factory():
                await self._append(stream_id, event)
                event_type = event.get("type")
                if event_type in {"done", "complete"}:
                    await self._set_status(stream_id, "completed")
                    terminal = True
                    break
                if event_type == "error":
                    await self._set_status(stream_id, "failed")
                    terminal = True
                    break
            if not terminal:
                await self._append(
                    stream_id,
                    {"type": "error", "message": "流任务提前结束，请重新发起请求"},
                )
                await self._set_status(stream_id, "failed")
        except asyncio.CancelledError:
            await self._append(
                stream_id,
                {"type": "error", "message": "服务关闭导致流任务中断，请重新发起请求"},
            )
            await self._set_status(stream_id, "failed")
            raise
        except Exception as exc:
            logger.exception("resumable_sse_producer_failed stream_id={} error={}", stream_id, type(exc).__name__)
            await self._append(
                stream_id,
                {"type": "error", "message": "任务执行失败，请稍后重试"},
            )
            await self._set_status(stream_id, "failed")

    async def _append(self, stream_id: str, event: dict[str, Any]) -> str:
        event_id = await self.redis.xadd(
            self.events_key(stream_id),
            {"payload": json.dumps(event, ensure_ascii=False)},
            maxlen=5000,
            approximate=True,
        )
        await self.redis.expire(self.events_key(stream_id), self.ttl_seconds)
        return str(event_id)

    async def _set_status(self, stream_id: str, status: str) -> None:
        await self.redis.hset(
            self.meta_key(stream_id),
            mapping={"status": status, "updated_at": str(time.time())},
        )
        await self.redis.expire(self.meta_key(stream_id), self.ttl_seconds)
        await self.redis.srem(self.running_key, stream_id)

    async def metadata(self, stream_id: str) -> dict[str, str]:
        return await self.redis.hgetall(self.meta_key(stream_id))

    async def events(
        self,
        stream_id: str,
        after: str = "0-0",
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        cursor = after or "0-0"
        while True:
            batches = await self.redis.xread(
                {self.events_key(stream_id): cursor},
                count=100,
                block=self.block_ms,
            )
            if batches:
                for _, entries in batches:
                    for event_id, fields in entries:
                        cursor = str(event_id)
                        yield cursor, json.loads(fields["payload"])
                continue

            status = (await self.metadata(stream_id)).get("status")
            if status in {"completed", "failed"} or not status:
                return

    async def wait(self, stream_id: str) -> None:
        task = self._tasks.get(stream_id)
        if task:
            await task

    async def close(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self.redis.aclose()


resumable_stream_service = ResumableStreamService()
