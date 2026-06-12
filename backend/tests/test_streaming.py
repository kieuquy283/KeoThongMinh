from __future__ import annotations

import asyncio
import json

import pytest
from app.services.stream_manager import StreamManager, StreamSession, StreamState, get_stream_manager


class TestStreamSession:
    def test_initial_state(self):
        session = StreamSession(session_id="test")
        assert session.state == StreamState.idle
        assert session.tokens == []
        assert not session.is_cancelled()

    def test_start_transitions_to_streaming(self):
        session = StreamSession(session_id="test")
        session.start()
        assert session.state == StreamState.streaming
        assert not session.is_cancelled()

    def test_add_token_and_partial_text(self):
        session = StreamSession(session_id="test")
        session.add_token("Hello ")
        session.add_token("world")
        assert session.partial_text() == "Hello world"

    def test_cancel(self):
        session = StreamSession(session_id="test")
        session.start()
        session.cancel()
        assert session.state == StreamState.cancelled
        assert session.is_cancelled()

    def test_complete(self):
        session = StreamSession(session_id="test")
        session.start()
        session.complete()
        assert session.state == StreamState.completed

    def test_reset(self):
        session = StreamSession(session_id="test")
        session.start()
        session.add_token("some text")
        session.cancel()
        session.reset()
        assert session.state == StreamState.idle
        assert session.tokens == []
        assert not session.is_cancelled()


class TestStreamManager:
    def test_create_and_get_session(self):
        mgr = StreamManager()
        session = mgr.create_session("s1")
        assert mgr.get_session("s1") is session
        assert session.session_id == "s1"

    def test_get_or_create_returns_existing(self):
        mgr = StreamManager()
        s1 = mgr.create_session("s1")
        s2 = mgr.get_or_create("s1")
        assert s1 is s2

    def test_get_or_create_creates_new(self):
        mgr = StreamManager()
        session = mgr.get_or_create("new-session")
        assert session.session_id == "new-session"
        assert session.state == StreamState.idle

    def test_cancel_returns_false_for_idle(self):
        mgr = StreamManager()
        mgr.create_session("s1")
        assert mgr.cancel("s1") is False

    def test_cancel_returns_true_for_streaming(self):
        mgr = StreamManager()
        session = mgr.create_session("s1")
        session.start()
        assert mgr.cancel("s1") is True
        assert session.state == StreamState.cancelled

    def test_cancel_returns_false_for_nonexistent(self):
        mgr = StreamManager()
        assert mgr.cancel("ghost") is False

    def test_remove_session(self):
        mgr = StreamManager()
        mgr.create_session("s1")
        mgr.remove_session("s1")
        assert mgr.get_session("s1") is None

    def test_active_count(self):
        mgr = StreamManager()
        assert mgr.active_count() == 0
        s1 = mgr.create_session("s1")
        s1.start()
        assert mgr.active_count() == 1
        s2 = mgr.create_session("s2")
        s2.start()
        assert mgr.active_count() == 2
        s1.complete()
        assert mgr.active_count() == 1

    def test_get_or_create_global(self):
        mgr1 = get_stream_manager()
        mgr2 = get_stream_manager()
        assert mgr1 is mgr2


class TestStreamEndpoint:
    def test_stream_endpoint_returns_events(self, client):
        resp = client.post("/text-chat/stream", json={"message": "xin chào", "session_id": "stream-test-1"})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body = resp.text
        assert body.startswith("data: ")
        assert "\n\n" in body

    def test_stream_without_session_id(self, client):
        resp = client.post("/text-chat/stream", json={"message": "bạn là ai?"})
        assert resp.status_code == 200
        body = resp.text
        assert "data: " in body

    def test_cancel_nonexistent_stream(self, client):
        resp = client.post("/stream/nonexistent/cancel")
        assert resp.status_code == 404

    def test_cancel_active_stream(self, client):
        import httpx
        from app.services.stream_manager import get_stream_manager
        mgr = get_stream_manager()
        session = mgr.create_session("cancel-me")
        session.start()

        resp = client.post("/stream/cancel-me/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["session_id"] == "cancel-me"
        assert data["state"] == "cancelled"


class TestStreamManagerReset:
    def test_full_lifecycle(self):
        mgr = StreamManager()
        session = mgr.create_session("lifecycle")
        assert session.state == StreamState.idle

        session.start()
        assert session.state == StreamState.streaming

        session.add_token("token1")
        session.add_token("token2")
        assert session.partial_text() == "token1token2"

        session.complete()
        assert session.state == StreamState.completed

        session.reset()
        assert session.state == StreamState.idle
        assert session.partial_text() == ""
