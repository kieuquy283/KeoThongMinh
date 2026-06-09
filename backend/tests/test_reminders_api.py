from __future__ import annotations

from datetime import datetime, timedelta


def test_create_and_list_reminders(client):
    remind_at = datetime.now() + timedelta(hours=1)

    create_response = client.post(
        "/reminders",
        json={
            "title": "uống nước",
            "remind_at": remind_at.isoformat(),
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["title"] == "uống nước"
    assert created["status"] == "pending"
    assert created["triggered_at"] is None

    list_response = client.get("/reminders")

    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]


def test_due_and_triggered_flow(client):
    remind_at = datetime.now() - timedelta(minutes=5)
    create_response = client.post(
        "/reminders",
        json={
            "title": "kiểm tra email",
            "remind_at": remind_at.isoformat(),
        },
    )
    reminder_id = create_response.json()["id"]

    due_response = client.get("/reminders/due")

    assert due_response.status_code == 200
    due_items = due_response.json()
    assert [item["id"] for item in due_items] == [reminder_id]

    triggered_response = client.post(f"/reminders/{reminder_id}/triggered")

    assert triggered_response.status_code == 200
    triggered = triggered_response.json()
    assert triggered["id"] == reminder_id
    assert triggered["status"] == "triggered"
    assert triggered["triggered_at"] is not None

    due_after_trigger = client.get("/reminders/due")
    assert due_after_trigger.status_code == 200
    assert due_after_trigger.json() == []


def test_delete_reminder(client):
    remind_at = datetime.now() + timedelta(hours=2)
    create_response = client.post(
        "/reminders",
        json={
            "title": "gọi điện",
            "remind_at": remind_at.isoformat(),
        },
    )
    reminder_id = create_response.json()["id"]

    delete_response = client.delete(f"/reminders/{reminder_id}")

    assert delete_response.status_code == 200
    assert delete_response.json() == {"ok": True}
    assert client.get("/reminders").json() == []


def test_reminder_404s(client):
    assert client.delete("/reminders/999").status_code == 404
    assert client.post("/reminders/999/triggered").status_code == 404
