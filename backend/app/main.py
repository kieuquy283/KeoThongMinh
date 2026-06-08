from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.providers.llm import generate_keobot_response
from app.schemas import HealthResponse, TextChatRequest, TextChatResponse, VoiceChatResponse
from app.services.voice_chat import run_voice_chat

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
    return HealthResponse()


@app.post("/text-chat", response_model=TextChatResponse)
async def text_chat(payload: TextChatRequest) -> TextChatResponse:
    try:
        llm_response = await generate_keobot_response(payload.message)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return TextChatResponse(
        user_text=payload.message,
        bot_text=llm_response["bot_text"],
        emotion=llm_response["emotion"],
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
