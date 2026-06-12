from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger("keobot.stream")


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
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stream_started_at: datetime | None = None
    stream_ended_at: datetime | None = None

    def transition_to(self, target: StreamState) -> None:
        validate_transition(self.state, target)
        self.state = target
        self.last_activity = datetime.now(timezone.utc)

    def add_token(self, token: str) -> None:
        self.tokens.append(token)

    def partial_text(self) -> str:
        return "".join(self.tokens)

    def interrupt(self) -> None:
        self.transition_to(StreamState.interrupted)
        self.cancel_event.set()
        self.stream_ended_at = datetime.now(timezone.utc)

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
        self.stream_started_at = datetime.now(timezone.utc)
        self.stream_ended_at = None

    def complete(self) -> None:
        self.transition_to(StreamState.completed)
        self.stream_ended_at = datetime.now(timezone.utc)

    def reset(self) -> None:
        self.state = StreamState.idle
        self.tokens.clear()
        self.cancel_event.clear()
        self.replan_context = None
        self.stream_started_at = None
        self.stream_ended_at = None
        self.last_activity = datetime.now(timezone.utc)

    @property
    def stream_duration(self) -> float | None:
        if self.stream_started_at and self.stream_ended_at:
            return (self.stream_ended_at - self.stream_started_at).total_seconds()
        if self.stream_started_at:
            return (datetime.now(timezone.utc) - self.stream_started_at).total_seconds()
        return None

    def is_expired(self, ttl_seconds: int = 600) -> bool:
        elapsed = (datetime.now(timezone.utc) - self.last_activity).total_seconds()
        return elapsed > ttl_seconds


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
        session = self._sessions.pop(session_id, None)
        if session and session.state == StreamState.streaming:
            session.interrupt()

    def active_count(self) -> int:
        return sum(
            1 for s in self._sessions.values()
            if s.state in (StreamState.streaming, StreamState.replanning)
        )

    def total_sessions(self) -> int:
        return len(self._sessions)

    def cleanup_stale(self, ttl_seconds: int = 600) -> int:
        now = datetime.now(timezone.utc)
        stale_ids = [
            sid for sid, sess in self._sessions.items()
            if sess.is_expired(ttl_seconds)
        ]
        for sid in stale_ids:
            session = self._sessions.pop(sid, None)
            if session:
                if session.state == StreamState.streaming:
                    session.interrupt()
                logger.info(
                    "session_cleanup id=%s state=%s age=%.1fs tokens=%d",
                    sid, session.state.value,
                    (now - session.created_at).total_seconds(),
                    len(session.tokens),
                )
        return len(stale_ids)


_manager: StreamManager | None = None


def get_stream_manager() -> StreamManager:
    global _manager
    if _manager is None:
        _manager = StreamManager()
    return _manager
