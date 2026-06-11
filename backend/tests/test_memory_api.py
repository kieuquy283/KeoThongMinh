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


def test_memory_api_update_endpoint(client):
    client.post("/memory", json={"key": "user_name", "value": "Quy"})

    response = client.patch("/memory/user_name", json={"value": "Minh"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["value"] == "Minh"

    response = client.patch("/memory/user_name", json={"is_enabled": False})
    assert response.status_code == 200
    assert response.json()["is_enabled"] is False

    response = client.patch("/memory/nonexistent", json={"value": "x"})
    assert response.status_code == 404


def test_memory_api_enable_disable_endpoints(client):
    client.post("/memory", json={"key": "user_name", "value": "Quy"})

    response = client.post("/memory/user_name/disable")
    assert response.status_code == 200
    assert response.json()["is_enabled"] is False

    response = client.post("/memory/user_name/enable")
    assert response.status_code == 200
    assert response.json()["is_enabled"] is True

    response = client.post("/memory/nonexistent/enable")
    assert response.status_code == 404

    response = client.post("/memory/nonexistent/disable")
    assert response.status_code == 404


def test_memory_api_context_endpoint(client):
    client.post("/memory", json={"key": "user_name", "value": "Quy"})
    client.post("/memory", json={"key": "default_city", "value": "Hà Nội"})

    response = client.get("/memory/context")
    assert response.status_code == 200
    payload = response.json()
    assert payload["context"]["user_name"] == "Quy"
    assert payload["context"]["default_city"] == "Hà Nội"

    client.post("/memory/user_name/disable")

    response = client.get("/memory/context")
    assert response.status_code == 200
    assert "user_name" not in response.json()["context"]


def test_memory_api_enhanced_fields(client):
    response = client.post(
        "/memory",
        json={"key": "default_city", "value": "Hà Nội"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "explicit_user_request"
    assert payload["confidence"] == 1.0
    assert payload["is_enabled"] is True
