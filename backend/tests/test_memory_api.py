from __future__ import annotations


def test_memory_api_crud_roundtrip(client):
    response = client.get("/memory")
    assert response.status_code == 200
    assert response.json() == []

    response = client.post(
        "/memory",
        json={"key": "default_city", "value": "Hà Nội", "category": "preference"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["key"] == "default_city"
    assert payload["value"] == "Hà Nội"
    assert payload["category"] == "preference"

    response = client.get("/memory")
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.delete("/memory/default_city")
    assert response.status_code == 200
    assert response.json()["ok"] is True

    response = client.delete("/memory")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["deleted"] == 0


def test_memory_api_rejects_invalid_keys(client):
    response = client.post(
        "/memory",
        json={"key": "api_key", "value": "secret", "category": "preference"},
    )

    assert response.status_code == 422
