from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

_cancellation_registry: dict[str, asyncio.Event] = {}


def create_session() -> str:
    session_id = uuid4().hex
    _cancellation_registry[session_id] = asyncio.Event()
    return session_id


def cancel_session(session_id: str) -> bool:
    event = _cancellation_registry.get(session_id)
    if event is None:
        return False
    event.set()
    return True


def is_cancelled(session_id: str) -> bool:
    event = _cancellation_registry.get(session_id)
    if event is None:
        return False
    return event.is_set()


async def wait_with_cancellation(session_id: str, awaitable: Any, poll_interval: float = 0.1) -> Any:
    event = _cancellation_registry.get(session_id)
    if event is None:
        return await awaitable

    task = asyncio.ensure_future(awaitable)

    while True:
        if event.is_set():
            task.cancel()
            raise asyncio.CancelledError("Session was cancelled.")
        if task.done():
            return task.result()
        await asyncio.sleep(poll_interval)


def cleanup_session(session_id: str) -> None:
    _cancellation_registry.pop(session_id, None)


def get_active_session_ids() -> list[str]:
    return list(_cancellation_registry.keys())
