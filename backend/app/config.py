from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from app.data_paths import get_data_root

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
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class Settings:
    app_name: str = get_env("APP_NAME", "Kẹo Thông Minh Voice Pipeline") or "Kẹo Thông Minh Voice Pipeline"
    app_env: str = get_env("APP_ENV", "development") or "development"
    backend_host: str = get_env("BACKEND_HOST", "127.0.0.1") or "127.0.0.1"
    backend_port: int = int(get_env("BACKEND_PORT", "8000") or "8000")
    frontend_origin: str = get_env("FRONTEND_ORIGIN", "http://localhost:5173") or "http://localhost:5173"
    data_dir: Path = get_data_root()

    stt_provider: str = get_env("STT_PROVIDER", "dashscope") or "dashscope"
    llm_provider: str = get_env("LLM_PROVIDER", "qwen3.6-plus") or "qwen3.6-plus"
    tts_provider: str = get_env("TTS_PROVIDER", "edge_tts") or "edge_tts"

    openai_api_key: str | None = get_env("OPENAI_API_KEY")
    openai_stt_model: str = get_env("OPENAI_STT_MODEL", "gpt-4o-mini-transcribe") or "gpt-4o-mini-transcribe"
    openai_chat_model: str = get_env("OPENAI_CHAT_MODEL", "gpt-4o-mini") or "gpt-4o-mini"
    gemini_api_key: str | None = get_env("GEMINI_API_KEY") or get_env("GOOGLE_API_KEY")
    gemini_model: str = get_env("GEMINI_MODEL", "gemini-2.0-flash") or "gemini-2.0-flash"

    dashscope_api_key: str | None = get_env("DASHSCOPE_API_KEY")
    dashscope_base_url: str | None = get_env("DASHSCOPE_BASE_URL")
    dashscope_llm_model: str = get_env("DASHSCOPE_LLM_MODEL", "qwen3.6-plus") or "qwen3.6-plus"
    dashscope_stt_model: str = get_env("DASHSCOPE_STT_MODEL", "Qwen3-ASR-Flash") or "Qwen3-ASR-Flash"

    currency_provider: str = get_env("CURRENCY_PROVIDER", "none") or "none"
    exchange_rate_api_key: str | None = get_env("EXCHANGE_RATE_API_KEY")
    exchange_rate_api_url: str | None = get_env("EXCHANGE_RATE_API_URL")

    weather_provider: str = get_env("WEATHER_PROVIDER", "none") or "none"
    openweather_api_key: str | None = get_env("OPENWEATHER_API_KEY")

    search_provider: str = get_env("SEARCH_PROVIDER", "none") or "none"
    tavily_api_key: str | None = get_env("TAVILY_API_KEY")
    serpapi_api_key: str | None = get_env("SERPAPI_API_KEY")

    edge_tts_voice: str = get_env("EDGE_TTS_VOICE", "vi-VN-HoaiMyNeural") or "vi-VN-HoaiMyNeural"
    edge_tts_rate: str = get_env("EDGE_TTS_RATE", "+0%") or "+0%"
    edge_tts_volume: str = get_env("EDGE_TTS_VOLUME", "+0%") or "+0%"

    max_upload_size_mb: int = int(get_env("MAX_UPLOAD_SIZE_MB", "15") or "15")
    mock_stt_text: str = get_env("MOCK_STT_TEXT", "Kẹo Thông Minh oi, ban la ai?") or "Kẹo Thông Minh oi, ban la ai?"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
