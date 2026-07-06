from app.core.persistence import RedisJSONCache


class FakeRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.last_ttl = ttl

    def delete(self, key):
        self.values.pop(key, None)


def test_redis_json_cache_round_trips_namespaced_values():
    client = FakeRedis()
    cache = RedisJSONCache(client=client, namespace="rag", ttl_seconds=60)

    cache.set("question", {"answer": "ok"})

    assert cache.get("question") == {"answer": "ok"}
    assert len(client.values) == 1
    assert next(iter(client.values)).startswith("aiops:rag:")
    assert "question" not in next(iter(client.values))
    assert client.last_ttl == 60


def test_redis_json_cache_degrades_to_miss_when_redis_fails():
    class BrokenRedis:
        def get(self, key):
            raise ConnectionError("offline")

    cache = RedisJSONCache(client=BrokenRedis(), namespace="rag", ttl_seconds=60)

    assert cache.get("question") is None
