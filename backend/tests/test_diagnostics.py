from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from fastapi.testclient import TestClient


def test_health_response_has_version_and_mode():
    os.environ["STT_PROVIDER"] = "mock"
    os.environ["LLM_PROVIDER"] = "local"

    from app.main import app

    client = TestClient(app)
    response = client.get("/health")
    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert isinstance(payload.get("version"), str)
    assert isinstance(payload.get("mode"), str)
    assert payload["version"] == "0.3.0"
    assert payload["mode"] == "mock_local"


REDACT_PATTERNS = [
    (r"(API_KEY=\s*)[^\s]+", r"\1***"),
    (r"(ACCESS_KEY=\s*)[^\s]+", r"\1***"),
    (r"(SECRET=\s*)[^\s]+", r"\1***"),
    (r"(TOKEN=\s*)[^\s]+", r"\1***"),
]


def apply_redact(text: str) -> str:
    for pattern, replacement in REDACT_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def test_redact_api_key_in_log():
    raw = "OPENAI_API_KEY=sk-abc123def456"
    result = apply_redact(raw)
    assert result == "OPENAI_API_KEY=***"


def test_redact_access_key_in_log():
    raw = "PICOVOICE_ACCESS_KEY=abc123secret"
    result = apply_redact(raw)
    assert result == "PICOVOICE_ACCESS_KEY=***"


def test_redact_does_not_affect_normal_text():
    raw = "Backend health check passed"
    result = apply_redact(raw)
    assert result == raw


def test_redact_multiple_keys():
    raw = "OPENAI_API_KEY=sk-123 PICOVOICE_ACCESS_KEY=abc"
    result = apply_redact(raw)
    assert "***" in result
    assert "sk-123" not in result
    assert "abc" not in result
