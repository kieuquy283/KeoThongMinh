from __future__ import annotations

import importlib


def test_gemini_api_key_alias(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "alias-key")

    config_module = importlib.import_module("app.config")
    config_module = importlib.reload(config_module)
    config_module.get_settings.cache_clear()

    settings = config_module.get_settings()

    assert settings.gemini_api_key == "alias-key"
