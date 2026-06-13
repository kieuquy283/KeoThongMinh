from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator

from app.config import get_settings
from app.providers.llm import (
    CONVERSATION_CONTEXT_PROMPT,
    MEMORY_CONTEXT_PROMPT,
    SYSTEM_PROMPT,
    TOOL_SYSTEM_PROMPT,
    _coerce_response,
    _extract_json_object,
    _format_memory_context,
    _is_qwen_provider,
    _local_keobot_response,
    _local_tool_response,
)
from app.schemas import KeoBotLLMResponse

logger = logging.getLogger("keobot.llm_stream")


@dataclass
class StreamCallbacks:
    on_start: Any = None
    on_token: Any = None
    on_end: Any = None


async def stream_keobot_response(
    user_text: str,
    memory_context: dict[str, Any] | None = None,
    conversation_context: str | None = None,
    cancel_check: Any = None,
) -> AsyncIterator[str]:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider in {"local", "mock"}:
        result = _local_keobot_response(user_text, memory_context)
        yield json.dumps(result, ensure_ascii=False)
        return

    memory_prompt = _format_memory_context(memory_context)
    conv_prompt = CONVERSATION_CONTEXT_PROMPT.format(conversation_context) if conversation_context else ""

    if provider == "openai" or _is_qwen_provider(provider):
        if provider == "openai":
            if not settings.openai_api_key:
                raise RuntimeError("Thieu OPENAI_API_KEY cho LLM provider openai.")
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            model = settings.openai_chat_model
        else:
            if not settings.dashscope_api_key:
                raise RuntimeError("Thieu DASHSCOPE_API_KEY cho LLM provider qwen/dashscope.")
            from openai import OpenAI
            client = OpenAI(
                api_key=settings.dashscope_api_key,
                base_url=settings.dashscope_base_url,
            )
            model = settings.dashscope_llm_model
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if conv_prompt:
            messages.append({"role": "system", "content": conv_prompt})
        if memory_prompt:
            messages.append({"role": "system", "content": memory_prompt})
        messages.append({"role": "user", "content": user_text})

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                stream = client.chat.completions.create(
                    model=model,
                    temperature=0.6,
                    response_format={"type": "json_object"},
                    messages=messages,
                    stream=True,
                )
                break
            except Exception as exc:
                last_error = exc
                logger.warning("openai_retry attempt=%d error=%s", attempt + 1, exc)
                if attempt < 2:
                    await asyncio.sleep(1.0 * (2 ** attempt))
        else:
            logger.error("openai_failed after 3 retries: %s", last_error)
            yield json.dumps({"bot_text": "Xin lỗi, dịch vụ AI tạm thời không khả dụng. Vui lòng thử lại sau.", "is_available": False}, ensure_ascii=False)
            return
        collected = ""
        for chunk in stream:
            if cancel_check and cancel_check():
                stream.close()
                return
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                collected += delta
                yield delta
        if collected.strip():
            payload = _extract_json_object(collected)
            if payload:
                normalized = _coerce_response(payload, collected)
                result = normalized.model_dump()
                yield json.dumps(result, ensure_ascii=False)

    elif provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("Thieu GEMINI_API_KEY cho LLM provider gemini.")
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        system_parts = [SYSTEM_PROMPT]
        if conv_prompt:
            system_parts.append(conv_prompt)
        if memory_prompt:
            system_parts.append(memory_prompt)
        model = genai.GenerativeModel(
            settings.gemini_model,
            system_instruction="\n\n".join(system_parts),
        )
        last_error = None
        response = None
        for attempt in range(3):
            try:
                response = model.generate_content(user_text, stream=True)
                break
            except Exception as exc:
                last_error = exc
                logger.warning("gemini_retry attempt=%d error=%s", attempt + 1, exc)
                if attempt < 2:
                    await asyncio.sleep(1.0 * (2 ** attempt))
        if response is None:
            logger.error("gemini_failed after 3 retries: %s", last_error)
            yield json.dumps({"bot_text": "Xin lỗi, dịch vụ AI tạm thời không khả dụng. Vui lòng thử lại sau.", "is_available": False}, ensure_ascii=False)
            return
        collected = ""
        for chunk in response:
            if cancel_check and cancel_check():
                response.cancel()
                return
            text = chunk.text if hasattr(chunk, "text") else ""
            if text:
                collected += text
                yield text
        if collected.strip():
            payload = _extract_json_object(collected)
            if payload:
                normalized = _coerce_response(payload, collected)
                result = normalized.model_dump()
                yield json.dumps(result, ensure_ascii=False)
    else:
        raise RuntimeError(f"LLM_PROVIDER khong duoc ho tro: {settings.llm_provider}")


async def stream_keobot_text_raw(
    user_text: str,
    memory_context: dict[str, Any] | None = None,
    conversation_context: str | None = None,
    cancel_check: Any = None,
) -> AsyncIterator[str]:
    """Stream raw text tokens from LLM (no JSON parsing)."""
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider in {"local", "mock"}:
        result = _local_keobot_response(user_text, memory_context)
        yield result.get("bot_text", "")
        return

    memory_prompt = _format_memory_context(memory_context)
    conv_prompt = CONVERSATION_CONTEXT_PROMPT.format(conversation_context) if conversation_context else ""

    if provider == "openai" or _is_qwen_provider(provider):
        if provider == "openai":
            if not settings.openai_api_key:
                raise RuntimeError("Thieu OPENAI_API_KEY cho LLM provider openai.")
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            model = settings.openai_chat_model
        else:
            if not settings.dashscope_api_key:
                raise RuntimeError("Thieu DASHSCOPE_API_KEY cho LLM provider qwen/dashscope.")
            from openai import OpenAI
            client = OpenAI(
                api_key=settings.dashscope_api_key,
                base_url=settings.dashscope_base_url,
            )
            model = settings.dashscope_llm_model
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if conv_prompt:
            messages.append({"role": "system", "content": conv_prompt})
        if memory_prompt:
            messages.append({"role": "system", "content": memory_prompt})
        messages.append({"role": "user", "content": user_text})

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                stream = client.chat.completions.create(
                    model=model,
                    temperature=0.6,
                    messages=messages,
                    stream=True,
                )
                break
            except Exception as exc:
                last_error = exc
                logger.warning("llm_raw_retry attempt=%d error=%s", attempt + 1, exc)
                if attempt < 2:
                    await asyncio.sleep(1.0 * (2 ** attempt))
        else:
            logger.error("llm_raw_failed after 3 retries: %s", last_error)
            yield "Xin lỗi, dịch vụ AI tạm thời không khả dụng."
            return

        for chunk in stream:
            if cancel_check and cancel_check():
                stream.close()
                return
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

    elif provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("Thieu GEMINI_API_KEY cho LLM provider gemini.")
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        system_parts = [SYSTEM_PROMPT]
        if conv_prompt:
            system_parts.append(conv_prompt)
        if memory_prompt:
            system_parts.append(memory_prompt)
        model = genai.GenerativeModel(
            settings.gemini_model,
            system_instruction="\n\n".join(system_parts),
        )
        last_error = None
        response = None
        for attempt in range(3):
            try:
                response = model.generate_content(user_text, stream=True)
                break
            except Exception as exc:
                last_error = exc
                logger.warning("gemini_raw_retry attempt=%d error=%s", attempt + 1, exc)
                if attempt < 2:
                    await asyncio.sleep(1.0 * (2 ** attempt))
        if response is None:
            logger.error("gemini_raw_failed after 3 retries: %s", last_error)
            yield "Xin lỗi, dịch vụ AI tạm thời không khả dụng."
            return
        for chunk in response:
            if cancel_check and cancel_check():
                response.cancel()
                return
            text = chunk.text if hasattr(chunk, "text") else ""
            if text:
                yield text
    else:
        raise RuntimeError(f"LLM_PROVIDER khong duoc ho tro: {settings.llm_provider}")


async def stream_keobot_tool_response(
    user_text: str,
    tool_name: str,
    tool_result: dict[str, Any],
    conversation_context: str | None = None,
    cancel_check: Any = None,
) -> AsyncIterator[str]:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider in {"local", "mock"}:
        result = _local_tool_response(tool_name, tool_result)
        yield json.dumps(result, ensure_ascii=False)
        return

    tool_payload = json.dumps(tool_result, ensure_ascii=False)
    prompt_parts = [f"Cau hoi nguoi dung: {user_text}", f"Tool: {tool_name}", f"Tool data: {tool_payload}"]
    if conversation_context:
        prompt_parts.insert(0, f"Lich su hoi thoai:\n{conversation_context}")
    prompt = "\n".join(prompt_parts)

    if provider == "openai" or _is_qwen_provider(provider):
        if provider == "openai":
            if not settings.openai_api_key:
                raise RuntimeError("Thieu OPENAI_API_KEY cho LLM provider openai.")
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            model = settings.openai_chat_model
        else:
            if not settings.dashscope_api_key:
                raise RuntimeError("Thieu DASHSCOPE_API_KEY cho LLM provider qwen/dashscope.")
            from openai import OpenAI
            client = OpenAI(
                api_key=settings.dashscope_api_key,
                base_url=settings.dashscope_base_url,
            )
            model = settings.dashscope_llm_model
        last_error = None
        stream = None
        for attempt in range(3):
            try:
                stream = client.chat.completions.create(
                    model=model,
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": TOOL_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    stream=True,
                )
                break
            except Exception as exc:
                last_error = exc
                logger.warning("tool_openai_retry attempt=%d error=%s", attempt + 1, exc)
                if attempt < 2:
                    await asyncio.sleep(1.0 * (2 ** attempt))
        if stream is None:
            logger.error("tool_openai_failed after 3 retries: %s", last_error)
            yield json.dumps({"bot_text": "Xin lỗi, dịch vụ AI tạm thời không khả dụng.", "is_available": False}, ensure_ascii=False)
            return
        collected = ""
        for chunk in stream:
            if cancel_check and cancel_check():
                stream.close()
                return
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                collected += delta
                yield delta
        if collected.strip():
            payload = _extract_json_object(collected)
            if payload:
                normalized = _coerce_response(payload, collected)
                result = normalized.model_dump()
                yield json.dumps(result, ensure_ascii=False)

    elif provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("Thieu GEMINI_API_KEY cho LLM provider gemini.")
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            settings.gemini_model,
            system_instruction=TOOL_SYSTEM_PROMPT,
        )
        last_error = None
        response = None
        for attempt in range(3):
            try:
                response = model.generate_content(prompt, stream=True)
                break
            except Exception as exc:
                last_error = exc
                logger.warning("tool_gemini_retry attempt=%d error=%s", attempt + 1, exc)
                if attempt < 2:
                    await asyncio.sleep(1.0 * (2 ** attempt))
        if response is None:
            logger.error("tool_gemini_failed after 3 retries: %s", last_error)
            yield json.dumps({"bot_text": "Xin lỗi, dịch vụ AI tạm thời không khả dụng.", "is_available": False}, ensure_ascii=False)
            return
        collected = ""
        for chunk in response:
            if cancel_check and cancel_check():
                response.cancel()
                return
            text = chunk.text if hasattr(chunk, "text") else ""
            if text:
                collected += text
                yield text
        if collected.strip():
            payload = _extract_json_object(collected)
            if payload:
                normalized = _coerce_response(payload, collected)
                result = normalized.model_dump()
                yield json.dumps(result, ensure_ascii=False)
    else:
        raise RuntimeError(f"LLM_PROVIDER khong duoc ho tro: {settings.llm_provider}")
