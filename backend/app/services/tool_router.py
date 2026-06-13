from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

from app.services.entity_extractor import extract_entities, BROWSER_HINTS, WEBSITE_ALIASES

ToolIntent = Literal["weather", "time", "currency", "news_search", "general_search", "system", "none"]


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
SYSTEM_HINTS = ("tat may", "shutdown", "khoi dong lai", "restart", "ngu", "sleep", "mo app", "mo ung dung", "dong app", "dong ung dung", "truy cap")
SYSTEM_CANCEL_HINTS = ("huy tat may", "huy shutdown", "huy khoi dong lai", "huy restart", "cancel shutdown", "cancel restart", "huy")

TOOL_CONFIDENCE_THRESHOLD = 0.65


def detect_tool_intent(user_text: str, context_turns: list[dict[str, str]] | None = None) -> ToolRoute:
    normalized = _normalize_text(user_text)
    entities = extract_entities(user_text)

    candidates = [
        _score_weather(normalized, entities),
        _score_time(normalized, entities),
        _score_currency(normalized, entities),
        _score_news(normalized, entities),
        _score_search(normalized, entities),
        _score_system(normalized, entities),
    ]
    best_intent, best_confidence = max(candidates, key=lambda item: item[1])

    if best_confidence < TOOL_CONFIDENCE_THRESHOLD and context_turns:
        prev_intent = _detect_prev_tool_intent(context_turns)
        if prev_intent != "none":
            best_intent = prev_intent
            best_confidence = 0.66

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


def _score_system(normalized: str, entities: dict[str, Any]) -> tuple[ToolIntent, float]:
    # Check for cancel commands first
    if entities.get("cancel_command"):
        return "system", 0.95
    if any(hint in normalized for hint in SYSTEM_CANCEL_HINTS):
        return "system", 0.85
    # Browser hints with URL — specific open browser commands
    if any(hint in normalized for hint in BROWSER_HINTS):
        if entities.get("browser_url"):
            return "system", 0.95
        return "system", 0.75
    # Detect "mo {website}" pattern: e.g. "mo youtube", "mo zalo"
    if entities.get("browser_url") and normalized.startswith("mo "):
        return "system", 0.90
    if not any(hint in normalized for hint in SYSTEM_HINTS):
        return "none", 0.0
    if entities.get("system_command"):
        return "system", 0.95
    return "system", 0.75


def _detect_prev_tool_intent(turns: list[dict[str, str]]) -> ToolIntent:
    for t in reversed(turns):
        if t["role"] == "user":
            prev_text = t["text"]
            prev_normalized = _normalize_text(prev_text)
            if any(hint in prev_normalized for hint in WEATHER_HINTS):
                return "weather"
            if any(hint in prev_normalized for hint in TIME_HINTS):
                return "time"
            if any(hint in prev_normalized for hint in CURRENCY_HINTS):
                return "currency"
            if any(hint in prev_normalized for hint in NEWS_HINTS):
                return "news_search"
            if any(hint in prev_normalized for hint in SEARCH_HINTS):
                return "general_search"
            if any(hint in prev_normalized for hint in SYSTEM_HINTS):
                return "system"
    return "none"


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    without_marks = "".join(character for character in decomposed if unicodedata.category(character) != "Mn")
    normalized = without_marks.replace("đ", "d")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()
