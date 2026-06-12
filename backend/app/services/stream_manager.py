from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StreamState(str, Enum):
    idle = "idle"
    streaming = "streaming"
    interrupted = "interrupted"
    replanning = "replanning"
    completed = "completed"


_VALID_TRANSITIONS: dict[StreamState, set[StreamState]] = {
    StreamState.idle: {StreamState.streaming},
    StreamState.streaming: {StreamState.completed, StreamState.interrupted, StreamState.replanning},
    StreamState.interrupted: {StreamState.idle, StreamState.replanning},
    StreamState.replanning: {StreamState.streaming, StreamState.completed, StreamState.interrupted},
    StreamState.completed: {StreamState.idle},
}


class InvalidTransitionError(Exception):
    pass


def validate_transition(from_state: StreamState, to_state: StreamState) -> None:
    allowed = _VALID_TRANSITIONS.get(from_state)
    if allowed is None or to_state not in allowed:
        raise InvalidTransitionError(
            f"Invalid transition: {from_state.value} -> {to_state.value}"
        )


@dataclass
class StreamSession:
    session_id: str
    state: StreamState = StreamState.idle
    tokens: list[str] = field(default_factory=list)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    replan_context: dict[str, Any] | None = None

    def transition_to(self, target: StreamState) -> None:
        validate_transition(self.state, target)
        self.state = target

    def add_token(self, token: str) -> None:
        self.tokens.append(token)

    def partial_text(self) -> str:
        return "".join(self.tokens)

    def interrupt(self) -> None:
        self.transition_to(StreamState.interrupted)
        self.cancel_event.set()

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def start(self) -> None:
        allowed = _VALID_TRANSITIONS.get(self.state)
        if allowed and StreamState.streaming in allowed:
            self.transition_to(StreamState.streaming)
        else:
            self.reset()
            self.transition_to(StreamState.streaming)
        self.cancel_event.clear()

    def complete(self) -> None:
        self.transition_to(StreamState.completed)

    def reset(self) -> None:
        self.state = StreamState.idle
        self.tokens.clear()
        self.cancel_event.clear()
        self.replan_context = None


class StreamManager:
    def __init__(self) -> None:
        self._sessions: dict[str, StreamSession] = {}
        self._started = False

    def subscribe_to_events(self) -> None:
        if self._started:
            return
        self._started = True
        from app.services.event_bus import EventType, get_event_bus
        bus = get_event_bus()
        bus.subscribe(EventType.cancel, self._on_cancel_event)
        bus.subscribe(EventType.interrupt, self._on_interrupt_event)

    def _on_cancel_event(self, event: Event) -> None:
        session_id = event.session_id
        if session_id:
            self.cancel(session_id)

    def _on_interrupt_event(self, event: Event) -> None:
        session_id = event.session_id
        if session_id:
            session = self._sessions.get(session_id)
            if session and session.state in (StreamState.streaming, StreamState.replanning):
                session.interrupt()

    def _emit(self, event_type: str, session_id: str | None = None, payload: dict[str, Any] | None = None) -> None:
        from app.services.event_bus import Event as EBEvent, EventType as ET, get_event_bus
        try:
            et = ET(event_type)
        except ValueError:
            return
        bus = get_event_bus()
        ev = EBEvent(type=et, payload=payload or {}, session_id=session_id)
        bus.publish(ev)

    def create_session(self, session_id: str) -> StreamSession:
        session = StreamSession(session_id=session_id)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> StreamSession | None:
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str) -> StreamSession:
        session = self._sessions.get(session_id)
        if session is None:
            session = self.create_session(session_id)
        self.subscribe_to_events()
        return session

    def cancel(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None or session.state not in (StreamState.streaming, StreamState.replanning):
            return False
        session.interrupt()
        self._emit("interrupt", session_id=session_id)
        return True

    def remove_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def active_count(self) -> int:
        return sum(
            1 for s in self._sessions.values()
            if s.state in (StreamState.streaming, StreamState.replanning)
        )


_manager: StreamManager | None = None


def get_stream_manager() -> StreamManager:
    global _manager
    if _manager is None:
        _manager = StreamManager()
    return _manager
