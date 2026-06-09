from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.tools.time_tool import get_time_info, resolve_timezone_target


def test_resolve_timezone_target_japan_from_query():
    target = resolve_timezone_target("Bây giờ là mấy giờ ở Nhật?")

    assert target.label == "Nhật"
    assert target.timezone == "Asia/Tokyo"


def test_resolve_timezone_target_from_entity():
    target = resolve_timezone_target("Mấy giờ ở đâu?", entities={"timezone": "Europe/London"})

    assert target.label == "United Kingdom/London"
    assert target.timezone == "Europe/London"


def test_resolve_timezone_target_new_york():
    target = resolve_timezone_target("Mấy giờ ở New York rồi?")

    assert target.label == "Mỹ/New York"
    assert target.timezone == "America/New_York"


def test_get_time_info_formats_in_target_timezone():
    now = datetime(2026, 6, 9, 10, 0, 0, tzinfo=ZoneInfo("UTC"))

    payload = get_time_info("Mấy giờ ở Nhật?", now=now)

    assert payload["location"] == "Nhật"
    assert payload["timezone"] == "Asia/Tokyo"
    assert payload["local_time"].startswith("2026-06-09T19:00:00")
    assert payload["updated_at"].startswith("2026-06-09T19:00:00")


def test_get_time_info_supports_london():
    now = datetime(2026, 6, 9, 10, 0, 0, tzinfo=ZoneInfo("UTC"))

    payload = get_time_info("Mấy giờ ở Anh?", entities={"location": "London"}, now=now)

    assert payload["location"] == "United Kingdom/London"
    assert payload["timezone"] == "Europe/London"
    assert payload["local_time"].startswith("2026-06-09T11:00:00")


def test_get_time_info_defaults_to_utc():
    now = datetime(2026, 6, 9, 10, 0, 0, tzinfo=ZoneInfo("UTC"))

    payload = get_time_info("Thời gian trên trạm vũ trụ là gì?", now=now)

    assert payload["location"] == "UTC"
    assert payload["timezone"] == "UTC"
    assert payload["local_time"].startswith("2026-06-09T10:00:00")
