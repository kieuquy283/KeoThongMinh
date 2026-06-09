from __future__ import annotations


def test_tools_status_endpoint(client):
    response = client.get("/tools/status")

    assert response.status_code == 200
    payload = response.json()

    assert payload["weather"]["provider"] in {"none", "openweathermap"}
    assert payload["search"]["provider"] in {"none", "tavily", "serpapi"}
    assert payload["currency"]["provider"] in {"demo", "exchangerate_api"}
    assert payload["currency"]["configured"] is True
    assert "api_key" not in response.text.lower()
