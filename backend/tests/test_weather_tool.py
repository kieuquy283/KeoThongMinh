from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError

from app.tools import weather_tool


class _FakeResponse:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_weather_tool_returns_unconfigured_fallback(monkeypatch):
    class _Settings:
        weather_provider = "none"
        openweather_api_key = None

    monkeypatch.setattr(weather_tool, "get_settings", lambda: _Settings())

    payload = weather_tool.get_weather_info("Thoi tiet Ha Noi hom nay?", now=datetime(2026, 6, 9, tzinfo=timezone.utc))

    assert payload["location"] == "Hanoi, VN"
    assert payload["available"] is False
    assert payload["reason"] == "Weather provider not configured"
    assert payload["status"] == "not_configured"
    assert payload["live"] is False


def test_weather_tool_resolves_tokyo():
    assert weather_tool.resolve_weather_location("Nhiệt độ ở Tokyo thế nào?") == "Tokyo"


def test_weather_tool_defaults_to_hanoi():
    assert weather_tool.resolve_weather_location("Thoi tiet hom nay?") == "Hanoi, VN"


def test_weather_tool_invalid_key(monkeypatch):
    class _Settings:
        weather_provider = "openweathermap"
        openweather_api_key = "bad-key"

    def _fake_urlopen(url: str, timeout: int):
        raise HTTPError(url, 401, "Unauthorized", hdrs=None, fp=None)

    monkeypatch.setattr(weather_tool, "get_settings", lambda: _Settings())
    monkeypatch.setattr(weather_tool, "urlopen", _fake_urlopen)

    payload = weather_tool.get_weather_info("Thoi tiet Ha Noi hom nay?")

    assert payload["available"] is False
    assert payload["status"] == "invalid_key"
    assert payload["live"] is False
    assert "invalid key" in payload["message"].lower()


def test_weather_tool_network_error(monkeypatch):
    class _Settings:
        weather_provider = "openweathermap"
        openweather_api_key = "weather-key"

    def _fake_urlopen(url: str, timeout: int):
        raise URLError("offline")

    monkeypatch.setattr(weather_tool, "get_settings", lambda: _Settings())
    monkeypatch.setattr(weather_tool, "urlopen", _fake_urlopen)

    payload = weather_tool.get_weather_info("Thoi tiet Ha Noi hom nay?")

    assert payload["available"] is False
    assert payload["status"] == "network_error"
    assert payload["live"] is False


def test_weather_tool_rate_limited(monkeypatch):
    class _Settings:
        weather_provider = "openweathermap"
        openweather_api_key = "weather-key"

    def _fake_urlopen(url: str, timeout: int):
        raise HTTPError(url, 429, "Too Many Requests", hdrs=None, fp=None)

    monkeypatch.setattr(weather_tool, "get_settings", lambda: _Settings())
    monkeypatch.setattr(weather_tool, "urlopen", _fake_urlopen)

    payload = weather_tool.get_weather_info("Thoi tiet Ha Noi hom nay?")

    assert payload["available"] is False
    assert payload["status"] == "rate_limited"
    assert payload["live"] is False


def test_weather_tool_live_provider(monkeypatch):
    class _Settings:
        weather_provider = "openweathermap"
        openweather_api_key = "weather-key"

    def _fake_urlopen(url: str, timeout: int):
        assert "appid=weather-key" in url
        return _FakeResponse(
            {
                "name": "Hanoi",
                "weather": [{"description": "nhiều mây"}],
                "main": {"temp": 31.5, "feels_like": 36.0, "humidity": 70},
            }
        )

    monkeypatch.setattr(weather_tool, "get_settings", lambda: _Settings())
    monkeypatch.setattr(weather_tool, "urlopen", _fake_urlopen)

    payload = weather_tool.get_weather_info("Thoi tiet Ha Noi hom nay?")

    assert payload["location"] == "Hanoi"
    assert payload["description"] == "nhiều mây"
    assert payload["temperature_c"] == 31.5
    assert payload["available"] is True
    assert payload["reason"] is None
    assert payload["status"] == "ok"
    assert payload["live"] is True
