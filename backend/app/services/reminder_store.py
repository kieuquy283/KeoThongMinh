from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    repeat_interval: int | None = None  # seconds between repeats, None = one-shot


def get_default_db_path() -> Path:
    from app.data_paths import get_reminder_db_path, migrate_old_db
    migrate_old_db("reminders.sqlite3")
    return get_reminder_db_path()


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
                    triggered_at TEXT,
                    repeat_interval INTEGER
                )
                """
            )
            try:
                connection.execute("ALTER TABLE reminders ADD COLUMN repeat_interval INTEGER")
            except sqlite3.OperationalError:
                pass

    def create(self, title: str, remind_at: datetime, *, created_at: datetime | None = None, repeat_interval: int | None = None) -> Reminder:
        created_at = created_at or datetime.now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO reminders (title, remind_at, status, created_at, triggered_at, repeat_interval)
                VALUES (?, ?, 'pending', ?, NULL, ?)
                """,
                (title, remind_at.isoformat(), created_at.isoformat(), repeat_interval),
            )
            reminder_id = int(cursor.lastrowid)

        return self.get(reminder_id)

    def list(self) -> list[Reminder]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, remind_at, status, created_at, triggered_at, repeat_interval
                FROM reminders
                ORDER BY remind_at ASC, id ASC
                """
            ).fetchall()
        return [self._row_to_reminder(row) for row in rows]

    _UNSET = object()

    def update(self, reminder_id: int, *, title: str | None = None, remind_at: datetime | None = None, repeat_interval: int | None | object = _UNSET) -> Reminder | None:
        try:
            existing = self.get(reminder_id)
        except KeyError:
            return None
        new_title = title if title is not None else existing.title
        new_remind_at = remind_at if remind_at is not None else existing.remind_at
        if repeat_interval is not self._UNSET:
            new_repeat = None if repeat_interval is None else (repeat_interval if isinstance(repeat_interval, int) else existing.repeat_interval)
        else:
            new_repeat = existing.repeat_interval
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE reminders
                SET title = ?, remind_at = ?, repeat_interval = ?
                WHERE id = ?
                """,
                (new_title, new_remind_at.isoformat(), new_repeat, reminder_id),
            )
        if cursor.rowcount == 0:
            return None
        return self.get(reminder_id)

    def delete(self, reminder_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        return cursor.rowcount > 0

    def get_due(self, *, now: datetime | None = None) -> list[Reminder]:
        due_at = (now or datetime.now()).isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, remind_at, status, created_at, triggered_at, repeat_interval
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
                SELECT id, title, remind_at, status, created_at, triggered_at, repeat_interval
                FROM reminders
                WHERE id = ?
                """,
                (reminder_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Reminder not found: {reminder_id}")
        return self._row_to_reminder(row)

    def get_recurring_due(self, *, now: datetime | None = None) -> list[Reminder]:
        """Get triggered reminders with repeat_interval whose next occurrence is due."""
        current_time = now or datetime.now()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, remind_at, status, created_at, triggered_at, repeat_interval
                FROM reminders
                WHERE status = 'triggered' AND repeat_interval IS NOT NULL
                """,
            ).fetchall()
        due: list[Reminder] = []
        for row in rows:
            reminder = self._row_to_reminder(row)
            if reminder.triggered_at and reminder.repeat_interval:
                next_at = reminder.triggered_at + timedelta(seconds=reminder.repeat_interval)
                if next_at <= current_time:
                    due.append(reminder)
        return due

    def reschedule_recurring(self, reminder_id: int, *, now: datetime | None = None) -> Reminder | None:
        reminder = self.get(reminder_id)
        if reminder.repeat_interval is None:
            return None
        current_time = now or datetime.now()
        next_time = current_time + timedelta(seconds=reminder.repeat_interval)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE reminders
                SET remind_at = ?, status = 'pending', triggered_at = NULL
                WHERE id = ?
                """,
                (next_time.isoformat(), reminder_id),
            )
        if cursor.rowcount == 0:
            return None
        return self.get(reminder_id)

    def clear_reminders(self) -> int:
        with self._connect() as connection:
            count_row = connection.execute("SELECT COUNT(*) AS count FROM reminders").fetchone()
            count = int(count_row["count"]) if count_row is not None else 0
            connection.execute("DELETE FROM reminders")
        return count

    def _row_to_reminder(self, row: sqlite3.Row) -> Reminder:
        return Reminder(
            id=int(row["id"]),
            title=str(row["title"]),
            remind_at=datetime.fromisoformat(str(row["remind_at"])),
            status=str(row["status"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            triggered_at=datetime.fromisoformat(str(row["triggered_at"])) if row["triggered_at"] else None,
            repeat_interval=int(row["repeat_interval"]) if row["repeat_interval"] else None,
        )
