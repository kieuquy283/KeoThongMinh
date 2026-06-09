from __future__ import annotations

from datetime import datetime, timezone

from app.services.memory_store import MemoryStore


def test_memory_store_set_get_list_delete_clear(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")

    item = store.set_memory("default_city", "Hà Nội")
    assert item["key"] == "default_city"
    assert item["value"] == "Hà Nội"
    assert item["category"] == "preference"
    assert item["created_at"]
    assert item["updated_at"]

    fetched = store.get_memory("default_city")
    assert fetched is not None
    assert fetched["value"] == "Hà Nội"

    store.set_memory("default_timezone", "Asia/Ho_Chi_Minh")
    items = store.list_memory()
    assert [entry["key"] for entry in items] == ["default_timezone", "default_city"]

    context = store.get_memory_context()
    assert context == {
        "default_timezone": "Asia/Ho_Chi_Minh",
        "default_city": "Hà Nội",
    }

    assert store.delete_memory("default_city") is True
    assert store.get_memory("default_city") is None

    deleted = store.clear_memory()
    assert deleted == 1
    assert store.list_memory() == []


def test_memory_store_updates_existing_key_preserves_key(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")

    first = store.set_memory("user_name", "Quy")
    second = store.set_memory("user_name", "Minh")

    assert first["created_at"] == second["created_at"]
    assert second["value"] == "Minh"
    assert second["updated_at"] >= first["updated_at"]

