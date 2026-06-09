from __future__ import annotations

import json
import unicodedata
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from app.config import get_settings

DEFAULT_LOCATION = "Hanoi, VN"


def get_weather_info(query: str, entities: dict[str, Any] | None = None, now: datetime | None = None) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    location = resolve_weather_location(query, entities=entities)
    settings = get_settings()
    provider = settings.weather_provider.lower()
    configured = provider == "openweathermap" and bool(settings.openweather_api_key)

    if not configured:
        return _diagnostic_weather(
            provider=provider or "none",
            configured=False,
            live=False,
            status="not_configured",
            message="Weather provider not configured",
            last_checked_at=current_time,
            location=location,
        )

    try:
        payload = _fetch_openweather(location, settings.openweather_api_key or "")
    except HTTPError as exc:
        status, message = _classify_http_error(exc)
        return _diagnostic_weather(
            provider=provider,
            configured=True,
            live=False,
            status=status,
            message=message,
            last_checked_at=current_time,
            location=location,
        )
    except URLError:
        return _diagnostic_weather(
            provider=provider,
            configured=True,
            live=False,
            status="network_error",
            message="Weather provider network error",
            last_checked_at=current_time,
            location=location,
        )
    except Exception:
        return _diagnostic_weather(
            provider=provider,
            configured=True,
            live=False,
            status="unknown_error",
            message="Weather provider unknown error",
            last_checked_at=current_time,
            location=location,
        )

    return {
        "provider": provider,
        "configured": True,
        "live": True,
        "status": "ok",
        "message": "Live weather data",
        "last_checked_at": current_time.isoformat(),
        "location": payload["location"],
        "description": payload["description"],
        "temperature_c": payload["temperature_c"],
        "feels_like_c": payload["feels_like_c"],
        "humidity": payload["humidity"],
        "available": True,
        "reason": None,
        "updated_at": payload["updated_at"],
    }


def resolve_weather_location(query: str, entities: dict[str, Any] | None = None) -> str:
    entities = entities or {}
    location = entities.get("location")
    if isinstance(location, str) and location.strip():
        return _canonicalize_location(location)

    normalized = _normalize_text(query)
    for keyword in ("hanoi", "ha noi", "tokyo", "seoul", "new york", "london", "ho chi minh", "saigon"):
        if keyword in normalized:
            return _canonicalize_location(keyword)

    return DEFAULT_LOCATION


def _fetch_openweather(location: str, api_key: str) -> dict[str, Any]:
    params = urlencode(
        {
            "q": location,
            "appid": api_key,
            "units": "metric",
            "lang": "vi",
        }
    )
    request_url = f"https://api.openweathermap.org/data/2.5/weather?{params}"
    with urlopen(request_url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    weather_items = payload.get("weather") or []
    main_payload = payload.get("main") or {}
    if not weather_items or "temp" not in main_payload:
        raise RuntimeError("Weather provider returned an unsupported payload.")

    return {
        "location": payload.get("name", location),
        "description": weather_items[0].get("description", ""),
        "temperature_c": float(main_payload["temp"]),
        "feels_like_c": float(main_payload.get("feels_like", main_payload["temp"])),
        "humidity": int(main_payload.get("humidity", 0)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _diagnostic_weather(
    *,
    provider: str,
    configured: bool,
    live: bool,
    status: str,
    message: str,
    last_checked_at: datetime,
    location: str,
) -> dict[str, Any]:
    return {
        "provider": provider or "none",
        "configured": configured,
        "live": live,
        "status": status,
        "message": message,
        "last_checked_at": last_checked_at.isoformat(),
        "location": location,
        "available": False,
        "reason": message,
        "updated_at": last_checked_at.isoformat(),
    }


def _classify_http_error(exc: HTTPError) -> tuple[str, str]:
    if exc.code in {401, 403}:
        return "invalid_key", "Weather provider invalid key"
    if exc.code == 429:
        return "rate_limited", "Weather provider rate limited"
    return "unknown_error", f"Weather provider HTTP {exc.code}"


def _canonicalize_location(value: str) -> str:
    normalized = _normalize_text(value)
    if "tokyo" in normalized or "japan" in normalized:
        return "Tokyo"
    if "seoul" in normalized or "korea" in normalized:
        return "Seoul"
    if "new york" in normalized or "los angeles" in normalized or "san francisco" in normalized:
        return value.title()
    if "london" in normalized or "uk" in normalized or "united kingdom" in normalized:
        return "London"
    if "ho chi minh" in normalized or "saigon" in normalized:
        return "Ho Chi Minh City"
    if "da nang" in normalized:
        return "Da Nang"
    if "hai phong" in normalized:
        return "Hai Phong"
    if "can tho" in normalized:
        return "Can Tho"
    if "singapore" in normalized:
        return "Singapore"
    if "bangkok" in normalized:
        return "Bangkok"
    if "paris" in normalized:
        return "Paris"
    if "berlin" in normalized:
        return "Berlin"
    if "sydney" in normalized:
        return "Sydney"
    return "Hanoi, VN"


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    without_marks = "".join(character for character in decomposed if unicodedata.category(character) != "Mn")
    return without_marks.replace("đ", "d").strip()
