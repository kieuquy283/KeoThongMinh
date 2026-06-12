from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StreamState(str, Enum):
    idle = "idle"
    streaming = "streaming"
    completed = "completed"
    cancelled = "cancelled"


@dataclass
class StreamSession:
    session_id: str
    state: StreamState = StreamState.idle
    tokens: list[str] = field(default_factory=list)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    def add_token(self, token: str) -> None:
        self.tokens.append(token)

    def partial_text(self) -> str:
        return "".join(self.tokens)

    def cancel(self) -> None:
        self.state = StreamState.cancelled
        self.cancel_event.set()

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def start(self) -> None:
        self.state = StreamState.streaming
        self.cancel_event.clear()

    def complete(self) -> None:
        self.state = StreamState.completed

    def reset(self) -> None:
        self.state = StreamState.idle
        self.tokens.clear()
        self.cancel_event.clear()


class StreamManager:
    def __init__(self) -> None:
        self._sessions: dict[str, StreamSession] = {}

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
        return session

    def cancel(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None or session.state == StreamState.idle:
            return False
        session.cancel()
        return True

    def remove_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def active_count(self) -> int:
        return sum(
            1 for s in self._sessions.values()
            if s.state == StreamState.streaming
        )


_manager: StreamManager | None = None


def get_stream_manager() -> StreamManager:
    global _manager
    if _manager is None:
        _manager = StreamManager()
    return _manager
