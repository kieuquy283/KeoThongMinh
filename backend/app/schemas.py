from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Emotion = Literal["neutral", "happy", "thinking", "sad", "surprised", "angry", "wink"]
ReminderStatus = Literal["pending", "triggered"]
ChatAction = Literal["reminder_created", "tool_response", "memory_updated", "memory_deleted"]
ToolUsed = Literal["weather", "time", "currency", "news_search", "general_search", "none"]


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "Kẹo Thông Minh Voice Pipeline"
    version: str = "0.3.0"
    mode: str = "local_mock"


class TextChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class TextChatResponse(BaseModel):
    user_text: str
    bot_text: str
    emotion: Emotion
    action: ChatAction | None = None
    reminder: "ReminderResponse | None" = None
    tool_used: ToolUsed = "none"
    tool_result: dict[str, Any] | None = None
    sources: list["ToolSource"] = Field(default_factory=list)
    updated_at: datetime | None = None


class VoiceChatResponse(BaseModel):
    user_text: str
    bot_text: str
    audio_url: str
    emotion: Emotion
    action: ChatAction | None = None
    reminder: "ReminderResponse | None" = None
    tool_used: ToolUsed = "none"
    tool_result: dict[str, Any] | None = None
    sources: list["ToolSource"] = Field(default_factory=list)
    updated_at: datetime | None = None


class KeoBotLLMResponse(BaseModel):
    bot_text: str
    emotion: Emotion = "neutral"


class ReminderCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    remind_at: datetime


class ReminderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    remind_at: datetime
    status: ReminderStatus
    created_at: datetime
    triggered_at: datetime | None


class ReminderDeleteResponse(BaseModel):
    ok: bool = True


class MemoryItemResponse(BaseModel):
    key: str
    value: str
    category: str = "preference"
    source: str = "explicit_user_request"
    confidence: float = 1.0
    is_enabled: bool = True
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None = None


class MemoryUpsertRequest(BaseModel):
    key: Literal[
        "user_name",
        "preferred_form_of_address",
        "default_city",
        "default_timezone",
        "default_currency",
        "preferred_tts_voice",
        "answer_style",
    ]
    value: str = Field(min_length=1, max_length=200)
    category: str = Field(default="preference", min_length=1, max_length=100)


class MemoryUpdateRequest(BaseModel):
    value: str | None = None
    category: str | None = None
    is_enabled: bool | None = None


class MemoryDeleteResponse(BaseModel):
    ok: bool = True


class MemoryClearResponse(BaseModel):
    ok: bool = True
    deleted: int = 0


class MemoryContextResponse(BaseModel):
    context: dict[str, str]


class MemoryExportRecord(BaseModel):
    key: str
    value: str
    category: str
    source: str
    confidence: float
    is_enabled: bool
    created_at: str
    updated_at: str
    last_used_at: str | None = None


class MemoryExportResponse(BaseModel):
    schema_version: int = 1
    exported_at: str
    app_version: str = ""
    records: list[MemoryExportRecord]


_SECRET_KEY_PATTERNS = {
    "api_key", "apikey", "secret", "password", "token", "auth",
}


class MemoryImportRecord(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=200)
    category: str = Field(default="preference", max_length=100)
    source: str = Field(default="import", max_length=100)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_enabled: bool = True

    @field_validator("key")
    @classmethod
    def check_not_secret(cls, value: str) -> str:
        lower = value.lower().replace("-", "_")
        if any(pattern in lower for pattern in _SECRET_KEY_PATTERNS):
            raise ValueError(f"Key '{value}' looks like a secret and cannot be imported as memory.")
        return value


class MemoryImportRequest(BaseModel):
    records: list[MemoryImportRecord]
    mode: Literal["merge", "replace"] = "merge"


class MemoryImportResponse(BaseModel):
    ok: bool = True
    records_found: int = 0
    records_added: int = 0
    records_updated: int = 0
    records_invalid: int = 0
    errors: list[str] = Field(default_factory=list)


class ResetPersonalDataResponse(BaseModel):
    ok: bool = True
    memory_deleted: int = 0
    reminders_deleted: int = 0
    temp_files_deleted: int = 0
    documents_deleted: int = 0
    indexes_deleted: int = 0


class ToolProviderStatus(BaseModel):
    provider: str
    configured: bool
    live: bool | None = None
    status: Literal[
        "ok",
        "not_configured",
        "invalid_key",
        "network_error",
        "rate_limited",
        "unknown_error",
    ] = "unknown_error"
    message: str = ""
    last_checked_at: datetime | None = None


class ToolsStatusResponse(BaseModel):
    weather: ToolProviderStatus
    search: ToolProviderStatus
    currency: ToolProviderStatus


class ToolTestRequest(BaseModel):
    tool: Literal["weather", "search", "currency", "time"]
    sample_query: str = Field(min_length=1, max_length=4000)


class ToolTestResponse(BaseModel):
    tool: Literal["weather", "search", "currency", "time"]
    status: Literal[
        "ok",
        "not_configured",
        "invalid_key",
        "network_error",
        "rate_limited",
        "unknown_error",
    ]
    message: str
    sample_result: dict[str, Any] | None = None
    checked_at: datetime


class ToolSource(BaseModel):
    title: str
    url: str
    published_at: datetime | None = None


class KnowledgeDocument(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: str
    size_bytes: int
    sha256: str
    stored_path: str
    status: str
    created_at: str
    updated_at: str
    chunk_count: int
    error_message: str | None = None


class KnowledgeChunk(BaseModel):
    id: int
    document_id: int
    chunk_index: int
    text: str
    source_title: str | None = None
    source_location: str | None = None
    token_estimate: int = 0
    created_at: str
    document_filename: str = ""
    document_original_filename: str = ""


class KnowledgeSearchResult(BaseModel):
    query: str
    results: list[KnowledgeChunk]
    total: int = 0


class KnowledgeAnswerResponse(BaseModel):
    query: str
    answer: str
    sources: list[KnowledgeChunk] = Field(default_factory=list)
    has_sufficient_context: bool = False


class KnowledgeClearRequest(BaseModel):
    confirm: bool = False


class ImportPathRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


TextChatResponse.model_rebuild()
VoiceChatResponse.model_rebuild()
