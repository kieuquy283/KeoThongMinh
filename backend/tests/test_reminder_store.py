from __future__ import annotations

import importlib
from datetime import datetime, timedelta
from pathlib import Path

from app.services.reminder_store import ReminderStore


def reload_settings():
    config_module = importlib.import_module("app.config")
    config_module = importlib.reload(config_module)
    config_module.get_settings.cache_clear()
    return config_module.get_settings()


def test_data_dir_defaults_to_backend_data(monkeypatch):
    monkeypatch.delenv("KEOBOT_DATA_DIR", raising=False)

    settings = reload_settings()

    assert settings.data_dir == Path(__file__).resolve().parents[1] / "data"


def test_data_dir_uses_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("KEOBOT_DATA_DIR", str(tmp_path))

    settings = reload_settings()

    assert settings.data_dir == tmp_path


def test_reminder_store_crud_and_due_flow(tmp_path):
    store = ReminderStore(tmp_path / "reminders.sqlite3")
    now = datetime(2026, 6, 9, 14, 0, 0)
    remind_at = now + timedelta(minutes=15)
    triggered_at = now + timedelta(minutes=30)

    created = store.create("uong nuoc", remind_at, created_at=now)

    assert created.id > 0
    assert created.title == "uong nuoc"
    assert created.status == "pending"
    assert created.created_at == now
    assert created.triggered_at is None

    items = store.list()
    assert [item.id for item in items] == [created.id]

    assert store.get_due(now=now) == []

    due_items = store.get_due(now=triggered_at)
    assert [item.id for item in due_items] == [created.id]

    triggered = store.mark_triggered(created.id, triggered_at=triggered_at)
    assert triggered is not None
    assert triggered.status == "triggered"
    assert triggered.triggered_at == triggered_at

    assert store.get_due(now=triggered_at + timedelta(minutes=1)) == []

    assert store.delete(created.id) is True
    assert store.list() == []


def test_mark_triggered_returns_none_for_unknown_id(tmp_path):
    store = ReminderStore(tmp_path / "reminders.sqlite3")

    assert store.mark_triggered(999) is None


def test_delete_returns_false_for_unknown_id(tmp_path):
    store = ReminderStore(tmp_path / "reminders.sqlite3")

    assert store.delete(999) is False
