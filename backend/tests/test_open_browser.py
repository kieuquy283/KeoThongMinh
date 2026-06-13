"""Tests for open_browser / web navigation feature."""
from __future__ import annotations

import pytest

from app.services.entity_extractor import (
    extract_entities,
    BROWSER_HINTS,
    WEBSITE_ALIASES,
    SYSTEM_COMMAND_ALIASES,
    URL_PATTERN,
)
from app.services.tool_router import detect_tool_intent, _score_system


# ---------------------------------------------------------------------------
# WEBSITE_ALIASES coverage
# ---------------------------------------------------------------------------
class TestWebsiteAliases:
    @pytest.mark.parametrize(
        "alias,expected_url",
        list(WEBSITE_ALIASES.items()),
    )
    def test_alias_maps_to_url(self, alias, expected_url):
        entities = extract_entities(f"Mở {alias} cho mình")
        assert entities["browser_url"] == expected_url, f"Failed for alias: {alias}"

    def test_google_alias(self):
        entities = extract_entities("Mở google")
        assert entities["browser_url"] == "https://www.google.com"

    def test_youtube_alias(self):
        entities = extract_entities("Mở youtube")
        assert entities["browser_url"] == "https://www.youtube.com"

    def test_zalo_alias(self):
        entities = extract_entities("Mở zalo")
        assert entities["browser_url"] == "https://chat.zalo.me"

    def test_facebook_alias(self):
        entities = extract_entities("Mở facebook")
        assert entities["browser_url"] == "https://www.facebook.com"

    def test_vnexpress_alias(self):
        entities = extract_entities("Mở VnExpress")
        assert entities["browser_url"] == "https://vnexpress.net"


# ---------------------------------------------------------------------------
# SYSTEM_COMMAND_ALIASES for browser
# ---------------------------------------------------------------------------
class TestBrowserSystemAliases:
    @pytest.mark.parametrize(
        "phrase,expected",
        [
            ("mo trinh duyet", "open_browser"),
            ("mo chrome", "open_browser"),
            ("mo edge", "open_browser"),
            ("mo firefox", "open_browser"),
            ("mo coccoc", "open_browser"),
            ("mo coc coc", "open_browser"),
            ("mo browser", "open_browser"),
            ("mo web", "open_browser"),
            ("mo trang web", "open_browser"),
            ("mo link", "open_browser"),
        ],
    )
    def test_browser_alias_in_system_commands(self, phrase, expected):
        assert SYSTEM_COMMAND_ALIASES[phrase] == expected


# ---------------------------------------------------------------------------
# Browser hints
# ---------------------------------------------------------------------------
class TestBrowserHints:
    def test_no_truy_cap_in_hints(self):
        """'truy cap' should NOT be in BROWSER_HINTS to avoid search conflicts."""
        assert "truy cap" not in BROWSER_HINTS

    def test_no_vao_mang_in_hints(self):
        """'vao mang' should NOT be in BROWSER_HINTS (too broad)."""
        assert "vao mang" not in BROWSER_HINTS

    def test_mo_chrome_is_hint(self):
        assert "mo chrome" in BROWSER_HINTS


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------
class TestOpenBrowserIntent:
    def test_mo_google(self):
        route = detect_tool_intent("Mở google")
        assert route.intent == "system"
        assert route.confidence >= 0.90

    def test_mo_youtube(self):
        route = detect_tool_intent("Mở youtube")
        assert route.intent == "system"
        assert route.confidence >= 0.90

    def test_mo_trinh_duyet(self):
        route = detect_tool_intent("Mở trình duyệt")
        assert route.intent == "system"

    def test_mo_chrome(self):
        route = detect_tool_intent("Mở chrome")
        assert route.intent == "system"

    def test_open_browser_with_alias(self):
        route = detect_tool_intent("Mo chrome")  # normalized
        assert route.intent == "system"
        assert route.entities.get("system_command") == "open_browser"

    def test_mo_zalo(self):
        route = detect_tool_intent("Mở zalo")
        assert route.intent == "system"

    def test_truy_cap_youtube_no_false_positive(self):
        """'truy cập youtube' should still detect as system (has browser_url)."""
        route = detect_tool_intent("Truy cập youtube")
        # browser_url should be extracted
        entities = extract_entities("Truy cập youtube")
        assert entities["browser_url"] == "https://www.youtube.com"

    def test_search_not_confused_as_browser(self):
        """Search queries should NOT be detected as browser intent."""
        route = detect_tool_intent("Tìm thông tin về youtube")
        assert route.intent != "system"

    def test_weather_not_confused_as_browser(self):
        route = detect_tool_intent("Thời tiết Hà Nội")
        assert route.intent != "system"

    def test_time_not_confused_as_browser(self):
        route = detect_tool_intent("Bây giờ là mấy giờ")
        assert route.intent != "system"


# ---------------------------------------------------------------------------
# Entity extraction: browser_url
# ---------------------------------------------------------------------------
class TestBrowserUrlExtraction:
    def test_google_url(self):
        entities = extract_entities("Mở google")
        assert entities["browser_url"] == "https://www.google.com"

    def test_explicit_url(self):
        """URLs like 'google.com' should be extracted."""
        entities = extract_entities("Mở google.com")
        assert entities["browser_url"] is not None
        assert "google.com" in entities["browser_url"]

    def test_no_browser_url_for_normal_text(self):
        entities = extract_entities("Xin chào bạn")
        assert entities["browser_url"] is None

    def test_no_browser_url_for_weather(self):
        entities = extract_entities("Thời tiết Hà Nội hôm nay")
        assert entities["browser_url"] is None


# ---------------------------------------------------------------------------
# _score_system for browser
# ---------------------------------------------------------------------------
class TestScoreSystemBrowser:
    def test_browser_hint_with_url_high_confidence(self):
        entities = extract_entities("Mở google")
        intent, confidence = _score_system("mo google", entities)
        assert intent == "system"
        # "mo google" matches via "mo {website}" pattern (0.90), not explicit BROWSER_HINTS (0.95)
        assert confidence >= 0.90

    def test_mo_website_pattern(self):
        """'mo youtube' should be detected even without explicit browser hint."""
        entities = extract_entities("Mở youtube")
        # browser_url is set from WEBSITE_ALIASES
        assert entities["browser_url"] is not None
        intent, confidence = _score_system("mo youtube", entities)
        assert intent == "system"
        assert confidence >= 0.90

    def test_browser_hint_without_url(self):
        """'mo trinh duyet' without specific URL — still system, lower confidence."""
        entities = extract_entities("Mở trình duyệt")
        intent, confidence = _score_system("mo trinh duyet", entities)
        assert intent == "system"
        # No browser_url, but hint matches
        assert confidence == 0.75
