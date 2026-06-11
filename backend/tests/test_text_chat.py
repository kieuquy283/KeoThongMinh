from __future__ import annotations


def test_text_chat_local_mode(client):
    message = "Kẹo Thông Minh oi, ban la ai?"

    response = client.post("/text-chat", json={"message": message})

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_text"] == message
    assert isinstance(payload["bot_text"], str)
    assert payload["bot_text"].strip()
    assert payload["emotion"] == "happy"
