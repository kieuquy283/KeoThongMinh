from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, TypeVar

from typing import Awaitable, ParamSpec

logger = logging.getLogger("keobot.stability")

P = ParamSpec("P")
T = TypeVar("T")


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 10.0
    backoff_factor: float = 2.0
    retryable_exceptions: tuple[type[Exception], ...] = (
        TimeoutError,
        ConnectionError,
        ConnectionResetError,
        ConnectionRefusedError,
        OSError,
    )


async def retry_async(
    coro_factory: Callable[[], Awaitable[T]],
    config: RetryConfig | None = None,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> T:
    cfg = config or RetryConfig()
    last_exc: Exception | None = None
    for attempt in range(cfg.max_retries + 1):
        try:
            return await coro_factory()
        except cfg.retryable_exceptions as exc:
            last_exc = exc
            if attempt < cfg.max_retries:
                delay = min(cfg.base_delay * (cfg.backoff_factor ** attempt), cfg.max_delay)
                if on_retry:
                    on_retry(attempt + 1, exc)
                logger.warning(
                    "retry attempt=%d/%d error=%s delay=%.1fs",
                    attempt + 1, cfg.max_retries, exc, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "retry exhausted attempts=%d error=%s",
                    cfg.max_retries + 1, exc,
                )
    raise last_exc  # type: ignore[misc]


def retryable(config: RetryConfig | None = None):
    cfg = config or RetryConfig()

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await retry_async(
                lambda: func(*args, **kwargs),
                config=cfg,
            )
        return wrapper
    return decorator


_TOOL_FALLBACK_RESPONSES: dict[str, Callable[[], dict[str, Any]]] = {}


def register_tool_fallback(intent: str, fallback_fn: Callable[[], dict[str, Any]]) -> None:
    _TOOL_FALLBACK_RESPONSES[intent] = fallback_fn


def get_tool_fallback(intent: str) -> dict[str, Any]:
    fn = _TOOL_FALLBACK_RESPONSES.get(intent)
    if fn:
        return fn()
    return {
        "is_available": False,
        "available": False,
        "message": f"Dich vu {intent} tam thoi khong kha dung.",
        "status": "unavailable",
    }


@dataclass
class TimingStats:
    stream_starts: int = 0
    stream_ends: int = 0
    stream_latency_total: float = 0.0
    tool_executions: int = 0
    tool_execution_time_total: float = 0.0
    interrupts: int = 0
    events_by_type: dict[str, int] = field(default_factory=dict)

    @property
    def avg_stream_latency(self) -> float:
        if self.stream_ends == 0:
            return 0.0
        return self.stream_latency_total / self.stream_ends

    @property
    def avg_tool_execution_time(self) -> float:
        if self.tool_executions == 0:
            return 0.0
        return self.tool_execution_time_total / self.tool_executions


_timing = TimingStats()


def get_timing_stats() -> TimingStats:
    return _timing


def reset_timing_stats() -> None:
    global _timing
    _timing = TimingStats()


def record_event(event_type: str) -> None:
    _timing.events_by_type[event_type] = _timing.events_by_type.get(event_type, 0) + 1
    if event_type == "interrupt":
        _timing.interrupts += 1


def record_stream_start() -> None:
    _timing.stream_starts += 1


def record_stream_end(latency: float) -> None:
    _timing.stream_ends += 1
    _timing.stream_latency_total += latency


def record_tool_execution(elapsed: float) -> None:
    _timing.tool_executions += 1
    _timing.tool_execution_time_total += elapsed


def log_timing_stats() -> None:
    stats = _timing
    logger.info(
        "TimingStats streams=%d/%d avg_latency=%.2fs tools=%d avg_tool=%.2fs interrupts=%d events=%s",
        stats.stream_ends, stats.stream_starts,
        stats.avg_stream_latency,
        stats.tool_executions, stats.avg_tool_execution_time,
        stats.interrupts,
        dict(sorted(stats.events_by_type.items())),
    )


_STREAM_TIMEOUT_SECONDS = 600


def set_stream_timeout(seconds: int) -> None:
    global _STREAM_TIMEOUT_SECONDS
    _STREAM_TIMEOUT_SECONDS = seconds


def get_stream_timeout() -> int:
    return _STREAM_TIMEOUT_SECONDS
