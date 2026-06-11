from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger("keobot.document_importer")

SUPPORTED_EXTENSIONS: set[str] = {".txt", ".md", ".pdf", ".docx"}


def import_document(file_path: str | Path, source_name: str | None = None) -> dict[str, Any]:
    from app.data_paths import get_documents_dir, get_temp_dir
    from app.services.knowledge_store import get_knowledge_store
    from app.services.text_chunker import chunk_text

    file_path = Path(file_path).expanduser().resolve()
    if not file_path.exists():
        return {"ok": False, "error": f"File not found: {file_path}"}

    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return {"ok": False, "error": f"Unsupported file type: {ext}"}

    original_name = source_name or file_path.name

    raw_bytes = file_path.read_bytes()
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    size_bytes = len(raw_bytes)

    store = get_knowledge_store()
    existing = store.get_document_by_sha256(sha256)
    if existing is not None:
        return {
            "ok": False,
            "error": f"Duplicate document (SHA256: {sha256[:12]}...) already imported as: {existing['original_filename']}",
            "existing_id": existing["id"],
            "existing_filename": existing["original_filename"],
        }

    safe_name = f"{uuid4().hex}{ext}"
    docs_dir = get_documents_dir()
    docs_dir.mkdir(parents=True, exist_ok=True)
    stored_path = docs_dir / safe_name
    stored_path.write_bytes(raw_bytes)

    doc = store.add_document(
        filename=safe_name,
        original_filename=original_name,
        file_type=ext.lstrip("."),
        size_bytes=size_bytes,
        sha256=sha256,
        stored_path=str(stored_path),
    )
    doc_id = doc["id"]

    try:
        text = _extract_text(file_path, ext)
    except Exception as exc:
        store.update_document_status(doc_id, "failed", error_message=str(exc))
        logger.error("Text extraction failed for %s: %s", original_name, exc)
        return {"ok": False, "error": f"Text extraction failed: {exc}"}

    if not text.strip():
        store.update_document_status(doc_id, "failed", error_message="No extractable text found")
        logger.warning("No text extracted from %s", original_name)
        return {"ok": False, "error": "No extractable text found in document"}

    page_count = _extract_page_count(file_path, ext)
    location = f"File: {original_name}"
    if page_count:
        location += f" ({page_count} trang)"

    chunks = chunk_text(text, source_title=original_name, source_location=location)

    if not chunks:
        store.update_document_status(doc_id, "failed", error_message="Chunking produced no output")
        return {"ok": False, "error": "Chunking produced no output"}

    chunk_count = store.add_chunks(doc_id, chunks)

    logger.info(
        "Document imported: id=%d name=%s type=%s size=%d sha256=%s chunks=%d",
        doc_id, original_name, ext, size_bytes, sha256, chunk_count,
    )

    return {
        "ok": True,
        "document_id": doc_id,
        "filename": original_name,
        "file_type": ext.lstrip("."),
        "size_bytes": size_bytes,
        "sha256": sha256,
        "chunk_count": chunk_count,
    }


def _extract_text(file_path: Path, ext: str) -> str:
    if ext == ".txt":
        return file_path.read_text(encoding="utf-8", errors="replace")
    if ext == ".md":
        return _extract_markdown_text(file_path)
    if ext == ".pdf":
        return _extract_pdf_text(file_path)
    if ext == ".docx":
        return _extract_docx_text(file_path)
    return ""


def _extract_markdown_text(file_path: Path) -> str:
    text = file_path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~`]", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^[>\-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^(\d+)\.\s+", r"\1. ", text, flags=re.MULTILINE)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_pdf_text(file_path: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(file_path))
    parts: list[str] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            parts.append(f"[Trang {i + 1}]\n{text.strip()}")
    return "\n\n".join(parts)


def _extract_docx_text(file_path: Path) -> str:
    from docx import Document
    doc = Document(str(file_path))
    parts: list[str] = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text.strip())
    return "\n\n".join(parts)


def _extract_page_count(file_path: Path, ext: str) -> int | None:
    try:
        if ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(file_path))
            return len(reader.pages)
        return None
    except Exception:
        return None
