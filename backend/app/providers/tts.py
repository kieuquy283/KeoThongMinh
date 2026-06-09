from __future__ import annotations

from pathlib import Path

from app.config import get_settings


async def synthesize_speech(text: str, output_path: str) -> str:
    settings = get_settings()
    provider = settings.tts_provider.lower()
    if provider != "edge_tts":
        raise RuntimeError(f"TTS_PROVIDER không được hỗ trợ: {settings.tts_provider}")

    content = text.strip()
    if not content:
        raise ValueError("Không có nội dung để tổng hợp giọng nói.")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    import edge_tts

    communicator = edge_tts.Communicate(
        text=content,
        voice=settings.edge_tts_voice,
        rate=settings.edge_tts_rate,
        volume=settings.edge_tts_volume,
    )
    await communicator.save(str(path))
    return str(path)
