from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("keobot.conversation")

MAX_TURNS = 20
SUMMARY_THRESHOLD = 10
DEFAULT_SESSION_TTL_SECONDS = 300


@dataclass
class ConversationTurn:
    role: str
    text: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ConversationSession:
    session_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    follow_up_timeout: int = 8
    session_timeout: int = 20
    summary: str | None = None

    def add_turn(self, role: str, text: str) -> None:
        self.turns.append(ConversationTurn(role=role, text=text))
        self.last_activity = datetime.now(timezone.utc)
        if len(self.turns) > MAX_TURNS:
            self.turns = self.turns[-MAX_TURNS:]

    def get_context_turns(self, limit: int = 10) -> list[dict[str, str]]:
        recent = self.turns[-limit:] if len(self.turns) > limit else self.turns
        return [{"role": t.role, "text": t.text} for t in recent]

    def needs_summarization(self) -> bool:
        return len(self.turns) >= SUMMARY_THRESHOLD

    def compact_with_summary(self, summary_text: str) -> None:
        self.summary = summary_text
        if len(self.turns) > 4:
            self.turns = self.turns[-4:]

    def get_context_with_summary(self, limit: int = 10) -> list[dict[str, str]]:
        result = self.get_context_turns(limit=limit)
        if self.summary:
            result.insert(0, {"role": "system", "text": f"[Tóm tắt hội thoại: {self.summary}]"})
        return result

    def is_expired(self, ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS) -> bool:
        if not self.is_active:
            return True
        elapsed = (datetime.now(timezone.utc) - self.last_activity).total_seconds()
        return elapsed > ttl_seconds

    def touch(self) -> None:
        self.last_activity = datetime.now(timezone.utc)


class ConversationManager:
    def __init__(self) -> None:
        self._sessions: dict[str, ConversationSession] = {}
        self._cleanup_interval = timedelta(minutes=5)
        self._last_cleanup = datetime.now(timezone.utc)

    def create_session(
        self, follow_up_timeout: int = 8, session_timeout: int = 20
    ) -> ConversationSession:
        self._cleanup_stale()
        session_id = uuid.uuid4().hex[:12]
        session = ConversationSession(
            session_id=session_id,
            follow_up_timeout=follow_up_timeout,
            session_timeout=session_timeout,
        )
        self._sessions[session_id] = session
        logger.info(
            "session_start id=%s follow_up_timeout=%d session_timeout=%d",
            session_id, follow_up_timeout, session_timeout,
        )
        return session

    def get_session(self, session_id: str) -> ConversationSession | None:
        self._cleanup_stale()
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.is_expired():
            logger.info("session_end id=%s reason=expired", session_id)
            self.end_session(session_id)
            return None
        return session

    def end_session(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session:
            session.is_active = False
            logger.info("session_end id=%s reason=explicit turns=%d", session_id, len(session.turns))
            return True
        return False

    def touch(self, session_id: str) -> bool:
        session = self.get_session(session_id)
        if session is None:
            return False
        session.touch()
        return True

    def add_user_turn(self, session_id: str, text: str) -> bool:
        session = self.get_session(session_id)
        if session is None:
            return False
        session.add_turn("user", text)
        return True

    def add_bot_turn(self, session_id: str, text: str) -> bool:
        session = self.get_session(session_id)
        if session is None:
            return False
        session.add_turn("assistant", text)
        return True

    def get_context(
        self, session_id: str, limit: int = 10
    ) -> list[dict[str, str]]:
        session = self.get_session(session_id)
        if session is None:
            return []
        return session.get_context_turns(limit=limit)

    def resolve_follow_up(self, session_id: str, current_query: str) -> str:
        session = self.get_session(session_id)
        if session is None or len(session.turns) < 2:
            return current_query
        resolved = _resolve_references(current_query, session)
        if resolved != current_query:
            logger.info(
                "follow_up_resolved id=%s original='%s' resolved='%s'",
                session_id, current_query, resolved,
            )
        return resolved

    def _cleanup_stale(self) -> None:
        now = datetime.now(timezone.utc)
        if (now - self._last_cleanup) < self._cleanup_interval:
            return
        self._last_cleanup = now
        stale_ids = [
            sid for sid, sess in self._sessions.items()
            if sess.is_expired()
        ]
        for sid in stale_ids:
            logger.info("session_end id=%s reason=stale_cleanup", sid)
            del self._sessions[sid]

    def get_active_session_count(self) -> int:
        self._cleanup_stale()
        return len(self._sessions)

    def force_cleanup(self) -> int:
        stale_ids = [
            sid for sid, sess in self._sessions.items()
            if sess.is_expired()
        ]
        for sid in stale_ids:
            logger.info("session_end id=%s reason=force_cleanup", sid)
            del self._sessions[sid]
        return len(stale_ids)


def _resolve_references(query: str, session: ConversationSession) -> str:
    turns = session.turns
    if len(turns) < 2:
        return query
    last_user_turn = None
    last_bot_text = None
    for t in reversed(turns):
        if t.role == "user" and last_user_turn is None:
            last_user_turn = t.text
        if t.role == "assistant" and last_bot_text is None:
            last_bot_text = t.text
        if last_user_turn and last_bot_text:
            break
    q_lower = query.lower().strip()
    is_follow_up = _is_follow_up_query(q_lower)
    if not is_follow_up:
        return query
    resolved = query
    if last_user_turn:
        resolved = _resolve_temporal(resolved, last_user_turn)
        resolved = _resolve_location(resolved, last_user_turn)
        resolved = _resolve_demonstrative(resolved, last_user_turn, last_bot_text)
        resolved = _resolve_topic_shift(resolved, last_user_turn)
    return resolved


def _is_follow_up_query(query: str) -> bool:
    follow_up_patterns = (
        r"\bngày\s*mai\b",
        r"\btomorrow\b",
        r"\bở\s*đó\b",
        r"\bthere\b",
        r"\bcái\s*đó\b",
        r"\bđó\b",
        r"\bthat\b",
        r"\bcòn\b.*\bthì\s*sao\b",
        r"\bwhat\s*about\b",
        r"\band\b",
        r"\bcòn\b",
        r"\btiếp\s*theo\b",
        r"\bnext\b",
        r"\blại\b",
        r"\btoo\b",
        r"\bas\b.*\bwell\b",
        r"\balso\b",
        r"\bnữa\b",
    )
    return any(re.search(p, query, re.IGNORECASE) for p in follow_up_patterns)


_TIME_PATTERNS = {
    r"\bngày\s*mai\b": "tomorrow",
    r"\btomorrow\b": "tomorrow",
    r"\bhôm\s*nay\b": "today",
    r"\btoday\b": "today",
    r"\btuần\s*sau\b": "next week",
    r"\bnext\s*week\b": "next week",
}


def _resolve_temporal(query: str, last_user_turn: str) -> str:
    for pattern, replacement in _TIME_PATTERNS.items():
        if re.search(pattern, query, re.IGNORECASE):
            last_date = _extract_date(last_user_turn)
            if last_date:
                resolved = re.sub(
                    pattern, f"{replacement} ({last_date})", query, flags=re.IGNORECASE,
                )
                return resolved
    return query


def _extract_date(text: str) -> str | None:
    patterns = [
        r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)",
        r"(\d{4}-\d{2}-\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return None


def _resolve_location(query: str, last_user_turn: str) -> str:
    location_pattern = r"\b(ở\s*đó|there|chỗ\s*đó|đó)\b"
    if re.search(location_pattern, query, re.IGNORECASE):
        last_location = _extract_location(last_user_turn)
        if last_location:
            resolved = re.sub(
                location_pattern, last_location, query, flags=re.IGNORECASE,
            )
            return resolved
    return query


_CITY_PATTERN = re.compile(
    r"\b(thành phố|tp\.?\s*|tại\s+)?"
    r"(Hà Nội|Hanoi|Sài Gòn|TP HCM|Hồ Chí Minh|"
    r"Đà Nẵng|Da Nang|Huế|Hue|Tokyo|London|Paris|New York|"
    r"Washington|Berlin|Moscow|Sydney|Seoul|Bangkok)\b",
    re.IGNORECASE,
)


def _extract_location(text: str) -> str | None:
    m = _CITY_PATTERN.search(text)
    if m:
        return m.group(0).strip()
    return None


def _resolve_demonstrative(
    query: str, last_user_turn: str, last_bot_text: str | None
) -> str:
    demo_pattern = r"\b(cái\s*đó|đó|that|this)\b"
    if re.search(demo_pattern, query, re.IGNORECASE):
        key_noun = _extract_key_noun(last_user_turn, last_bot_text)
        if key_noun:
            resolved = re.sub(
                demo_pattern, key_noun, query, flags=re.IGNORECASE,
            )
            return resolved
    return query


def _extract_key_noun(user_text: str, bot_text: str | None) -> str | None:
    candidates = []
    extraction_patterns = [
        r"(thời tiết|weather)\s*(\w+\s*)*\b(tại|ở|tại)\s+(\w+)",
        r"(giờ|time)\s*(\w+\s*)*\b(tại|ở|tại)\s+(\w+)",
        r"(tỷ giá|exchange rate|giá)\s*(\w+\s*)*\b(\w+)",
    ]
    for pat in extraction_patterns:
        m = re.search(pat, user_text, re.IGNORECASE)
        if m:
            candidates.append(m.group(0))
    if not candidates and bot_text:
        for pat in extraction_patterns:
            m = re.search(pat, bot_text, re.IGNORECASE)
            if m:
                candidates.append(m.group(0))
    return candidates[0] if candidates else None


def _resolve_topic_shift(query: str, last_user_turn: str) -> str:
    shift_pattern = r"\b(còn|what\s*about)\b\s*(.*)"
    m = re.search(shift_pattern, query, re.IGNORECASE)
    if m:
        new_topic = m.group(2).strip()
        if new_topic and not re.search(r"\b(thời tiết|weather|giờ|time|tỷ giá|rate)\b", query, re.IGNORECASE):
            last_topic = _detect_topic(last_user_turn)
            if last_topic:
                return f"{new_topic} {last_topic}"
    return query


def _detect_topic(text: str) -> str:
    topic_keywords = {
        "weather": ["thời tiết", "weather", "nhiệt độ", "temperature", "mưa", "rain", "nắng", "sun"],
        "time": ["giờ", "time", "múi giờ", "timezone"],
        "currency": ["tỷ giá", "exchange rate", "giá", "price", "tiền tệ", "currency"],
    }
    lower = text.lower()
    for topic, keywords in topic_keywords.items():
        if any(kw in lower for kw in keywords):
            return topic
    return ""


_manager: ConversationManager | None = None


def get_conversation_manager() -> ConversationManager:
    global _manager
    if _manager is None:
        _manager = ConversationManager()
    return _manager
