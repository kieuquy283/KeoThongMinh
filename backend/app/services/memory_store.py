from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger("keobot.memory")

SCHEMA_VERSION = 2


def get_default_db_path() -> Path:
    from app.data_paths import get_memory_db_path, migrate_old_db
    migrate_old_db("memory.sqlite3")
    return get_memory_db_path()


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
            self._migrate(connection)

    def _migrate(self, connection: sqlite3.Connection) -> None:
        cursor = connection.execute("PRAGMA user_version")
        current_version = int(cursor.fetchone()[0])

        if current_version < 2:
            connection.execute("ALTER TABLE memory_items ADD COLUMN source TEXT NOT NULL DEFAULT 'explicit_user_request'")
            connection.execute("ALTER TABLE memory_items ADD COLUMN confidence REAL NOT NULL DEFAULT 1.0")
            connection.execute("ALTER TABLE memory_items ADD COLUMN is_enabled INTEGER NOT NULL DEFAULT 1")
            connection.execute("ALTER TABLE memory_items ADD COLUMN last_used_at TEXT")
            connection.execute("PRAGMA user_version = 2")

    def set_memory(self, key: str, value: str, category: str = "preference", source: str = "explicit_user_request", confidence: float = 1.0) -> dict[str, Any]:
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
                    INSERT INTO memory_items (key, value, category, source, confidence, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (normalized_key, normalized_value, normalized_category, source, confidence, current_time, current_time),
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
        logger.info("Memory set: key=%s value=%s category=%s source=%s", normalized_key, normalized_value, normalized_category, source)
        return item

    def update_memory(self, key: str, value: str | None = None, category: str | None = None, is_enabled: bool | None = None) -> dict[str, Any] | None:
        normalized_key = _normalize_key(key)
        existing = self.get_memory(normalized_key)
        if existing is None:
            return None

        current_time = datetime.now(timezone.utc).isoformat()
        new_value = value if value is not None else existing["value"]
        new_category = category if category is not None else existing["category"]
        new_is_enabled = is_enabled if is_enabled is not None else existing["is_enabled"]

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE memory_items
                SET value = ?, category = ?, is_enabled = ?, updated_at = ?
                WHERE key = ?
                """,
                (new_value, new_category, int(new_is_enabled), current_time, normalized_key),
            )

        logger.info("Memory updated: key=%s value=%s category=%s is_enabled=%s", normalized_key, new_value, new_category, new_is_enabled)
        return self.get_memory(normalized_key)

    def set_memory_enabled(self, key: str, is_enabled: bool) -> dict[str, Any] | None:
        normalized_key = _normalize_key(key)
        existing = self.get_memory(normalized_key)
        if existing is None:
            return None

        current_time = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                "UPDATE memory_items SET is_enabled = ?, updated_at = ? WHERE key = ?",
                (int(is_enabled), current_time, normalized_key),
            )

        logger.info("Memory toggle: key=%s is_enabled=%s", normalized_key, is_enabled)
        return self.get_memory(normalized_key)

    def touch_memory(self, key: str) -> None:
        normalized_key = _normalize_key(key)
        current_time = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                "UPDATE memory_items SET last_used_at = ? WHERE key = ?",
                (current_time, normalized_key),
            )

    def get_memory(self, key: str) -> dict[str, Any] | None:
        normalized_key = _normalize_key(key)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT key, value, category, source, confidence, is_enabled, created_at, updated_at, last_used_at
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
                SELECT key, value, category, source, confidence, is_enabled, created_at, updated_at, last_used_at
                FROM memory_items
                ORDER BY updated_at DESC, key ASC
                """
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def delete_memory(self, key: str) -> bool:
        normalized_key = _normalize_key(key)
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM memory_items WHERE key = ?", (normalized_key,))
        result = cursor.rowcount > 0
        if result:
            logger.info("Memory deleted: key=%s", normalized_key)
        return result

    def clear_memory(self) -> int:
        with self._connect() as connection:
            count_row = connection.execute("SELECT COUNT(*) AS count FROM memory_items").fetchone()
            count = int(count_row["count"]) if count_row is not None else 0
            connection.execute("DELETE FROM memory_items")
        logger.info("Memory cleared: deleted=%d", count)
        return count

    def get_memory_context(self) -> dict[str, str]:
        context: dict[str, str] = {}
        for item in self.list_memory():
            if item["key"] in SAFE_CONTEXT_KEYS and item["value"] and item["is_enabled"]:
                context[item["key"]] = item["value"]
        return context

    def import_memories(self, records: list[dict], mode: str = "merge") -> dict:
        errors: list[str] = []
        records_found = len(records)
        records_added = 0
        records_updated = 0
        records_invalid = 0

        if mode == "replace":
            self.clear_memory()

        normalized_keys: set[str] = set()
        for record in records:
            try:
                key = _normalize_key(record.get("key", ""))
                if key in normalized_keys:
                    records_invalid += 1
                    errors.append(f"Duplicate key: {key}")
                    continue
                normalized_keys.add(key)
                value = _normalize_value(record.get("value", ""))
                category = record.get("category", "preference") or "preference"
                source = str(record.get("source", "import")) or "import"
                confidence = float(record.get("confidence", 1.0))
                is_enabled = bool(record.get("is_enabled", True))
                current_time = datetime.now(timezone.utc).isoformat()

                existing = self.get_memory(key)
                with self._connect() as connection:
                    if existing is None:
                        connection.execute(
                            """
                            INSERT INTO memory_items (key, value, category, source, confidence, is_enabled, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (key, value, category, source, confidence, int(is_enabled), current_time, current_time),
                        )
                        records_added += 1
                    else:
                        connection.execute(
                            """
                            UPDATE memory_items
                            SET value = ?, category = ?, source = ?, confidence = ?, is_enabled = ?, updated_at = ?
                            WHERE key = ?
                            """,
                            (value, category, source, confidence, int(is_enabled), current_time, key),
                        )
                        records_updated += 1
            except (ValueError, TypeError) as e:
                records_invalid += 1
                errors.append(f"Invalid record: {e}")

        return {
            "records_found": records_found,
            "records_added": records_added,
            "records_updated": records_updated,
            "records_invalid": records_invalid,
            "errors": errors,
        }

    def _row_to_item(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "key": str(row["key"]),
            "value": str(row["value"]),
            "category": str(row["category"]),
            "source": str(row["source"]),
            "confidence": float(row["confidence"]),
            "is_enabled": bool(row["is_enabled"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "last_used_at": str(row["last_used_at"]) if row["last_used_at"] else None,
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
