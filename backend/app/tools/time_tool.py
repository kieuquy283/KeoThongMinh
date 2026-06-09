from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class TimezoneTarget:
    label: str
    timezone: str


LOCATION_TO_TIMEZONE: tuple[tuple[tuple[str, ...], TimezoneTarget], ...] = (
    (("viet nam", "vietnam", "vn", "hanoi", "ha noi", "ho chi minh", "ho chi minh city"), TimezoneTarget(label="Việt Nam", timezone="Asia/Ho_Chi_Minh")),
    (("japan", "nhat", "nhat ban", "tokyo"), TimezoneTarget(label="Nhật", timezone="Asia/Tokyo")),
    (("korea", "han", "han quoc", "seoul"), TimezoneTarget(label="Hàn", timezone="Asia/Seoul")),
    (("united states", "my", "usa", "new york"), TimezoneTarget(label="Mỹ/New York", timezone="America/New_York")),
    (("united kingdom", "uk", "anh", "london"), TimezoneTarget(label="United Kingdom/London", timezone="Europe/London")),
    (("utc", "gmt"), TimezoneTarget(label="UTC", timezone="UTC")),
)


def get_time_info(query: str, entities: dict[str, Any] | None = None, now: datetime | None = None) -> dict[str, str]:
    target = resolve_timezone_target(query, entities=entities)
    current_time = _to_timezone(now or datetime.now(ZoneInfo(target.timezone)), target.timezone)

    return {
        "location": target.label,
        "timezone": target.timezone,
        "local_time": current_time.isoformat(),
        "formatted_time": current_time.strftime("%H:%M, %d/%m/%Y"),
        "updated_at": current_time.isoformat(),
    }


def resolve_timezone_target(query: str, entities: dict[str, Any] | None = None) -> TimezoneTarget:
    entities = entities or {}

    timezone = entities.get("timezone")
    if isinstance(timezone, str) and timezone.strip():
        return TimezoneTarget(label=_label_from_timezone(timezone), timezone=timezone)

    location = entities.get("location")
    if isinstance(location, str) and location.strip():
        resolved = _resolve_from_location(location)
        if resolved is not None:
            return resolved

    normalized = _normalize_text(query)
    for keywords, target in LOCATION_TO_TIMEZONE:
        if any(keyword in normalized for keyword in keywords):
            return target

    return TimezoneTarget(label="UTC", timezone="UTC")


def _resolve_from_location(location: str) -> TimezoneTarget | None:
    normalized = _normalize_text(location)
    for keywords, target in LOCATION_TO_TIMEZONE:
        if any(keyword == normalized or keyword in normalized for keyword in keywords):
            return target
    return None


def _label_from_timezone(timezone: str) -> str:
    for _, target in LOCATION_TO_TIMEZONE:
        if target.timezone == timezone:
            return target.label
    return timezone


def _to_timezone(dt: datetime, timezone: str) -> datetime:
    zone = ZoneInfo(timezone)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=zone)
    return dt.astimezone(zone)


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    without_marks = "".join(character for character in decomposed if unicodedata.category(character) != "Mn")
    return without_marks.replace("đ", "d").strip()
