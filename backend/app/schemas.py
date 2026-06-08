from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Emotion = Literal["neutral", "happy", "thinking", "sad", "surprised", "angry", "wink"]


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "KeoBot Voice Pipeline"


class TextChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class TextChatResponse(BaseModel):
    user_text: str
    bot_text: str
    emotion: Emotion


class VoiceChatResponse(BaseModel):
    user_text: str
    bot_text: str
    audio_url: str
    emotion: Emotion


class KeoBotLLMResponse(BaseModel):
    bot_text: str
    emotion: Emotion = "neutral"
