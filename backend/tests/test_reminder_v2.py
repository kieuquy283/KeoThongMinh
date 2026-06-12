from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.services.reminder_checker import run_reminder_checker_loop
from app.services.reminder_parser import ReminderDraft, parse_reminder_text
from app.services.reminder_store import Reminder, ReminderStore, get_reminder_store
from app.services.event_bus import EventType, get_event_bus


@pytest.fixture(autouse=True)
def _fresh_store(tmp_path):
    db_file = tmp_path / "test_reminders.sqlite3"
    store = ReminderStore(db_path=db_file)
    yield store


class TestReminderStoreV2:
    def test_create_with_repeat_interval(self, _fresh_store: ReminderStore):
        now = datetime.now()
        r = _fresh_store.create("test", now, repeat_interval=3600)
        assert r.repeat_interval == 3600
        assert r.status == "pending"

    def test_create_without_repeat(self, _fresh_store: ReminderStore):
        now = datetime.now()
        r = _fresh_store.create("test", now)
        assert r.repeat_interval is None

    def test_update_title(self, _fresh_store: ReminderStore):
        now = datetime.now()
        r = _fresh_store.create("old", now)
        updated = _fresh_store.update(r.id, title="new")
        assert updated is not None
        assert updated.title == "new"

    def test_update_remind_at(self, _fresh_store: ReminderStore):
        now = datetime.now()
        r = _fresh_store.create("test", now)
        later = now + timedelta(hours=2)
        updated = _fresh_store.update(r.id, remind_at=later)
        assert updated is not None
        assert updated.remind_at == later

    def test_update_repeat_interval(self, _fresh_store: ReminderStore):
        now = datetime.now()
        r = _fresh_store.create("test", now, repeat_interval=3600)
        updated = _fresh_store.update(r.id, repeat_interval=1800)
        assert updated is not None
        assert updated.repeat_interval == 1800

    def test_update_removes_repeat_interval(self, _fresh_store: ReminderStore):
        now = datetime.now()
        r = _fresh_store.create("test", now, repeat_interval=3600)
        updated = _fresh_store.update(r.id, repeat_interval=None)
        assert updated is not None
        assert updated.repeat_interval is None

    def test_update_nonexistent_returns_none(self, _fresh_store: ReminderStore):
        updated = _fresh_store.update(9999, title="nope")
        assert updated is None

    def test_reschedule_recurring(self, _fresh_store: ReminderStore):
        now = datetime.now()
        r = _fresh_store.create("test", now - timedelta(minutes=5), repeat_interval=3600)
        _fresh_store.mark_triggered(r.id)
        rescheduled = _fresh_store.reschedule_recurring(r.id, now=now)
        assert rescheduled is not None
        assert rescheduled.status == "pending"
        assert rescheduled.triggered_at is None
        assert rescheduled.remind_at > now

    def test_reschedule_non_recurring_returns_none(self, _fresh_store: ReminderStore):
        now = datetime.now()
        r = _fresh_store.create("test", now)
        _fresh_store.mark_triggered(r.id)
        result = _fresh_store.reschedule_recurring(r.id, now=now)
        assert result is None

    def test_get_recurring_due(self, _fresh_store: ReminderStore):
        now = datetime.now()
        r = _fresh_store.create("test", now - timedelta(hours=2), repeat_interval=3600)
        _fresh_store.mark_triggered(r.id, triggered_at=now - timedelta(hours=1))
        due_list = _fresh_store.get_recurring_due(now=now)
        assert len(due_list) == 1
        assert due_list[0].id == r.id

    def test_get_recurring_not_due_yet(self, _fresh_store: ReminderStore):
        now = datetime.now()
        r = _fresh_store.create("test", now - timedelta(hours=2), repeat_interval=7200)
        _fresh_store.mark_triggered(r.id, triggered_at=now)
        due_list = _fresh_store.get_recurring_due(now=now)
        assert len(due_list) == 0


class TestReminderParserV2:
    def test_parse_repeat_relative_minutes(self):
        draft = parse_reminder_text("30 phút nữa nhắc tôi uống nước, lặp lại mỗi 30 phút")
        assert draft is not None
        assert draft.repeat_interval == 1800
        assert "lặp" not in draft.title

    def test_parse_repeat_hours(self):
        draft = parse_reminder_text("1 tiếng nữa nhắc mình tập thể dục, lặp lại mỗi 2 tiếng")
        assert draft is not None
        assert draft.repeat_interval == 7200

    def test_parse_repeat_daily(self):
        draft = parse_reminder_text("7 giờ sáng nhắc mình đánh răng, lặp lại mỗi ngày")
        assert draft is not None
        assert draft.repeat_interval == 86400

    def test_parse_repeat_every_day(self):
        draft = parse_reminder_text("7 giờ tối nhắc tôi học bài, mỗi ngày")
        assert draft is not None
        assert draft.repeat_interval == 86400

    def test_parse_repeat_interval_short(self):
        draft = parse_reminder_text("5 phút nữa nhắc mình nghỉ ngơi, mỗi 5 phút")
        assert draft is not None
        assert draft.repeat_interval == 300

    def test_parse_without_repeat(self):
        draft = parse_reminder_text("15 phút nữa nhắc mình mua sữa")
        assert draft is not None
        assert draft.repeat_interval is None

    def test_repeat_cleaned_title(self):
        draft = parse_reminder_text("30 phút nữa nhắc tôi uống nước, lặp lại mỗi 30 phút")
        assert draft is not None
        assert "uống nước" in draft.title
        assert "lặp" not in draft.title


class TestReminderDataclassV2:
    def test_repeat_interval_field_exists(self):
        r = Reminder(id=1, title="test", remind_at=datetime.now(), status="pending", created_at=datetime.now(), triggered_at=None, repeat_interval=3600)
        assert r.repeat_interval == 3600

    def test_repeat_interval_default_none(self):
        r = Reminder(id=1, title="test", remind_at=datetime.now(), status="pending", created_at=datetime.now(), triggered_at=None)
        assert r.repeat_interval is None


class TestEventTypeV2:
    def test_reminder_due_event_type_exists(self):
        assert hasattr(EventType, "reminder_due")
        assert EventType.reminder_due.value == "reminder_due"


class TestReminderCheckerEventPublishing:
    @pytest.mark.asyncio
    async def test_checker_fires_and_publishes_event(self, tmp_path):
        from app.services.reminder_store import ReminderStore
        store = ReminderStore(db_path=tmp_path / "test_checker.sqlite3")
        now = datetime.now()
        store.create("test", now - timedelta(seconds=10), repeat_interval=3600)

        received_events = []

        def listener(event):
            received_events.append(event)

        bus = get_event_bus()
        bus.subscribe(EventType.reminder_due, listener)

        import app.services.reminder_checker as rc
        rc._CHECK_INTERVAL = 0.1

        import asyncio
        task = asyncio.create_task(run_reminder_checker_loop(store=store))
        await asyncio.sleep(0.3)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, StopIteration):
            pass

        assert len(received_events) >= 1
        evt = received_events[0]
        assert evt.type == EventType.reminder_due
        assert evt.payload["title"] == "test"
        assert evt.payload["repeat_interval"] == 3600

    @pytest.mark.asyncio
    async def test_checker_reschedules_recurring(self, tmp_path):
        from app.services.reminder_store import ReminderStore
        store = ReminderStore(db_path=tmp_path / "test_checker2.sqlite3")
        now = datetime.now()
        store.create("recurring", now - timedelta(seconds=10), repeat_interval=3600)

        import app.services.reminder_checker as rc
        rc._CHECK_INTERVAL = 0.1

        import asyncio
        task = asyncio.create_task(run_reminder_checker_loop(store=store))
        await asyncio.sleep(0.3)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, StopIteration):
            pass

        due = store.get_due(now=now + timedelta(seconds=30))
        recurring_due = store.get_recurring_due(now=now + timedelta(seconds=30))
        assert len(due) == 0
        assert len(recurring_due) == 0
        all_reminders = store.list()
        assert len(all_reminders) == 1
        assert all_reminders[0].status == "pending"
