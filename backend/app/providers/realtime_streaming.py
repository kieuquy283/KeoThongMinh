from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import tempfile
from typing import Any, AsyncIterator

logger = logging.getLogger("keobot.realtime")

# Realtime API system prompt in Vietnamese
REALTIME_SYSTEM_PROMPT = (
    "Bạn là Kẹo Thông Minh, một trợ lý AI tiếng Việt thân thiện, thông minh và hài hước. "
    "Bạn trả lời tự nhiên, ngắn gọn, dễ hiểu. Ưu tiên tiếng Việt. "
    "Nếu người dùng hỏi học tập hoặc kỹ thuật, hãy giải thích từng bước. "
    "Nếu không chắc, hãy hỏi lại nhẹ nhàng. Không trả lời quá dài nếu câu hỏi đơn giản."
)


class OpenAIRealtimeProvider:
    """Async client for OpenAI Realtime API over WebSockets."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-realtime-preview-2024-12-17",
        instructions: str = REALTIME_SYSTEM_PROMPT,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.instructions = instructions
        self.ws: Any = None
        self._connected = False
        self._receive_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._receive_task: asyncio.Task[Any] | None = None

    async def connect(self) -> None:
        try:
            import websockets
        except ImportError as exc:
            raise RuntimeError("Package 'websockets' is required for realtime streaming. Install: pip install websockets") from exc

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1",
        }
        url = f"wss://api.openai.com/v1/realtime?model={self.model}"

        self.ws = await websockets.connect(url, extra_headers=headers)
        self._connected = True
        self._receive_task = asyncio.create_task(self._receive_loop())
        logger.info("Connected to OpenAI Realtime API (model=%s)", self.model)

    async def _receive_loop(self) -> None:
        while self._connected:
            try:
                raw = await self.ws.recv()
                data = json.loads(raw)
                await self._receive_queue.put(data)
            except Exception as exc:
                if self._connected:
                    logger.warning("Realtime receive loop ended: %s", exc)
                break

    async def configure_session(self) -> None:
        if not self._connected or not self.ws:
            return
        payload = {
            "type": "session.update",
            "session": {
                "turn_detection": {"type": "server_vad"},
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "voice": "alloy",
                "instructions": self.instructions,
                "modalities": ["text", "audio"],
            },
        }
        await self.ws.send(json.dumps(payload))
        logger.info("Realtime session configured")

    async def send_audio(self, base64_pcm16: str) -> None:
        if not self._connected or not self.ws:
            return
        await self.ws.send(
            json.dumps({
                "type": "input_audio_buffer.append",
                "audio": base64_pcm16,
            })
        )

    async def receive(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            data = await self._receive_queue.get()
            event_type = data.get("type", "")

            if event_type == "response.audio.delta":
                yield {"type": "audio", "data": data.get("delta", "")}
            elif event_type == "response.audio_transcript.delta":
                yield {"type": "text", "data": data.get("delta", "")}
            elif event_type == "response.done":
                yield {"type": "done"}
            elif event_type == "error":
                yield {"type": "error", "data": data.get("error", {})}
            elif event_type == "session.updated":
                logger.info("Realtime session.updated received")

    async def interrupt(self) -> None:
        if not self._connected or not self.ws:
            return
        await self.ws.send(json.dumps({"type": "response.cancel"}))
        logger.info("Sent response.cancel to Realtime API")

    async def disconnect(self) -> None:
        self._connected = False
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            await self.ws.close()
            logger.info("Disconnected from OpenAI Realtime API")


class WebmToPCM16Converter:
    """Buffer webm/opus chunks and convert to PCM16 24kHz mono via ffmpeg."""

    def __init__(self, flush_interval_chunks: int = 3) -> None:
        self._buffer: list[str] = []
        self._lock = asyncio.Lock()
        self._flush_interval = flush_interval_chunks
        self._ffmpeg_available = self._check_ffmpeg()
        if not self._ffmpeg_available:
            logger.warning("ffmpeg not found in PATH. Realtime streaming will not work.")

    @staticmethod
    def _check_ffmpeg() -> bool:
        import shutil
        return shutil.which("ffmpeg") is not None

    async def add_chunk(self, base64_webm: str) -> list[str] | None:
        """Add a chunk. Returns list of base64 PCM16 chunks if buffer is ready to flush."""
        async with self._lock:
            self._buffer.append(base64_webm)
            if len(self._buffer) >= self._flush_interval:
                chunks_to_convert = self._buffer[: self._flush_interval]
                self._buffer = self._buffer[self._flush_interval :]
                return chunks_to_convert
            return None

    async def flush_all(self) -> str | None:
        """Convert all remaining buffered chunks."""
        async with self._lock:
            if not self._buffer:
                return None
            chunks_to_convert = self._buffer
            self._buffer = []
            return await self._convert_chunks(chunks_to_convert)

    async def _convert_chunks(self, base64_chunks: list[str]) -> str | None:
        if not self._ffmpeg_available:
            return None
        if not base64_chunks:
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
                "-y",
                "-i",
                tmp_in_path,
                "-f",
                "s16le",
                "-ar",
                "24000",
                "-ac",
                "1",
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
