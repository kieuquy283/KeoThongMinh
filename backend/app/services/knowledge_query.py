from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app.services.knowledge_store import get_knowledge_store

logger = logging.getLogger("keobot.knowledge")

NOT_ENOUGH_CONTEXT = "Mình chưa có đủ thông tin trong tài liệu local để trả lời câu hỏi này. Bạn hãy thử import thêm tài liệu liên quan nhé."


async def answer_from_knowledge(
    query: str, max_sources: int = 3, mode: str = "hybrid"
) -> dict[str, Any]:
    store = get_knowledge_store()
    chunks = store.hybrid_search_chunks(query, limit=max_sources, mode=mode)

    if not chunks:
        logger.info("Knowledge answer: no relevant chunks for query='%s'", query)
        return {
            "query": query,
            "answer": NOT_ENOUGH_CONTEXT,
            "sources": [],
            "has_sufficient_context": False,
        }

    context_parts: list[str] = []
    for i, chunk in enumerate(chunks):
        header = ""
        citation = f"[{i + 1}]"
        if chunk.get("source_title"):
            header = f"{citation} {chunk['source_title']}"
            if chunk.get("source_location"):
                header += f" ({chunk['source_location']})"
        text = chunk.get("text", "").strip()
        if header:
            context_parts.append(f"{header}\n{text}")
        else:
            context_parts.append(f"{citation}\n{text}")

    context = "\n\n---\n\n".join(context_parts)
    answer = await _generate_answer(query, context)

    sources = []
    for i, c in enumerate(chunks):
        score = c.get("score", 1.0)
        if isinstance(score, (np.floating,)):
            score = float(score)
        sources.append({
            "id": c.get("id"),
            "document_id": c.get("document_id"),
            "chunk_index": c.get("chunk_index"),
            "citation_index": i + 1,
            "text": c.get("text", "")[:300],
            "source_title": c.get("source_title") or c.get("original_filename", ""),
            "source_location": c.get("source_location"),
            "score": score,
        })

    logger.info(
        "Knowledge answer generated: query='%s' sources=%d mode=%s",
        query, len(sources), mode,
    )
    return {
        "query": query,
        "answer": answer,
        "sources": sources,
        "has_sufficient_context": True,
    }


async def _generate_answer(query: str, context: str) -> str:
    try:
        from app.providers.llm import generate_keobot_response
        prompt = (
            f"Người dùng hỏi: {query}\n\n"
            f"Dưới đây là thông tin từ tài liệu local của người dùng:\n\n{context}\n\n"
            f"Hãy trả lời dựa trên thông tin trên. Khi trích dẫn, hãy dùng [số] để chỉ nguồn. "
            f"Nếu không đủ thông tin, hãy nói rõ."
        )
        response = await generate_keobot_response(prompt)
        return response.get("bot_text", "")
    except Exception as exc:
        logger.warning("LLM answer generation failed, using extractive fallback: %s", exc)
        return _extractive_answer(query, context)


def _extractive_answer(query: str, context: str) -> str:
    sentences = context.replace("\n", " ").split(". ")
    relevant = [s for s in sentences if any(w.lower() in s.lower() for w in query.split())]
    if relevant:
        snippet = ". ".join(relevant[:3])
        if not snippet.endswith("."):
            snippet += "."
        return f"Theo tài liệu của bạn:\n\n{snippet}"
    first_part = context[:500].strip()
    return f"Mình tìm thấy thông tin sau trong tài liệu của bạn:\n\n{first_part}..."
