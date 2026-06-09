from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings

MEMORY_DB_FILENAME = "memory.sqlite3"


def get_default_db_path() -> Path:
    settings = get_settings()
    return settings.data_dir / MEMORY_DB_FILENAME


@lru_cache(maxsize=1)
def get_memory_store() -> "MemoryStore":
    return MemoryStore()


class MemoryStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else get_default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_items (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'preference',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def set_memory(self, key: str, value: str, category: str = "preference") -> dict[str, Any]:
        normalized_key = _normalize_key(key)
        normalized_value = _normalize_value(value)
        normalized_category = _normalize_category(category)
        current_time = datetime.now(timezone.utc).isoformat()

        with self._connect() as connection:
            row = connection.execute(
                "SELECT created_at FROM memory_items WHERE key = ?",
                (normalized_key,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO memory_items (key, value, category, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (normalized_key, normalized_value, normalized_category, current_time, current_time),
                )
            else:
                connection.execute(
                    """
                    UPDATE memory_items
                    SET value = ?, category = ?, updated_at = ?
                    WHERE key = ?
                    """,
                    (normalized_value, normalized_category, current_time, normalized_key),
                )

        item = self.get_memory(normalized_key)
        if item is None:
            raise RuntimeError("Failed to persist memory item.")
        return item

    def get_memory(self, key: str) -> dict[str, Any] | None:
        normalized_key = _normalize_key(key)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT key, value, category, created_at, updated_at
                FROM memory_items
                WHERE key = ?
                """,
                (normalized_key,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_item(row)

    def list_memory(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT key, value, category, created_at, updated_at
                FROM memory_items
                ORDER BY updated_at DESC, key ASC
                """
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def delete_memory(self, key: str) -> bool:
        normalized_key = _normalize_key(key)
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM memory_items WHERE key = ?", (normalized_key,))
        return cursor.rowcount > 0

    def clear_memory(self) -> int:
        with self._connect() as connection:
            count_row = connection.execute("SELECT COUNT(*) AS count FROM memory_items").fetchone()
            count = int(count_row["count"]) if count_row is not None else 0
            connection.execute("DELETE FROM memory_items")
        return count

    def get_memory_context(self) -> dict[str, str]:
        context: dict[str, str] = {}
        for item in self.list_memory():
            if item["key"] in SAFE_CONTEXT_KEYS and item["value"]:
                context[item["key"]] = item["value"]
        return context

    def _row_to_item(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "key": str(row["key"]),
            "value": str(row["value"]),
            "category": str(row["category"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }


SAFE_CONTEXT_KEYS = {
    "user_name",
    "preferred_form_of_address",
    "default_city",
    "default_timezone",
    "default_currency",
    "preferred_tts_voice",
    "answer_style",
}


def _normalize_key(key: str) -> str:
    cleaned = str(key).strip()
    if not cleaned:
        raise ValueError("Memory key cannot be empty.")
    return cleaned


def _normalize_value(value: str) -> str:
    cleaned = str(value).strip()
    if not cleaned:
        raise ValueError("Memory value cannot be empty.")
    return cleaned


def _normalize_category(category: str) -> str:
    cleaned = str(category).strip()
    return cleaned or "preference"
