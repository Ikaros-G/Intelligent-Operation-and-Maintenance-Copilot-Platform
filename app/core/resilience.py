"""Timeout, retry, and circuit-breaker policy for external tool calls."""

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_fixed

from app.config import config


class CircuitOpenError(RuntimeError):
    pass


@dataclass
class _CircuitState:
    failures: int = 0
    opened_at: float | None = None


def _is_transient(exc: BaseException) -> bool:
    return isinstance(exc, (ConnectionError, TimeoutError, asyncio.TimeoutError))


class ResilientToolExecutor:
    def __init__(
        self,
        timeout_seconds: float | None = None,
        max_attempts: int | None = None,
        failure_threshold: int | None = None,
        recovery_seconds: float | None = None,
        wait_seconds: float = 0.25,
    ):
        self.timeout_seconds = timeout_seconds or config.tool_timeout_seconds
        self.max_attempts = max_attempts or config.tool_max_attempts
        self.failure_threshold = failure_threshold or config.circuit_failure_threshold
        self.recovery_seconds = recovery_seconds or config.circuit_recovery_seconds
        self.wait_seconds = wait_seconds
        self._circuits: dict[str, _CircuitState] = {}

    async def invoke(self, tool: Any, arguments: dict[str, Any]) -> Any:
        name = getattr(tool, "name", tool.__class__.__name__)
        state = self._circuits.setdefault(name, _CircuitState())
        if state.opened_at is not None:
            if time.monotonic() - state.opened_at < self.recovery_seconds:
                raise CircuitOpenError(f"工具 {name} 熔断中")
            state.opened_at = None
            state.failures = 0

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.max_attempts),
                wait=wait_fixed(self.wait_seconds),
                retry=retry_if_exception(_is_transient),
                reraise=True,
            ):
                with attempt:
                    async with asyncio.timeout(self.timeout_seconds):
                        result = await tool.ainvoke(arguments)
            state.failures = 0
            return result
        except Exception:
            state.failures += 1
            if state.failures >= self.failure_threshold:
                state.opened_at = time.monotonic()
            raise


resilient_tool_executor = ResilientToolExecutor()
