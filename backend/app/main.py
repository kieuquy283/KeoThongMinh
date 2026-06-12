from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app import data_paths
from app.data_paths import ensure_data_dirs, get_static_dir
from app.schemas import (
    DocumentContentResponse,
    HealthResponse,
    ImportPathRequest,
    KnowledgeAnswerResponse,
    KnowledgeChunk,
    KnowledgeClearRequest,
    KnowledgeDocument,
    KnowledgeExportResponse,
    KnowledgeExportRecord,
    KnowledgeImportRequest,
    KnowledgeImportResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResult,
    MemoryClearResponse,
    MemoryContextResponse,
    MemoryDeleteResponse,
    MemoryExportResponse,
    MemoryExportRecord,
    MemoryImportRequest,
    MemoryImportResponse,
    MemoryItemResponse,
    MemoryUpdateRequest,
    MemoryUpsertRequest,
    ReminderCreateRequest,
    ReminderDeleteResponse,
    ReminderResponse,
    ResetPersonalDataResponse,
    TextChatRequest,
    TextChatResponse,
    ToolTestRequest,
    ToolTestResponse,
    ToolProviderStatus,
    ToolSource,
    ToolsStatusResponse,
    VoiceChatResponse,
)
from app.services.chat_flow import generate_chat_response, stream_chat_response
from app.services.document_importer import import_document
from app.services.event_bus import Event, EventType, get_event_bus
from app.services.stream_manager import StreamState, get_stream_manager
from fastapi.responses import StreamingResponse
from app.services.entity_extractor import extract_entities
from app.services.knowledge_store import get_knowledge_store
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_periodic_session_cleanup())
    yield
    task.cancel()


async def _periodic_session_cleanup() -> None:
    from app.services.conversation_context import get_conversation_manager
    from app.services.voice_session_manager import cleanup_session, get_active_session_ids
    while True:
        await asyncio.sleep(300)
        try:
            mgr = get_conversation_manager()
            mgr.force_cleanup()
            for sid in get_active_session_ids():
                cleanup_session(sid)
        except Exception:
            logger = logging.getLogger("keobot.session_cleanup")
            logger.exception("Session cleanup error")


app = FastAPI(title=settings.app_name, lifespan=lifespan)

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

ensure_data_dirs()
static_dir = get_static_dir()
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


@app.get("/memory/export", response_model=MemoryExportResponse)
async def export_memory() -> MemoryExportResponse:
    store = get_memory_store()
    items = store.list_memory()
    def _parse_dt(raw: str | None) -> str:
        if not raw:
            return ""
        try:
            return datetime.fromisoformat(raw).isoformat()
        except (ValueError, TypeError):
            return raw
    records = [
        MemoryExportRecord(
            key=item["key"],
            value=item["value"],
            category=item["category"],
            source=item["source"],
            confidence=item["confidence"],
            is_enabled=item["is_enabled"],
            created_at=_parse_dt(item.get("created_at")),
            updated_at=_parse_dt(item.get("updated_at")),
            last_used_at=_parse_dt(item.get("last_used_at")) or None,
        )
        for item in items
    ]
    return MemoryExportResponse(
        exported_at=datetime.now(timezone.utc).isoformat(),
        records=records,
    )


@app.post("/memory/import", response_model=MemoryImportResponse)
async def import_memory(payload: MemoryImportRequest) -> MemoryImportResponse:
    store = get_memory_store()
    result = store.import_memories(
        records=[r.model_dump() for r in payload.records],
        mode=payload.mode,
    )
    return MemoryImportResponse(
        records_found=result["records_found"],
        records_added=result["records_added"],
        records_updated=result["records_updated"],
        records_invalid=result["records_invalid"],
        errors=result.get("errors", []),
    )


@app.delete("/memory", response_model=MemoryClearResponse)
async def clear_memory() -> MemoryClearResponse:
    deleted = get_memory_store().clear_memory()
    return MemoryClearResponse(deleted=deleted)


@app.post("/personal-data/reset", response_model=ResetPersonalDataResponse)
async def reset_personal_data() -> ResetPersonalDataResponse:
    import shutil
    memory_deleted = get_memory_store().clear_memory()
    reminders = get_reminder_store().clear_reminders()
    temp_deleted = 0
    docs_deleted = 0
    idx_deleted = 0
    temp_dir = data_paths.get_temp_dir()
    if temp_dir.exists():
        for child in temp_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
            temp_deleted += 1
    docs_dir = data_paths.get_documents_dir()
    if docs_dir.exists():
        for child in docs_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
            docs_deleted += 1
    idx_dir = data_paths.get_indexes_dir()
    if idx_dir.exists():
        for child in idx_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
            idx_deleted += 1
    return ResetPersonalDataResponse(
        memory_deleted=memory_deleted,
        reminders_deleted=reminders,
        temp_files_deleted=temp_deleted,
        documents_deleted=docs_deleted,
        indexes_deleted=idx_deleted,
    )


@app.get("/knowledge/documents", response_model=list[KnowledgeDocument])
async def list_knowledge_documents() -> list[KnowledgeDocument]:
    return [KnowledgeDocument(**d) for d in get_knowledge_store().list_documents()]


@app.post("/knowledge/documents/import")
async def import_knowledge_document(file: UploadFile = File(...)) -> dict[str, Any]:
    from app.data_paths import get_temp_dir
    temp_dir = get_temp_dir()
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / (file.filename or "upload")
    try:
        content = await file.read()
        temp_path.write_bytes(content)
        result = import_document(temp_path, source_name=file.filename)
        return result
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


@app.post("/knowledge/documents/import-path")
async def import_knowledge_document_from_path(payload: ImportPathRequest) -> dict[str, Any]:
    result = import_document(payload.path)
    return result


@app.delete("/knowledge/documents/{document_id}")
async def delete_knowledge_document(document_id: int) -> dict[str, Any]:
    deleted = get_knowledge_store().delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"ok": True, "document_id": document_id}


@app.post("/knowledge/search", response_model=KnowledgeSearchResult)
async def search_knowledge(
    query: str = "",
    limit: int = 5,
    mode: str = "hybrid",
    payload: KnowledgeSearchRequest | None = None,
) -> KnowledgeSearchResult:
    if payload is not None:
        query = payload.query
        limit = payload.limit
        mode = payload.mode
    if mode not in ("keyword", "semantic", "hybrid"):
        mode = "hybrid"
    chunks = get_knowledge_store().hybrid_search_chunks(query, limit=limit, mode=mode)
    return KnowledgeSearchResult(
        query=query,
        results=[KnowledgeChunk(**c) for c in chunks],
        total=len(chunks),
    )


@app.post("/knowledge/ask", response_model=KnowledgeAnswerResponse)
async def ask_knowledge(
    query: str,
    mode: str = "hybrid",
) -> KnowledgeAnswerResponse:
    from app.services.knowledge_query import answer_from_knowledge
    if mode not in ("keyword", "semantic", "hybrid"):
        mode = "hybrid"
    result = await answer_from_knowledge(query, mode=mode)
    return KnowledgeAnswerResponse(**result)


@app.delete("/knowledge")
async def clear_knowledge(payload: KnowledgeClearRequest | None = None) -> dict[str, Any]:
    if payload and not payload.confirm:
        return {"ok": False, "error": "Confirmation required. Set confirm=true to clear all knowledge."}
    deleted = get_knowledge_store().clear_knowledge_base()
    logger = logging.getLogger("keobot.knowledge")
    logger.info("Knowledge base cleared via API: %d documents", deleted)
    return {"ok": True, "documents_deleted": deleted}


@app.get("/knowledge/documents/{document_id}/content", response_model=DocumentContentResponse)
async def get_knowledge_document_content(document_id: int) -> DocumentContentResponse:
    store = get_knowledge_store()
    doc = store.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    content = store.get_document_text(document_id)
    if content is None:
        raise HTTPException(status_code=404, detail="No content found for this document.")
    return DocumentContentResponse(
        id=doc["id"],
        original_filename=doc["original_filename"],
        file_type=doc["file_type"],
        content=content,
    )


@app.get("/knowledge/export", response_model=KnowledgeExportResponse)
async def export_knowledge() -> KnowledgeExportResponse:
    from datetime import datetime, timezone
    store = get_knowledge_store()
    documents = store.list_documents()
    records = []
    for doc in documents:
        doc_id = doc["id"]
        chunks = store.get_chunks_for_document(doc_id)
        records.append(
            KnowledgeExportRecord(
                document=KnowledgeDocument(**doc),
                chunks=[KnowledgeChunk(**c) for c in chunks],
            )
        )
    return KnowledgeExportResponse(
        exported_at=datetime.now(timezone.utc).isoformat(),
        records=records,
    )


@app.post("/knowledge/import", response_model=KnowledgeImportResponse)
async def import_knowledge(payload: KnowledgeImportRequest) -> KnowledgeImportResponse:
    from app.services.document_importer import import_document
    store = get_knowledge_store()
    errors: list[str] = []
    docs_found = len(payload.records)
    docs_imported = 0
    chunks_imported = 0
    for record in payload.records:
        doc_data = record.document.model_dump()
        existing = store.get_document_by_sha256(doc_data["sha256"])
        if existing is not None:
            if payload.mode == "replace":
                store.delete_document(existing["id"])
            else:
                errors.append(
                    f"Duplicate document: {doc_data['original_filename']} (SHA256: {doc_data['sha256'][:12]}...)"
                )
                continue
        from app.data_paths import get_documents_dir
        import hashlib
        import uuid
        ext = f".{doc_data['file_type']}"
        safe_name = f"{uuid.uuid4().hex}{ext}"
        from pathlib import Path
        stored_path = get_documents_dir() / safe_name
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        chunk_texts = [c.text for c in record.chunks]
        full_text = "\n\n".join(chunk_texts)
        raw_bytes = full_text.encode("utf-8")
        stored_path.write_bytes(raw_bytes)
        doc = store.add_document(
            filename=safe_name,
            original_filename=doc_data["original_filename"],
            file_type=doc_data["file_type"],
            size_bytes=doc_data.get("size_bytes", len(raw_bytes)),
            sha256=doc_data["sha256"],
            stored_path=str(stored_path),
        )
        doc_id = doc["id"]
        chunks_data = [
            {
                "text": c.text,
                "source_title": c.source_title or doc_data["original_filename"],
                "source_location": c.source_location,
                "token_estimate": c.token_estimate,
            }
            for c in record.chunks
        ]
        store.add_chunks(doc_id, chunks_data)
        docs_imported += 1
        chunks_imported += len(record.chunks)
    log = logging.getLogger("keobot.knowledge")
    log.info(
        "Knowledge import: found=%d imported=%d chunks=%d errors=%d",
        docs_found, docs_imported, chunks_imported, len(errors),
    )
    return KnowledgeImportResponse(
        documents_found=docs_found,
        documents_imported=docs_imported,
        chunks_imported=chunks_imported,
        errors=errors,
    )


@app.post("/reminders/{reminder_id}/triggered", response_model=ReminderResponse)
async def mark_reminder_triggered(reminder_id: int) -> ReminderResponse:
    reminder = get_reminder_store().mark_triggered(reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail="Reminder not found.")
    return ReminderResponse.model_validate(reminder)


@app.post("/text-chat", response_model=TextChatResponse)
async def text_chat(payload: TextChatRequest) -> TextChatResponse:
    bus = get_event_bus()
    bus.publish(Event(type=EventType.user_message, payload={"text": payload.message}, session_id=payload.session_id))
    try:
        chat_response = await generate_chat_response(payload.message, session_id=payload.session_id)
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


async def _stream_events(payload: TextChatRequest):
    async for token in stream_chat_response(payload.message, session_id=payload.session_id):
        yield f"data: {token}\n\n"


@app.post("/text-chat/stream")
async def text_chat_stream(payload: TextChatRequest):
    bus = get_event_bus()
    bus.publish(Event(type=EventType.user_message, payload={"text": payload.message}, session_id=payload.session_id))
    stream_mgr = get_stream_manager()
    stream_mgr.get_or_create(payload.session_id or "_default")
    return StreamingResponse(
        _stream_events(payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/stream/{session_id}/cancel")
async def cancel_stream(session_id: str):
    stream_mgr = get_stream_manager()
    session = stream_mgr.get_session(session_id)
    if session is None or session.state not in (StreamState.streaming, StreamState.replanning):
        raise HTTPException(status_code=404, detail="No active stream found for this session.")
    bus = get_event_bus()
    bus.publish(Event(type=EventType.cancel, payload={}, session_id=session_id))
    state = session.state
    return {
        "ok": True,
        "session_id": session_id,
        "state": state,
        "cancelled_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/voice-chat", response_model=VoiceChatResponse)
async def voice_chat(
    audio: UploadFile = File(...),
    session_id: str | None = None,
) -> VoiceChatResponse:
    try:
        result = await run_voice_chat(audio, session_id=session_id)
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


@app.post("/sessions/cleanup")
async def cleanup_sessions():
    from app.services.conversation_context import get_conversation_manager
    mgr = get_conversation_manager()
    before = mgr.get_active_session_count()
    mgr.force_cleanup()
    voice_ids = get_active_session_ids()
    for sid in voice_ids:
        cleanup_session(sid)
    return {
        "conversation_sessions_before": before,
        "conversation_sessions_after": mgr.get_active_session_count(),
        "voice_sessions_cleaned": len(voice_ids),
        "cleaned_at": datetime.now(timezone.utc).isoformat(),
    }


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
