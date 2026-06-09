from __future__ import annotations

from app.services.tool_router import detect_tool_intent


def test_detect_weather_intent():
    route = detect_tool_intent("Thời tiết Hà Nội hôm nay thế nào?")

    assert route.intent == "weather"
    assert route.confidence >= 0.9
    assert route.entities["location"] == "Hà Nội"


def test_detect_time_intent():
    route = detect_tool_intent("Bây giờ là mấy giờ ở Nhật?")

    assert route.intent == "time"
    assert route.confidence >= 0.9
    assert route.entities["timezone"] == "Asia/Tokyo"


def test_detect_currency_intent():
    route = detect_tool_intent("100 USD sang VND hôm nay?")

    assert route.intent == "currency"
    assert route.confidence >= 0.9
    assert route.entities["amount"] == 100.0


def test_detect_news_search_intent():
    route = detect_tool_intent("Tin AI mới nhất có gì?")

    assert route.intent == "news_search"
    assert route.confidence >= 0.9
    assert route.entities["news_topic"] == "AI"


def test_detect_general_search_intent():
    route = detect_tool_intent("Tìm thông tin mới về OpenAI")

    assert route.intent == "general_search"
    assert route.confidence >= 0.85
    assert route.entities["search_query"] == "OpenAI"


def test_detect_none_intent():
    route = detect_tool_intent("Hôm nay mình hơi mệt")

    assert route.intent == "none"
    assert route.confidence < 0.65


def test_weather_without_keyword_does_not_route():
    route = detect_tool_intent("Hôm nay ở Hà Nội khá đẹp")

    assert route.intent == "none"


def test_time_without_timezone_or_city_does_not_route():
    route = detect_tool_intent("Mấy giờ ăn trưa?")

    assert route.intent == "none"
