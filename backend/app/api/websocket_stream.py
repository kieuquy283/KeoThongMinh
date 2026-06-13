from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.providers.realtime_streaming import OpenAIRealtimeProvider, WebmToPCM16Converter

logger = logging.getLogger("keobot.websocket_stream")
router = APIRouter()


@router.websocket("/v2/stream-chat")
async def stream_chat(websocket: WebSocket) -> None:
    """Full-duplex native audio streaming voice chat over WebSocket.

    Ingests raw audio chunks (webm/opus base64) from the frontend,
    forwards them to the OpenAI Realtime API after PCM16 conversion,
    and streams audio/text tokens back to the client.
    """
    await websocket.accept()
    settings = get_settings()
    provider: OpenAIRealtimeProvider | None = None
    converter = WebmToPCM16Converter(flush_interval_chunks=3)
    audio_buffer: list[str] = []
    receive_task: asyncio.Task[Any] | None = None
    send_task: asyncio.Task[Any] | None = None
    is_open = True

    try:
        # Validate provider key
        api_key = settings.openai_api_key
        if not api_key:
            await websocket.send_text(
                json.dumps({"event": "error", "data": {"message": "Realtime API key not configured."}})
            )
            await websocket.close(code=1008)
            return

        # Initialize upstream provider
        provider = OpenAIRealtimeProvider(
            api_key=api_key,
            model="gpt-4o-realtime-preview-2024-12-17",
        )
        await provider.connect()
        await provider.configure_session()

        async def receive_from_frontend() -> None:
            """Continuously read from frontend and forward to upstream."""
            nonlocal audio_buffer, is_open
            while is_open:
                try:
                    raw = await websocket.receive_text()
                except WebSocketDisconnect:
                    logger.info("Frontend WebSocket disconnected")
                    is_open = False
                    break
                except Exception as exc:
                    logger.warning("WebSocket receive error: %s", exc)
                    is_open = False
                    break

                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON from frontend")
                    continue

                event = frame.get("event")
                if event == "audio_chunk":
                    chunk = frame.get("data", "")
                    if chunk:
                        audio_buffer.append(chunk)
                        # Flush every 3 chunks (~300ms) to keep latency low
                        if len(audio_buffer) >= 3:
                            chunks_to_convert = audio_buffer[:3]
                            audio_buffer = audio_buffer[3:]
                            pcm16 = await converter._convert_chunks(chunks_to_convert)
                            if pcm16 and provider:
                                await provider.send_audio(pcm16)
                elif event == "user_interrupt":
                    # Flush any pending audio and send upstream interrupt
                    if audio_buffer and provider:
                        remaining_pcm16 = await converter._convert_chunks(audio_buffer)
                        audio_buffer = []
                        if remaining_pcm16:
                            await provider.send_audio(remaining_pcm16)
                    if provider:
                        await provider.interrupt()
                    try:
                        await websocket.send_text(json.dumps({"event": "clear"}))
                    except Exception:
                        pass
                else:
                    logger.debug("Unknown frontend event: %s", event)

        async def send_to_frontend() -> None:
            """Stream upstream tokens back to frontend."""
            nonlocal is_open
            if not provider:
                return
            try:
                async for token in provider.receive():
                    if not is_open:
                        break
                    token_type = token.get("type")
                    if token_type == "audio":
                        payload = {
                            "event": "audio_response",
                            "data": token.get("data", ""),
                        }
                        try:
                            await websocket.send_text(json.dumps(payload))
                        except Exception:
                            is_open = False
                            break
                    elif token_type == "text":
                        payload = {
                            "event": "text_response",
                            "data": token.get("data", ""),
                        }
                        try:
                            await websocket.send_text(json.dumps(payload))
                        except Exception:
                            is_open = False
                            break
                    elif token_type == "done":
                        try:
                            await websocket.send_text(json.dumps({"event": "response_done"}))
                        except Exception:
                            is_open = False
                            break
                    elif token_type == "error":
                        error_data = token.get("data", {})
                        logger.error("Realtime API error: %s", error_data)
                        try:
                            await websocket.send_text(
                                json.dumps({"event": "error", "data": error_data})
                            )
                        except Exception:
                            is_open = False
                            break
            except Exception as exc:
                logger.error("send_to_frontend loop error: %s", exc)
                is_open = False

        # Drive both directions concurrently
        receive_task = asyncio.create_task(receive_from_frontend())
        send_task = asyncio.create_task(send_to_frontend())

        # Wait for either task to finish (disconnect or error)
        done, pending = await asyncio.wait(
            [receive_task, send_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Drain any exceptions from completed tasks
        for task in done:
            if task.exception():
                logger.warning("Task ended with exception: %s", task.exception())

    except WebSocketDisconnect:
        logger.info("WebSocket /v2/stream-chat disconnected cleanly")
    except Exception as exc:
        logger.error("WebSocket /v2/stream-chat error: %s", exc)
        try:
            await websocket.send_text(
                json.dumps({"event": "error", "data": {"message": str(exc)}})
            )
        except Exception:
            pass
    finally:
        is_open = False
        # Flush any remaining buffered audio
        if audio_buffer:
            try:
                remaining_pcm16 = await converter._convert_chunks(audio_buffer)
                if remaining_pcm16 and provider:
                    await provider.send_audio(remaining_pcm16)
            except Exception:
                pass
        # Gracefully close upstream
        if provider:
            try:
                await provider.disconnect()
            except Exception as exc:
                logger.warning("Provider disconnect error: %s", exc)
        # Close WebSocket if still open
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("WebSocket /v2/stream-chat cleanup complete")
