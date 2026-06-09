from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

from app.services.entity_extractor import extract_entities

ToolIntent = Literal["weather", "time", "currency", "news_search", "general_search", "none"]


@dataclass(frozen=True)
class ToolRoute:
    intent: ToolIntent
    confidence: float
    entities: dict[str, Any]
    query: str


WEATHER_HINTS = ("thoi tiet", "nhiet do", "mua", "du bao", "weather")
TIME_HINTS = ("may gio", "gio o", "bay gio", "time in")
CURRENCY_HINTS = ("ty gia", "usd", "vnd", "eur", "jpy", "doi tien", "gia tien")
NEWS_HINTS = ("tin moi", "tin tuc", "tin ai", "news")
SEARCH_HINTS = ("tim thong tin moi", "tim thong tin", "cap nhat", "tra cuu", "search")

TOOL_CONFIDENCE_THRESHOLD = 0.65


def detect_tool_intent(user_text: str) -> ToolRoute:
    normalized = _normalize_text(user_text)
    entities = extract_entities(user_text)

    candidates = [
        _score_weather(normalized, entities),
        _score_time(normalized, entities),
        _score_currency(normalized, entities),
        _score_news(normalized, entities),
        _score_search(normalized, entities),
    ]
    best_intent, best_confidence = max(candidates, key=lambda item: item[1])

    if best_confidence < TOOL_CONFIDENCE_THRESHOLD:
        return ToolRoute(intent="none", confidence=best_confidence, entities=entities, query=user_text.strip())

    return ToolRoute(intent=best_intent, confidence=best_confidence, entities=entities, query=user_text.strip())


def _score_weather(normalized: str, entities: dict[str, Any]) -> tuple[ToolIntent, float]:
    if not any(hint in normalized for hint in WEATHER_HINTS):
        return "none", 0.0
    if entities.get("location"):
        return "weather", 0.95
    return "weather", 0.65


def _score_time(normalized: str, entities: dict[str, Any]) -> tuple[ToolIntent, float]:
    if not any(hint in normalized for hint in TIME_HINTS):
        return "none", 0.0
    if entities.get("timezone"):
        return "time", 0.96
    if entities.get("location"):
        return "time", 0.78
    return "time", 0.55


def _score_currency(normalized: str, entities: dict[str, Any]) -> tuple[ToolIntent, float]:
    has_hint = any(hint in normalized for hint in CURRENCY_HINTS) or entities.get("base_currency") is not None
    if not has_hint:
        return "none", 0.0

    if entities.get("amount") is not None and entities.get("base_currency") and entities.get("target_currency"):
        return "currency", 0.97
    if entities.get("base_currency") and entities.get("target_currency"):
        return "currency", 0.92
    if entities.get("base_currency"):
        return "currency", 0.82
    return "currency", 0.7


def _score_news(normalized: str, entities: dict[str, Any]) -> tuple[ToolIntent, float]:
    if not any(hint in normalized for hint in NEWS_HINTS):
        return "none", 0.0
    if "thong tin" in normalized or "tim thong tin" in normalized:
        return "none", 0.0
    if entities.get("news_topic"):
        return "news_search", 0.93
    return "news_search", 0.7


def _score_search(normalized: str, entities: dict[str, Any]) -> tuple[ToolIntent, float]:
    if not any(hint in normalized for hint in SEARCH_HINTS):
        return "none", 0.0
    if entities.get("search_query"):
        return "general_search", 0.9
    return "general_search", 0.68


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    without_marks = "".join(character for character in decomposed if unicodedata.category(character) != "Mn")
    normalized = without_marks.replace("đ", "d")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()
