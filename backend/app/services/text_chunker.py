from __future__ import annotations

import re
from typing import Any

TARGET_WORD_COUNT = 700
MAX_CHUNK_WORDS = 1000
MIN_CHUNK_WORDS = 300


def chunk_text(
    text: str,
    source_title: str | None = None,
    source_location: str | None = None,
    page_number: int | None = None,
) -> list[dict[str, Any]]:
    if not text or not text.strip():
        return []

    text = _normalize_whitespace(text)
    paragraphs = _split_paragraphs(text)

    chunks: list[dict[str, Any]] = []
    buffer: list[str] = []
    buffer_words = 0

    for para in paragraphs:
        para_words = len(para.split())
        combined_words = buffer_words + para_words

        if combined_words > MAX_CHUNK_WORDS and buffer:
            chunks.append(_make_chunk(buffer, source_title, source_location, page_number, len(chunks)))
            buffer = [para]
            buffer_words = para_words
        elif combined_words >= MIN_CHUNK_WORDS:
            buffer.append(para)
            buffer_words = combined_words
            if buffer_words >= TARGET_WORD_COUNT:
                chunks.append(_make_chunk(buffer, source_title, source_location, page_number, len(chunks)))
                buffer = []
                buffer_words = 0
        else:
            buffer.append(para)
            buffer_words = combined_words

    if buffer:
        if chunks and buffer_words < MIN_CHUNK_WORDS // 2:
            chunks[-1]["text"] += "\n\n" + "\n\n".join(buffer)
            chunks[-1]["token_estimate"] = _estimate_tokens(chunks[-1]["text"])
        else:
            chunks.append(_make_chunk(buffer, source_title, source_location, page_number, len(chunks)))

    return chunks


def _normalize_whitespace(text: str) -> str:
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_paragraphs(text: str) -> list[str]:
    raw = re.split(r"\n\n+", text)
    return [p.strip() for p in raw if p.strip()]


def _make_chunk(
    paragraphs: list[str],
    source_title: str | None,
    source_location: str | None,
    page_number: int | None,
    index: int,
) -> dict[str, Any]:
    text = "\n\n".join(paragraphs)
    location_parts: list[str] = []
    if source_location:
        location_parts.append(source_location)
    if page_number is not None:
        location_parts.append(f"Trang {page_number}")
    location = ", ".join(location_parts) if location_parts else None
    return {
        "text": text,
        "source_title": source_title or "",
        "source_location": location,
        "token_estimate": _estimate_tokens(text),
    }


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
