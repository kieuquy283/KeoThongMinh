from __future__ import annotations

import io
from pathlib import Path


async def _fake_synthesize_speech(text: str, output_path: str) -> str:
    Path(output_path).write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00\x00")
    return output_path


def test_text_chat_uses_time_tool(client):
    response = client.post("/text-chat", json={"message": "Bay gio la may gio o Nhat?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "tool_response"
    assert payload["tool_used"] == "time"
    assert payload["tool_result"]["timezone"] == "Asia/Tokyo"
    assert payload["updated_at"]
    assert "Japan" not in payload["bot_text"]


def test_text_chat_currency_demo_returns_demo_note(client):
    response = client.post("/text-chat", json={"message": "100 USD sang VND hom nay?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "tool_response"
    assert payload["tool_used"] == "currency"
    assert payload["tool_result"]["is_live"] is False
    assert payload["tool_result"]["note"] == "Demo rate, not live."
    assert "demo" in payload["bot_text"].lower()


def test_text_chat_weather_without_provider_returns_clear_fallback(client):
    response = client.post("/text-chat", json={"message": "Thoi tiet Tokyo hom nay the nao?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "tool_response"
    assert payload["tool_used"] == "weather"
    assert payload["bot_text"] == "Mình chưa được cấu hình công cụ thời tiết."
    assert payload["tool_result"]["available"] is False
    assert payload["tool_result"]["reason"] == "Weather provider not configured"


def test_text_chat_search_without_provider_returns_clear_fallback(client):
    response = client.post("/text-chat", json={"message": "Tin AI moi nhat co gi?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "tool_response"
    assert payload["tool_used"] == "news_search"
    assert payload["bot_text"] == "Mình chưa được cấu hình công cụ tìm kiếm/cập nhật tin tức."
    assert payload["tool_result"]["available"] is False
    assert payload["tool_result"]["reason"] == "Search provider not configured"


async def _fake_transcribe_time(_file_path: str) -> str:
    return "Bay gio la may gio o Nhat?"


def test_voice_chat_uses_tool_response(client, monkeypatch):
    from app.services import voice_chat as voice_service

    monkeypatch.setattr(voice_service, "synthesize_speech", _fake_synthesize_speech)
    monkeypatch.setattr(voice_service, "transcribe_audio", _fake_transcribe_time)

    response = client.post(
        "/voice-chat",
        files={"audio": ("voice.webm", io.BytesIO(b"fake audio bytes"), "audio/webm")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "tool_response"
    assert payload["tool_used"] == "time"
    assert payload["tool_result"]["timezone"] == "Asia/Tokyo"
    assert payload["audio_url"].startswith("http://localhost:8000/static/audio/")
