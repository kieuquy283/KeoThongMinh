from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from app.config import get_settings


@dataclass(frozen=True)
class CurrencyPair:
    base: str
    target: str


DEMO_RATES: dict[tuple[str, str], float] = {
    ("USD", "VND"): 25_400.0,
    ("EUR", "VND"): 27_600.0,
    ("JPY", "VND"): 176.0,
}

SUPPORTED_CURRENCIES = {"USD", "EUR", "JPY", "VND", "KRW", "CNY", "GBP", "AUD", "CAD", "SGD", "THB"}


def get_currency_info(query: str, entities: dict[str, Any] | None = None, now: datetime | None = None) -> dict[str, Any]:
    entities = entities or {}
    pair = resolve_currency_pair(query, entities=entities)
    amount = _resolve_amount(entities)
    current_time = now or datetime.now(timezone.utc)
    settings = get_settings()

    provider = _resolve_provider_label(settings)
    live_requested = settings.currency_provider.lower() == "exchangerate_api"

    if not live_requested:
        return _build_demo_payload(pair, amount, current_time, provider=provider)

    if not settings.exchange_rate_api_url or not settings.exchange_rate_api_key:
        return _build_unavailable_payload(
            pair=pair,
            amount=amount,
            current_time=current_time,
            provider=provider,
            status="not_configured",
            message="Currency live provider not configured.",
        )

    try:
        rate, source_updated_at = _fetch_live_rate(pair, settings.exchange_rate_api_url, settings.exchange_rate_api_key)
    except HTTPError as exc:
        if exc.code in {401, 403}:
            return _build_unavailable_payload(
                pair=pair,
                amount=amount,
                current_time=current_time,
                provider=provider,
                status="invalid_key",
                message="Currency provider key is invalid.",
            )
        if exc.code == 429:
            return _build_unavailable_payload(
                pair=pair,
                amount=amount,
                current_time=current_time,
                provider=provider,
                status="rate_limited",
                message="Currency provider rate limited the request.",
            )
        return _build_unavailable_payload(
            pair=pair,
            amount=amount,
            current_time=current_time,
            provider=provider,
            status="unknown_error",
            message="Currency provider returned an unexpected error.",
        )
    except URLError:
        return _build_unavailable_payload(
            pair=pair,
            amount=amount,
            current_time=current_time,
            provider=provider,
            status="network_error",
            message="Currency provider network error.",
        )
    except Exception:
        return _build_unavailable_payload(
            pair=pair,
            amount=amount,
            current_time=current_time,
            provider=provider,
            status="unknown_error",
            message="Currency provider returned an unexpected error.",
        )

    converted_amount = amount * rate if amount is not None else None
    return {
        "provider": provider,
        "configured": True,
        "live": True,
        "status": "ok",
        "message": "Live exchange rate.",
        "amount": amount,
        "base_currency": pair.base,
        "target_currency": pair.target,
        "rate": rate,
        "converted_amount": converted_amount,
        "is_live": True,
        "note": "Live exchange rate.",
        "updated_at": source_updated_at or current_time.isoformat(),
        "last_checked_at": current_time.isoformat(),
    }


def resolve_currency_pair(query: str, entities: dict[str, Any] | None = None) -> CurrencyPair:
    entities = entities or {}
    base = _normalize_currency_code(entities.get("base_currency"))
    target = _normalize_currency_code(entities.get("target_currency"))

    normalized = _normalize_text(query)
    if base is None:
        base = _guess_currency_from_text(normalized)
    if target is None:
        target = _guess_target_currency(normalized, base)

    if base in {"USD", "EUR", "JPY", "KRW", "CNY", "GBP", "AUD", "CAD", "SGD", "THB"} and target is None:
        target = "VND"

    if base is None:
        base = _guess_currency_from_text(normalized) or "USD"
    if target is None:
        target = "VND"

    return CurrencyPair(base=base, target=target)


def _resolve_amount(entities: dict[str, Any]) -> float | None:
    amount = entities.get("amount")
    if isinstance(amount, (int, float)):
        return float(amount)
    return None


def _fetch_live_rate(pair: CurrencyPair, api_url: str, api_key: str | None) -> tuple[float, str | None]:
    params = {
        "base": pair.base,
        "symbols": pair.target,
    }
    if api_key:
        params["apikey"] = api_key

    request_url = f"{api_url}?{urlencode(params)}"
    with urlopen(request_url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if isinstance(payload.get("rates"), dict) and pair.target in payload["rates"]:
        return float(payload["rates"][pair.target]), str(payload.get("date") or "")

    if isinstance(payload.get("conversion_rates"), dict) and pair.target in payload["conversion_rates"]:
        return float(payload["conversion_rates"][pair.target]), str(payload.get("time_last_update_utc") or "")

    raise RuntimeError("Currency provider returned an unsupported payload.")


def _resolve_provider_label(settings: Any) -> str:
    if settings.currency_provider.lower() == "exchangerate_api":
        return "exchangerate_api"
    return "demo"


def _build_demo_payload(pair: CurrencyPair, amount: float | None, current_time: datetime, provider: str) -> dict[str, Any]:
    rate = DEMO_RATES.get((pair.base, pair.target))
    if rate is None:
        rate = 1.0 if pair.base == pair.target else 0.0
    converted_amount = amount * rate if amount is not None else None
    return {
        "provider": provider,
        "configured": True,
        "live": False,
        "status": "ok",
        "message": "Demo rate, not live.",
        "amount": amount,
        "base_currency": pair.base,
        "target_currency": pair.target,
        "rate": rate,
        "converted_amount": converted_amount,
        "is_live": False,
        "note": "Demo rate, not live.",
        "updated_at": current_time.isoformat(),
        "last_checked_at": current_time.isoformat(),
    }


def _build_unavailable_payload(
    *,
    pair: CurrencyPair,
    amount: float | None,
    current_time: datetime,
    provider: str,
    status: str,
    message: str,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "configured": False,
        "live": False,
        "status": status,
        "message": message,
        "amount": amount,
        "base_currency": pair.base,
        "target_currency": pair.target,
        "rate": None,
        "converted_amount": None,
        "is_live": False,
        "note": message,
        "updated_at": current_time.isoformat(),
        "last_checked_at": current_time.isoformat(),
    }


def _guess_currency_from_text(normalized: str) -> str | None:
    for code in ("usd", "eur", "jpy", "vnd", "krw", "cny", "gbp", "aud", "cad", "sgd", "thb"):
        if re_search_word(code, normalized):
            return _normalize_currency_code(code)
    return None


def _guess_target_currency(normalized: str, base: str | None) -> str | None:
    if "sang vnd" in normalized or "to vnd" in normalized:
        return "VND"
    for code in ("vnd", "usd", "eur", "jpy", "krw", "cny", "gbp", "aud", "cad", "sgd", "thb"):
        normalized_code = _normalize_currency_code(code)
        if re_search_word(code, normalized) and normalized_code != base:
            return normalized_code
    return None


def _normalize_currency_code(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    code = value.strip().upper()
    if code == "YEN":
        return "JPY"
    if code in SUPPORTED_CURRENCIES:
        return code
    return None


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    without_marks = "".join(character for character in decomposed if unicodedata.category(character) != "Mn")
    normalized = without_marks.replace("Ä‘", "d")
    normalized = unicodedata.normalize("NFKC", normalized)
    return " ".join(normalized.split())


def re_search_word(word: str, text: str) -> bool:
    return bool(re.search(rf"\b{re.escape(word)}\b", text))
