from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.services.memory_store import SAFE_CONTEXT_KEYS

ALLOWED_MEMORY_KEYS = SAFE_CONTEXT_KEYS

DELETE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("user_name", r"(?:forget my name|delete my name|remove my name|xoa ten cua minh di|xoa ten cua toi di|xoa ten cua toi|xoa ten cua minh)"),
    ("default_city", r"(?:forget my default city|delete my default city|remove my default city|xoa thanh pho mac dinh cua minh|xoa thanh pho mac dinh cua toi)"),
    ("default_timezone", r"(?:forget my default timezone|delete my default timezone|remove my default timezone|xoa mui gio mac dinh cua minh|xoa mui gio mac dinh cua toi)"),
    ("default_currency", r"(?:forget my default currency|delete my default currency|remove my default currency|xoa tien te mac dinh cua minh|xoa tien te mac dinh cua toi)"),
    ("answer_style", r"(?:forget my answer style|delete my answer style|remove my answer style|xoa kieu tra loi cua minh|xoa kieu tra loi cua toi)"),
    ("preferred_form_of_address", r"(?:forget my preferred form of address|delete my preferred form of address|remove my preferred form of address|xoa cach xung ho cua minh|xoa cach xung ho cua toi)"),
)

SET_PATTERNS: tuple[tuple[str, str], ...] = (
    ("user_name", r"(?:from now on,? call me|call me|goi minh la|goi toi la|tu gio goi minh la|tu gio goi toi la)\s+(.+)$"),
    ("default_city", r"(?:remember that my default city is|my default city is|thanh pho mac dinh cua minh la|thanh pho mac dinh cua toi la)\s+(.+)$"),
    ("default_timezone", r"(?:remember that my default timezone is|my default timezone is|mui gio mac dinh cua minh la|mui gio mac dinh cua toi la)\s+(.+)$"),
    ("default_currency", r"(?:remember that my default currency is|my default currency is|tien te mac dinh cua minh la|tien te mac dinh cua toi la)\s+(.+)$"),
    ("preferred_form_of_address", r"(?:my preferred form of address is|preferred form of address is|cach xung ho cua minh la|cach xung ho cua toi la)\s+(.+)$"),
)


def parse_memory_text(user_text: str) -> dict[str, Any]:
    normalized, index_map = _normalize_text_with_map(user_text)

    delete_key = _detect_delete_key(normalized)
    if delete_key is not None:
        return {
            "action": "delete",
            "key": delete_key,
            "value": None,
            "category": "preference",
        }

    set_match = _detect_set_pattern(normalized, user_text, index_map)
    if set_match is not None:
        key, value = set_match
        if key == "answer_style":
            value = _normalize_answer_style(value)
        if key == "preferred_form_of_address":
            value = _normalize_form_of_address(value)
        return {
            "action": "set",
            "key": key,
            "value": value,
            "category": "preference",
        }

    return {
        "action": "none",
        "key": None,
        "value": None,
        "category": "preference",
    }


def _detect_delete_key(normalized: str) -> str | None:
    for key, pattern in DELETE_PATTERNS:
        if re.search(rf"\b{pattern}\b", normalized):
            return key
    return None


def _detect_set_pattern(normalized: str, original: str, index_map: list[int]) -> tuple[str, str] | None:
    for key, pattern in SET_PATTERNS:
        match = re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
        if match:
            value = _extract_original_span(original, index_map, match.span(1)).strip(" ?!.:,;\"'")
            if value:
                return key, _restore_title_case(value)

    if "use a shorter answer style" in normalized or "ngan gon hon" in normalized or "tra loi ngan gon" in normalized:
        return "answer_style", "short"

    return None


def _normalize_answer_style(value: str) -> str:
    normalized = _normalize_text(value)
    if any(keyword in normalized for keyword in ("short", "ngan gon", "ngan", "brief", "concise")):
        return "short"
    if any(keyword in normalized for keyword in ("detailed", "chi tiet", "day du", "long")):
        return "detailed"
    return _restore_title_case(value)


def _normalize_form_of_address(value: str) -> str:
    normalized = _normalize_text(value)
    for candidate in ("anh", "chi", "em", "ban", "toi", "minh", "you"):
        if candidate in normalized:
            return _restore_title_case(candidate)
    return _restore_title_case(value)


def _restore_title_case(value: str) -> str:
    cleaned = " ".join(part for part in value.strip().split() if part)
    if not cleaned:
        return cleaned
    return cleaned[:1].upper() + cleaned[1:]


def _normalize_text(value: str) -> str:
    normalized, _ = _normalize_text_with_map(value)
    return normalized


def _normalize_text_with_map(value: str) -> tuple[str, list[int]]:
    raw_chars: list[str] = []
    raw_map: list[int] = []

    for original_index, character in enumerate(value):
        normalized_char = unicodedata.normalize("NFD", character.casefold())
        normalized_char = "".join(part for part in normalized_char if unicodedata.category(part) != "Mn")
        normalized_char = normalized_char.replace("đ", "d").replace("Đ", "d")
        for output_char in normalized_char:
            raw_chars.append(output_char)
            raw_map.append(original_index)

    collapsed_chars: list[str] = []
    collapsed_map: list[int] = []
    previous_space = True
    for character, original_index in zip(raw_chars, raw_map, strict=False):
        if character.isspace():
            if previous_space or not collapsed_chars:
                continue
            collapsed_chars.append(" ")
            collapsed_map.append(original_index)
            previous_space = True
            continue
        collapsed_chars.append(character)
        collapsed_map.append(original_index)
        previous_space = False

    while collapsed_chars and collapsed_chars[0] == " ":
        collapsed_chars.pop(0)
        collapsed_map.pop(0)
    while collapsed_chars and collapsed_chars[-1] == " ":
        collapsed_chars.pop()
        collapsed_map.pop()

    return "".join(collapsed_chars), collapsed_map


def _extract_original_span(original: str, index_map: list[int], span: tuple[int, int]) -> str:
    start, end = span
    if start >= end or not index_map:
        return ""

    original_start = index_map[min(start, len(index_map) - 1)]
    original_end = index_map[min(end - 1, len(index_map) - 1)] + 1
    return original[original_start:original_end]
