from __future__ import annotations

import asyncio
from pathlib import Path

from app.config import get_settings


async def _transcribe_with_openai(file_path: str) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("Thiếu OPENAI_API_KEY cho STT provider openai.")

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file audio: {file_path}")

    def _do_transcribe() -> str:
        with path.open("rb") as audio_file:
            result = client.audio.transcriptions.create(
                model=settings.openai_stt_model,
                file=audio_file,
            )
        text = getattr(result, "text", "") or ""
        return text.strip()

    return await asyncio.to_thread(_do_transcribe)


async def _transcribe_with_dashscope(file_path: str) -> str:
    settings = get_settings()
    if not settings.dashscope_api_key:
        raise RuntimeError("Thiếu DASHSCOPE_API_KEY cho STT provider dashscope.")

    from openai import OpenAI

    client = OpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file audio: {file_path}")

    def _do_transcribe() -> str:
        with path.open("rb") as audio_file:
            result = client.audio.transcriptions.create(
                model=settings.dashscope_stt_model,
                file=audio_file,
            )
        text = getattr(result, "text", "") or ""
        return text.strip()

    return await asyncio.to_thread(_do_transcribe)


async def transcribe_audio(file_path: str) -> str:
    settings = get_settings()
    provider = settings.stt_provider.lower()

    if provider in {"mock", "local"}:
        transcript = settings.mock_stt_text.strip()
        if not transcript:
            raise ValueError("Không nhận diện được giọng nói.")
        return transcript

    if provider == "openai":
        try:
            text = await _transcribe_with_openai(file_path)
        except Exception as exc:
            raise RuntimeError(f"STT thất bại: {exc}") from exc

        if not text:
            raise ValueError("Không nhận diện được giọng nói.")
        return text

    if provider == "dashscope" or provider.startswith("qwen"):
        try:
            text = await _transcribe_with_dashscope(file_path)
        except Exception as exc:
            raise RuntimeError(f"STT thất bại: {exc}") from exc

        if not text:
            raise ValueError("Không nhận diện được giọng nói.")
        return text

    raise RuntimeError(f"STT_PROVIDER không được hỗ trợ: {settings.stt_provider}")
