from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.providers.streaming_pipeline import StreamingPipeline

logger = logging.getLogger("keobot.websocket_stream")
router = APIRouter()


@router.websocket("/v2/stream-chat")
async def stream_chat(websocket: WebSocket) -> None:
    """Low-latency streaming voice chat over WebSocket.

    Ingests audio chunks from the frontend, runs STT -> LLM streaming -> TTS
    sentence-by-sentence, and streams audio/text back to the client.
    """
    await websocket.accept()
    settings = get_settings()
    pipeline = StreamingPipeline()
    receive_task: asyncio.Task[Any] | None = None
    send_task: asyncio.Task[Any] | None = None
    is_open = True

    try:
        # Validate provider key
        if not settings.dashscope_api_key and not settings.openai_api_key:
            await websocket.send_text(
                json.dumps({"event": "error", "data": {"message": "API key not configured."}})
            )
            await websocket.close(code=1008)
            return

        async def receive_from_frontend() -> None:
            """Read audio chunks / commands from the frontend."""
            nonlocal is_open
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
                        await pipeline.add_audio_chunk(chunk)
                elif event == "finish_turn":
                    # Trigger processing in a background task so receive loop
                    # stays unblocked and can catch user_interrupt.
                    asyncio.create_task(_process_and_send())
                elif event == "user_interrupt":
                    pipeline.cancel()
                    try:
                        await websocket.send_text(json.dumps({"event": "clear"}))
                    except Exception:
                        pass
                else:
                    logger.debug("Unknown frontend event: %s", event)

        async def _process_and_send() -> None:
            """Run the pipeline and stream results back to the frontend."""
            try:
                async for token in pipeline.process_turn():
                    if not is_open:
                        break
                    token_type = token.get("type")
                    if token_type == "audio":
                        payload = {"event": "audio_response", "data": token.get("data", "")}
                    elif token_type == "text":
                        payload = {"event": "text_response", "data": token.get("data", "")}
                    elif token_type == "done":
                        payload = {"event": "response_done"}
                    elif token_type == "error":
                        payload = {"event": "error", "data": token.get("data", {})}
                    else:
                        continue
                    try:
                        await websocket.send_text(json.dumps(payload))
                    except Exception:
                        break
            except Exception as exc:
                logger.error("Pipeline processing error: %s", exc)
                try:
                    await websocket.send_text(
                        json.dumps({"event": "error", "data": {"message": str(exc)}})
                    )
                except Exception:
                    pass
            finally:
                pipeline.reset()

        # Drive the receive loop
        receive_task = asyncio.create_task(receive_from_frontend())

        # Wait for the receive loop to finish (disconnect or error)
        await receive_task

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
        pipeline.cancel()
        if receive_task and not receive_task.done():
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("WebSocket /v2/stream-chat cleanup complete")
