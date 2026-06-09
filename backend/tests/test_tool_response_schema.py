from __future__ import annotations

from datetime import datetime

from app.schemas import TextChatResponse, VoiceChatResponse


def test_text_chat_response_defaults_tool_metadata():
    payload = TextChatResponse(
        user_text="xin chao",
        bot_text="chao ban",
        emotion="neutral",
    )

    assert payload.tool_used == "none"
    assert payload.tool_result is None
    assert payload.sources == []
    assert payload.updated_at is None


def test_voice_chat_response_accepts_tool_metadata():
    payload = VoiceChatResponse(
        user_text="may gio o Nhat",
        bot_text="Bay gio o Nhat la ...",
        audio_url="http://localhost:8000/static/audio/test.mp3",
        emotion="neutral",
        action="tool_response",
        tool_used="time",
        tool_result={"timezone": "Asia/Tokyo"},
        sources=[{"title": "IANA TZ", "url": "https://example.com", "published_at": "2026-06-09T12:00:00"}],
        updated_at=datetime(2026, 6, 9, 12, 0, 0),
    )

    assert payload.tool_used == "time"
    assert payload.tool_result == {"timezone": "Asia/Tokyo"}
    assert len(payload.sources) == 1
    assert payload.sources[0].title == "IANA TZ"
    assert payload.updated_at == datetime(2026, 6, 9, 12, 0, 0)
