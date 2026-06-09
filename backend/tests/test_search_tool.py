from __future__ import annotations

import json
from datetime import datetime, timezone

from app.tools import search_tool


class _FakeResponse:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_search_tool_returns_unconfigured_fallback(monkeypatch):
    class _Settings:
        search_provider = "none"
        tavily_api_key = None
        serpapi_api_key = None

    monkeypatch.setattr(search_tool, "get_settings", lambda: _Settings())

    payload = search_tool.get_search_info("Tin AI mới nhất có gì?", "news_search", now=datetime(2026, 6, 9, tzinfo=timezone.utc))

    assert payload["sources"] == []
    assert payload["available"] is False
    assert payload["reason"] == "Search provider not configured"


def test_search_tool_tavily_provider_deduplicates(monkeypatch):
    class _Settings:
        search_provider = "tavily"
        tavily_api_key = "tavily-key"
        serpapi_api_key = None

    def _fake_urlopen(url: str, timeout: int):
        assert "api_key=tavily-key" in url
        assert "topic=news" in url
        return _FakeResponse(
            {
                "results": [
                    {
                        "title": "AI update",
                        "url": "https://example.com/ai-update",
                        "published_date": "2026-06-09T10:30:00Z",
                        "content": "Latest AI story",
                    },
                    {
                        "title": "AI update",
                        "url": "https://example.com/ai-update",
                        "published_date": "2026-06-09T10:30:00Z",
                        "content": "Duplicate",
                    },
                ],
            }
        )

    monkeypatch.setattr(search_tool, "get_settings", lambda: _Settings())
    monkeypatch.setattr(search_tool, "urlopen", _fake_urlopen)

    payload = search_tool.get_search_info("Tin AI mới nhất có gì?", "news_search", entities={"news_topic": "AI"})

    assert payload["available"] is True
    assert len(payload["sources"]) == 1
    assert payload["sources"][0]["title"] == "AI update"
    assert payload["sources"][0]["source"] == "tavily"


def test_search_tool_serpapi_general_provider(monkeypatch):
    class _Settings:
        search_provider = "serpapi"
        tavily_api_key = None
        serpapi_api_key = "serp-key"

    def _fake_urlopen(url: str, timeout: int):
        assert "api_key=serp-key" in url
        assert "engine=google" in url
        return _FakeResponse(
            {
                "organic_results": [
                    {
                        "title": "OpenAI update",
                        "link": "https://example.com/openai",
                        "date": "2026-06-09",
                        "snippet": "OpenAI latest information",
                    },
                    {
                        "title": "OpenAI update",
                        "link": "https://example.com/openai",
                        "date": "2026-06-09",
                        "snippet": "Duplicate",
                    },
                ]
            }
        )

    monkeypatch.setattr(search_tool, "get_settings", lambda: _Settings())
    monkeypatch.setattr(search_tool, "urlopen", _fake_urlopen)

    payload = search_tool.get_search_info("Tìm thông tin mới về OpenAI", "general_search", entities={"search_query": "OpenAI"})

    assert payload["available"] is True
    assert len(payload["sources"]) == 1
    assert payload["sources"][0]["source"] == "serpapi"
