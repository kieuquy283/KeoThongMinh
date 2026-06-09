from __future__ import annotations

from datetime import datetime

from app.services.reminder_parser import parse_reminder_text


def test_parse_relative_minutes_minh():
    now = datetime(2026, 6, 9, 14, 0, 0)

    draft = parse_reminder_text("15 phút nữa nhắc mình uống nước", now=now)

    assert draft is not None
    assert draft.title == "uống nước"
    assert draft.remind_at == datetime(2026, 6, 9, 14, 15, 0)


def test_parse_relative_minutes_toi():
    now = datetime(2026, 6, 9, 14, 0, 0)

    draft = parse_reminder_text("30 phút nữa nhắc tôi kiểm tra email", now=now)

    assert draft is not None
    assert draft.title == "kiểm tra email"
    assert draft.remind_at == datetime(2026, 6, 9, 14, 30, 0)


def test_parse_evening_hour():
    now = datetime(2026, 6, 9, 14, 0, 0)

    draft = parse_reminder_text("8 giờ tối nhắc mình học tiếng Anh", now=now)

    assert draft is not None
    assert draft.title == "học tiếng Anh"
    assert draft.remind_at == datetime(2026, 6, 9, 20, 0, 0)


def test_parse_tomorrow_hour():
    now = datetime(2026, 6, 9, 14, 0, 0)

    draft = parse_reminder_text("ngày mai 9 giờ nhắc mình nộp báo cáo", now=now)

    assert draft is not None
    assert draft.title == "nộp báo cáo"
    assert draft.remind_at == datetime(2026, 6, 10, 9, 0, 0)


def test_parse_clock_time():
    now = datetime(2026, 6, 9, 14, 0, 0)

    draft = parse_reminder_text("20:30 nhắc mình gọi điện", now=now)

    assert draft is not None
    assert draft.title == "gọi điện"
    assert draft.remind_at == datetime(2026, 6, 9, 20, 30, 0)


def test_parse_clock_time_rolls_to_next_day_when_passed():
    now = datetime(2026, 6, 9, 21, 0, 0)

    draft = parse_reminder_text("20:30 nhắc mình gọi điện", now=now)

    assert draft is not None
    assert draft.remind_at == datetime(2026, 6, 10, 20, 30, 0)


def test_parse_non_reminder_returns_none():
    now = datetime(2026, 6, 9, 14, 0, 0)

    assert parse_reminder_text("hôm nay trời đẹp quá", now=now) is None
