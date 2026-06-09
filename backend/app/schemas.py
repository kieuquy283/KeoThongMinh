from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Emotion = Literal["neutral", "happy", "thinking", "sad", "surprised", "angry", "wink"]
ReminderStatus = Literal["pending", "triggered"]
ChatAction = Literal["reminder_created", "tool_response", "memory_updated", "memory_deleted"]
ToolUsed = Literal["weather", "time", "currency", "news_search", "general_search", "none"]


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "KeoBot Voice Pipeline"


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
    created_at: datetime
    updated_at: datetime


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


class MemoryDeleteResponse(BaseModel):
    ok: bool = True


class MemoryClearResponse(BaseModel):
    ok: bool = True
    deleted: int = 0


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


TextChatResponse.model_rebuild()
VoiceChatResponse.model_rebuild()
