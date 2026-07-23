import asyncio

from app.services.resumable_stream_service import ResumableStreamService


class FakeAsyncRedis:
    def __init__(self):
        self.hashes = {}
        self.sets = {}
        self.streams = {}
        self.expirations = {}
        self.sequence = 0
        self.changed = asyncio.Condition()

    async def ping(self):
        return True

    async def hset(self, key, mapping):
        self.hashes.setdefault(key, {}).update({str(k): str(v) for k, v in mapping.items()})

    async def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    async def sadd(self, key, *values):
        self.sets.setdefault(key, set()).update(values)

    async def srem(self, key, *values):
        self.sets.setdefault(key, set()).difference_update(values)

    async def smembers(self, key):
        return set(self.sets.get(key, set()))

    async def set(self, key, value, ex=None):
        self.hashes[key] = {"value": value}
        if ex:
            self.expirations[key] = ex

    async def get(self, key):
        return self.hashes.get(key, {}).get("value")

    async def expire(self, key, ttl):
        self.expirations[key] = ttl

    async def delete(self, *keys):
        for key in keys:
            self.hashes.pop(key, None)
            self.streams.pop(key, None)
            self.sets.pop(key, None)

    async def xadd(self, key, fields, maxlen=None, approximate=True):
        async with self.changed:
            self.sequence += 1
            event_id = f"{self.sequence}-0"
            self.streams.setdefault(key, []).append((event_id, dict(fields)))
            self.changed.notify_all()
            return event_id

    async def xread(self, streams, count=None, block=None):
        key, after = next(iter(streams.items()))

        def unread():
            after_number = int(str(after).split("-", 1)[0])
            return [item for item in self.streams.get(key, []) if int(item[0].split("-", 1)[0]) > after_number]

        events = unread()
        if not events and block:
            try:
                async with self.changed:
                    await asyncio.wait_for(self.changed.wait(), block / 1000)
            except TimeoutError:
                pass
            events = unread()
        return [(key, events[:count])] if events else []

    async def aclose(self):
        return None


async def test_stream_continues_after_subscriber_disconnect_and_resumes_from_cursor():
    redis = FakeAsyncRedis()
    service = ResumableStreamService(redis_client=redis, namespace="test", block_ms=20)
    continue_producing = asyncio.Event()

    async def producer():
        yield {"type": "content", "data": "first"}
        await continue_producing.wait()
        yield {"type": "content", "data": "second"}
        yield {"type": "done", "data": {"answer": "firstsecond"}}

    stream_id = await service.start("chat", "session-1", producer)
    received = []
    async for event_id, event in service.events(stream_id):
        received.append((event_id, event))
        if event.get("data") == "first":
            break

    last_event_id = received[-1][0]
    continue_producing.set()
    await service.wait(stream_id)

    resumed = []
    async for event_id, event in service.events(stream_id, after=last_event_id):
        resumed.append((event_id, event))

    assert [event["type"] for _, event in resumed] == ["content", "done"]
    assert resumed[0][1]["data"] == "second"
    assert all(event_id != last_event_id for event_id, _ in resumed)
    assert (await service.metadata(stream_id))["status"] == "completed"

    await service.close()


async def test_startup_marks_orphaned_running_stream_as_failed():
    redis = FakeAsyncRedis()
    service = ResumableStreamService(redis_client=redis, namespace="test", block_ms=20)
    stream_id = "orphaned"
    await redis.hset(service.meta_key(stream_id), mapping={"status": "running", "kind": "aiops"})
    await redis.sadd(service.running_key, stream_id)

    await service.startup()

    events = []
    async for _, event in service.events(stream_id):
        events.append(event)

    assert events[-1]["type"] == "error"
    assert "重启" in events[-1]["message"]
    assert (await service.metadata(stream_id))["status"] == "failed"

    await service.close()
