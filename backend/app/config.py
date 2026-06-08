from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)
load_dotenv()


def get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def require_env(name: str) -> str:
    value = get_env(name)
    if not value:
        raise RuntimeError(f"Thiếu biến môi trường bắt buộc: {name}")
    return value


class Settings:
    app_name: str = get_env("APP_NAME", "KeoBot Voice Pipeline") or "KeoBot Voice Pipeline"
    app_env: str = get_env("APP_ENV", "development") or "development"
    backend_host: str = get_env("BACKEND_HOST", "127.0.0.1") or "127.0.0.1"
    backend_port: int = int(get_env("BACKEND_PORT", "8000") or "8000")
    frontend_origin: str = get_env("FRONTEND_ORIGIN", "http://localhost:5173") or "http://localhost:5173"

    stt_provider: str = get_env("STT_PROVIDER", "openai") or "openai"
    llm_provider: str = get_env("LLM_PROVIDER", "openai") or "openai"
    tts_provider: str = get_env("TTS_PROVIDER", "edge_tts") or "edge_tts"

    openai_api_key: str | None = get_env("OPENAI_API_KEY")
    openai_stt_model: str = get_env("OPENAI_STT_MODEL", "gpt-4o-mini-transcribe") or "gpt-4o-mini-transcribe"
    openai_chat_model: str = get_env("OPENAI_CHAT_MODEL", "gpt-4o-mini") or "gpt-4o-mini"
    gemini_api_key: str | None = get_env("GEMINI_API_KEY")
    gemini_model: str = get_env("GEMINI_MODEL", "gemini-1.5-flash") or "gemini-1.5-flash"

    edge_tts_voice: str = get_env("EDGE_TTS_VOICE", "vi-VN-HoaiMyNeural") or "vi-VN-HoaiMyNeural"
    edge_tts_rate: str = get_env("EDGE_TTS_RATE", "+0%") or "+0%"
    edge_tts_volume: str = get_env("EDGE_TTS_VOLUME", "+0%") or "+0%"

    max_upload_size_mb: int = int(get_env("MAX_UPLOAD_SIZE_MB", "15") or "15")
    mock_stt_text: str = get_env("MOCK_STT_TEXT", "KeoBot oi, ban la ai?") or "KeoBot oi, ban la ai?"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
