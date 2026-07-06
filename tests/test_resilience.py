import pytest

from app.core.resilience import CircuitOpenError, ResilientToolExecutor


class FlakyTool:
    name = "flaky"

    def __init__(self):
        self.calls = 0

    async def ainvoke(self, args):
        self.calls += 1
        if self.calls < 3:
            raise ConnectionError("temporary")
        return {"ok": True}


async def test_tool_executor_retries_transient_failures():
    tool = FlakyTool()
    executor = ResilientToolExecutor(timeout_seconds=1, max_attempts=3, wait_seconds=0)

    assert await executor.invoke(tool, {}) == {"ok": True}
    assert tool.calls == 3


async def test_circuit_opens_after_repeated_failures():
    class BrokenTool:
        name = "broken"

        async def ainvoke(self, args):
            raise ConnectionError("offline")

    executor = ResilientToolExecutor(
        timeout_seconds=1,
        max_attempts=1,
        failure_threshold=2,
        recovery_seconds=60,
        wait_seconds=0,
    )

    with pytest.raises(ConnectionError):
        await executor.invoke(BrokenTool(), {})
    with pytest.raises(ConnectionError):
        await executor.invoke(BrokenTool(), {})
    with pytest.raises(CircuitOpenError):
        await executor.invoke(BrokenTool(), {})
