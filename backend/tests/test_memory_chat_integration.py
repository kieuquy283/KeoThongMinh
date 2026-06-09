from __future__ import annotations


def test_chat_flow_handles_memory_set_and_lookup(client):
    response = client.post("/text-chat", json={"message": "Từ giờ gọi mình là Quy"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "memory_updated"
    assert payload["emotion"] == "happy"
    assert "Quy" in payload["bot_text"]

    response = client.post("/text-chat", json={"message": "Bạn là ai?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] is None
    assert payload["tool_used"] == "none"
    assert "Quy" in payload["bot_text"]


def test_chat_flow_handles_memory_delete(client):
    response = client.post("/text-chat", json={"message": "Nhớ rằng thành phố mặc định của mình là Hà Nội"})
    assert response.status_code == 200
    assert response.json()["action"] == "memory_updated"

    response = client.post("/text-chat", json={"message": "Xóa thành phố mặc định của mình"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "memory_deleted"
    assert "Da xoa" in payload["bot_text"] or "xoa" in payload["bot_text"].lower()


def test_chat_flow_keeps_reminder_and_tool_ordering(client):
    response = client.post("/text-chat", json={"message": "1 phút nữa nhắc mình uống nước"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "reminder_created"
    assert payload["tool_used"] == "none"

    response = client.post("/text-chat", json={"message": "Bây giờ là mấy giờ ở Nhật?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_used"] == "time"
    assert payload["tool_result"]["timezone"] == "Asia/Tokyo"


def test_memory_defaults_apply_to_weather_and_currency(client):
    response = client.post("/memory", json={"key": "default_city", "value": "Hà Nội", "category": "preference"})
    assert response.status_code == 200
    response = client.post("/memory", json={"key": "default_currency", "value": "EUR", "category": "preference"})
    assert response.status_code == 200

    response = client.post("/text-chat", json={"message": "Thời tiết hôm nay thế nào?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_used"] == "weather"
    assert "Hanoi" in payload["tool_result"]["location"]

    response = client.post("/text-chat", json={"message": "100 USD hôm nay?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_used"] == "currency"
    assert payload["tool_result"]["target_currency"] == "EUR"


def test_explicit_entities_override_memory_defaults(client):
    client.post("/memory", json={"key": "default_city", "value": "Hà Nội", "category": "preference"})
    client.post("/memory", json={"key": "default_currency", "value": "EUR", "category": "preference"})

    response = client.post("/text-chat", json={"message": "Thời tiết Tokyo hôm nay thế nào?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_used"] == "weather"
    assert payload["tool_result"]["location"] == "Tokyo"

    response = client.post("/text-chat", json={"message": "100 USD sang VND hôm nay?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_used"] == "currency"
    assert payload["tool_result"]["target_currency"] == "VND"
