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


def test_memory_store_enhanced_fields(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")

    item = store.set_memory("default_city", "Hà Nội", source="settings_ui", confidence=0.9)
    assert item["source"] == "settings_ui"
    assert item["confidence"] == 0.9
    assert item["is_enabled"] is True
    assert item["last_used_at"] is None


def test_memory_store_update_memory(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")

    store.set_memory("user_name", "Quy")
    updated = store.update_memory("user_name", value="Minh", category="personal")
    assert updated is not None
    assert updated["value"] == "Minh"
    assert updated["category"] == "personal"

    updated2 = store.update_memory("user_name", is_enabled=False)
    assert updated2 is not None
    assert updated2["is_enabled"] is False
    assert updated2["value"] == "Minh"

    not_found = store.update_memory("nonexistent", value="x")
    assert not_found is None


def test_memory_store_enable_disable(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")

    store.set_memory("user_name", "Quy")
    disabled = store.set_memory_enabled("user_name", False)
    assert disabled is not None
    assert disabled["is_enabled"] is False

    enabled = store.set_memory_enabled("user_name", True)
    assert enabled is not None
    assert enabled["is_enabled"] is True

    not_found = store.set_memory_enabled("nonexistent", False)
    assert not_found is None


def test_memory_store_context_excludes_disabled(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")

    store.set_memory("user_name", "Quy")
    store.set_memory("default_city", "Hà Nội")
    store.set_memory_enabled("user_name", False)

    context = store.get_memory_context()
    assert "user_name" not in context
    assert context["default_city"] == "Hà Nội"


def test_memory_store_touch_memory(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")

    store.set_memory("user_name", "Quy")
    assert store.get_memory("user_name")["last_used_at"] is None

    store.touch_memory("user_name")
    assert store.get_memory("user_name")["last_used_at"] is not None


def test_memory_store_migration_from_v1(tmp_path):
    v1_path = tmp_path / "memory_v1.sqlite3"
    import sqlite3
    conn = sqlite3.connect(v1_path)
    conn.execute(
        """
        CREATE TABLE memory_items (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'preference',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute("PRAGMA user_version = 1")
    conn.execute(
        "INSERT INTO memory_items (key, value, category, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("user_name", "Quy", "preference", "2024-01-01T00:00:00", "2024-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()

    store = MemoryStore(v1_path)
    item = store.get_memory("user_name")
    assert item is not None
    assert item["value"] == "Quy"
    assert item["source"] == "explicit_user_request"
    assert item["is_enabled"] is True
    assert item["confidence"] == 1.0
    assert item["last_used_at"] is None

