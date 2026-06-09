from __future__ import annotations

import io
from pathlib import Path


async def _fake_synthesize_speech(text: str, output_path: str) -> str:
    Path(output_path).write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00\x00")
    return output_path


async def _fake_transcribe_reminder(_file_path: str) -> str:
    return "15 phút nữa nhắc mình uống nước"


def test_text_chat_creates_reminder(client):
    response = client.post("/text-chat", json={"message": "15 phút nữa nhắc mình uống nước"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["emotion"] == "happy"
    assert payload["action"] == "reminder_created"
    assert payload["reminder"]["title"] == "uống nước"
    assert payload["reminder"]["status"] == "pending"
    assert payload["bot_text"]

    reminders = client.get("/reminders").json()
    assert len(reminders) == 1
    assert reminders[0]["id"] == payload["reminder"]["id"]


def test_voice_chat_creates_reminder(client, monkeypatch):
    from app.services import voice_chat as voice_service

    monkeypatch.setattr(voice_service, "synthesize_speech", _fake_synthesize_speech)
    monkeypatch.setattr(voice_service, "transcribe_audio", _fake_transcribe_reminder)

    response = client.post(
        "/voice-chat",
        files={"audio": ("voice.webm", io.BytesIO(b"fake audio bytes"), "audio/webm")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_text"] == "15 phút nữa nhắc mình uống nước"
    assert payload["emotion"] == "happy"
    assert payload["action"] == "reminder_created"
    assert payload["reminder"]["title"] == "uống nước"
    assert payload["audio_url"].startswith("http://localhost:8000/static/audio/")
