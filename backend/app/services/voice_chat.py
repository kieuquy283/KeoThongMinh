from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import UploadFile

from app.config import get_settings
from app.providers.stt import transcribe_audio
from app.providers.tts import synthesize_speech
from app.schemas import ReminderResponse, ToolSource
from app.services.chat_flow import generate_chat_response

ALLOWED_AUDIO_SUFFIXES = {".webm", ".wav", ".mp3", ".m4a", ".ogg", ".mp4"}


async def _save_upload(audio_file: UploadFile) -> tuple[Path, str]:
    settings = get_settings()
    upload_dir = Path(__file__).resolve().parents[2] / "tmp" / "voice_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    original_suffix = Path(audio_file.filename or "").suffix.lower()
    suffix = original_suffix if original_suffix in ALLOWED_AUDIO_SUFFIXES else ".webm"
    temp_path = upload_dir / f"{uuid4().hex}{suffix}"

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    total_bytes = 0

    async with aiofiles.open(temp_path, "wb") as out_file:
        while True:
            chunk = await audio_file.read(1024 * 1024)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                raise ValueError(f"Audio upload vuot qua gioi han {settings.max_upload_size_mb}MB.")
            await out_file.write(chunk)

    return temp_path, suffix


async def run_voice_chat(audio_file: UploadFile) -> dict[str, object]:
    settings = get_settings()
    temp_path: Path | None = None

    try:
        temp_path, _ = await _save_upload(audio_file)
        user_text = await transcribe_audio(str(temp_path))
        chat_response = await generate_chat_response(user_text)

        audio_dir = Path(__file__).resolve().parents[1] / "static" / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        generated_name = f"response_{uuid4().hex}.mp3"
        generated_path = audio_dir / generated_name

        await synthesize_speech(chat_response["bot_text"], str(generated_path))

        return {
            "user_text": user_text,
            "bot_text": chat_response["bot_text"],
            "audio_url": f"http://localhost:{settings.backend_port}/static/audio/{generated_name}",
            "emotion": chat_response["emotion"],
            "action": chat_response["action"],
            "reminder": ReminderResponse.model_validate(chat_response["reminder"]).model_dump() if chat_response["reminder"] else None,
            "tool_used": chat_response["tool_used"],
            "tool_result": chat_response["tool_result"],
            "sources": [ToolSource.model_validate(source).model_dump() for source in chat_response["sources"]],
            "updated_at": chat_response["updated_at"],
        }
    finally:
        await audio_file.close()
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
