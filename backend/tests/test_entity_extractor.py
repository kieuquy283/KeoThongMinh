from __future__ import annotations

import pytest

from app.services.entity_extractor import extract_entities


@pytest.mark.parametrize(
    ("query", "location"),
    [
        ("Thời tiết Hà Nội hôm nay thế nào?", "Hà Nội"),
        ("Thoi tiet o Tokyo", "Tokyo"),
        ("Thời tiết Đà Nẵng hôm nay", "Đà Nẵng"),
        ("Thời tiết Hai Phong", "Hải Phòng"),
        ("Thời tiết Can Tho", "Cần Thơ"),
        ("Thời tiết ở Singapore", "Singapore"),
        ("Thời tiết Bangkok", "Bangkok"),
        ("Thời tiết Paris", "Paris"),
        ("Thời tiết Berlin", "Berlin"),
        ("Thời tiết Sydney", "Sydney"),
        ("Thời tiết Los Angeles", "Los Angeles"),
        ("Thời tiết San Francisco", "San Francisco"),
    ],
)
def test_extract_weather_locations(query: str, location: str):
    entities = extract_entities(query)

    assert entities["location"] == location


@pytest.mark.parametrize(
    ("query", "timezone"),
    [
        ("Bây giờ là mấy giờ ở Nhật?", "Asia/Tokyo"),
        ("Bây gio la may gio o Singapore?", "Asia/Singapore"),
        ("Mấy giờ ở Bangkok?", "Asia/Bangkok"),
        ("Bây giờ là mấy giờ ở Paris?", "Europe/Paris"),
        ("Mấy giờ ở Berlin?", "Europe/Berlin"),
        ("Mấy giờ ở Sydney?", "Australia/Sydney"),
        ("Mấy giờ ở Los Angeles?", "America/Los_Angeles"),
        ("Mấy giờ ở San Francisco?", "America/Los_Angeles"),
    ],
)
def test_extract_time_timezones(query: str, timezone: str):
    entities = extract_entities(query)

    assert entities["timezone"] == timezone


@pytest.mark.parametrize(
    ("query", "amount", "base", "target"),
    [
        ("100 USD sang VND hôm nay?", 100.0, "USD", "VND"),
        ("Tỷ giá EUR sang VND", None, "EUR", "VND"),
        ("100 KRW sang VND", 100.0, "KRW", "VND"),
        ("2500 CNY sang VND", 2500.0, "CNY", "VND"),
        ("100 GBP sang VND", 100.0, "GBP", "VND"),
        ("100 AUD sang VND", 100.0, "AUD", "VND"),
        ("100 CAD sang VND", 100.0, "CAD", "VND"),
        ("100 SGD sang VND", 100.0, "SGD", "VND"),
        ("100 THB sang VND", 100.0, "THB", "VND"),
    ],
)
def test_extract_currency_pairs(query: str, amount: float | None, base: str, target: str):
    entities = extract_entities(query)

    assert entities["amount"] == amount
    assert entities["base_currency"] == base
    assert entities["target_currency"] == target


@pytest.mark.parametrize(
    ("query", "topic"),
    [
        ("Tin AI mới nhất", "AI"),
        ("Tin OpenAI mới nhất", "OpenAI"),
        ("Tin Gemini mới nhất", "Gemini"),
        ("Tin ChatGPT mới nhất", "ChatGPT"),
        ("Tin kinh tế mới nhất", "Kinh tế"),
        ("Tin giáo dục mới nhất", "Giáo dục"),
        ("Tin công nghệ mới nhất", "Công nghệ"),
        ("Tin bóng đá mới nhất", "Bóng đá"),
        ("Tin pháp luật mới nhất", "Pháp luật"),
    ],
)
def test_extract_news_topics(query: str, topic: str):
    entities = extract_entities(query)

    assert entities["news_topic"] == topic


def test_extract_search_query():
    entities = extract_entities("Tìm thông tin mới về OpenAI")

    assert entities["search_query"] == "OpenAI"
