from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.providers.llm import _is_qwen_provider
from app.services.event_bus import Event, EventType, get_event_bus
from app.services.memory_store import get_memory_store
from app.services.stream_manager import StreamState, get_stream_manager


class ReplanDecision(str, Enum):
    continue_ = "continue"
    restart = "restart"
    switch_intent = "switch_intent"
    ask_missing_info = "ask_missing_info"


_REPLAN_EXPLANATIONS: dict[str, str] = {
    "follow_up": "Nguoi dung bo sung thong tin, tiep tuc cau tra loi.",
    "new_topic": "Nguoi dung chuyen chu de, can bat dau lai.",
    "tool_change": "Nguoi dung muon dung cong cu khac, chuyen huong.",
    "missing_info": "Thieu thong tin de chay tool, can hoi them.",
}


@dataclass
class ReplanInput:
    partial_response: str = ""
    new_input: str = ""
    conversation_turns: list[dict[str, str]] = field(default_factory=list)
    memory_context: dict[str, str] = field(default_factory=dict)
    intent: str = "none"
    tool_result: dict[str, Any] | None = None
    missing_field: str | None = None


@dataclass
class ReplanOutput:
    decision: ReplanDecision
    reason: str = ""
    new_intent: str | None = None
    explanation: str = ""


_SWITCH_INTENT_KEYWORDS: dict[str, list[str]] = {
    "weather": ["thoi tiet", "nhiet do", "do am", "mua", "nang", "nhiet", "am ap", "lanh", "nong", "nhiet do"],
    "time": ["bay gio", "may gio", "mui gio", "gio giac", "thoi gian", "ngay may", "hom qua", "ngay mai", "time", "zone"],
    "currency": ["ty gia", "ti gia", "tien te", "ngoai te", "quy doi", "chuyen doi", "doi tien", "exchange", "currency", "usd", "vnd", "eur", "gbp", "jpy"],
    "news_search": ["tin tuc", "tin moi", "tin nong", "thoi su", "su kien", "news", "moi nhat"],
    "general_search": ["tim kiem", "tra cuu", "search", "google", "thong tin"],
}

_RESTART_TRIGGERS = [
    "thoi ko", "thoi khong", "bo qua", "chuyen khac",
    "khong co gi", "het", "cam on", "thanks", "bye", "tam biet",
    "another", "different", "switch topic", "change",
]


def _compute_similarity(a: str, b: str) -> float:
    a_words = set(a.lower().split())
    b_words = set(b.lower().split())
    if not a_words or not b_words:
        return 0.0
    intersection = a_words & b_words
    return len(intersection) / max(len(a_words), len(b_words))


def _detect_intent_from_text(text: str) -> str | None:
    lower = text.lower()
    best_intent: str | None = None
    best_count = 0
    for intent, keywords in _SWITCH_INTENT_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in lower)
        if count > best_count:
            best_count = count
            best_intent = intent
    return best_intent


def _heuristic_decide(input_data: ReplanInput) -> ReplanOutput:
    lower_new = input_data.new_input.lower().strip()
    partial = input_data.partial_response.strip()

    has_restart_trigger = any(trig in lower_new for trig in _RESTART_TRIGGERS)
    if has_restart_trigger and _compute_similarity(lower_new, partial) < 0.4:
        return ReplanOutput(
            decision=ReplanDecision.restart,
            reason="new_topic",
            explanation=_REPLAN_EXPLANATIONS["new_topic"],
        )

    new_intent = _detect_intent_from_text(input_data.new_input)
    if new_intent and new_intent != input_data.intent:
        return ReplanOutput(
            decision=ReplanDecision.switch_intent,
            reason="tool_change",
            new_intent=new_intent,
            explanation=_REPLAN_EXPLANATIONS["tool_change"],
        )

    if input_data.intent == "none" and partial:
        similarity = _compute_similarity(lower_new, partial)
        if similarity < 0.2 and len(lower_new.split()) >= 3:
            return ReplanOutput(
                decision=ReplanDecision.restart,
                reason="new_topic",
                explanation=_REPLAN_EXPLANATIONS["new_topic"],
            )

    if input_data.missing_field:
        has_missing_info = False
        if input_data.missing_field == "location":
            has_missing_info = bool(
                re.search(r"(?:o|tai|in|at|cho)\s+\w+|(?:[A-ZÀ-Ỹ][a-zà-ỹ]+\s*)+", input_data.new_input)
            )
        elif input_data.missing_field == "timezone":
            has_missing_info = bool(
                re.search(r"(?:mui gio|timezone|UTC|GMT|UTC[+-]|GMT[+-]|[+-]\d)", input_data.new_input, re.IGNORECASE)
            )
        elif input_data.missing_field in ("base_currency", "target_currency"):
            has_missing_info = bool(
                re.search(r"(?:USD|VND|EUR|GBP|JPY|AUD|tien|\w+ sang \w+)", input_data.new_input, re.IGNORECASE)
            )

        if has_missing_info:
            return ReplanOutput(
                decision=ReplanDecision.continue_,
                reason="missing_info",
                explanation=_REPLAN_EXPLANATIONS["missing_info"],
            )

        if len(input_data.new_input.split()) <= 3:
            return ReplanOutput(
                decision=ReplanDecision.ask_missing_info,
                reason="missing_info",
                explanation=_REPLAN_EXPLANATIONS["missing_info"],
            )

    if input_data.tool_result and _tool_is_unavailable(input_data.tool_result):
        return ReplanOutput(
            decision=ReplanDecision.restart,
            reason="new_topic",
            explanation="Tool khong kha dung, chuyen sang hoi thoai thuong.",
        )

    return ReplanOutput(
        decision=ReplanDecision.continue_,
        reason="follow_up",
        explanation=_REPLAN_EXPLANATIONS["follow_up"],
    )


def _tool_is_unavailable(tool_result: dict[str, Any]) -> bool:
    return tool_result.get("available") is False or tool_result.get("is_available") is False


def _prepare_input_from_session(
    session_id: str,
    new_input: str,
    intent: str = "none",
    tool_result: dict[str, Any] | None = None,
    missing_field: str | None = None,
) -> ReplanInput:
    stream_mgr = get_stream_manager()
    session = stream_mgr.get_session(session_id)
    partial = session.partial_text() if session else ""

    from app.services.conversation_context import get_conversation_manager
    mgr = get_conversation_manager()
    conv_session = mgr.get_session(session_id) if session_id else None
    turns = conv_session.get_context_turns(limit=6) if conv_session else []

    memory_context = get_memory_store().get_memory_context()

    return ReplanInput(
        partial_response=partial,
        new_input=new_input,
        conversation_turns=turns,
        memory_context=memory_context,
        intent=intent,
        tool_result=tool_result,
        missing_field=missing_field,
    )


REPLAN_SYSTEM_PROMPT = """Ban la bo phan lap ke hoach cua Kẹo Thông Minh (Replanner).
Nhieu vu: phan tich tinh huong va quyet dinh tiep theo.

Quyet dinh:
- continue: Tiep tuc cau tra loi hien tai, bo sung noi dung moi.
- restart: Bat dau lai hoan toan (nguoi dung chuyen chu de hoac hoi cau hoi khac).
- switch_intent: Chuyen sang tool khac (nguoi dung muon hoi ve chu de khac).

Chi tiet tinh huong:
- partial_response: Cau tra loi dang do dang dang tra loi do.
- new_input: Tin nhan moi nhat cua nguoi dung.
- lich_su_hoi_thoai: Cac tin nhan truoc do.
- intent: Tool hien tai (weather, time, currency, search, hoac none).
- missing_field: Truong bi thieu neu tool can them thong tin.

Tra ve JSON:
{
  "decision": "continue|restart|switch_intent",
  "reason": "ly do",
  "new_intent": "ten tool neu switch_intent, neu khong null",
  "explanation": "giai thich"
}"""


async def decide_replan(input_data: ReplanInput) -> ReplanOutput:
    from app.config import get_settings
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider in {"local", "mock"}:
        return _heuristic_decide(input_data)

    prompt_parts = [
        f"partial_response: {input_data.partial_response}",
        f"new_input: {input_data.new_input}",
        f"intent: {input_data.intent}",
    ]
    if input_data.missing_field:
        prompt_parts.append(f"missing_field: {input_data.missing_field}")
    if input_data.tool_result:
        prompt_parts.append(f"tool_result: {json.dumps(input_data.tool_result, ensure_ascii=False)}")
    if input_data.conversation_turns:
        turns_text = "\n".join(
            f"{t['role']}: {t['text']}" for t in input_data.conversation_turns[-4:]
        )
        prompt_parts.append(f"lich_su_hoi_thoai:\n{turns_text}")

    prompt = "\n".join(prompt_parts)

    if provider == "openai" or _is_qwen_provider(provider):
        if provider == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            model = settings.openai_chat_model
        else:
            if not settings.dashscope_api_key:
                return _heuristic_decide(input_data)
            from openai import OpenAI
            client = OpenAI(
                api_key=settings.dashscope_api_key,
                base_url=settings.dashscope_base_url,
            )
            model = settings.dashscope_llm_model
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": REPLAN_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        raw_text = response.choices[0].message.content or ""
    elif provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            settings.gemini_model,
            system_instruction=REPLAN_SYSTEM_PROMPT,
        )
        response = model.generate_content(prompt)
        raw_text = getattr(response, "text", "") or ""
    else:
        return _heuristic_decide(input_data)

    payload = _extract_json_object(raw_text)
    if payload is None:
        return _heuristic_decide(input_data)

    decision_str = payload.get("decision", "continue")
    try:
        decision = ReplanDecision(decision_str)
    except ValueError:
        decision = ReplanDecision.continue_

    return ReplanOutput(
        decision=decision,
        reason=payload.get("reason", ""),
        new_intent=payload.get("new_intent"),
        explanation=payload.get("explanation", ""),
    )


def _extract_json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None
    return None


class Replanner:
    def __init__(self) -> None:
        self._started = False

    def subscribe_to_events(self) -> None:
        if self._started:
            return
        self._started = True
        bus = get_event_bus()
        bus.subscribe(EventType.interrupt, self._on_interrupt)
        bus.subscribe(EventType.replanning, self._on_replanning)

    def _on_interrupt(self, event: Event) -> None:
        session_id = event.session_id
        if not session_id:
            return
        new_input = event.payload.get("text", "")
        intent = event.payload.get("intent", "none")
        tool_result = event.payload.get("tool_result")
        missing_field = event.payload.get("missing_field")

        input_data = _prepare_input_from_session(
            session_id=session_id,
            new_input=new_input,
            intent=intent,
            tool_result=tool_result,
            missing_field=missing_field,
        )

        stream_mgr = get_stream_manager()
        session = stream_mgr.get_session(session_id)
        if session:
            import asyncio
            output = asyncio.run(decide_replan(input_data))
            session.replan_context = {
                "decision": output.decision.value,
                "reason": output.reason,
                "new_intent": output.new_intent,
                "explanation": output.explanation,
                "partial_response": input_data.partial_response,
                "new_input": input_data.new_input,
            }

    def _on_replanning(self, event: Event) -> None:
        session_id = event.session_id
        if not session_id:
            return
        intent = event.payload.get("tool", "none")
        reason = event.payload.get("reason", "missing_info")
        tool_result = event.payload.get("tool_result")
        new_input = event.payload.get("text", "")

        input_data = _prepare_input_from_session(
            session_id=session_id,
            new_input=new_input,
            intent=intent,
            tool_result=tool_result,
            missing_field=intent if reason == "missing_info" else None,
        )

        stream_mgr = get_stream_manager()
        session = stream_mgr.get_session(session_id)
        if session:
            import asyncio
            output = asyncio.run(decide_replan(input_data))
            session.replan_context = {
                "decision": output.decision.value,
                "reason": output.reason,
                "new_intent": output.new_intent,
                "explanation": output.explanation,
                "partial_response": input_data.partial_response,
                "new_input": input_data.new_input,
            }


_replanner: Replanner | None = None


def get_replanner() -> Replanner:
    global _replanner
    if _replanner is None:
        _replanner = Replanner()
    return _replanner
