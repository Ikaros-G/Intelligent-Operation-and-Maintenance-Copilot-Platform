"""Redis-backed cache and LangGraph checkpoint helpers with safe fallback."""

import hashlib
import json
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from loguru import logger
from redis import Redis

from app.config import config
from app.core.observability import RAG_CACHE


class RedisJSONCache:
    def __init__(self, client: Any | None = None, namespace: str = "cache", ttl_seconds: int | None = None):
        self.client = client or Redis.from_url(config.redis_url, decode_responses=True, socket_timeout=2)
        self.namespace = namespace
        self.ttl_seconds = ttl_seconds or config.redis_cache_ttl_seconds

    def _key(self, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"aiops:{self.namespace}:{digest}"

    def get(self, key: str) -> Any | None:
        try:
            value = self.client.get(self._key(key))
            RAG_CACHE.labels(result="hit" if value else "miss").inc()
            return json.loads(value) if value else None
        except Exception as exc:
            RAG_CACHE.labels(result="error").inc()
            logger.warning("redis_cache_read_failed: {}", type(exc).__name__)
            return None

    def set(self, key: str, value: Any) -> None:
        try:
            self.client.setex(self._key(key), self.ttl_seconds, json.dumps(value, ensure_ascii=False))
        except Exception as exc:
            logger.warning("redis_cache_write_failed: {}", type(exc).__name__)

    def delete(self, key: str) -> None:
        try:
            self.client.delete(self._key(key))
        except Exception as exc:
            logger.warning("redis_cache_delete_failed: {}", type(exc).__name__)


async def create_async_checkpointer() -> Any:
    """Create the production Redis saver, falling back to memory when Redis is unavailable."""
    try:
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver

        saver = AsyncRedisSaver(redis_url=config.redis_url, ttl={"default_ttl": 1440, "refresh_on_read": True})
        await saver.asetup()
        logger.info("langgraph_checkpointer_ready backend=redis")
        return saver
    except Exception as exc:
        logger.warning("langgraph_checkpointer_fallback backend=memory reason={}", type(exc).__name__)
        return MemorySaver()


async def close_checkpointer(checkpointer: Any) -> None:
    client = getattr(checkpointer, "_redis", None)
    close = getattr(client, "aclose", None)
    if close:
        await close()
