from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from app.config import get_settings


@dataclass(slots=True)
class Reminder:
    id: int
    title: str
    remind_at: datetime
    status: str
    created_at: datetime
    triggered_at: datetime | None


def get_default_db_path() -> Path:
    settings = get_settings()
    return settings.data_dir / "reminders.sqlite3"


@lru_cache(maxsize=1)
def get_reminder_store() -> "ReminderStore":
    return ReminderStore()


class ReminderStore:
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
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    remind_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    triggered_at TEXT
                )
                """
            )

    def create(self, title: str, remind_at: datetime, *, created_at: datetime | None = None) -> Reminder:
        created_at = created_at or datetime.now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO reminders (title, remind_at, status, created_at, triggered_at)
                VALUES (?, ?, 'pending', ?, NULL)
                """,
                (title, remind_at.isoformat(), created_at.isoformat()),
            )
            reminder_id = int(cursor.lastrowid)

        return self.get(reminder_id)

    def list(self) -> list[Reminder]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, remind_at, status, created_at, triggered_at
                FROM reminders
                ORDER BY remind_at ASC, id ASC
                """
            ).fetchall()
        return [self._row_to_reminder(row) for row in rows]

    def delete(self, reminder_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        return cursor.rowcount > 0

    def get_due(self, *, now: datetime | None = None) -> list[Reminder]:
        due_at = (now or datetime.now()).isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, remind_at, status, created_at, triggered_at
                FROM reminders
                WHERE status = 'pending' AND remind_at <= ?
                ORDER BY remind_at ASC, id ASC
                """,
                (due_at,),
            ).fetchall()
        return [self._row_to_reminder(row) for row in rows]

    def mark_triggered(self, reminder_id: int, *, triggered_at: datetime | None = None) -> Reminder | None:
        triggered_at = triggered_at or datetime.now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE reminders
                SET status = 'triggered', triggered_at = ?
                WHERE id = ?
                """,
                (triggered_at.isoformat(), reminder_id),
            )
        if cursor.rowcount == 0:
            return None
        return self.get(reminder_id)

    def get(self, reminder_id: int) -> Reminder:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, title, remind_at, status, created_at, triggered_at
                FROM reminders
                WHERE id = ?
                """,
                (reminder_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Reminder not found: {reminder_id}")
        return self._row_to_reminder(row)

    def _row_to_reminder(self, row: sqlite3.Row) -> Reminder:
        return Reminder(
            id=int(row["id"]),
            title=str(row["title"]),
            remind_at=datetime.fromisoformat(str(row["remind_at"])),
            status=str(row["status"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            triggered_at=datetime.fromisoformat(str(row["triggered_at"])) if row["triggered_at"] else None,
        )
