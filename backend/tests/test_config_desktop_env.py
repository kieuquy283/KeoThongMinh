from __future__ import annotations

import importlib


def reload_settings():
    config_module = importlib.import_module("app.config")
    config_module = importlib.reload(config_module)
    config_module.get_settings.cache_clear()
    return config_module.get_settings()


def test_google_api_key_alias(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "alias-key")
    settings = reload_settings()

    assert settings.gemini_api_key == "alias-key"


def test_env_override_prefers_runtime_value(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "openai")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("TTS_PROVIDER", "edge_tts")
    monkeypatch.setenv("OPENAI_API_KEY", "runtime-openai")
    monkeypatch.setenv("GEMINI_API_KEY", "runtime-gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "runtime-google")
    monkeypatch.setenv("EDGE_TTS_VOICE", "vi-VN-TestNeural")

    settings = reload_settings()

    assert settings.stt_provider == "openai"
    assert settings.llm_provider == "gemini"
    assert settings.openai_api_key == "runtime-openai"
    assert settings.gemini_api_key == "runtime-gemini"
    assert settings.edge_tts_voice == "vi-VN-TestNeural"


def test_default_mock_local_mode(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "local")
    monkeypatch.setenv("TTS_PROVIDER", "edge_tts")
    for key in (
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "EDGE_TTS_VOICE",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = reload_settings()

    assert settings.stt_provider == "mock"
    assert settings.llm_provider == "local"
    assert settings.tts_provider == "edge_tts"
