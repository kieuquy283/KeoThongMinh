from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from app.services.conversation_context import ConversationManager, ConversationSession, ConversationTurn
from app.services.tool_router import detect_tool_intent
from app.services.voice_session_manager import create_session, cancel_session, is_cancelled, cleanup_session


class TestConversationSummaries:
    def test_needs_summarization_when_under_threshold(self):
        session = ConversationSession(session_id="test")
        for i in range(4):
            session.add_turn("user", f"message {i}")
            session.add_turn("assistant", f"response {i}")
        assert not session.needs_summarization()

    def test_needs_summarization_when_at_threshold(self):
        session = ConversationSession(session_id="test")
        for i in range(5):
            session.add_turn("user", f"message {i}")
            session.add_turn("assistant", f"response {i}")
        assert session.needs_summarization()

    def test_compact_with_summary(self):
        session = ConversationSession(session_id="test")
        for i in range(12):
            session.add_turn("user", f"message {i}")
            session.add_turn("assistant", f"response {i}")
        session.compact_with_summary("Nguoi dung da hoi ve nhieu chu de.")
        assert session.summary == "Nguoi dung da hoi ve nhieu chu de."
        assert len(session.turns) <= 4

    def test_get_context_with_summary(self):
        session = ConversationSession(session_id="test")
        session.add_turn("user", "hello")
        session.add_turn("assistant", "hi")
        session.summary = "short summary"
        ctx = session.get_context_with_summary()
        assert ctx[0]["role"] == "system"
        assert "short summary" in ctx[0]["text"]
        assert len(ctx) == 3

    def test_get_context_without_summary(self):
        session = ConversationSession(session_id="test")
        session.add_turn("user", "hello")
        session.add_turn("assistant", "hi")
        ctx = session.get_context_with_summary()
        assert len(ctx) == 2
        assert all(t["role"] in ("user", "assistant") for t in ctx)


class TestVoiceFollowUpSessionId:
    def test_text_chat_with_session_id(self, client):
        resp = client.post("/text-chat", json={"message": "xin chao", "session_id": "test-session-123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_text"] == "xin chao"

    def test_voice_chat_accepts_session_id(self, client):
        resp = client.post(
            "/voice-chat",
            data={"session_id": "test-voice-session"},
            files={"audio": ("test.webm", b"fake audio", "audio/webm")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "user_text" in data


class TestContextAwareToolRouting:
    def test_context_boosts_below_threshold(self):
        context = [{"role": "user", "text": "Thời tiết Hà Nội hôm nay thế nào?"}]
        route = detect_tool_intent("còn ở Sài Gòn thì sao?", context)
        assert route.intent == "weather"
        assert route.confidence >= 0.65

    def test_context_without_previous_tool_returns_none(self):
        context = [{"role": "user", "text": "Hôm nay mình hơi mệt"}]
        route = detect_tool_intent("còn ở Sài Gòn thì sao?", context)
        assert route.intent == "none"

    def test_context_empty_returns_normal(self):
        route = detect_tool_intent("Thời tiết Hà Nội", [])
        assert route.intent == "weather"

    def test_context_none_returns_normal(self):
        route = detect_tool_intent("Thời tiết Hà Nội", None)
        assert route.intent == "weather"


class TestMissingInformationFollowUp:
    def test_weather_missing_location_or_unavailable(self, client):
        resp = client.post("/text-chat", json={"message": "thời tiết hôm nay thế nào?"})
        assert resp.status_code == 200
        data = resp.json()
        bot_lower = data["bot_text"].lower()
        has_missing_info = "ở đâu" in bot_lower or "o dau" in bot_lower
        has_unavailable = "chưa được cấu hình" in bot_lower
        assert has_missing_info or has_unavailable

    def test_currency_missing_info_or_unavailable(self, client):
        resp = client.post("/text-chat", json={"message": "tỷ giá hôm nay thế nào?"})
        assert resp.status_code == 200
        data = resp.json()
        bot_lower = data["bot_text"].lower()
        has_missing_info = "tien" in bot_lower or "currency" in bot_lower
        has_unavailable = "chưa được cấu hình" in bot_lower
        assert has_missing_info or has_unavailable


class TestSessionCleanup:
    def test_cleanup_endpoint(self, client):
        resp = client.post("/sessions/cleanup")
        assert resp.status_code == 200
        data = resp.json()
        assert "conversation_sessions_before" in data
        assert "conversation_sessions_after" in data
        assert "voice_sessions_cleaned" in data

    def test_force_cleanup_removes_expired(self):
        mgr = ConversationManager()
        session = mgr.create_session()
        session.last_activity = datetime.now(timezone.utc) - timedelta(days=1)
        removed = mgr.force_cleanup()
        assert removed > 0

    def test_force_cleanup_active_sessions(self):
        mgr = ConversationManager()
        session = mgr.create_session()
        removed = mgr.force_cleanup()
        assert removed == 0

    def test_voice_session_cleanup(self):
        sid = create_session()
        assert is_cancelled(sid) is False
        cleanup_session(sid)

    def test_cancellation_and_cleanup(self):
        sid = create_session()
        cancel_session(sid)
        assert is_cancelled(sid) is True
        cleanup_session(sid)


class TestConversationManagerIntegration:
    def test_session_lifecycle(self):
        mgr = ConversationManager()
        session = mgr.create_session()
        session_id = session.session_id
        assert mgr.get_session(session_id) is not None
        assert mgr.end_session(session_id) is True
        assert mgr.get_session(session_id) is None

    def test_context_with_summary_via_manager(self):
        mgr = ConversationManager()
        session = mgr.create_session()
        for i in range(12):
            mgr.add_user_turn(session.session_id, f"user message {i}")
            mgr.add_bot_turn(session.session_id, f"bot response {i}")
        session = mgr.get_session(session.session_id)
        assert session is not None
        assert session.needs_summarization()
        session.compact_with_summary("test summary")
        ctx = mgr.get_context(session.session_id, limit=10)
        assert len(ctx) > 0
