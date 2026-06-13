from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import tempfile
from typing import Any, AsyncIterator

from app.config import get_settings
from app.providers.llm_stream import stream_keobot_text_raw, stream_keobot_tool_response
from app.providers.stt import transcribe_audio
from app.providers.tts import synthesize_speech
from app.services.conversation_context import get_conversation_manager
from app.services.entity_extractor import extract_entities
from app.services.memory_store import get_memory_store
from app.services.reminder_parser import parse_reminder_text
from app.services.reminder_store import get_reminder_store
from app.services.tool_router import TOOL_CONFIDENCE_THRESHOLD, detect_tool_intent
from app.tools.currency_tool import get_currency_info
from app.tools.search_tool import get_search_info
from app.tools.time_tool import get_time_info
from app.tools.weather_tool import get_weather_info

logger = logging.getLogger("keobot.streaming_pipeline")

# Sentence delimiters for Vietnamese
_SENTENCE_DELIMITERS = frozenset(".?!。，,;:；？！")


async def _text_async_iterator(text: str) -> AsyncIterator[str]:
    """Yield each character of text as a token for TTS pipeline compatibility."""
    for ch in text:
        yield ch


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

    def __init__(self, session_id: str | None = None) -> None:
        self._cancelled = False
        self._audio_buffer: list[str] = []
        self._converter = WebmToPCM16Converter()
        self.session_id = session_id

    async def add_audio_chunk(self, base64_webm: str) -> None:
        """Buffer incoming audio chunks."""
        self._audio_buffer.append(base64_webm)

    async def process_turn(self) -> AsyncIterator[dict[str, Any]]:
        """Process the buffered audio into a streaming response.

        Yields:
            {"type": "user_text", "data": str}  - transcribed user text
            {"type": "text", "data": str}       - text token
            {"type": "audio", "data": str}      - base64 audio chunk
            {"type": "action", "data": json}    - action event (reminder_created, system_command)
            {"type": "done"}                    - turn complete
            {"type": "error", "data": str}      - error message
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

        # Yield transcribed text so frontend can display it
        yield {"type": "user_text", "data": user_text}

        # 3. Build conversation context if session_id is provided
        conversation_context: str | None = None
        context_turns: list[dict[str, str]] = []
        if self.session_id:
            mgr = get_conversation_manager()
            mgr.add_user_turn(self.session_id, user_text)
            context_turns = mgr.get_context(self.session_id, limit=10)
            if context_turns:
                parts = []
                for t in context_turns:
                    label = "Người dùng" if t["role"] == "user" else "Kẹo Thông Minh"
                    parts.append(f"{label}: {t['text']}")
                conversation_context = "\n".join(parts)

        # 4. Check for reminder commands FIRST (before tool routing)
        reminder_result = self._try_parse_reminder(user_text)
        if reminder_result is not None:
            yield reminder_result
            yield {"type": "done"}
            return

        # 5. Entity extraction + tool routing
        tool_result = self._try_run_tool(user_text, context_turns)
        if tool_result is not None:
            action_type = tool_result.get("action_type")
            bot_text = tool_result.get("bot_text", "")
            action_payload = tool_result.get("action_payload")

            # If tool is unavailable or missing info, just stream the text
            if action_type == "tool_unavailable":
                await self._stream_text(bot_text, conversation_context)
                yield {"type": "done"}
                return

            # For system commands, yield action event then stream confirmation
            if action_type == "system_command" and action_payload:
                yield {"type": "action", "data": json.dumps({
                    "action": "system_command",
                    "system_command": action_payload.get("system_command"),
                    "delay_seconds": action_payload.get("delay_seconds", 0),
                    "app_name": action_payload.get("app_name", ""),
                    "browser_url": action_payload.get("browser_url", ""),
                    "bot_text": bot_text,
                }, ensure_ascii=False)}
                await self._stream_text(bot_text)
                yield {"type": "done"}
                return

            # For tool responses, stream LLM response with tool context
            if action_type == "tool_response" and tool_result.get("tool_name"):
                await self._stream_tool_response(
                    user_text,
                    tool_result["tool_name"],
                    tool_result["tool_data"],
                    conversation_context,
                )
                yield {"type": "done"}
                return

            # Fallback: stream the bot text directly
            await self._stream_text(bot_text)
            yield {"type": "done"}
            return

        # 6. No tool matched — free-form LLM response
        await self._stream_text_with_context(user_text, conversation_context)
        yield {"type": "done"}

    # ------------------------------------------------------------------
    # Reminder parsing
    # ------------------------------------------------------------------
    def _try_parse_reminder(self, user_text: str) -> dict[str, Any] | None:
        """Try to parse reminder text. Returns action event dict or None."""
        draft = parse_reminder_text(user_text)
        if draft is None:
            return None

        reminder = get_reminder_store().create(
            draft.title, draft.remind_at, repeat_interval=draft.repeat_interval,
        )

        # Build confirmation message
        from datetime import datetime
        now = datetime.now()
        same_day = draft.remind_at.date() == now.date()
        if same_day:
            when_text = draft.remind_at.strftime("%H:%M")
            bot_text = f"Được rồi, mình sẽ nhắc bạn {draft.title} lúc {when_text}."
        else:
            when_text = draft.remind_at.strftime("%H:%M ngày %d/%m")
            bot_text = f"Được rồi, mình sẽ nhắc bạn {draft.title} lúc {when_text}."

        if draft.repeat_interval:
            if draft.repeat_interval < 3600:
                interval_text = f"mỗi {draft.repeat_interval // 60} phút"
            elif draft.repeat_interval < 86400:
                interval_text = f"mỗi {draft.repeat_interval // 3600} tiếng"
            else:
                interval_text = "mỗi ngày"
            bot_text += f" Mình sẽ nhắc lại {interval_text}."

        # Save to conversation context
        if self.session_id:
            mgr = get_conversation_manager()
            mgr.add_bot_turn(self.session_id, bot_text)

        return {"type": "action", "data": json.dumps({
            "action": "reminder_created",
            "reminder": {
                "id": reminder["id"],
                "title": reminder["title"],
                "remind_at": reminder["remind_at"],
            },
            "bot_text": bot_text,
        }, ensure_ascii=False)}

    # ------------------------------------------------------------------
    # Tool routing
    # ------------------------------------------------------------------
    def _try_run_tool(self, user_text: str, context_turns: list[dict[str, str]]) -> dict[str, Any] | None:
        """Run entity extraction + tool routing. Returns tool result dict or None."""
        entities = extract_entities(user_text)
        memory_context = get_memory_store().get_memory_context()

        # Apply memory defaults
        tool_route = detect_tool_intent(user_text, context_turns)
        if tool_route.intent == "none" or tool_route.confidence < TOOL_CONFIDENCE_THRESHOLD:
            return None

        tool_entities = dict(tool_route.entities)
        if tool_route.intent == "weather" and not tool_entities.get("location") and memory_context.get("default_city"):
            tool_entities["location"] = memory_context["default_city"]
        if tool_route.intent == "time" and not tool_entities.get("timezone") and memory_context.get("default_timezone"):
            tool_entities["timezone"] = memory_context["default_timezone"]
        if tool_route.intent == "currency" and not tool_entities.get("target_currency") and memory_context.get("default_currency"):
            tool_entities["target_currency"] = memory_context["default_currency"]

        # Run the tool
        tool_data = self._execute_tool(tool_route.intent, user_text, tool_entities)

        # Check unavailability
        if self._tool_is_unavailable(tool_data):
            bot_text = self._build_tool_unavailable_message(tool_route.intent)
            if self.session_id:
                get_conversation_manager().add_bot_turn(self.session_id, bot_text)
            return {"action_type": "tool_unavailable", "bot_text": bot_text}

        # Check missing info
        missing = self._detect_missing_info(tool_route.intent, tool_entities, tool_data)
        if missing:
            if self.session_id:
                get_conversation_manager().add_bot_turn(self.session_id, missing)
            return {"action_type": "tool_unavailable", "bot_text": missing}

        # System command
        if tool_route.intent == "system":
            sys_cmd = tool_data.get("system_command")
            bot_text = f"Đã nhận lệnh {sys_cmd}."
            delay = tool_data.get("delay_seconds", 0)
            if delay > 0:
                minutes = delay / 60
                bot_text += f" Sau {minutes:.0f} phút."
            if sys_cmd == "open_browser":
                url = tool_data.get("browser_url", "")
                if url:
                    # Extract domain name for a friendly message
                    try:
                        domain = url.split("//")[-1].split("/")[0].replace("www.", "")
                        bot_text = f"Mình mở {domain} cho bạn nhé."
                    except Exception:
                        bot_text = f"Mở trình duyệt cho bạn."
            if self.session_id:
                get_conversation_manager().add_bot_turn(self.session_id, bot_text)
            return {
                "action_type": "system_command",
                "bot_text": bot_text,
                "action_payload": {
                    "system_command": sys_cmd,
                    "delay_seconds": delay,
                    "app_name": tool_data.get("app_name", ""),
                    "browser_url": tool_data.get("browser_url", ""),
                },
            }

        # Other tools (weather, time, currency, search)
        return {
            "action_type": "tool_response",
            "tool_name": tool_route.intent,
            "tool_data": tool_data,
        }

    @staticmethod
    def _execute_tool(intent: str, query: str, entities: dict) -> dict[str, Any]:
        from datetime import datetime, timezone
        if intent == "time":
            return get_time_info(query, entities=entities)
        if intent == "currency":
            return get_currency_info(query, entities=entities)
        if intent == "weather":
            return get_weather_info(query, entities=entities)
        if intent in ("news_search", "general_search"):
            return get_search_info(query, intent, entities=entities)
        if intent == "system":
            cmd = entities.get("system_command")
            # If open_browser detected, use that command
            if entities.get("browser_url"):
                cmd = "open_browser"
            return {
                "is_available": True,
                "system_command": cmd,
                "delay_seconds": entities.get("delay_seconds") or 0,
                "app_name": entities.get("app_name", ""),
                "browser_url": entities.get("browser_url", ""),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        return {"is_available": False, "message": "Unsupported tool."}

    @staticmethod
    def _tool_is_unavailable(tool_result: dict) -> bool:
        return tool_result.get("available") is False or tool_result.get("is_available") is False

    @staticmethod
    def _detect_missing_info(intent: str, entities: dict, tool_result: dict) -> str | None:
        if intent == "weather" and not entities.get("location"):
            return "Mình cần biết bạn muốn xem thời tiết ở đâu để trả lời."
        if intent == "time" and not entities.get("timezone") and not entities.get("location"):
            return "Mình cần biết bạn muốn xem giờ ở thành phố nào."
        if intent == "currency" and not entities.get("base_currency") and not entities.get("target_currency"):
            return "Mình cần biết bạn muốn đổi từ tiền nào sang tiền nào."
        return None

    @staticmethod
    def _build_tool_unavailable_message(intent: str) -> str:
        messages = {
            "weather": "Xin lỗi, mình chưa xem được thời tiết vì chưa cấu hình API.",
            "time": "Xin lỗi, mình chưa xem được giờ.",
            "currency": "Xin lỗi, mình chưa tra cứu được tỷ giá.",
            "news_search": "Xin lỗi, mình chưa tìm được tin tức.",
            "general_search": "Xin lỗi, mình chưa tìm kiếm được.",
            "system": "Xin lỗi, lệnh hệ thống không khả dụng.",
        }
        return messages.get(intent, "Xin lỗi, công cụ chưa sẵn sàng.")

    # ------------------------------------------------------------------
    # Streaming helpers with TTS
    # ------------------------------------------------------------------
    async def _stream_text(self, bot_text: str) -> None:
        """Stream text tokens and run TTS for each sentence."""
        await self._run_streaming_pipeline(
            _text_async_iterator(bot_text),
        )

    async def _stream_text_with_context(self, user_text: str, conversation_context: str | None) -> None:
        """Stream LLM response with conversation context and run TTS."""
        async def gen() -> AsyncIterator[str]:
            async for token in stream_keobot_text_raw(
                user_text, conversation_context=conversation_context, cancel_check=lambda: self._cancelled
            ):
                yield token
        await self._run_streaming_pipeline(gen())

    async def _stream_tool_response(
        self, user_text: str, tool_name: str, tool_result: dict, conversation_context: str | None,
    ) -> None:
        """Stream LLM response with tool context and run TTS."""
        async def gen() -> AsyncIterator[str]:
            async for token in stream_keobot_tool_response(
                user_text, tool_name, tool_result,
                conversation_context=conversation_context,
                cancel_check=lambda: self._cancelled,
            ):
                yield token
        await self._run_streaming_pipeline(gen())

    async def _run_streaming_pipeline(self, token_stream: AsyncIterator[str]) -> None:
        """Consume a token stream, yield text events, and run TTS sentence-by-sentence."""
        sentence_buffer: list[str] = []
        tts_tasks: list[asyncio.Task[str | None]] = []
        full_response: list[str] = []
        llm_error: Exception | None = None

        try:
            async for token in token_stream:
                if self._cancelled:
                    return

                yield {"type": "text", "data": token}
                full_response.append(token)

                sentence_buffer.append(token)
                buffer_text = "".join(sentence_buffer)

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

        # Save bot response to conversation context
        if self.session_id and full_response and not self._cancelled:
            bot_text = "".join(full_response)
            mgr = get_conversation_manager()
            mgr.add_bot_turn(self.session_id, bot_text)

        # Yield audio from completed TTS tasks
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
