from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from typing import AsyncIterator

from app.providers.llm import generate_conversation_summary, generate_keobot_response, generate_keobot_tool_response
from app.providers.llm_stream import stream_keobot_response, stream_keobot_tool_response
from app.services.async_tool_executor import AsyncToolExecutor
from app.services.event_bus import Event, EventType, get_event_bus
from app.services.stream_manager import StreamState, get_stream_manager
from app.services.conversation_context import get_conversation_manager
from app.services.knowledge_store import get_knowledge_store
from app.services.memory_parser import parse_memory_text
from app.services.memory_store import get_memory_store
from app.services.reminder_parser import parse_reminder_text
from app.services.reminder_store import Reminder, get_reminder_store
from app.services.tool_router import TOOL_CONFIDENCE_THRESHOLD, detect_tool_intent
from app.tools.currency_tool import get_currency_info
from app.tools.search_tool import get_search_info
from app.tools.time_tool import get_time_info
from app.tools.weather_tool import get_weather_info

_follow_up_log = __import__("logging").getLogger("keobot.follow_up")


def _build_conversation_context(turns: list[dict[str, str]], summary: str | None = None) -> str:
    parts = []
    if summary:
        parts.append(f"[Tóm tắt: {summary}]")
    for t in turns:
        label = "Người dùng" if t["role"] == "user" else "Kẹo Thông Minh"
        parts.append(f"{label}: {t['text']}")
    return "\n".join(parts)


TOOL_EVENT_PREFIX = "__tool__:"

_THINKING_MESSAGES = {
    "weather": "Minh dang kiem tra thoi tiet",
    "time": "Minh dang xem gio",
    "currency": "Minh dang tra cuu ty gia",
    "news_search": "Minh dang tim tin",
    "general_search": "Minh dang tra cuu",
}
_FALLBACK_THINKING = "Minh dang xu ly"


async def _yield_thinking(
    intent: str,
    cancel_check: Any = None,
    interval: float = 0.04,
) -> AsyncIterator[str]:
    text = _THINKING_MESSAGES.get(intent, _FALLBACK_THINKING)
    for ch in text:
        if cancel_check and cancel_check():
            return
        yield ch
        await asyncio.sleep(interval)


def _interrupt_active_stream(session_id: str) -> bool:
    """If there's an active stream for this session, interrupt it and preserve partial output."""
    stream_mgr = get_stream_manager()
    session = stream_mgr.get_session(session_id)
    if session is None or session.state != StreamState.streaming:
        return False

    partial = session.partial_text()
    session.interrupt()

    if partial.strip():
        mgr = get_conversation_manager()
        mgr.add_bot_turn(session_id, f"[interrupted] {partial.strip()}")

    session.reset()
    return True


async def generate_chat_response(
    user_text: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    resolved_text = user_text
    context_turns: list[dict[str, str]] = []
    mgr = get_conversation_manager()

    if session_id:
        _interrupt_active_stream(session_id)
        resolved_text = mgr.resolve_follow_up(session_id, user_text)
        mgr.add_user_turn(session_id, resolved_text)
        session = mgr.get_session(session_id)
        if session and session.needs_summarization():
            all_turns = [{"role": t["role"], "text": t["text"]} for t in mgr.get_context(session_id, limit=15)]
            summary = await generate_conversation_summary(all_turns)
            session.compact_with_summary(summary)
        context_turns = mgr.get_context(session_id, limit=10)
        mgr.touch(session_id)

    memory_draft = parse_memory_text(resolved_text)
    if memory_draft["action"] in {"set", "delete"}:
        memory_store = get_memory_store()
        if memory_draft["action"] == "set":
            assert memory_draft["key"] is not None
            assert memory_draft["value"] is not None
            memory_item = memory_store.set_memory(
                str(memory_draft["key"]),
                str(memory_draft["value"]),
                str(memory_draft.get("category") or "preference"),
            )
            bot_text = _build_memory_confirmation(memory_item)
            if session_id:
                mgr.add_bot_turn(session_id, bot_text)
            return {
                "bot_text": bot_text,
                "emotion": "happy",
                "action": "memory_updated",
                "memory": memory_item,
                "reminder": None,
                "tool_used": "none",
                "tool_result": None,
                "sources": [],
                "updated_at": memory_item["updated_at"],
            }

        assert memory_draft["key"] is not None
        deleted = memory_store.delete_memory(str(memory_draft["key"]))
        bot_text = _build_memory_delete_confirmation(str(memory_draft["key"]), deleted)
        if session_id:
            mgr.add_bot_turn(session_id, bot_text)
        return {
            "bot_text": bot_text,
            "emotion": "happy",
            "action": "memory_deleted",
            "memory": None,
            "reminder": None,
            "tool_used": "none",
            "tool_result": None,
            "sources": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    reminder_draft = parse_reminder_text(resolved_text)
    if reminder_draft is not None:
        reminder = get_reminder_store().create(reminder_draft.title, reminder_draft.remind_at)
        bot_text = _build_reminder_confirmation(reminder)
        if session_id:
            mgr.add_bot_turn(session_id, bot_text)
        return {
            "bot_text": bot_text,
            "emotion": "happy",
            "action": "reminder_created",
            "reminder": reminder,
            "tool_used": "none",
            "tool_result": None,
            "sources": [],
            "updated_at": None,
        }

    knowledge_result = _detect_knowledge_query(resolved_text)
    if knowledge_result is not None:
        if session_id:
            mgr.add_bot_turn(session_id, str(knowledge_result.get("bot_text", "")))
        return knowledge_result

    memory_context = get_memory_store().get_memory_context()
    tool_route = detect_tool_intent(resolved_text, context_turns)
    if tool_route.intent != "none" and tool_route.confidence >= TOOL_CONFIDENCE_THRESHOLD:
        tool_entities = _apply_memory_defaults(tool_route.intent, tool_route.entities, memory_context)
        tool_result = _run_tool(tool_route.intent, tool_route.query, tool_entities)
        sources = _build_sources(tool_route.intent, tool_result)
        updated_at = tool_result.get("updated_at")

        if _tool_is_unavailable(tool_result):
            bot_text = _build_tool_unavailable_message(tool_route.intent)
            if session_id:
                mgr.add_bot_turn(session_id, bot_text)
            return {
                "bot_text": bot_text,
                "emotion": "sad",
                "action": "tool_response",
                "reminder": None,
                "tool_used": tool_route.intent,
                "tool_result": tool_result,
                "sources": sources,
                "updated_at": updated_at,
            }

        missing = _detect_missing_info(tool_route.intent, tool_entities, tool_result)
        if missing:
            bot_text = missing
            if session_id:
                mgr.add_bot_turn(session_id, bot_text)
            return {
                "bot_text": bot_text,
                "emotion": "thinking",
                "action": "tool_response",
                "reminder": None,
                "tool_used": tool_route.intent,
                "tool_result": tool_result,
                "sources": sources,
                "updated_at": updated_at,
            }

        session_obj = mgr.get_session(session_id) if session_id else None
        session_summary = session_obj.summary if session_obj else None
        context_str = _build_conversation_context(context_turns, session_summary)
        llm_response = await generate_keobot_tool_response(
            resolved_text, tool_route.intent, tool_result,
            conversation_context=context_str or None,
        )
        bot_text = llm_response["bot_text"]
        if session_id:
            mgr.add_bot_turn(session_id, bot_text)
        return {
            "bot_text": bot_text,
            "emotion": llm_response["emotion"],
            "action": "tool_response",
            "reminder": None,
            "tool_used": tool_route.intent,
            "tool_result": tool_result,
            "sources": sources,
            "updated_at": updated_at,
        }

    session_obj = mgr.get_session(session_id) if session_id else None
    session_summary = session_obj.summary if session_obj else None
    context_str = _build_conversation_context(context_turns, session_summary)
    llm_response = await generate_keobot_response(
        resolved_text,
        memory_context=memory_context,
        conversation_context=context_str or None,
    )
    bot_text = llm_response["bot_text"]
    if session_id:
        mgr.add_bot_turn(session_id, bot_text)
    return {
        "bot_text": bot_text,
        "emotion": llm_response["emotion"],
        "action": None,
        "reminder": None,
        "tool_used": "none",
        "tool_result": None,
        "sources": [],
        "updated_at": None,
    }


_KNOWLEDGE_TRIGGERS = (
    "tài liệu", "trong file", "trong document", "trong ghi chú", "trong note",
    "dựa trên tài liệu", "dựa trên file", "dựa trên ghi chú",
    "tìm trong tài liệu", "hỏi tài liệu", "cv của tôi", "hồ sơ của tôi",
    "local document", "my document", "my notes", "my file",
)


def _detect_knowledge_query(user_text: str) -> dict | None:
    lower = user_text.lower()
    triggered = any(kw in lower for kw in _KNOWLEDGE_TRIGGERS)
    if not triggered:
        return None

    store = get_knowledge_store()
    docs = store.list_documents()
    if not docs:
        return {
            "bot_text": "Mình chưa có tài liệu nào trong kho local. Bạn hãy import tài liệu trước nhé.",
            "emotion": "neutral",
            "action": None,
            "reminder": None,
            "tool_used": "none",
            "tool_result": None,
            "sources": [],
            "updated_at": None,
        }

    chunks = store.search_chunks(user_text, limit=3)
    if not chunks:
        return {
            "bot_text": "Mình chưa tìm thấy thông tin phù hợp trong tài liệu local của bạn.",
            "emotion": "neutral",
            "action": None,
            "reminder": None,
            "tool_used": "none",
            "tool_result": None,
            "sources": [],
            "updated_at": None,
        }

    context_parts = []
    for c in chunks:
        header = c.get("source_title") or c.get("original_filename", "")
        text = c.get("text", "").strip()[:500]
        if header:
            context_parts.append(f"[{header}]\n{text}")
        else:
            context_parts.append(text)
    context = "\n\n".join(context_parts)

    return {
        "bot_text": f"Mình tìm thấy thông tin sau trong tài liệu của bạn:\n\n{context}\n\n(Bạn có thể hỏi chi tiết hơn bằng cách dùng chức năng 'Hỏi tài liệu' trong phần Knowledge.)",
        "emotion": "thinking",
        "action": None,
        "reminder": None,
        "tool_used": "none",
        "tool_result": None,
        "sources": [],
        "updated_at": None,
    }


def _build_reminder_confirmation(reminder: Reminder) -> str:
    now = datetime.now()
    same_day = reminder.remind_at.date() == now.date()
    if same_day:
        when_text = reminder.remind_at.strftime("%H:%M")
        return f"Duoc roi, minh se nhac ban {reminder.title} luc {when_text}."

    when_text = reminder.remind_at.strftime("%H:%M ngay %d/%m")
    return f"Duoc roi, minh se nhac ban {reminder.title} luc {when_text}."


def _build_memory_confirmation(memory_item: dict[str, Any]) -> str:
    key = str(memory_item["key"])
    value = str(memory_item["value"])
    if key == "user_name":
        return f"Da nho roi, minh se goi ban la {value}."
    if key == "default_city":
        return f"Da nho roi, thanh pho mac dinh cua ban la {value}."
    if key == "default_timezone":
        return f"Da nho roi, mui gio mac dinh cua ban la {value}."
    if key == "default_currency":
        return f"Da nho roi, tien te mac dinh cua ban la {value}."
    if key == "preferred_tts_voice":
        return f"Da nho roi, minh se uu tien giong {value}."
    if key == "answer_style":
        return f"Da nho roi, minh se tra loi theo kieu {value}."
    if key == "preferred_form_of_address":
        return f"Da nho roi, minh se xung ho theo kieu {value}."
    return "Da nho roi."


def _build_memory_delete_confirmation(key: str, deleted: bool) -> str:
    if not deleted:
        return f"Minh khong tim thay bo nho {key} de xoa."
    return f"Da xoa bo nho {key}."


def _apply_memory_defaults(intent: str, entities: dict[str, Any], memory_context: dict[str, str]) -> dict[str, Any]:
    merged = dict(entities)
    if intent == "weather" and not merged.get("location") and memory_context.get("default_city"):
        merged["location"] = memory_context["default_city"]
    if intent == "time" and not merged.get("timezone") and memory_context.get("default_timezone"):
        merged["timezone"] = memory_context["default_timezone"]
    if intent == "currency" and not merged.get("target_currency") and memory_context.get("default_currency"):
        merged["target_currency"] = memory_context["default_currency"]
    return merged


def _run_tool(intent: str, query: str, entities: dict[str, Any]) -> dict[str, Any]:
    if intent == "time":
        return get_time_info(query, entities=entities)
    if intent == "currency":
        return get_currency_info(query, entities=entities)
    if intent == "weather":
        return get_weather_info(query, entities=entities)
    if intent in {"news_search", "general_search"}:
        return get_search_info(query, intent, entities=entities)
    return {
        "is_available": False,
        "message": "Unsupported tool.",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _build_sources(intent: str, tool_result: dict[str, Any]) -> list[dict[str, Any]]:
    if intent in {"news_search", "general_search"}:
        return [
            {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "published_at": result.get("published_at"),
            }
            for result in tool_result.get("results", [])
            if result.get("title") and result.get("url")
        ]

    return []


def _tool_is_unavailable(tool_result: dict[str, Any]) -> bool:
    if tool_result.get("available") is False:
        return True
    if tool_result.get("is_available") is False:
        return True
    return False


def _detect_missing_info(intent: str, entities: dict[str, Any], tool_result: dict[str, Any]) -> str | None:
    if intent == "weather" and not entities.get("location"):
        return "Minh can biet ban muon xem thoi tiet o dau de tra loi."
    if intent == "time" and not entities.get("timezone") and not entities.get("location"):
        return "Minh can biet ban muon xem gio o thanh pho nao."
    if intent == "currency":
        if not entities.get("base_currency") and not entities.get("target_currency"):
            return "Minh can biet ban muon doi tu tien nao sang tien nao."
    return None


class StreamOrchestrator:
    def __init__(self) -> None:
        self._tool_futures: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._started = False

    def subscribe_to_events(self) -> None:
        if self._started:
            return
        self._started = True
        bus = get_event_bus()
        bus.subscribe(EventType.tool_result, self._on_tool_result)

    def _on_tool_result(self, event: Event) -> None:
        session_id = event.session_id
        if session_id and session_id in self._tool_futures:
            future = self._tool_futures.pop(session_id)
            if not future.done():
                future.set_result(event.payload)

    async def wait_for_tool_result(self, session_id: str) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._tool_futures[session_id] = future
        return await future

    def cancel_wait(self, session_id: str) -> None:
        future = self._tool_futures.pop(session_id, None)
        if future and not future.done():
            future.cancel()


_orchestrator: StreamOrchestrator | None = None


def get_orchestrator() -> StreamOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = StreamOrchestrator()
    return _orchestrator


async def stream_chat_response(
    user_text: str,
    session_id: str | None = None,
) -> AsyncIterator[str]:
    if session_id:
        _interrupt_active_stream(session_id)

    bus = get_event_bus()
    stream_mgr = get_stream_manager()
    stream_session = stream_mgr.get_or_create(session_id or "_default")
    stream_session.start()

    resolved_text = user_text
    context_turns: list[dict[str, str]] = []
    mgr = get_conversation_manager()

    if session_id:
        resolved_text = mgr.resolve_follow_up(session_id, user_text)
        mgr.add_user_turn(session_id, resolved_text)
        context_turns = mgr.get_context(session_id, limit=10)
        mgr.touch(session_id)

    bus.publish(Event(type=EventType.stream_start, payload={"text": resolved_text}, session_id=session_id))

    memory_context = get_memory_store().get_memory_context()
    tool_route = detect_tool_intent(resolved_text, context_turns)

    if tool_route.intent != "none" and tool_route.confidence >= TOOL_CONFIDENCE_THRESHOLD:
        orchestrator = get_orchestrator()
        orchestrator.subscribe_to_events()

        bus.publish(Event(type=EventType.tool_call, payload={
            "intent": tool_route.intent,
            "query": tool_route.query,
            "entities": tool_route.entities,
        }, session_id=session_id))

        yield f"{TOOL_EVENT_PREFIX}{json.dumps({'tool': tool_route.intent, 'status': 'running'}, ensure_ascii=False)}"

        async for ch in _yield_thinking(tool_route.intent, cancel_check=stream_session.is_cancelled):
            if stream_session.is_cancelled():
                break
            stream_session.add_token(ch)
            yield ch

        payload = await orchestrator.wait_for_tool_result(session_id or "_default")

        if stream_session.is_cancelled():
            return

        result = payload.get("result")
        error = payload.get("error")
        exec_entities = payload.get("entities", tool_route.entities)

        if result is None or _tool_is_unavailable(result):
            yield f"{TOOL_EVENT_PREFIX}{json.dumps({'tool': tool_route.intent, 'status': 'failed', 'error': error or 'unavailable'}, ensure_ascii=False)}"
            bot_text = _build_tool_unavailable_message(tool_route.intent)
            for ch in bot_text:
                if stream_session.is_cancelled():
                    break
                stream_session.add_token(ch)
                yield ch
            if session_id and not stream_session.is_cancelled():
                mgr.add_bot_turn(session_id, bot_text)
            if stream_session.state == StreamState.streaming:
                stream_session.complete()
            bus.publish(Event(type=EventType.stream_end, payload={"tool": tool_route.intent, "status": "failed"}, session_id=session_id))
            return

        missing = _detect_missing_info(tool_route.intent, exec_entities, result)
        if missing:
            stream_session.transition_to(StreamState.replanning)
            bus.publish(Event(type=EventType.replanning, payload={"tool": tool_route.intent, "reason": "missing_info"}, session_id=session_id))
            yield f"{TOOL_EVENT_PREFIX}{json.dumps({'tool': tool_route.intent, 'status': 'completed', 'missing_info': True}, ensure_ascii=False)}"
            for ch in missing:
                if stream_session.is_cancelled():
                    break
                stream_session.add_token(ch)
                yield ch
            if session_id and not stream_session.is_cancelled():
                mgr.add_bot_turn(session_id, missing)
            if stream_session.state == StreamState.replanning:
                stream_session.complete()
            bus.publish(Event(type=EventType.stream_end, payload={"tool": tool_route.intent, "status": "replanning"}, session_id=session_id))
            return

        sources = _build_sources(tool_route.intent, result)
        updated_at = result.get("updated_at")

        yield f"{TOOL_EVENT_PREFIX}{json.dumps({'tool': tool_route.intent, 'status': 'completed'}, ensure_ascii=False)}"

        session_obj = mgr.get_session(session_id) if session_id else None
        session_summary = session_obj.summary if session_obj else None
        context_str = _build_conversation_context(context_turns, session_summary)

        full_response = ""
        async for token in stream_keobot_tool_response(
            resolved_text, tool_route.intent, result,
            conversation_context=context_str or None,
            cancel_check=stream_session.is_cancelled,
        ):
            if stream_session.is_cancelled():
                break
            stream_session.add_token(token)
            bus.publish(Event(type=EventType.llm_token, payload={"token": token}, session_id=session_id))
            full_response += token
            yield token

        bot_text = ""
        if full_response.strip():
            try:
                parsed = json.loads(full_response)
                bot_text = parsed.get("bot_text", full_response)
            except (json.JSONDecodeError, TypeError):
                bot_text = full_response

        if session_id and not stream_session.is_cancelled() and bot_text.strip():
            mgr.add_bot_turn(session_id, bot_text)

        if stream_session.state == StreamState.streaming:
            stream_session.complete()
        bus.publish(Event(type=EventType.stream_end, payload={"tool": tool_route.intent, "status": "completed"}, session_id=session_id))
        return

    session_obj = mgr.get_session(session_id) if session_id else None
    session_summary = session_obj.summary if session_obj else None
    context_str = _build_conversation_context(context_turns, session_summary)

    async for token in stream_keobot_response(
        resolved_text,
        memory_context=memory_context,
        conversation_context=context_str or None,
        cancel_check=stream_session.is_cancelled,
    ):
        if stream_session.is_cancelled():
            break
        stream_session.add_token(token)
        bus.publish(Event(type=EventType.llm_token, payload={"token": token}, session_id=session_id))
        yield token

    if stream_session.state == StreamState.streaming:
        stream_session.complete()
    bus.publish(Event(type=EventType.stream_end, payload={"status": "completed"}, session_id=session_id))


def _build_tool_unavailable_message(intent: str) -> str:
    if intent == "weather":
        return "Mình chưa được cấu hình công cụ thời tiết."
    if intent in {"news_search", "general_search"}:
        return "Mình chưa được cấu hình công cụ tìm kiếm/cập nhật tin tức."
    return "Mình chưa được cấu hình công cụ cập nhật thông tin này."
