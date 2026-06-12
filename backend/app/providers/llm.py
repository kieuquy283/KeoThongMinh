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

CONVERSATION_CONTEXT_PROMPT = """Lich su hoi thoai truoc do:
{}
Hay su dung thong tin nay de tra loi cau hoi tiep theo mot cach nhat quan, tranh lap lai thong tin da noi.
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
        return KeoBotLLMResponse(bot_text=raw_text.strip() or "Mình chưa nghĩ ra câu trả lời phù hợp.", emotion="neutral")

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
            return {"bot_text": f"Mình là Kẹo Thông Minh, trợ lý AI tiếng Việt thân thiện của {user_name}.", "emotion": "happy"}
        return {"bot_text": "Mình là Kẹo Thông Minh, trợ lý AI tiếng Việt thân thiện của bạn.", "emotion": "happy"}
    if any(keyword in text for keyword in ["dua", "joke", "cau dua", "cuoi"]):
        return {"bot_text": "Đây nhé: Kẹo Thông Minh mà buồn thì vẫn phải... bật chế độ vui vẻ trước đã!", "emotion": "wink"}
    if any(keyword in text for keyword in ["met", "buon", "chan", "stress", "duoi"]):
        return {"bot_text": "Nghe có vẻ bạn đang mệt. Nghỉ một chút rồi mình tính tiếp nhé.", "emotion": "sad"}
    if any(keyword in text for keyword in ["giai thich", "la gi", "tai sao", "how", "roi sao"]):
        return {"bot_text": "Mình sẽ giải thích ngắn gọn từng bước nhé.", "emotion": "thinking"}
    if user_name:
        if answer_style == "short":
            return {"bot_text": f"Mình đã nghe, {user_name}. Bạn muốn mình làm gì tiếp?", "emotion": "neutral"}
        return {"bot_text": f"Mình đã nghe rồi, {user_name}. Bạn muốn mình hỗ trợ phần nào tiếp theo?", "emotion": "neutral"}
    return {"bot_text": "Mình đã nghe rồi. Bạn muốn mình hỗ trợ phần nào tiếp theo?", "emotion": "neutral"}


def _local_tool_response(tool_name: str, tool_result: dict[str, Any]) -> dict[str, str]:
    if tool_name == "time":
        return {
            "bot_text": f'Bây giờ ở {tool_result["location"]} là {tool_result["formatted_time"]}.',
            "emotion": "neutral",
        }

    if tool_name == "currency":
        suffix = " Đây là tỷ giá demo, không phải dữ liệu live." if not tool_result.get("is_live", False) else ""
        converted_amount = tool_result.get("converted_amount")
        amount_prefix = f'{tool_result["amount"]} ' if tool_result.get("amount") is not None else ""
        return {
            "bot_text": (
                f'{amount_prefix}{tool_result["base_currency"]} hiện tại khoảng {converted_amount if converted_amount is not None else tool_result["rate"]} '
                f'{tool_result["target_currency"]}.{suffix}'
            ),
            "emotion": "thinking",
        }

    if tool_name == "weather":
        return {
            "bot_text": (
                f'Thời tiết tại {tool_result["location"]}: {tool_result["description"]}, '
                f'{tool_result["temperature_c"]} độ C, cảm giác như {tool_result["feels_like_c"]} độ C.'
            ),
            "emotion": "neutral",
        }

    if tool_name in {"news_search", "general_search"}:
        results = tool_result.get("results") or []
        if results:
            first = results[0]
            return {
                "bot_text": f'Thông tin nổi bật: {first.get("title", "")}. Mình đã kèm nguồn để bạn xem chi tiết.',
                "emotion": "thinking",
            }

    return {
        "bot_text": "Mình đã nhận dữ liệu từ công cụ và sẽ hiển thị kèm nguồn tham khảo.",
        "emotion": "neutral",
    }


async def generate_keobot_response(user_text: str, memory_context: dict[str, Any] | None = None, conversation_context: str | None = None) -> dict[str, str]:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider in {"local", "mock"}:
        return _local_keobot_response(user_text, memory_context)

    memory_prompt = _format_memory_context(memory_context)
    conv_prompt = CONVERSATION_CONTEXT_PROMPT.format(conversation_context) if conversation_context else ""
    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("Thieu OPENAI_API_KEY cho LLM provider openai.")
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if conv_prompt:
            messages.append({"role": "system", "content": conv_prompt})
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
        system_parts = [SYSTEM_PROMPT]
        if conv_prompt:
            system_parts.append(conv_prompt)
        if memory_prompt:
            system_parts.append(memory_prompt)
        model = genai.GenerativeModel(
            settings.gemini_model,
            system_instruction="\n\n".join(system_parts),
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


async def generate_keobot_tool_response(user_text: str, tool_name: str, tool_result: dict[str, Any], conversation_context: str | None = None) -> dict[str, str]:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider in {"local", "mock"}:
        return _local_tool_response(tool_name, tool_result)

    tool_payload = json.dumps(tool_result, ensure_ascii=False)
    prompt_parts = [f"Cau hoi nguoi dung: {user_text}", f"Tool: {tool_name}", f"Tool data: {tool_payload}"]
    if conversation_context:
        prompt_parts.insert(0, f"Lich su hoi thoai:\n{conversation_context}")
    prompt = "\n".join(prompt_parts)

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


SUMMARIZE_SYSTEM_PROMPT = """Tom tat cuoc hoi thoai sau bang 2-3 cau tieng Viet, giu lai thong tin chinh.
Chi tra ve phan tom tat, khong co markup."""


async def generate_conversation_summary(turns: list[dict[str, str]]) -> str:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    parts = []
    for t in turns:
        label = "Nguoi dung" if t["role"] == "user" else "Tro ly"
        parts.append(f"{label}: {t['text']}")
    conversation = "\n".join(parts)

    if provider in {"local", "mock"}:
        user_msgs = [t["text"] for t in turns if t["role"] == "user"]
        topics = "; ".join(user_msgs[:3])
        return f"Nguoi dung da hoi: {topics}" if topics else "Hoi thoai ngan."

    if provider == "openai":
        if not settings.openai_api_key:
            return "Hoi thoai khong duoc tom tat (thieu API key)."
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_chat_model,
            temperature=0.3,
            messages=[
                {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
                {"role": "user", "content": conversation},
            ],
        )
        return (response.choices[0].message.content or "").strip()

    if provider == "gemini":
        if not settings.gemini_api_key:
            return "Hoi thoai khong duoc tom tat (thieu API key)."
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            settings.gemini_model,
            system_instruction=SUMMARIZE_SYSTEM_PROMPT,
        )
        response = model.generate_content(conversation)
        return (getattr(response, "text", "") or "").strip()

    return "Hoi thoai khong duoc tom tat."
