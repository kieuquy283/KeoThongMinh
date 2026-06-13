from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EntityExtraction:
    location: str | None = None
    timezone: str | None = None
    amount: float | None = None
    base_currency: str | None = None
    target_currency: str | None = None
    search_query: str | None = None
    news_topic: str | None = None


LOCATION_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Hà Nội", ("ha noi", "hanoi")),
    ("Đà Nẵng", ("da nang", "danang")),
    ("Hải Phòng", ("hai phong", "haiphong")),
    ("Cần Thơ", ("can tho", "cantho")),
    ("Ho Chi Minh City", ("ho chi minh city", "ho chi minh", "hcmc", "saigon", "sai gon")),
    ("Tokyo", ("tokyo",)),
    ("Singapore", ("singapore",)),
    ("Bangkok", ("bangkok",)),
    ("Paris", ("paris",)),
    ("Berlin", ("berlin",)),
    ("Sydney", ("sydney",)),
    ("Los Angeles", ("los angeles", "la")),
    ("San Francisco", ("san francisco", "sf")),
    ("New York", ("new york",)),
    ("London", ("london",)),
    ("Vietnam", ("vietnam", "viet nam", "vn")),
    ("Japan", ("japan", "nhat", "nhat ban")),
    ("Korea", ("korea", "han", "han quoc")),
    ("United Kingdom", ("uk", "united kingdom", "anh")),
    ("United States", ("united states", "my", "usa", "u s a")),
    ("UTC", ("utc", "gmt")),
)

TIMEZONE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Asia/Ho_Chi_Minh", ("hanoi", "ha noi", "ho chi minh", "ho chi minh city", "vietnam", "viet nam", "vn")),
    ("Asia/Tokyo", ("tokyo", "japan", "nhat", "nhat ban")),
    ("Asia/Seoul", ("seoul", "korea", "han", "han quoc")),
    ("Asia/Singapore", ("singapore",)),
    ("Asia/Bangkok", ("bangkok", "thailand", "thai lan")),
    ("Europe/Paris", ("paris", "france", "phap")),
    ("Europe/Berlin", ("berlin", "germany", "duc")),
    ("Australia/Sydney", ("sydney", "australia", "uc")),
    ("America/Los_Angeles", ("los angeles", "san francisco", "california")),
    ("America/New_York", ("new york", "united states", "my", "usa", "u s a")),
    ("Europe/London", ("london", "united kingdom", "uk", "anh")),
    ("UTC", ("utc", "gmt")),
)

CURRENCY_ALIASES: dict[str, str] = {
    "usd": "USD",
    "dollar": "USD",
    "do la my": "USD",
    "vnd": "VND",
    "dong": "VND",
    "dong viet": "VND",
    "eur": "EUR",
    "euro": "EUR",
    "jpy": "JPY",
    "yen": "JPY",
    "krw": "KRW",
    "won": "KRW",
    "won han": "KRW",
    "cny": "CNY",
    "yuan": "CNY",
    "nhan dan te": "CNY",
    "gbp": "GBP",
    "pound": "GBP",
    "bang anh": "GBP",
    "aud": "AUD",
    "australian dollar": "AUD",
    "do la uc": "AUD",
    "cad": "CAD",
    "canadian dollar": "CAD",
    "do la canada": "CAD",
    "sgd": "SGD",
    "singapore dollar": "SGD",
    "do la singapore": "SGD",
    "thb": "THB",
    "baht": "THB",
    "baht thai": "THB",
}

SEARCH_HINTS = (
    "tim thong tin moi ve",
    "tim thong tin ve",
    "tim thong tin",
    "cap nhat",
    "search",
    "tra cuu",
)
NEWS_HINTS = (
    "tin moi",
    "tin tuc",
    "tin ai",
    "news",
    "cap nhat",
)

TOPIC_ALIASES: dict[str, str] = {
    "ai": "AI",
    "openai": "OpenAI",
    "gemini": "Gemini",
    "chatgpt": "ChatGPT",
    "kinh te": "Kinh tế",
    "giao duc": "Giáo dục",
    "cong nghe": "Công nghệ",
    "bong da": "Bóng đá",
    "phap luat": "Pháp luật",
}


SYSTEM_COMMAND_ALIASES: dict[str, str] = {
    "tat may": "shutdown",
    "shutdown": "shutdown",
    "khoi dong lai": "restart",
    "restart": "restart",
    "ngu": "sleep",
    "sleep": "sleep",
    "mo app": "open_app",
    "mo ung dung": "open_app",
    "open app": "open_app",
    "dong app": "close_app",
    "dong ung dung": "close_app",
    "close app": "close_app",
    "mo trinh duyet": "open_browser",
    "mo trinh duyêt": "open_browser",
    "mo chrome": "open_browser",
    "mo edge": "open_browser",
    "mo firefox": "open_browser",
    "mo coccoc": "open_browser",
    "mo coc coc": "open_browser",
    "mo browser": "open_browser",
    "mo web": "open_browser",
    "mo trang web": "open_browser",
    "mo link": "open_browser",
}

# Website/browser hints for intent detection
# Only include specific browser open commands — avoid ambiguous phrases like "truy cap" (search) or "vao mang" (go online)
BROWSER_HINTS = (
    "mo trinh duyet", "mo trinh duyêt", "mo chrome", "mo edge",
    "mo firefox", "mo coccoc", "mo coc coc", "mo browser",
    "mo web", "mo trang web", "mo link",
)

# URL pattern — matches http(s)://, www., and common Vietnamese "open X" phrases
URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z]{2,})+(?:/[^\s]*)?)"
)

# Website shortcut aliases — maps Vietnamese phrases to full URLs
WEBSITE_ALIASES: dict[str, str] = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "facebook": "https://www.facebook.com",
    "fb": "https://www.facebook.com",
    "zalo": "https://chat.zalo.me",
    "tiktok": "https://www.tiktok.com",
    "shopee": "https://shopee.vn",
    "ladida": "https://lazada.vn",
    "tiki": "https://tiki.vn",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "mail": "https://mail.google.com",
    "vietnamnet": "https://vietnamnet.vn",
    "vnexpress": "https://vnexpress.net",
    "dan tri": "https://dantri.com.vn",
    "baomoi": "https://baomoi.com",
    "chatgpt": "https://chat.openai.com",
}

# Cancel system command patterns
SYSTEM_COMMAND_CANCEL_PATTERNS: list[tuple[str, str]] = [
    ("huy tat may", "shutdown"),
    ("huy shutdown", "shutdown"),
    ("huy khoi dong lai", "restart"),
    ("huy restart", "restart"),
    ("cancel shutdown", "shutdown"),
    ("cancel restart", "restart"),
]


def extract_entities(user_text: str) -> dict[str, str | float | None]:
    normalized = _normalize_text(user_text)
    entities: dict[str, str | float | None] = {
        "location": None,
        "timezone": None,
        "amount": None,
        "base_currency": None,
        "target_currency": None,
        "search_query": None,
        "news_topic": None,
        "system_command": None,
        "delay_seconds": None,
        "app_name": None,
        "browser_url": None,
        "cancel_command": None,
    }

    # Check for cancel commands FIRST
    cancel_cmd = _detect_cancel_command(normalized)
    if cancel_cmd:
        entities["cancel_command"] = cancel_cmd
        return entities

    entities["location"] = _extract_location(normalized)
    entities["timezone"] = _extract_timezone(normalized)
    amount, base_currency, target_currency = _extract_currency(normalized)
    entities["amount"] = amount
    entities["base_currency"] = base_currency
    entities["target_currency"] = target_currency
    entities["search_query"] = _extract_search_query(normalized)
    entities["news_topic"] = _extract_news_topic(normalized)
    system_cmd, delay, app_name = _extract_system_command(normalized)
    entities["system_command"] = system_cmd
    entities["delay_seconds"] = delay
    entities["app_name"] = app_name
    entities["browser_url"] = _extract_browser_url(normalized, user_text)
    return entities


def _detect_cancel_command(normalized: str) -> str | None:
    """Detect cancel system command phrases like 'hủy tắt máy'."""
    for pattern, cmd in SYSTEM_COMMAND_CANCEL_PATTERNS:
        if pattern in normalized:
            return cmd
    return None


def _extract_browser_url(normalized: str, original_text: str) -> str | None:
    """Extract URL from browser open requests.

    Supports:
    - Explicit URLs (google.com, https://...)
    - Website aliases (google, youtube, facebook, zalo, etc.)
    - Domain patterns in Vietnamese text
    """
    # 1. Check for website aliases first (e.g., "mở google", "truy cập youtube")
    for alias, url in WEBSITE_ALIASES.items():
        if alias in normalized:
            return url

    # 2. Try to extract a URL-like pattern from original text
    url_match = URL_PATTERN.search(original_text)
    if url_match:
        domain = url_match.group(1)
        # Only accept if it looks like a real domain (has a dot)
        if "." in domain and len(domain) > 3:
            return f"https://{domain}"

    return None


def _extract_location(normalized: str) -> str | None:
    for canonical, aliases in LOCATION_RULES:
        if any(alias in normalized for alias in aliases):
            return canonical

    weather_like = _match_after_markers(normalized, ("thoi tiet", "nhiet do", "mua", "du bao", "weather"))
    if weather_like:
        return weather_like

    time_like = _match_after_markers(normalized, ("may gio", "bay gio", "gio o", "time in"))
    if time_like:
        return time_like

    return None


def _extract_timezone(normalized: str) -> str | None:
    for timezone, aliases in TIMEZONE_RULES:
        if any(alias in normalized for alias in aliases):
            return timezone
    return None


def _extract_currency(normalized: str) -> tuple[float | None, str | None, str | None]:
    amount_match = re.search(r"\b(\d+(?:[.,]\d+)?)\b", normalized)
    amount = float(amount_match.group(1).replace(",", ".")) if amount_match else None

    codes_found = [_canonical_currency(match.group(1)) for match in re.finditer(r"\b(usd|vnd|eur|jpy|krw|cny|gbp|aud|cad|sgd|thb|yen|won|yuan|baht)\b", normalized)]
    base_currency = codes_found[0] if codes_found else None
    target_currency = codes_found[1] if len(codes_found) > 1 else None

    if "sang vnd" in normalized or "to vnd" in normalized:
        target_currency = "VND"

    if base_currency is None:
        base_currency = _guess_base_currency(normalized)

    if target_currency is None and "sang" in normalized:
        target_currency = _guess_target_currency(normalized, base_currency)

    return amount, base_currency, target_currency


def _extract_search_query(normalized: str) -> str | None:
    query = _capture_after_patterns(
        normalized,
        (
            r"(?:tim thong tin moi ve|tim thong tin ve|tim thong tin|tra cuu|cap nhat)\s+(.+)$",
            r"(?:search for|search)\s+(.+)$",
        ),
    )
    if query:
        return _canonicalize_topic(query)
    return None


def _extract_news_topic(normalized: str) -> str | None:
    if not any(hint in normalized for hint in NEWS_HINTS) and not normalized.startswith("tin "):
        return None

    matched = _match_topic_alias(normalized)
    if matched:
        return matched

    return None


def _extract_system_command(normalized: str) -> tuple[str | None, float | None, str | None]:
    command = None
    for alias, canonical in SYSTEM_COMMAND_ALIASES.items():
        if alias in normalized:
            command = canonical
            break

    if not command:
        return None, None, None

    # Extract delay: "5 phut nua", "10 phut", "1 tieng"
    delay = None
    delay_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(phut|tieng|gio|h|m)\s*(nua|sau|later)?", normalized)
    if delay_match:
        value = float(delay_match.group(1).replace(",", "."))
        unit = delay_match.group(2)
        if unit in ("tieng", "gio", "h"):
            delay = value * 3600
        elif unit in ("phut", "m"):
            delay = value * 60
        else:
            delay = value

    # Extract app name for open/close app
    app_name = None
    if command in ("open_app", "close_app"):
        app_match = re.search(r"(?:mo|dong)\s+(?:app|ung dung)\s+(.+)", normalized)
        if app_match:
            app_name = app_match.group(1).strip()
        else:
            # Try "app X" pattern
            app_match2 = re.search(r"(?:app|ung dung)\s+(.+)", normalized)
            if app_match2:
                app_name = app_match2.group(1).strip()

    return command, delay, app_name


def _match_after_markers(normalized: str, markers: tuple[str, ...]) -> str | None:
    for marker in markers:
        pattern = rf"{re.escape(marker)}\s+(?:o|tai|o tai|tai o|ở|tại)?\s*(.+?)(?:\s*(?:hom nay|hom nay|the nao|the nào|nhé|nha|khong|không)\b.*)?$"
        match = re.search(pattern, normalized)
        if match:
            candidate = match.group(1).strip()
            canonical = _canonicalize_location(candidate)
            if canonical:
                return canonical
    return None


def _capture_after_patterns(normalized: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
        if match:
            candidate = match.group(1).strip(" ?!.:,;")
            if candidate:
                return candidate
    return None


def _canonical_currency(code: str) -> str:
    code = code.upper()
    if code == "YEN":
        return "JPY"
    if code == "WON":
        return "KRW"
    if code == "YUAN":
        return "CNY"
    if code == "BAHT":
        return "THB"
    return code


def _guess_base_currency(normalized: str) -> str | None:
    for alias, canonical in CURRENCY_ALIASES.items():
        if alias in normalized:
            return canonical
    return None


def _guess_target_currency(normalized: str, base_currency: str | None) -> str | None:
    if "sang vnd" in normalized or "to vnd" in normalized:
        return "VND"
    for alias, canonical in CURRENCY_ALIASES.items():
        if alias in normalized and canonical != base_currency:
            return canonical
    return None


def _canonicalize_location(candidate: str) -> str | None:
    normalized = _normalize_text(candidate)
    for canonical, aliases in LOCATION_RULES:
        if any(alias == normalized or alias in normalized for alias in aliases):
            return canonical
    return None


def _canonicalize_topic(candidate: str) -> str:
    normalized = _normalize_text(candidate)
    matched = _match_topic_alias(normalized)
    if matched:
        return matched
    return _title_case_phrase(candidate)


def _match_topic_alias(normalized: str) -> str | None:
    for alias in sorted(TOPIC_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            return TOPIC_ALIASES[alias]
    return None


def _title_case_phrase(value: str) -> str:
    words = [word for word in value.strip().split() if word]
    if not words:
        return value.strip()
    return " ".join(word[:1].upper() + word[1:] for word in words)


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    without_marks = "".join(character for character in decomposed if unicodedata.category(character) != "Mn")
    normalized = without_marks.replace("đ", "d").replace("Đ", "d")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()
