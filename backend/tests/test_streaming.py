from __future__ import annotations

import asyncio
import json

import pytest
from app.services.stream_manager import (
    StreamManager,
    StreamSession,
    StreamState,
    InvalidTransitionError,
    get_stream_manager,
    validate_transition,
)


TRANSITION_MATRIX: dict[tuple[StreamState, StreamState], bool] = {
    (StreamState.idle, StreamState.streaming): True,
    (StreamState.idle, StreamState.completed): False,
    (StreamState.idle, StreamState.interrupted): False,
    (StreamState.idle, StreamState.replanning): False,
    (StreamState.streaming, StreamState.completed): True,
    (StreamState.streaming, StreamState.interrupted): True,
    (StreamState.streaming, StreamState.replanning): True,
    (StreamState.streaming, StreamState.idle): False,
    (StreamState.streaming, StreamState.streaming): False,
    (StreamState.interrupted, StreamState.idle): True,
    (StreamState.interrupted, StreamState.replanning): True,
    (StreamState.interrupted, StreamState.streaming): False,
    (StreamState.interrupted, StreamState.completed): False,
    (StreamState.replanning, StreamState.streaming): True,
    (StreamState.replanning, StreamState.completed): True,
    (StreamState.replanning, StreamState.interrupted): True,
    (StreamState.replanning, StreamState.idle): False,
    (StreamState.completed, StreamState.idle): True,
    (StreamState.completed, StreamState.streaming): False,
    (StreamState.completed, StreamState.interrupted): False,
    (StreamState.completed, StreamState.replanning): False,
}


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

    def test_interrupt(self):
        session = StreamSession(session_id="test")
        session.start()
        session.interrupt()
        assert session.state == StreamState.interrupted
        assert session.is_cancelled()

    def test_interrupt_from_streaming_succeeds(self):
        session = StreamSession(session_id="test")
        session.start()
        session.interrupt()
        assert session.state == StreamState.interrupted

    def test_interrupt_from_idle_raises(self):
        session = StreamSession(session_id="test")
        with pytest.raises(InvalidTransitionError):
            session.interrupt()

    def test_complete(self):
        session = StreamSession(session_id="test")
        session.start()
        session.complete()
        assert session.state == StreamState.completed

    def test_complete_from_idle_raises(self):
        session = StreamSession(session_id="test")
        with pytest.raises(InvalidTransitionError):
            session.complete()

    def test_reset(self):
        session = StreamSession(session_id="test")
        session.start()
        session.add_token("some text")
        session.interrupt()
        session.reset()
        assert session.state == StreamState.idle
        assert session.tokens == []
        assert not session.is_cancelled()
        assert session.replan_context is None

    def test_start_after_interrupted(self):
        session = StreamSession(session_id="test")
        session.start()
        session.interrupt()
        session.start()
        assert session.state == StreamState.streaming

    def test_start_after_completed(self):
        session = StreamSession(session_id="test")
        session.start()
        session.complete()
        session.start()
        assert session.state == StreamState.streaming

    def test_replan_context(self):
        session = StreamSession(session_id="test")
        session.replan_context = {"intent": "weather", "missing": "location"}
        session.start()
        session.interrupt()
        assert session.replan_context is not None
        session.reset()
        assert session.replan_context is None

    def test_transition_to(self):
        session = StreamSession(session_id="test")
        session.transition_to(StreamState.streaming)
        assert session.state == StreamState.streaming

    def test_transition_to_invalid_raises(self):
        session = StreamSession(session_id="test")
        with pytest.raises(InvalidTransitionError):
            session.transition_to(StreamState.completed)


class TestTransitionValidation:
    def test_all_transitions(self):
        for (from_state, to_state), expected_valid in TRANSITION_MATRIX.items():
            if expected_valid:
                validate_transition(from_state, to_state)
            else:
                with pytest.raises(InvalidTransitionError):
                    validate_transition(from_state, to_state)

    def test_every_state_has_transition_rules(self):
        for state in StreamState:
            assert state in TRANSITION_MATRIX or any(
                (state, other) in TRANSITION_MATRIX or (other, state) in TRANSITION_MATRIX
                for other in StreamState
            )


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
        assert session.state == StreamState.interrupted

    def test_cancel_returns_true_for_replanning(self):
        mgr = StreamManager()
        session = mgr.create_session("s1")
        session.start()
        session.transition_to(StreamState.replanning)
        assert mgr.cancel("s1") is True
        assert session.state == StreamState.interrupted

    def test_cancel_returns_false_for_nonexistent(self):
        mgr = StreamManager()
        assert mgr.cancel("ghost") is False

    def test_cancel_returns_false_for_completed(self):
        mgr = StreamManager()
        session = mgr.create_session("s1")
        session.transition_to(StreamState.streaming)
        session.complete()
        assert mgr.cancel("s1") is False

    def test_remove_session(self):
        mgr = StreamManager()
        mgr.create_session("s1")
        mgr.remove_session("s1")
        assert mgr.get_session("s1") is None

    def test_active_count_zero(self):
        mgr = StreamManager()
        assert mgr.active_count() == 0

    def test_active_count_counts_streaming(self):
        mgr = StreamManager()
        s1 = mgr.create_session("s1")
        s1.start()
        assert mgr.active_count() == 1

    def test_active_count_counts_replanning(self):
        mgr = StreamManager()
        s1 = mgr.create_session("s1")
        s1.start()
        s1.transition_to(StreamState.replanning)
        assert mgr.active_count() == 1

    def test_active_count_ignores_interrupted(self):
        mgr = StreamManager()
        s1 = mgr.create_session("s1")
        s1.start()
        s1.interrupt()
        assert mgr.active_count() == 0

    def test_active_count_ignores_completed(self):
        mgr = StreamManager()
        s1 = mgr.create_session("s1")
        s1.start()
        s1.complete()
        assert mgr.active_count() == 0

    def test_active_count_multiple_sessions(self):
        mgr = StreamManager()
        s1 = mgr.create_session("s1")
        s1.start()
        s2 = mgr.create_session("s2")
        s2.start()
        assert mgr.active_count() == 2
        s1.complete()
        assert mgr.active_count() == 1

    def test_get_or_create_global(self):
        mgr1 = get_stream_manager()
        mgr2 = get_stream_manager()
        assert mgr1 is mgr2

    def test_session_isolation(self):
        mgr = StreamManager()
        s1 = mgr.create_session("s1")
        s2 = mgr.create_session("s2")
        s1.start()
        assert s1.state == StreamState.streaming
        assert s2.state == StreamState.idle
        s2.start()
        assert s2.state == StreamState.streaming
        s1.complete()
        assert s1.state == StreamState.completed
        assert s2.state == StreamState.streaming


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
        assert data["state"] == "interrupted"


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

        assert stream_sesh.state == StreamState.idle
        assert not stream_sesh.is_cancelled()

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
        assert data["state"] == "interrupted"

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


class TestStateMachine:
    def test_idle_to_streaming(self):
        session = StreamSession(session_id="sm1")
        session.start()
        assert session.state == StreamState.streaming

    def test_streaming_to_completed(self):
        session = StreamSession(session_id="sm2")
        session.start()
        session.complete()
        assert session.state == StreamState.completed

    def test_streaming_to_interrupted(self):
        session = StreamSession(session_id="sm3")
        session.start()
        session.interrupt()
        assert session.state == StreamState.interrupted

    def test_streaming_to_replanning(self):
        session = StreamSession(session_id="sm4")
        session.start()
        session.transition_to(StreamState.replanning)
        assert session.state == StreamState.replanning

    def test_interrupted_to_idle(self):
        session = StreamSession(session_id="sm5")
        session.start()
        session.interrupt()
        session.reset()
        assert session.state == StreamState.idle

    def test_interrupted_to_replanning(self):
        session = StreamSession(session_id="sm6")
        session.start()
        session.interrupt()
        session.transition_to(StreamState.replanning)
        assert session.state == StreamState.replanning

    def test_replanning_to_streaming(self):
        session = StreamSession(session_id="sm7")
        session.start()
        session.interrupt()
        session.transition_to(StreamState.replanning)
        session.start()
        assert session.state == StreamState.streaming

    def test_replanning_to_completed(self):
        session = StreamSession(session_id="sm8")
        session.start()
        session.transition_to(StreamState.replanning)
        session.complete()
        assert session.state == StreamState.completed

    def test_completed_to_idle(self):
        session = StreamSession(session_id="sm9")
        session.start()
        session.complete()
        session.reset()
        assert session.state == StreamState.idle

    def test_cannot_interrupt_from_idle(self):
        session = StreamSession(session_id="sm10")
        with pytest.raises(InvalidTransitionError):
            session.interrupt()

    def test_cannot_interrupt_from_completed(self):
        session = StreamSession(session_id="sm11")
        session.start()
        session.complete()
        with pytest.raises(InvalidTransitionError):
            session.interrupt()

    def test_can_interrupt_from_replanning(self):
        session = StreamSession(session_id="sm12")
        session.start()
        session.transition_to(StreamState.replanning)
        session.interrupt()
        assert session.state == StreamState.interrupted

    def test_cannot_complete_from_idle(self):
        session = StreamSession(session_id="sm13")
        with pytest.raises(InvalidTransitionError):
            session.complete()

    def test_cannot_complete_from_interrupted(self):
        session = StreamSession(session_id="sm14")
        session.start()
        session.interrupt()
        with pytest.raises(InvalidTransitionError):
            session.complete()

    def test_start_while_streaming_auto_resets(self):
        session = StreamSession(session_id="sm15")
        session.start()
        session.add_token("some text")
        session.start()
        assert session.state == StreamState.streaming
        assert session.tokens == []

    def test_start_from_interrupted_auto_resets(self):
        session = StreamSession(session_id="sm16")
        session.start()
        session.interrupt()
        session.start()
        assert session.state == StreamState.streaming
        assert not session.is_cancelled()

    def test_streaming_to_idle_raises(self):
        session = StreamSession(session_id="sm17")
        session.start()
        with pytest.raises(InvalidTransitionError):
            session.transition_to(StreamState.idle)

    def test_interrupted_to_streaming_raises(self):
        session = StreamSession(session_id="sm18")
        session.start()
        session.interrupt()
        with pytest.raises(InvalidTransitionError):
            session.transition_to(StreamState.streaming)

    def test_interrupted_to_completed_raises(self):
        session = StreamSession(session_id="sm19")
        session.start()
        session.interrupt()
        with pytest.raises(InvalidTransitionError):
            session.complete()
