from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(slots=True)
class ReminderDraft:
    title: str
    remind_at: datetime
    repeat_interval: int | None = None


REPEAT_PATTERNS: list[tuple[str, int]] = [
    (r"lặp\s+lại\s+mỗi\s+(\d+)\s+phút", 60),
    (r"lặp\s+lại\s+mỗi\s+(\d+)\s+tiếng", 3600),
    (r"lặp\s+lại\s+mỗi\s+(\d+)\s+giờ", 3600),
    (r"lặp\s+lại\s+mỗi\s+ngày", 86400),
    (r"mỗi\s+(\d+)\s+phút", 60),
    (r"mỗi\s+(\d+)\s+tiếng", 3600),
    (r"mỗi\s+(\d+)\s+giờ", 3600),
    (r"mỗi\s+ngày", 86400),
]


def _extract_repeat_interval(title: str) -> tuple[str, int | None]:
    for pattern, multiplier in REPEAT_PATTERNS:
        match = re.search(pattern, title, flags=re.IGNORECASE)
        if match:
            cleaned = re.sub(pattern, "", title, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r"[,;:\s]+$", "", cleaned).strip()
            cleaned = re.sub(r"^[,;:\s]+", "", cleaned).strip()
            if match.lastindex and match.group(1):
                return cleaned, int(match.group(1)) * multiplier
            return cleaned, multiplier
    return title, None


def _parse_relative_hours(text: str, now: datetime) -> ReminderDraft | None:
    match = re.fullmatch(
        r"(?P<hours>\d{1,2})\s+tiếng\s+nữa\s+nhắc\s+(?:mình|tôi)\s+(?P<title>.+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    hours = int(match.group("hours"))
    if hours <= 0:
        return None
    return ReminderDraft(
        title=_clean_title(match.group("title")),
        remind_at=now + timedelta(hours=hours),
    )


def parse_reminder_text(text: str, *, now: datetime | None = None) -> ReminderDraft | None:
    reference_time = now or datetime.now()
    normalized = " ".join(text.strip().split())

    cleaned_text, global_repeat = _extract_repeat_interval(normalized)

    for parser in (
        _parse_relative_minutes,
        _parse_relative_hours,
        _parse_morning_hour,
        _parse_tomorrow_hour,
        _parse_evening_hour,
        _parse_clock_time,
    ):
        draft = parser(cleaned_text, reference_time)
        if draft is not None:
            if draft.repeat_interval is None and global_repeat is not None:
                draft.repeat_interval = global_repeat
            if draft.repeat_interval is None:
                _, title_repeat = _extract_repeat_interval(draft.title)
                if title_repeat is not None:
                    draft.repeat_interval = title_repeat
                    draft.title, _ = _extract_repeat_interval(draft.title)
            return draft

    return None


def _parse_relative_minutes(text: str, now: datetime) -> ReminderDraft | None:
    match = re.fullmatch(
        r"(?P<minutes>\d{1,3})\s+phút\s+nữa\s+nhắc\s+(?:mình|tôi)\s+(?P<title>.+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    minutes = int(match.group("minutes"))
    if minutes <= 0:
        return None

    return ReminderDraft(
        title=_clean_title(match.group("title")),
        remind_at=now + timedelta(minutes=minutes),
    )


def _parse_tomorrow_hour(text: str, now: datetime) -> ReminderDraft | None:
    match = re.fullmatch(
        r"ngày\s+mai\s+(?P<hour>\d{1,2})\s+giờ(?:\s+(?P<minute>\d{1,2}))?\s+nhắc\s+(?:mình|tôi)\s+(?P<title>.+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    scheduled = _build_datetime(
        now + timedelta(days=1),
        int(match.group("hour")),
        int(match.group("minute") or "0"),
    )
    if scheduled is None:
        return None

    return ReminderDraft(title=_clean_title(match.group("title")), remind_at=scheduled)


def _parse_morning_hour(text: str, now: datetime) -> ReminderDraft | None:
    match = re.fullmatch(
        r"(?P<hour>\d{1,2})\s+giờ\s+sáng\s+nhắc\s+(?:mình|tôi)\s+(?P<title>.+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    hour = int(match.group("hour"))
    if not (4 <= hour <= 11):
        hour = hour if 0 <= hour <= 23 else 0
    scheduled = _next_matching_time(now, hour, 0)
    if scheduled is None:
        return None
    return ReminderDraft(title=_clean_title(match.group("title")), remind_at=scheduled)


def _parse_evening_hour(text: str, now: datetime) -> ReminderDraft | None:
    match = re.fullmatch(
        r"(?P<hour>\d{1,2})\s+giờ\s+tối\s+nhắc\s+(?:mình|tôi)\s+(?P<title>.+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    hour = int(match.group("hour"))
    if 1 <= hour <= 11:
        hour += 12
    scheduled = _next_matching_time(now, hour, 0)
    if scheduled is None:
        return None

    return ReminderDraft(title=_clean_title(match.group("title")), remind_at=scheduled)


def _parse_clock_time(text: str, now: datetime) -> ReminderDraft | None:
    match = re.fullmatch(
        r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s+nhắc\s+(?:mình|tôi)\s+(?P<title>.+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    scheduled = _next_matching_time(now, int(match.group("hour")), int(match.group("minute")))
    if scheduled is None:
        return None

    return ReminderDraft(title=_clean_title(match.group("title")), remind_at=scheduled)


def _build_datetime(base_date: datetime, hour: int, minute: int) -> datetime | None:
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _next_matching_time(now: datetime, hour: int, minute: int) -> datetime | None:
    scheduled = _build_datetime(now, hour, minute)
    if scheduled is None:
        return None
    if scheduled <= now:
        scheduled = scheduled + timedelta(days=1)
    return scheduled


def _clean_title(title: str) -> str:
    return title.strip().rstrip(".!?")
