from __future__ import annotations

import asyncio
import importlib
import io
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[1]


def configure_offline_env() -> None:
    os.environ["STT_PROVIDER"] = "mock"
    os.environ["LLM_PROVIDER"] = "local"
    os.environ["TTS_PROVIDER"] = "edge_tts"
    os.environ.setdefault("MOCK_STT_TEXT", "KeoBot oi, ban la ai?")
    os.environ.setdefault("BACKEND_PORT", "8000")


def reload_backend_modules() -> None:
    config_module = importlib.import_module("app.config")
    config_module = importlib.reload(config_module)
    config_module.get_settings.cache_clear()

    for module_name in (
        "app.providers.stt",
        "app.providers.llm",
        "app.providers.tts",
        "app.services.voice_chat",
        "app.main",
    ):
        module = sys.modules.get(module_name)
        if module is not None:
            importlib.reload(module)
        else:
            importlib.import_module(module_name)


async def fake_synthesize_speech(text: str, output_path: str) -> str:
    Path(output_path).write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00\x00")
    return output_path


def main() -> int:
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

    configure_offline_env()
    reload_backend_modules()

    from app.services import voice_chat as voice_service

    client = TestClient(sys.modules["app.main"].app)
    failures: list[str] = []

    print("VALIDATION: import app ... PASS")

    try:
        response = client.get("/health")
        payload = response.json()
        if response.status_code != 200 or payload.get("status") != "ok":
            raise AssertionError(f"unexpected response: {response.status_code} {payload}")
        print("VALIDATION: GET /health ... PASS")
    except Exception as exc:
        failures.append(f"GET /health: {exc}")
        print(f"VALIDATION: GET /health ... FAIL ({exc})")

    try:
        response = client.post("/text-chat", json={"message": "KeoBot oi, ban la ai?"})
        payload = response.json()
        if response.status_code != 200:
            raise AssertionError(f"unexpected status: {response.status_code} {payload}")
        for key in ("user_text", "bot_text", "emotion"):
            if key not in payload:
                raise AssertionError(f"missing key: {key}")
        print("VALIDATION: POST /text-chat ... PASS")
    except Exception as exc:
        failures.append(f"POST /text-chat: {exc}")
        print(f"VALIDATION: POST /text-chat ... FAIL ({exc})")

    generated_path: Path | None = None
    original_synthesize = voice_service.synthesize_speech
    voice_service.synthesize_speech = fake_synthesize_speech  # type: ignore[assignment]
    try:
        response = client.post(
            "/voice-chat",
            files={"audio": ("sample.webm", io.BytesIO(b"sample audio"), "audio/webm")},
        )
        payload = response.json()
        if response.status_code != 200:
            raise AssertionError(f"unexpected status: {response.status_code} {payload}")
        for key in ("user_text", "bot_text", "audio_url", "emotion"):
            if key not in payload:
                raise AssertionError(f"missing key: {key}")
        generated_name = Path(payload["audio_url"]).name
        generated_path = ROOT_DIR / "app" / "static" / "audio" / generated_name
        if not generated_path.exists():
            raise AssertionError(f"generated audio not found: {generated_path}")
        print("VALIDATION: POST /voice-chat ... PASS")
    except Exception as exc:
        failures.append(f"POST /voice-chat: {exc}")
        print(f"VALIDATION: POST /voice-chat ... FAIL ({exc})")
    finally:
        voice_service.synthesize_speech = original_synthesize  # type: ignore[assignment]
        if generated_path and generated_path.exists():
            generated_path.unlink()

    if failures:
        print("VALIDATION RESULT: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("VALIDATION RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
