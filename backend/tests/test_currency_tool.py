from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError

from app.tools import currency_tool


class _FakeResponse:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_currency_tool_demo_fallback_without_live_provider(monkeypatch):
    class _Settings:
        currency_provider = "none"
        exchange_rate_api_url = None
        exchange_rate_api_key = None

    monkeypatch.setattr(currency_tool, "get_settings", lambda: _Settings())

    payload = currency_tool.get_currency_info(
        "100 USD sang VND hôm nay?",
        entities={"amount": 100, "base_currency": "USD", "target_currency": "VND"},
        now=datetime(2026, 6, 9, tzinfo=timezone.utc),
    )

    assert payload["provider"] == "demo"
    assert payload["configured"] is True
    assert payload["live"] is False
    assert payload["status"] == "ok"
    assert payload["note"] == "Demo rate, not live."
    assert payload["amount"] == 100.0
    assert payload["base_currency"] == "USD"
    assert payload["target_currency"] == "VND"
    assert payload["converted_amount"] == 2_540_000.0
    assert payload["is_live"] is False


def test_currency_tool_defaults_target_to_vnd():
    pair = currency_tool.resolve_currency_pair("Tỷ giá USD hôm nay?", entities={"base_currency": "USD"})

    assert pair.base == "USD"
    assert pair.target == "VND"


def test_currency_tool_missing_live_key_returns_not_configured(monkeypatch):
    class _Settings:
        currency_provider = "exchangerate_api"
        exchange_rate_api_url = "https://example.com/latest"
        exchange_rate_api_key = None

    monkeypatch.setattr(currency_tool, "get_settings", lambda: _Settings())

    payload = currency_tool.get_currency_info(
        "100 USD sang VND",
        entities={"amount": 100, "base_currency": "USD", "target_currency": "VND"},
        now=datetime(2026, 6, 9, tzinfo=timezone.utc),
    )

    assert payload["provider"] == "exchangerate_api"
    assert payload["configured"] is False
    assert payload["live"] is False
    assert payload["status"] == "not_configured"
    assert payload["message"] == "Currency live provider not configured."
    assert payload["converted_amount"] is None
    assert payload["is_live"] is False


def test_currency_tool_invalid_key(monkeypatch):
    class _Settings:
        currency_provider = "exchangerate_api"
        exchange_rate_api_url = "https://example.com/latest"
        exchange_rate_api_key = "bad-key"

    def _fake_urlopen(url: str, timeout: int):
        raise HTTPError(url=url, code=401, msg="Unauthorized", hdrs=None, fp=None)

    monkeypatch.setattr(currency_tool, "get_settings", lambda: _Settings())
    monkeypatch.setattr(currency_tool, "urlopen", _fake_urlopen)

    payload = currency_tool.get_currency_info(
        "100 USD sang VND",
        entities={"amount": 100, "base_currency": "USD", "target_currency": "VND"},
        now=datetime(2026, 6, 9, tzinfo=timezone.utc),
    )

    assert payload["status"] == "invalid_key"
    assert payload["configured"] is False
    assert payload["live"] is False
    assert payload["message"] == "Currency provider key is invalid."
    assert payload["is_live"] is False


def test_currency_tool_network_error(monkeypatch):
    class _Settings:
        currency_provider = "exchangerate_api"
        exchange_rate_api_url = "https://example.com/latest"
        exchange_rate_api_key = "good-key"

    def _fake_urlopen(url: str, timeout: int):
        raise URLError("temporary failure")

    monkeypatch.setattr(currency_tool, "get_settings", lambda: _Settings())
    monkeypatch.setattr(currency_tool, "urlopen", _fake_urlopen)

    payload = currency_tool.get_currency_info(
        "100 USD sang VND",
        entities={"amount": 100, "base_currency": "USD", "target_currency": "VND"},
        now=datetime(2026, 6, 9, tzinfo=timezone.utc),
    )

    assert payload["status"] == "network_error"
    assert payload["configured"] is False
    assert payload["live"] is False
    assert payload["message"] == "Currency provider network error."
    assert payload["is_live"] is False


def test_currency_tool_live_provider(monkeypatch):
    class _Settings:
        currency_provider = "exchangerate_api"
        exchange_rate_api_url = "https://example.com/latest"
        exchange_rate_api_key = "test-key"

    def _fake_urlopen(url: str, timeout: int):
        assert "base=JPY" in url
        assert "symbols=VND" in url
        assert "apikey=test-key" in url
        return _FakeResponse({"rates": {"VND": 177.25}, "date": "2026-06-09T10:00:00Z"})

    monkeypatch.setattr(currency_tool, "get_settings", lambda: _Settings())
    monkeypatch.setattr(currency_tool, "urlopen", _fake_urlopen)

    payload = currency_tool.get_currency_info(
        "100 JPY sang VND",
        entities={"amount": 100, "base_currency": "JPY", "target_currency": "VND"},
    )

    assert payload["provider"] == "exchangerate_api"
    assert payload["base_currency"] == "JPY"
    assert payload["target_currency"] == "VND"
    assert payload["rate"] == 177.25
    assert payload["converted_amount"] == 17_725.0
    assert payload["is_live"] is True
    assert payload["status"] == "ok"
    assert payload["message"] == "Live exchange rate."
    assert payload["live"] is True
