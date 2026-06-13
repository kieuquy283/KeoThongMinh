from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import tempfile
from typing import Any, AsyncIterator

from app.config import get_settings
from app.providers.llm_stream import stream_keobot_text_raw
from app.providers.stt import transcribe_audio
from app.providers.tts import synthesize_speech

logger = logging.getLogger("keobot.streaming_pipeline")

# Sentence delimiters for Vietnamese
_SENTENCE_DELIMITERS = frozenset(".?!。，,;:；？！")


def _is_sentence_end(text: str) -> bool:
    """Check if text ends with a sentence delimiter."""
    if not text:
        return False
    return text[-1] in _SENTENCE_DELIMITERS


class StreamingPipeline:
    """End-to-end streaming pipeline: STT -> LLM streaming -> TTS sentence-by-sentence.

    Optimised for low latency:
    - Text tokens are streamed to the frontend immediately.
    - Sentences are buffered and TTS is triggered as soon as a sentence is complete.
    - TTS tasks run concurrently (overlap with LLM streaming).
    - Audio chunks are sent back as soon as each TTS task completes.
    """

    def __init__(self) -> None:
        self._cancelled = False
        self._audio_buffer: list[str] = []
        self._converter = WebmToPCM16Converter()

    async def add_audio_chunk(self, base64_webm: str) -> None:
        """Buffer incoming audio chunks."""
        self._audio_buffer.append(base64_webm)

    async def process_turn(self) -> AsyncIterator[dict[str, Any]]:
        """Process the buffered audio into a streaming response.

        Yields:
            {"type": "text", "data": str}   - text token
            {"type": "audio", "data": str}  - base64 audio chunk
            {"type": "done"}                - turn complete
            {"type": "error", "data": str}  - error message
        """
        if not self._audio_buffer:
            return

        # 1. Convert buffered webm chunks to a single file
        full_audio = b"".join(base64.b64decode(c) for c in self._audio_buffer if c)
        self._audio_buffer = []

        if not full_audio:
            return

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
            f.write(full_audio)
            audio_path = f.name

        try:
            # 2. STT (blocking but fast ~0.5-1s)
            user_text = await transcribe_audio(audio_path)
        except Exception as exc:
            logger.error("Streaming STT failed: %s", exc)
            yield {"type": "error", "data": f"STT thất bại: {exc}"}
            return
        finally:
            try:
                os.unlink(audio_path)
            except OSError:
                pass

        if not user_text:
            yield {"type": "error", "data": "Không nhận diện được giọng nói."}
            return

        # 3. LLM streaming + TTS sentence pipeline
        sentence_buffer: list[str] = []
        tts_tasks: list[asyncio.Task[str | None]] = []
        llm_error: Exception | None = None

        try:
            async for token in stream_keobot_text_raw(user_text, cancel_check=lambda: self._cancelled):
                if self._cancelled:
                    return

                # Stream text to frontend immediately
                yield {"type": "text", "data": token}

                # Buffer for sentence splitting
                sentence_buffer.append(token)
                buffer_text = "".join(sentence_buffer)

                # Flush sentence when complete or buffer too large
                if _is_sentence_end(buffer_text) or len(buffer_text) > 80:
                    tts_task = asyncio.create_task(self._tts_sentence(buffer_text))
                    tts_tasks.append(tts_task)
                    sentence_buffer = []

        except Exception as exc:
            llm_error = exc
            logger.error("Streaming LLM failed: %s", exc)
            yield {"type": "error", "data": f"LLM lỗi: {exc}"}

        # TTS final sentence
        if sentence_buffer and not self._cancelled:
            buffer_text = "".join(sentence_buffer)
            tts_task = asyncio.create_task(self._tts_sentence(buffer_text))
            tts_tasks.append(tts_task)

        # Yield audio from completed TTS tasks (in order)
        for tts_task in tts_tasks:
            if self._cancelled:
                tts_task.cancel()
                try:
                    await tts_task
                except asyncio.CancelledError:
                    pass
                continue

            try:
                audio_b64 = await tts_task
                if audio_b64:
                    yield {"type": "audio", "data": audio_b64}
            except Exception as exc:
                logger.error("TTS task failed: %s", exc)

        if not llm_error and not self._cancelled:
            yield {"type": "done"}

    async def _tts_sentence(self, text: str) -> str | None:
        """TTS a single sentence and return base64 audio."""
        if not text.strip():
            return None

        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                output_path = f.name

            await synthesize_speech(text, output_path)

            with open(output_path, "rb") as f:
                audio_data = f.read()

            try:
                os.unlink(output_path)
            except OSError:
                pass

            return base64.b64encode(audio_data).decode()
        except Exception as exc:
            logger.error("TTS sentence failed: %s", exc)
            return None

    def cancel(self) -> None:
        """Cancel the current pipeline."""
        self._cancelled = True

    def reset(self) -> None:
        """Reset pipeline state for a new turn."""
        self._cancelled = False
        self._audio_buffer = []


class WebmToPCM16Converter:
    """Buffer webm/opus chunks and convert to PCM16 24kHz mono via ffmpeg."""

    def __init__(self, flush_interval_chunks: int = 3) -> None:
        self._flush_interval = flush_interval_chunks
        self._ffmpeg_available = self._check_ffmpeg()

    @staticmethod
    def _check_ffmpeg() -> bool:
        import shutil
        return shutil.which("ffmpeg") is not None

    async def _convert_chunks(self, base64_chunks: list[str]) -> str | None:
        if not self._ffmpeg_available or not base64_chunks:
            return None

        webm_data = b"".join(base64.b64decode(c) for c in base64_chunks)
        if not webm_data:
            return None

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_in:
            tmp_in.write(webm_data)
            tmp_in_path = tmp_in.name

        tmp_out_path = tmp_in_path + ".pcm"
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-y", "-i", tmp_in_path,
                "-f", "s16le", "-ar", "24000", "-ac", "1",
                tmp_out_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

            if proc.returncode != 0:
                logger.warning("ffmpeg conversion failed (code=%d)", proc.returncode)
                return None

            with open(tmp_out_path, "rb") as f:
                pcm_data = f.read()

            return base64.b64encode(pcm_data).decode()
        except Exception as exc:
            logger.warning("ffmpeg conversion error: %s", exc)
            return None
        finally:
            try:
                os.unlink(tmp_in_path)
            except OSError:
                pass
            try:
                os.unlink(tmp_out_path)
            except OSError:
                pass
