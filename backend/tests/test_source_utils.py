from __future__ import annotations

from app.tools.source_utils import deduplicate_sources, normalize_title, normalize_url, score_source_relevance, sort_sources


def test_normalize_url_removes_tracking_and_www():
    assert normalize_url("https://www.example.com/news/?utm_source=x&b=2&a=1") == "https://example.com/news?a=1&b=2"


def test_normalize_title_strips_accents_and_case():
    assert normalize_title("  Báo  Cáo  AI  ") == "bao cao ai"


def test_deduplicate_sources_removes_duplicate_url_or_title():
    sources = [
        {"title": "OpenAI launches model", "url": "https://example.com/a", "snippet": ""},
        {"title": "OpenAI launches model", "url": "https://example.com/b", "snippet": "duplicate by title"},
        {"title": "Different title", "url": "https://example.com/a?utm_source=news", "snippet": "duplicate by url"},
        {"title": "Unique title", "url": "https://example.com/c", "snippet": "keep"},
    ]

    deduped = deduplicate_sources(sources)

    assert len(deduped) == 2
    assert deduped[0]["title"] == "OpenAI launches model"
    assert deduped[1]["title"] == "Unique title"


def test_deduplicate_sources_prefers_published_item():
    sources = [
        {"title": "Same title", "url": "https://example.com/a", "snippet": "", "published_at": ""},
        {"title": "Same title", "url": "https://example.com/a?utm_source=news", "snippet": "has date", "published_at": "2026-06-09T10:00:00Z"},
    ]

    deduped = deduplicate_sources(sources)

    assert len(deduped) == 1
    assert deduped[0]["snippet"] == "has date"


def test_score_source_relevance_prefers_query_terms_and_freshness():
    query = "OpenAI Gemini"
    recent = {"title": "OpenAI launches new Gemini model", "url": "https://example.com/recent", "published_at": "2026-06-09T10:00:00Z"}
    old = {"title": "OpenAI launches new Gemini model", "url": "https://example.com/old", "published_at": "2025-06-09T10:00:00Z"}

    assert score_source_relevance(query, recent) > score_source_relevance(query, old)


def test_sort_sources_dedupes_and_limits_top_items():
    sources = [
        {"title": "OpenAI news", "url": "https://example.com/a", "published_at": "2026-06-09T10:00:00Z", "snippet": "OpenAI"},
        {"title": "OpenAI news", "url": "https://example.com/a?utm_source=x", "published_at": "2026-06-09T09:00:00Z", "snippet": "duplicate"},
        {"title": "Gemini update", "url": "https://example.com/b", "published_at": "2026-06-09T11:00:00Z", "snippet": "Gemini"},
        {"title": "AI policy", "url": "https://example.com/c", "published_at": "2026-06-08T09:00:00Z", "snippet": "policy"},
        {"title": "Other story", "url": "https://example.com/d", "published_at": "2026-06-07T09:00:00Z", "snippet": "other"},
        {"title": "Extra story", "url": "https://example.com/e", "published_at": "2026-06-06T09:00:00Z", "snippet": "extra"},
    ]

    ranked = sort_sources("OpenAI Gemini", sources, limit=3)

    assert len(ranked) == 3
    assert ranked[0]["title"] == "Gemini update"
    assert ranked[1]["title"] == "OpenAI news"
    assert ranked[2]["title"] == "AI policy"
