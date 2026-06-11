from __future__ import annotations

import json
import re
from typing import Any

from app.config import get_settings
from app.schemas import KeoBotLLMResponse

ALLOWED_EMOTIONS: set[str] = {
    "neutral",
    "happy",
    "thinking",
    "sad",
    "surprised",
    "angry",
    "wink",
}

SYSTEM_PROMPT = """Ban la Kẹo Thông Minh, mot tro ly AI tieng Viet than thien, thong minh va hoi hai huoc.
Ban tra loi tu nhien, ngan gon, de hieu.
Ban uu tien tieng Viet.
Neu nguoi dung hoi hoc tap hoac ky thuat, hay giai thich tung buoc.
Neu khong chac, hay hoi lai nhe nhang.
Khong tra loi qua dai neu cau hoi don gian.

Ban phai tra ve JSON hop le theo format:
{
  "bot_text": "...",
  "emotion": "neutral|happy|thinking|sad|surprised|angry|wink"
}"""

TOOL_SYSTEM_PROMPT = """Ban la Kẹo Thông Minh.
Ban chi duoc tom tat dua tren du lieu cong cu duoc cung cap.
Khong duoc bo sung su that moi neu tool khong co trong du lieu.
Neu du lieu la demo hoac fallback, phai noi ro dieu do.
Tra ve JSON hop le theo format:
{
  "bot_text": "...",
  "emotion": "neutral|happy|thinking|sad|surprised|angry|wink"
}"""

MEMORY_CONTEXT_PROMPT = """Thong tin bo nho an toan cua nguoi dung:
- Chi su dung neu lien quan truc tiep den cau tra loi.
- Khong suy dien them du lieu moi.
- Khong bao gio de xuat API key hoac thong tin nhay cam.
"""


def _extract_json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None
    return None


def _coerce_response(payload: dict[str, Any], raw_text: str) -> KeoBotLLMResponse:
    bot_text = payload.get("bot_text")
    emotion = payload.get("emotion", "neutral")

    if not isinstance(bot_text, str) or not bot_text.strip():
        return KeoBotLLMResponse(bot_text=raw_text.strip() or "Minh chua nghi ra cau tra loi phu hop.", emotion="neutral")

    if emotion not in ALLOWED_EMOTIONS:
        emotion = "neutral"

    return KeoBotLLMResponse(bot_text=bot_text.strip(), emotion=emotion)  # type: ignore[arg-type]


def _local_keobot_response(user_text: str, memory_context: dict[str, Any] | None = None) -> dict[str, str]:
    memory_context = memory_context or {}
    user_name = str(memory_context.get("user_name") or "").strip()
    answer_style = str(memory_context.get("answer_style") or "").strip().lower()
    text = user_text.lower()
    if any(keyword in text for keyword in ["ban la ai", "ai vay", "gioi thieu", "gioi thieu ve ban"]):
        if user_name:
            return {"bot_text": f"Minh la Kẹo Thông Minh, tro ly AI tieng Viet than thien cua {user_name}.", "emotion": "happy"}
        return {"bot_text": "Minh la Kẹo Thông Minh, tro ly AI tieng Viet than thien cua ban.", "emotion": "happy"}
    if any(keyword in text for keyword in ["dua", "joke", "cau dua", "cuoi"]):
        return {"bot_text": "Day nhe: Kẹo Thông Minh ma buon thi van phai... bat che do vui ve truoc da!", "emotion": "wink"}
    if any(keyword in text for keyword in ["met", "buon", "chan", "stress", "duoi"]):
        return {"bot_text": "Nghe co ve ban dang met. Nghi mot chut roi minh tinh tiep nhe.", "emotion": "sad"}
    if any(keyword in text for keyword in ["giai thich", "la gi", "tai sao", "how", "roi sao"]):
        return {"bot_text": "Minh se giai thich ngan gon tung buoc nhe.", "emotion": "thinking"}
    if user_name:
        if answer_style == "short":
            return {"bot_text": f"Minh da nghe, {user_name}. Ban muon minh lam gi tiep?", "emotion": "neutral"}
        return {"bot_text": f"Minh da nghe roi, {user_name}. Ban muon minh ho tro phan nao tiep theo?", "emotion": "neutral"}
    return {"bot_text": "Minh da nghe roi. Ban muon minh ho tro phan nao tiep theo?", "emotion": "neutral"}


def _local_tool_response(tool_name: str, tool_result: dict[str, Any]) -> dict[str, str]:
    if tool_name == "time":
        return {
            "bot_text": f'Bay gio o {tool_result["location"]} la {tool_result["formatted_time"]}.',
            "emotion": "neutral",
        }

    if tool_name == "currency":
        suffix = " Day la ty gia demo, khong phai du lieu live." if not tool_result.get("is_live", False) else ""
        converted_amount = tool_result.get("converted_amount")
        amount_prefix = f'{tool_result["amount"]} ' if tool_result.get("amount") is not None else ""
        return {
            "bot_text": (
                f'{amount_prefix}{tool_result["base_currency"]} hien tai khoang {converted_amount if converted_amount is not None else tool_result["rate"]} '
                f'{tool_result["target_currency"]}.{suffix}'
            ),
            "emotion": "thinking",
        }

    if tool_name == "weather":
        return {
            "bot_text": (
                f'Thoi tiet tai {tool_result["location"]}: {tool_result["description"]}, '
                f'{tool_result["temperature_c"]} do C, cam giac nhu {tool_result["feels_like_c"]} do C.'
            ),
            "emotion": "neutral",
        }

    if tool_name in {"news_search", "general_search"}:
        results = tool_result.get("results") or []
        if results:
            first = results[0]
            return {
                "bot_text": f'Thong tin noi bat: {first.get("title", "")}. Minh da kem nguon de ban xem chi tiet.',
                "emotion": "thinking",
            }

    return {
        "bot_text": "Minh da nhan du lieu tu cong cu va se hien thi kem nguon tham khao.",
        "emotion": "neutral",
    }


async def generate_keobot_response(user_text: str, memory_context: dict[str, Any] | None = None) -> dict[str, str]:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider in {"local", "mock"}:
        return _local_keobot_response(user_text, memory_context)

    memory_prompt = _format_memory_context(memory_context)
    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("Thieu OPENAI_API_KEY cho LLM provider openai.")
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if memory_prompt:
            messages.append({"role": "system", "content": memory_prompt})
        messages.append({"role": "user", "content": user_text})
        response = client.chat.completions.create(
            model=settings.openai_chat_model,
            temperature=0.6,
            response_format={"type": "json_object"},
            messages=messages,
        )
        raw_text = response.choices[0].message.content or ""
    elif provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("Thieu GEMINI_API_KEY cho LLM provider gemini.")
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            settings.gemini_model,
            system_instruction=f"{SYSTEM_PROMPT}\n\n{memory_prompt}".strip() if memory_prompt else SYSTEM_PROMPT,
        )
        response = model.generate_content(user_text)
        raw_text = getattr(response, "text", "") or ""
    else:
        raise RuntimeError(f"LLM_PROVIDER khong duoc ho tro: {settings.llm_provider}")

    payload = _extract_json_object(raw_text)
    if payload is None:
        return {"bot_text": raw_text.strip(), "emotion": "neutral"}

    normalized = _coerce_response(payload, raw_text)
    return normalized.model_dump()


async def generate_keobot_tool_response(user_text: str, tool_name: str, tool_result: dict[str, Any]) -> dict[str, str]:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider in {"local", "mock"}:
        return _local_tool_response(tool_name, tool_result)

    tool_payload = json.dumps(tool_result, ensure_ascii=False)
    prompt = f"Cau hoi nguoi dung: {user_text}\nTool: {tool_name}\nTool data: {tool_payload}"

    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("Thieu OPENAI_API_KEY cho LLM provider openai.")
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_chat_model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": TOOL_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        raw_text = response.choices[0].message.content or ""
    elif provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("Thieu GEMINI_API_KEY cho LLM provider gemini.")
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            settings.gemini_model,
            system_instruction=TOOL_SYSTEM_PROMPT,
        )
        response = model.generate_content(prompt)
        raw_text = getattr(response, "text", "") or ""
    else:
        raise RuntimeError(f"LLM_PROVIDER khong duoc ho tro: {settings.llm_provider}")

    payload = _extract_json_object(raw_text)
    if payload is None:
        return {"bot_text": raw_text.strip(), "emotion": "neutral"}

    normalized = _coerce_response(payload, raw_text)
    return normalized.model_dump()


def _format_memory_context(memory_context: dict[str, Any] | None) -> str:
    if not memory_context:
        return ""

    allowed_keys = (
        "user_name",
        "preferred_form_of_address",
        "default_city",
        "default_timezone",
        "default_currency",
        "preferred_tts_voice",
        "answer_style",
    )
    lines = [MEMORY_CONTEXT_PROMPT.strip()]
    for key in allowed_keys:
        value = memory_context.get(key)
        if isinstance(value, str) and value.strip():
            lines.append(f"- {key}: {value.strip()}")
    return "\n".join(lines)
