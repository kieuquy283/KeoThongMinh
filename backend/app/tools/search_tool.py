from __future__ import annotations

import json
import unicodedata
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from app.config import get_settings
from app.tools.source_utils import sort_sources

MAX_SOURCES = 5


def get_search_info(query: str, intent: str, entities: dict[str, Any] | None = None, now: datetime | None = None) -> dict[str, Any]:
    entities = entities or {}
    current_time = now or datetime.now(timezone.utc)
    settings = get_settings()
    search_query = _resolve_search_query(query, intent, entities)
    provider = settings.search_provider.lower()

    if provider == "tavily" and settings.tavily_api_key:
        try:
            sources = _fetch_tavily(search_query, intent, settings.tavily_api_key)
        except HTTPError as exc:
            return _diagnostic_result(
                provider=provider,
                configured=True,
                live=False,
                status=_classify_http_error(exc)[0],
                message=_classify_http_error(exc)[1],
                current_time=current_time,
                query=search_query,
                intent=intent,
            )
        except URLError:
            return _diagnostic_result(
                provider=provider,
                configured=True,
                live=False,
                status="network_error",
                message="Search provider network error",
                current_time=current_time,
                query=search_query,
                intent=intent,
            )
        except Exception:
            return _diagnostic_result(
                provider=provider,
                configured=True,
                live=False,
                status="unknown_error",
                message="Search provider unknown error",
                current_time=current_time,
                query=search_query,
                intent=intent,
            )

        return {
            "query": search_query,
            "intent": intent,
            "sources": sources,
            "results": sources,
            "available": True,
            "reason": None,
            "provider": provider,
            "configured": True,
            "live": True,
            "status": "ok",
            "message": "Live search results",
            "last_checked_at": current_time.isoformat(),
            "updated_at": current_time.isoformat(),
        }

    if provider == "serpapi" and settings.serpapi_api_key:
        try:
            sources = _fetch_serpapi(search_query, intent, settings.serpapi_api_key)
        except HTTPError as exc:
            return _diagnostic_result(
                provider=provider,
                configured=True,
                live=False,
                status=_classify_http_error(exc)[0],
                message=_classify_http_error(exc)[1],
                current_time=current_time,
                query=search_query,
                intent=intent,
            )
        except URLError:
            return _diagnostic_result(
                provider=provider,
                configured=True,
                live=False,
                status="network_error",
                message="Search provider network error",
                current_time=current_time,
                query=search_query,
                intent=intent,
            )
        except Exception:
            return _diagnostic_result(
                provider=provider,
                configured=True,
                live=False,
                status="unknown_error",
                message="Search provider unknown error",
                current_time=current_time,
                query=search_query,
                intent=intent,
            )

        return {
            "query": search_query,
            "intent": intent,
            "sources": sources,
            "results": sources,
            "available": True,
            "reason": None,
            "provider": provider,
            "configured": True,
            "live": True,
            "status": "ok",
            "message": "Live search results",
            "last_checked_at": current_time.isoformat(),
            "updated_at": current_time.isoformat(),
        }

    return _diagnostic_result(
        provider=provider or "none",
        configured=False,
        live=False,
        status="not_configured",
        message="Search provider not configured",
        current_time=current_time,
        query=search_query,
        intent=intent,
    )


def _fetch_tavily(query: str, intent: str, api_key: str) -> list[dict[str, Any]]:
    topic = "news" if intent == "news_search" else "general"
    params = urlencode(
        {
            "api_key": api_key,
            "query": query,
            "topic": topic,
            "max_results": MAX_SOURCES,
        }
    )
    request_url = f"https://api.tavily.com/search?{params}"
    with urlopen(request_url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    raw_sources = [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "published_at": item.get("published_date"),
            "source": "tavily",
            "snippet": item.get("content", ""),
        }
        for item in payload.get("results", [])
    ]
    return sort_sources(query, raw_sources, limit=MAX_SOURCES)


def _fetch_serpapi(query: str, intent: str, api_key: str) -> list[dict[str, Any]]:
    engine = "google_news" if intent == "news_search" else "google"
    params = urlencode(
        {
            "api_key": api_key,
            "q": query,
            "engine": engine,
        }
    )
    request_url = f"https://serpapi.com/search.json?{params}"
    with urlopen(request_url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    raw_items = payload.get("news_results") if intent == "news_search" else payload.get("organic_results")
    raw_sources = [
        {
            "title": item.get("title", ""),
            "url": item.get("link", ""),
            "published_at": item.get("date"),
            "source": "serpapi",
            "snippet": item.get("snippet", ""),
        }
        for item in (raw_items or [])
    ]
    return sort_sources(query, raw_sources, limit=MAX_SOURCES)


def _diagnostic_result(
    *,
    provider: str,
    configured: bool,
    live: bool,
    status: str,
    message: str,
    current_time: datetime,
    query: str,
    intent: str,
) -> dict[str, Any]:
    return {
        "query": query,
        "intent": intent,
        "sources": [],
        "results": [],
        "available": False,
        "reason": message,
        "provider": provider,
        "configured": configured,
        "live": live,
        "status": status,
        "message": message,
        "last_checked_at": current_time.isoformat(),
        "updated_at": current_time.isoformat(),
    }


def _classify_http_error(exc: HTTPError) -> tuple[str, str]:
    if exc.code in {401, 403}:
        return "invalid_key", "Search provider invalid key"
    if exc.code == 429:
        return "rate_limited", "Search provider rate limited"
    return "unknown_error", f"Search provider HTTP {exc.code}"


def _resolve_search_query(query: str, intent: str, entities: dict[str, Any]) -> str:
    if intent == "news_search" and isinstance(entities.get("news_topic"), str) and entities["news_topic"].strip():
        return entities["news_topic"].strip()
    if isinstance(entities.get("search_query"), str) and entities["search_query"].strip():
        return entities["search_query"].strip()
    return query.strip()


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    without_marks = "".join(character for character in decomposed if unicodedata.category(character) != "Mn")
    return without_marks.replace("đ", "d").strip()
