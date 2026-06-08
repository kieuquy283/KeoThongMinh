from __future__ import annotations

import io
from pathlib import Path


async def _fake_synthesize_speech(text: str, output_path: str) -> str:
    Path(output_path).write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00\x00")
    return output_path


async def _fake_transcribe_audio(file_path: str) -> str:
    if Path(file_path).stat().st_size == 0:
        raise ValueError("Khong nhan dien duoc giong noi.")
    return "KeoBot oi, ban la ai?"


def test_voice_chat_requires_audio_file(client):
    response = client.post("/voice-chat", data={})

    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"]


def test_voice_chat_rejects_empty_audio(client, monkeypatch):
    from app.services import voice_chat as voice_service

    monkeypatch.setattr(voice_service, "synthesize_speech", _fake_synthesize_speech)
    monkeypatch.setattr(voice_service, "transcribe_audio", _fake_transcribe_audio)

    response = client.post(
        "/voice-chat",
        files={"audio": ("empty.webm", io.BytesIO(b""), "audio/webm")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]
