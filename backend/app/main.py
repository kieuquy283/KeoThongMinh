from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.schemas import (
    HealthResponse,
    MemoryClearResponse,
    MemoryContextResponse,
    MemoryDeleteResponse,
    MemoryItemResponse,
    MemoryUpdateRequest,
    MemoryUpsertRequest,
    ReminderCreateRequest,
    ReminderDeleteResponse,
    ReminderResponse,
    TextChatRequest,
    TextChatResponse,
    ToolTestRequest,
    ToolTestResponse,
    ToolProviderStatus,
    ToolSource,
    ToolsStatusResponse,
    VoiceChatResponse,
)
from app.services.chat_flow import generate_chat_response
from app.services.entity_extractor import extract_entities
from app.services.memory_store import get_memory_store
from app.services.tool_router import detect_tool_intent
from app.services.reminder_store import get_reminder_store
from app.services.voice_chat import run_voice_chat
from app.services.voice_session_manager import cancel_session, cleanup_session, create_session, get_active_session_ids, is_cancelled
from app.tools.currency_tool import get_currency_info
from app.tools.search_tool import get_search_info
from app.tools.time_tool import get_time_info
from app.tools.weather_tool import get_weather_info

settings = get_settings()
app = FastAPI(title=settings.app_name)

allowed_origins = {
    settings.frontend_origin,
    settings.frontend_origin.replace("localhost", "127.0.0.1"),
    settings.frontend_origin.replace("127.0.0.1", "localhost"),
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in allowed_origins if origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    stt = settings.stt_provider
    llm = settings.llm_provider
    tts = settings.tts_provider
    mode = f"{stt}_{llm}"
    return HealthResponse(version="0.3.0", mode=mode)


@app.post("/reminders", response_model=ReminderResponse)
async def create_reminder(payload: ReminderCreateRequest) -> ReminderResponse:
    reminder = get_reminder_store().create(payload.title, payload.remind_at)
    return ReminderResponse.model_validate(reminder)


@app.get("/reminders", response_model=list[ReminderResponse])
async def list_reminders() -> list[ReminderResponse]:
    reminders = get_reminder_store().list()
    return [ReminderResponse.model_validate(reminder) for reminder in reminders]


@app.get("/reminders/due", response_model=list[ReminderResponse])
async def list_due_reminders() -> list[ReminderResponse]:
    reminders = get_reminder_store().get_due()
    return [ReminderResponse.model_validate(reminder) for reminder in reminders]


@app.delete("/reminders/{reminder_id}", response_model=ReminderDeleteResponse)
async def delete_reminder(reminder_id: int) -> ReminderDeleteResponse:
    deleted = get_reminder_store().delete(reminder_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Reminder not found.")
    return ReminderDeleteResponse()


@app.get("/memory", response_model=list[MemoryItemResponse])
async def list_memory() -> list[MemoryItemResponse]:
    items = get_memory_store().list_memory()
    return [MemoryItemResponse.model_validate(item) for item in items]


@app.post("/memory", response_model=MemoryItemResponse)
async def upsert_memory(payload: MemoryUpsertRequest) -> MemoryItemResponse:
    item = get_memory_store().set_memory(payload.key, payload.value, payload.category)
    return MemoryItemResponse.model_validate(item)


@app.delete("/memory/{memory_key}", response_model=MemoryDeleteResponse)
async def delete_memory(memory_key: str) -> MemoryDeleteResponse:
    deleted = get_memory_store().delete_memory(memory_key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory item not found.")
    return MemoryDeleteResponse()


@app.patch("/memory/{memory_key}", response_model=MemoryItemResponse)
async def update_memory(memory_key: str, payload: MemoryUpdateRequest) -> MemoryItemResponse:
    store = get_memory_store()
    item = store.update_memory(
        memory_key,
        value=payload.value,
        category=payload.category,
        is_enabled=payload.is_enabled,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Memory item not found.")
    return MemoryItemResponse.model_validate(item)


@app.post("/memory/{memory_key}/enable", response_model=MemoryItemResponse)
async def enable_memory(memory_key: str) -> MemoryItemResponse:
    store = get_memory_store()
    item = store.set_memory_enabled(memory_key, True)
    if item is None:
        raise HTTPException(status_code=404, detail="Memory item not found.")
    return MemoryItemResponse.model_validate(item)


@app.post("/memory/{memory_key}/disable", response_model=MemoryItemResponse)
async def disable_memory(memory_key: str) -> MemoryItemResponse:
    store = get_memory_store()
    item = store.set_memory_enabled(memory_key, False)
    if item is None:
        raise HTTPException(status_code=404, detail="Memory item not found.")
    return MemoryItemResponse.model_validate(item)


@app.get("/memory/context", response_model=MemoryContextResponse)
async def memory_context() -> MemoryContextResponse:
    context = get_memory_store().get_memory_context()
    return MemoryContextResponse(context=context)


@app.delete("/memory", response_model=MemoryClearResponse)
async def clear_memory() -> MemoryClearResponse:
    deleted = get_memory_store().clear_memory()
    return MemoryClearResponse(deleted=deleted)


@app.post("/reminders/{reminder_id}/triggered", response_model=ReminderResponse)
async def mark_reminder_triggered(reminder_id: int) -> ReminderResponse:
    reminder = get_reminder_store().mark_triggered(reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail="Reminder not found.")
    return ReminderResponse.model_validate(reminder)


@app.post("/text-chat", response_model=TextChatResponse)
async def text_chat(payload: TextChatRequest) -> TextChatResponse:
    try:
        chat_response = await generate_chat_response(payload.message)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return TextChatResponse(
        user_text=payload.message,
        bot_text=chat_response["bot_text"],
        emotion=chat_response["emotion"],
        action=chat_response["action"],
        reminder=ReminderResponse.model_validate(chat_response["reminder"]) if chat_response["reminder"] else None,
        tool_used=chat_response["tool_used"],
        tool_result=chat_response["tool_result"],
        sources=[ToolSource.model_validate(source) for source in chat_response["sources"]],
        updated_at=chat_response["updated_at"],
    )


@app.post("/voice-chat", response_model=VoiceChatResponse)
async def voice_chat(audio: UploadFile = File(...)) -> VoiceChatResponse:
    try:
        result = await run_voice_chat(audio)
        return VoiceChatResponse(**result)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.websocket("/ws/voice-turn")
async def voice_turn_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    session_id = create_session()
    try:
        await websocket.send_json({"event": "session_started", "session_id": session_id})
        while True:
            data = await websocket.receive_json()
            action = data.get("action", "")
            if action == "cancel":
                cancel_session(session_id)
                await websocket.send_json({"event": "cancelled", "session_id": session_id})
                break
            if action == "ping":
                await websocket.send_json({"event": "pong", "session_id": session_id})
    except WebSocketDisconnect:
        pass
    finally:
        cleanup_session(session_id)


@app.post("/voice-turn/{session_id}/cancel")
async def cancel_voice_turn(session_id: str):
    cancelled = cancel_session(session_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"ok": True, "session_id": session_id, "cancelled_at": datetime.now(timezone.utc).isoformat()}


@app.get("/voice-turn/sessions")
async def list_voice_sessions():
    return {"active_sessions": get_active_session_ids()}


@app.get("/tools/status", response_model=ToolsStatusResponse)
async def tools_status() -> ToolsStatusResponse:
    checked_at = datetime.now(timezone.utc)
    return ToolsStatusResponse(
        weather=_weather_provider_status(checked_at),
        search=_search_provider_status(checked_at),
        currency=_currency_provider_status(checked_at),
    )


@app.post("/tools/test", response_model=ToolTestResponse)
async def test_tool(payload: ToolTestRequest) -> ToolTestResponse:
    checked_at = datetime.now(timezone.utc)

    if payload.tool == "time":
        entities = extract_entities(payload.sample_query)
        sample_result = get_time_info(payload.sample_query, entities=entities, now=checked_at)
        return ToolTestResponse(
            tool="time",
            status="ok",
            message="Time tool resolved.",
            sample_result=sample_result,
            checked_at=checked_at,
        )

    if payload.tool == "weather":
        entities = extract_entities(payload.sample_query)
        sample_result = get_weather_info(payload.sample_query, entities=entities, now=checked_at)
        return ToolTestResponse(
            tool="weather",
            status=str(sample_result.get("status", "unknown_error")),
            message=str(sample_result.get("message", "Weather tool test completed.")),
            sample_result=sample_result,
            checked_at=checked_at,
        )

    if payload.tool == "currency":
        entities = extract_entities(payload.sample_query)
        sample_result = get_currency_info(payload.sample_query, entities=entities, now=checked_at)
        return ToolTestResponse(
            tool="currency",
            status=str(sample_result.get("status", "unknown_error")),
            message=str(sample_result.get("message", "Currency tool test completed.")),
            sample_result=sample_result,
            checked_at=checked_at,
        )

    route = detect_tool_intent(payload.sample_query)
    sample_result = get_search_info(payload.sample_query, route.intent, entities=route.entities, now=checked_at)
    return ToolTestResponse(
        tool="search",
        status=str(sample_result.get("status", "unknown_error")),
        message=str(sample_result.get("message", "Search tool test completed.")),
        sample_result=sample_result,
        checked_at=checked_at,
    )


def _weather_provider_status(checked_at: datetime) -> ToolProviderStatus:
    weather_provider = settings.weather_provider.lower()
    configured = weather_provider == "openweathermap" and bool(settings.openweather_api_key)
    return ToolProviderStatus(
        provider=weather_provider or "none",
        configured=configured,
        live=False,
        status="ok" if configured else "not_configured",
        message="Weather provider configured." if configured else "Weather provider not configured.",
        last_checked_at=checked_at,
    )


def _search_provider_status(checked_at: datetime) -> ToolProviderStatus:
    search_provider = settings.search_provider.lower()
    configured = (
        (search_provider == "tavily" and bool(settings.tavily_api_key))
        or (search_provider == "serpapi" and bool(settings.serpapi_api_key))
    )
    return ToolProviderStatus(
        provider=search_provider or "none",
        configured=configured,
        live=False,
        status="ok" if configured else "not_configured",
        message="Search provider configured." if configured else "Search provider not configured.",
        last_checked_at=checked_at,
    )


def _currency_provider_status(checked_at: datetime) -> ToolProviderStatus:
    currency_provider = settings.currency_provider.lower()
    live_configured = currency_provider == "exchangerate_api" and bool(settings.exchange_rate_api_url) and bool(settings.exchange_rate_api_key)
    if live_configured:
        return ToolProviderStatus(
            provider=currency_provider,
            configured=True,
            live=True,
            status="ok",
            message="Currency live provider configured.",
            last_checked_at=checked_at,
        )
    return ToolProviderStatus(
        provider=currency_provider if currency_provider == "exchangerate_api" else "demo",
        configured=currency_provider != "exchangerate_api",
        live=False,
        status="ok" if currency_provider != "exchangerate_api" else "not_configured",
        message="Demo rate, not live." if currency_provider != "exchangerate_api" else "Currency live provider not configured.",
        last_checked_at=checked_at,
    )
