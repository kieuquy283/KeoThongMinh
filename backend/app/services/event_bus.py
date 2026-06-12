from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from typing import Awaitable


class EventType(str, Enum):
    user_message = "user_message"
    llm_token = "llm_token"
    stream_start = "stream_start"
    stream_end = "stream_end"
    tool_call = "tool_call"
    tool_result = "tool_result"
    interrupt = "interrupt"
    cancel = "cancel"
    replanning = "replanning"


@dataclass
class Event:
    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "payload": self.payload,
            "session_id": self.session_id,
        }


SyncListener = Callable[[Event], None]
AsyncListener = Callable[[Event], Awaitable[None]]
Listener = SyncListener | AsyncListener


class EventBus:
    def __init__(self) -> None:
        self._sync_listeners: dict[EventType, list[SyncListener]] = {}
        self._async_listeners: dict[EventType, list[AsyncListener]] = {}

    def subscribe(self, event_type: EventType, listener: Listener) -> Callable[[], None]:
        if inspect.iscoroutinefunction(listener):
            self._async_listeners.setdefault(event_type, []).append(listener)
        else:
            self._sync_listeners.setdefault(event_type, []).append(listener)

        def unsubscribe() -> None:
            if inspect.iscoroutinefunction(listener):
                self._async_listeners[event_type].remove(listener)
            else:
                self._sync_listeners[event_type].remove(listener)

        return unsubscribe

    def publish(self, event: Event) -> None:
        listeners = self._sync_listeners.get(event.type, [])
        for listener in listeners:
            listener(event)

    async def publish_async(self, event: Event) -> None:
        self.publish(event)
        listeners = self._async_listeners.get(event.type, [])
        for listener in listeners:
            await listener(event)

    def clear(self) -> None:
        self._sync_listeners.clear()
        self._async_listeners.clear()


_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


def reset_event_bus() -> None:
    global _bus
    if _bus is not None:
        _bus.clear()
    _bus = None
