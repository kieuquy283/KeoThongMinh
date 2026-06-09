from __future__ import annotations

from types import SimpleNamespace


def test_tools_status_endpoint_returns_richer_diagnostics(app_module, client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "settings",
        SimpleNamespace(
            weather_provider="openweathermap",
            openweather_api_key=None,
            search_provider="tavily",
            tavily_api_key=None,
            serpapi_api_key=None,
            currency_provider="exchangerate_api",
            exchange_rate_api_url=None,
            exchange_rate_api_key=None,
        ),
    )

    response = client.get("/tools/status")

    assert response.status_code == 200
    payload = response.json()

    assert payload["weather"]["provider"] == "openweathermap"
    assert payload["weather"]["configured"] is False
    assert payload["weather"]["status"] == "not_configured"
    assert payload["weather"]["message"]
    assert payload["weather"]["last_checked_at"]

    assert payload["search"]["provider"] == "tavily"
    assert payload["search"]["configured"] is False
    assert payload["search"]["status"] == "not_configured"
    assert payload["search"]["message"]
    assert payload["search"]["last_checked_at"]

    assert payload["currency"]["provider"] == "exchangerate_api"
    assert payload["currency"]["configured"] is False
    assert payload["currency"]["status"] == "not_configured"
    assert payload["currency"]["message"]
    assert payload["currency"]["last_checked_at"]
    assert "api_key" not in response.text.lower()


def test_tools_test_time_endpoint(client):
    response = client.post(
        "/tools/test",
        json={"tool": "time", "sample_query": "Bây giờ là mấy giờ ở Nhật?"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["tool"] == "time"
    assert payload["status"] == "ok"
    assert payload["sample_result"]["timezone"] == "Asia/Tokyo"
    assert payload["checked_at"]


def test_tools_test_weather_endpoint_passes_through_tool_result(app_module, client, monkeypatch):
    def _fake_weather(query, entities=None, now=None):
        return {
            "provider": "openweathermap",
            "configured": False,
            "live": False,
            "status": "not_configured",
            "message": "Weather provider not configured",
            "location": "Hà Nội",
            "available": False,
            "reason": "Weather provider not configured",
            "updated_at": "2026-06-09T10:00:00Z",
            "last_checked_at": "2026-06-09T10:00:00Z",
        }

    monkeypatch.setattr(app_module, "get_weather_info", _fake_weather)

    response = client.post(
        "/tools/test",
        json={"tool": "weather", "sample_query": "Thời tiết Hà Nội hôm nay thế nào?"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["tool"] == "weather"
    assert payload["status"] == "not_configured"
    assert payload["sample_result"]["location"] == "Hà Nội"
    assert payload["sample_result"]["available"] is False


def test_tools_test_search_endpoint_uses_router_intent(app_module, client, monkeypatch):
    def _fake_route(query):
        return SimpleNamespace(intent="news_search", entities={"news_topic": "AI"})

    def _fake_search(query, intent, entities=None, now=None):
        assert intent == "news_search"
        assert entities["news_topic"] == "AI"
        return {
            "provider": "tavily",
            "configured": True,
            "live": True,
            "status": "ok",
            "message": "Live search results",
            "available": True,
            "reason": None,
            "sources": [],
            "results": [],
            "updated_at": "2026-06-09T10:00:00Z",
            "last_checked_at": "2026-06-09T10:00:00Z",
        }

    monkeypatch.setattr(app_module, "detect_tool_intent", _fake_route)
    monkeypatch.setattr(app_module, "get_search_info", _fake_search)

    response = client.post(
        "/tools/test",
        json={"tool": "search", "sample_query": "Tin AI mới nhất"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["tool"] == "search"
    assert payload["status"] == "ok"
    assert payload["sample_result"]["provider"] == "tavily"
