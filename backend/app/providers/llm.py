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

SYSTEM_PROMPT = """Bạn là KeoBot, một trợ lý AI tiếng Việt thân thiện, dễ thương, thông minh và hơi hài hước.
Bạn trả lời tự nhiên, ngắn gọn, dễ hiểu.
Bạn ưu tiên tiếng Việt.
Nếu người dùng hỏi học tập hoặc kỹ thuật, hãy giải thích từng bước.
Nếu không chắc, hãy hỏi lại nhẹ nhàng.
Không trả lời quá dài nếu câu hỏi đơn giản.

Bạn phải trả về JSON hợp lệ theo format:
{
  "bot_text": "...",
  "emotion": "neutral|happy|thinking|sad|surprised|angry|wink"
}"""


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


def _local_keobot_response(user_text: str) -> dict[str, str]:
    text = user_text.lower()
    if any(keyword in text for keyword in ["bạn là ai", "ban la ai", "ai vậy", "ai vay", "giới thiệu", "gioi thieu", "giới thiệu về bạn", "gioi thieu ve ban"]):
        return {"bot_text": "Mình là KeoBot, trợ lý AI tiếng Việt thân thiện của bạn.", "emotion": "happy"}
    if any(keyword in text for keyword in ["đùa", "dua", "joke", "câu đùa", "cau dua", "cười", "cuoi"]):
        return {"bot_text": "Đây nhé: KeoBot mà buồn thì vẫn phải... bật chế độ vui vẻ trước đã!", "emotion": "wink"}
    if any(keyword in text for keyword in ["mệt", "met", "buồn", "buon", "chán", "chan", "stress", "đuối", "duoi"]):
        return {"bot_text": "Nghe có vẻ bạn đang mệt. Nghỉ một chút rồi mình tính tiếp nhé.", "emotion": "sad"}
    if any(keyword in text for keyword in ["giải thích", "giai thich", "là gì", "la gi", "tại sao", "tai sao", "how", "rồi sao", "roi sao"]):
        return {"bot_text": "Mình sẽ giải thích ngắn gọn từng bước nhé.", "emotion": "thinking"}
    return {"bot_text": "Mình đã nghe rồi. Bạn muốn mình hỗ trợ phần nào tiếp theo?", "emotion": "neutral"}


async def generate_keobot_response(user_text: str) -> dict[str, str]:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider in {"local", "mock"}:
        return _local_keobot_response(user_text)

    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("Thiếu OPENAI_API_KEY cho LLM provider openai.")
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_chat_model,
            temperature=0.6,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
        )
        raw_text = response.choices[0].message.content or ""
    elif provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("Thiếu GEMINI_API_KEY cho LLM provider gemini.")
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            settings.gemini_model,
            system_instruction=SYSTEM_PROMPT,
        )
        response = model.generate_content(user_text)
        raw_text = getattr(response, "text", "") or ""
    else:
        raise RuntimeError(f"LLM_PROVIDER không được hỗ trợ: {settings.llm_provider}")

    payload = _extract_json_object(raw_text)
    if payload is None:
        return {"bot_text": raw_text.strip(), "emotion": "neutral"}

    normalized = _coerce_response(payload, raw_text)
    return normalized.model_dump()
