from __future__ import annotations

import io
from pathlib import Path


async def _fake_synthesize_speech(text: str, output_path: str) -> str:
    Path(output_path).write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00\x00")
    return output_path


def test_voice_chat_mock_mode(client, app_module, monkeypatch):
    from app.services import voice_chat as voice_service

    monkeypatch.setattr(voice_service, "synthesize_speech", _fake_synthesize_speech)

    response = client.post(
        "/voice-chat",
        files={"audio": ("voice.webm", io.BytesIO(b"fake audio bytes"), "audio/webm")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_text"] == "KeoBot oi, ban la ai?"
    assert isinstance(payload["bot_text"], str)
    assert payload["bot_text"].strip()
    assert payload["emotion"] == "happy"
    assert payload["audio_url"].startswith("http://localhost:8000/static/audio/")
    assert payload["audio_url"].endswith(".mp3")

    generated_name = Path(payload["audio_url"]).name
    generated_path = Path(__file__).resolve().parents[1] / "app" / "static" / "audio" / generated_name
    assert generated_path.exists()
    generated_path.unlink()
