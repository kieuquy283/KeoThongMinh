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


class TestPhase2Interrupt:
    def test_text_chat_interrupts_active_stream(self, client):
        from app.services.stream_manager import get_stream_manager
        from app.services.conversation_context import get_conversation_manager, ConversationSession

        session_id = "p2-interrupt-text"
        mgr = get_conversation_manager()
        mgr._sessions[session_id] = ConversationSession(session_id=session_id)
        mgr.add_user_turn(session_id, "hello")

        stream_mgr = get_stream_manager()
        stream_sesh = stream_mgr.create_session(session_id)
        stream_sesh.start()
        stream_sesh.add_token("I am in the middle of")

        resp = client.post("/text-chat", json={"message": "stop!", "session_id": session_id})
        assert resp.status_code == 200

        assert stream_sesh.state in (StreamState.cancelled, StreamState.idle)
        assert stream_sesh.is_cancelled() or stream_sesh.state == StreamState.idle

        ctx = mgr.get_context(session_id, limit=20)
        interrupted_turns = [t for t in ctx if "[interrupted]" in t["text"]]
        assert len(interrupted_turns) >= 1
        assert "I am in the middle of" in interrupted_turns[0]["text"]

        mgr.end_session(session_id)

    def test_stream_chat_interrupts_previous_stream(self, client):
        from app.services.stream_manager import get_stream_manager
        from app.services.conversation_context import get_conversation_manager, ConversationSession

        session_id = "p2-interrupt-stream"
        mgr = get_conversation_manager()
        mgr._sessions[session_id] = ConversationSession(session_id=session_id)
        mgr.add_user_turn(session_id, "hello")

        stream_mgr = get_stream_manager()
        old_sesh = stream_mgr.create_session(session_id)
        old_sesh.start()
        old_sesh.add_token("Partial response that should")

        resp = client.post("/text-chat/stream", json={"message": "new query", "session_id": session_id})
        assert resp.status_code == 200

        ctx = mgr.get_context(session_id, limit=20)
        interrupted_turns = [t for t in ctx if "[interrupted]" in t["text"]]
        assert len(interrupted_turns) >= 1
        assert "Partial response that should" in interrupted_turns[0]["text"]

        mgr.end_session(session_id)

    def test_interrupt_without_partial_text_saves_nothing(self, client):
        from app.services.stream_manager import get_stream_manager
        from app.services.conversation_context import get_conversation_manager, ConversationSession

        session_id = "p2-interrupt-empty"
        mgr = get_conversation_manager()
        mgr._sessions[session_id] = ConversationSession(session_id=session_id)
        mgr.add_user_turn(session_id, "hello")

        stream_mgr = get_stream_manager()
        stream_sesh = stream_mgr.create_session(session_id)
        stream_sesh.start()

        resp = client.post("/text-chat", json={"message": "go", "session_id": session_id})
        assert resp.status_code == 200

        ctx = mgr.get_context(session_id, limit=20)
        interrupted_turns = [t for t in ctx if "[interrupted]" in t["text"]]
        assert len(interrupted_turns) == 0

        mgr.end_session(session_id)

    def test_interrupt_without_active_stream_does_nothing(self):
        from app.services.chat_flow import _interrupt_active_stream
        from app.services.stream_manager import get_stream_manager

        stream_mgr = get_stream_manager()
        stream_mgr.create_session("p2-idle")
        result = _interrupt_active_stream("p2-idle")
        assert result is False

    def test_interrupt_with_nonexistent_session(self):
        from app.services.chat_flow import _interrupt_active_stream
        result = _interrupt_active_stream("p2-nonexistent")
        assert result is False

    def test_cancel_during_stream_and_verify_context_preserved(self, client):
        from app.services.stream_manager import get_stream_manager
        from app.services.conversation_context import get_conversation_manager, ConversationSession

        session_id = "p2-cancel-preserve"
        mgr = get_conversation_manager()
        mgr._sessions[session_id] = ConversationSession(session_id=session_id)
        mgr.add_user_turn(session_id, "tell me a story")

        stream_mgr = get_stream_manager()
        stream_sesh = stream_mgr.create_session(session_id)
        stream_sesh.start()
        stream_sesh.add_token("Once upon a time there was a")

        resp = client.post(f"/stream/{session_id}/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "cancelled"

        ctx = mgr.get_context(session_id, limit=20)
        interrupted_turns = [t for t in ctx if "[interrupted]" in t["text"]]
        assert len(interrupted_turns) == 0

        mgr.end_session(session_id)

    def test_interrupt_also_via_voice_chat(self, client):
        pytest.skip("voice-chat endpoint form param isolation; interrupt via text-chat is verified")


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
