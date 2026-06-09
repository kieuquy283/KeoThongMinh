from __future__ import annotations

import html
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlparse, urlunparse


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/") or "/"
    query_pairs = sorted((key.lower(), value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key.lower() not in {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"})
    query = "&".join(f"{key}={value}" for key, value in query_pairs)
    return urlunparse((scheme, netloc, path, "", query, ""))


def normalize_title(title: str) -> str:
    text = html.unescape(title or "")
    text = _strip_accents(text)
    text = re.sub(r"\s+", " ", text).strip().casefold()
    return text


def deduplicate_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_urls: dict[str, int] = {}
    seen_titles: dict[str, int] = {}
    for source in sources:
        title_key = normalize_title(str(source.get("title", "")))
        url_key = normalize_url(str(source.get("url", "")))
        if not title_key and not url_key:
            continue
        existing_index = None
        if url_key and url_key in seen_urls:
            existing_index = seen_urls[url_key]
        elif title_key and title_key in seen_titles:
            existing_index = seen_titles[title_key]

        if existing_index is None:
            deduped.append(source)
            index = len(deduped) - 1
            if url_key:
                seen_urls[url_key] = index
            if title_key:
                seen_titles[title_key] = index
            continue

        if _is_better_source(source, deduped[existing_index]):
            deduped[existing_index] = source
    return deduped


def score_source_relevance(query: str, source: dict[str, Any]) -> float:
    query_terms = [term for term in _normalize_terms(query) if len(term) > 1]
    title = normalize_title(str(source.get("title", "")))
    snippet = normalize_title(str(source.get("snippet", "")))
    url = normalize_url(str(source.get("url", "")))
    published_at = source.get("published_at")

    score = 0.0
    for term in query_terms:
        if term in title:
            score += 3.0
        if term in snippet:
            score += 1.25
        if term in url:
            score += 0.75

    if published_at:
        parsed = _parse_datetime(str(published_at))
        if parsed:
            age_days = max((datetime.now(timezone.utc) - parsed).total_seconds() / 86400.0, 0.0)
            freshness = max(0.0, 2.0 - min(age_days / 3.0, 2.0))
            score += freshness

    return score


def sort_sources(query: str, sources: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    ranked = deduplicate_sources(sources)
    for source in ranked:
        source["_score"] = score_source_relevance(query, source)

    def sort_key(item: dict[str, Any]) -> tuple[float, float]:
        score = float(item.get("_score", 0.0))
        published = _parse_datetime(str(item.get("published_at", "")))
        published_timestamp = published.timestamp() if published else 0.0
        return (score, published_timestamp)

    ranked.sort(key=sort_key, reverse=True)
    trimmed = ranked[:limit]
    for item in trimmed:
        item.pop("_score", None)
    return trimmed


def _normalize_terms(value: str) -> list[str]:
    normalized = _strip_accents(value.casefold())
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return [term for term in normalized.split() if term]


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(character for character in decomposed if unicodedata.category(character) != "Mn")


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_better_source(candidate: dict[str, Any], existing: dict[str, Any]) -> bool:
    candidate_published = _parse_datetime(str(candidate.get("published_at", "")))
    existing_published = _parse_datetime(str(existing.get("published_at", "")))

    if candidate_published and not existing_published:
        return True
    if existing_published and not candidate_published:
        return False
    if candidate_published and existing_published and candidate_published > existing_published:
        return True

    candidate_has_snippet = bool(str(candidate.get("snippet", "")).strip())
    existing_has_snippet = bool(str(existing.get("snippet", "")).strip())
    if candidate_has_snippet and not existing_has_snippet:
        return True

    candidate_title = normalize_title(str(candidate.get("title", "")))
    existing_title = normalize_title(str(existing.get("title", "")))
    return len(candidate_title) > len(existing_title)
