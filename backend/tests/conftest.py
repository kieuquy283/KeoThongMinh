from __future__ import annotations

import importlib
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_module(monkeypatch, tmp_path):
    monkeypatch.setenv("STT_PROVIDER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "local")
    monkeypatch.setenv("TTS_PROVIDER", "edge_tts")
    monkeypatch.setenv("MOCK_STT_TEXT", "Kẹo Thông Minh oi, ban la ai?")
    monkeypatch.setenv("BACKEND_PORT", "8000")
    monkeypatch.setenv("KEOBOT_DATA_DIR", str(tmp_path / "data"))

    config_module = importlib.import_module("app.config")
    config_module = importlib.reload(config_module)
    config_module.get_settings.cache_clear()

    for module_name in (
        "app.data_paths",
        "app.providers.stt",
        "app.providers.llm",
        "app.providers.tts",
        "app.services.reminder_parser",
        "app.services.reminder_store",
        "app.services.memory_store",
        "app.services.memory_parser",
        "app.services.entity_extractor",
        "app.services.tool_router",
        "app.services.chat_flow",
        "app.services.knowledge_store",
        "app.services.knowledge_query",
        "app.services.document_importer",
        "app.services.text_chunker",
        "app.services.voice_chat",
        "app.main",
    ):
        module = sys.modules.get(module_name)
        if module is not None:
            importlib.reload(module)
        else:
            importlib.import_module(module_name)

    module = sys.modules["app.main"]
    yield module
    config_module.get_settings.cache_clear()


@pytest.fixture
def client(app_module):
    return TestClient(app_module.app)
