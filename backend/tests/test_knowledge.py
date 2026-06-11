from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def sample_txt(tmp_path):
    p = tmp_path / "sample.txt"
    p.write_bytes("Xin chào, tôi là Kẹo Thông Minh.\n\nĐây là đoạn văn thứ hai để kiểm tra chunking.\n\nĐoạn thứ ba có nội dung về trí tuệ nhân tạo.".encode("utf-8"))
    return p


@pytest.fixture
def sample_md(tmp_path):
    p = tmp_path / "sample.md"
    p.write_bytes("# Tiêu đề\n\nNội dung markdown.\n\n## Phần 2\n\nChi tiết về phần 2.".encode("utf-8"))
    return p


class TestKnowledgeStore:
    def test_init_creates_db(self, app_module):
        from app.services.knowledge_store import get_knowledge_store, get_default_db_path
        store = get_knowledge_store()
        assert get_default_db_path().exists()

    def test_add_and_list_document(self, app_module):
        from app.services.knowledge_store import get_knowledge_store
        store = get_knowledge_store()
        store.add_document("test.txt", "test.txt", "txt", 100, "abc123", "/tmp/test.txt")
        docs = store.list_documents()
        assert len(docs) == 1
        assert docs[0]["original_filename"] == "test.txt"
        store.clear_knowledge_base()

    def test_duplicate_sha256_detected(self, app_module):
        from app.services.knowledge_store import get_knowledge_store
        store = get_knowledge_store()
        store.add_document("a.txt", "a.txt", "txt", 100, "dup123", "/tmp/a.txt")
        dup = store.get_document_by_sha256("dup123")
        assert dup is not None
        assert dup["original_filename"] == "a.txt"
        store.clear_knowledge_base()

    def test_add_chunks_and_search(self, app_module):
        from app.services.knowledge_store import get_knowledge_store
        store = get_knowledge_store()
        doc = store.add_document("test.txt", "test.txt", "txt", 100, "searchtest", "/tmp/test.txt")
        doc_id = doc["id"]
        store.add_chunks(doc_id, [
            {"text": "Trí tuệ nhân tạo đang phát triển nhanh chóng.", "source_title": "test.txt"},
            {"text": "Học máy là một nhánh của AI.", "source_title": "test.txt"},
        ])
        results = store.search_chunks("trí tuệ", limit=5)
        assert len(results) >= 1
        assert any("trí tuệ" in r["text"].lower() for r in results)
        store.clear_knowledge_base()

    def test_delete_document_removes_chunks(self, app_module):
        from app.services.knowledge_store import get_knowledge_store
        store = get_knowledge_store()
        doc = store.add_document("del.txt", "del.txt", "txt", 100, "deletestore", "/tmp/del.txt")
        doc_id = doc["id"]
        store.add_chunks(doc_id, [{"text": "Chunk to delete.", "source_title": "del.txt"}])
        store.delete_document(doc_id)
        assert store.get_document(doc_id) is None
        store.clear_knowledge_base()

    def test_clear_knowledge_base(self, app_module):
        from app.services.knowledge_store import get_knowledge_store
        store = get_knowledge_store()
        store.add_document("c.txt", "c.txt", "txt", 100, "clearstore", "/tmp/c.txt")
        count = store.clear_knowledge_base()
        assert count >= 1
        assert len(store.list_documents()) == 0


class TestDocumentImporter:
    def test_import_txt(self, app_module, sample_txt):
        from app.services.document_importer import import_document
        result = import_document(sample_txt)
        assert result["ok"]
        assert result["file_type"] == "txt"
        assert result["chunk_count"] > 0
        from app.services.knowledge_store import get_knowledge_store
        get_knowledge_store().clear_knowledge_base()

    def test_import_md(self, app_module, sample_md):
        from app.services.document_importer import import_document
        result = import_document(sample_md)
        assert result["ok"]
        assert result["file_type"] == "md"
        from app.services.knowledge_store import get_knowledge_store
        get_knowledge_store().clear_knowledge_base()

    def test_duplicate_import_rejected(self, app_module, sample_txt):
        from app.services.document_importer import import_document
        result1 = import_document(sample_txt)
        assert result1["ok"]
        result2 = import_document(sample_txt)
        assert not result2["ok"]
        assert "duplicate" in result2.get("error", "").lower()
        from app.services.knowledge_store import get_knowledge_store
        get_knowledge_store().clear_knowledge_base()

    def test_unsupported_extension_rejected(self, app_module, tmp_path):
        from app.services.document_importer import import_document
        p = tmp_path / "test.png"
        p.write_text("not a document")
        result = import_document(p)
        assert not result["ok"]
        assert "unsupported" in result.get("error", "").lower()

    def test_import_saves_under_documents_dir(self, app_module, sample_txt):
        from app.services.document_importer import import_document
        from app.data_paths import get_documents_dir
        result = import_document(sample_txt)
        assert result["ok"]
        docs_dir = get_documents_dir()
        stored = list(docs_dir.glob("*.txt"))
        assert len(stored) >= 1
        from app.services.knowledge_store import get_knowledge_store
        get_knowledge_store().clear_knowledge_base()


class TestTextChunker:
    def test_basic_chunking(self):
        from app.services.text_chunker import chunk_text
        text = "Đoạn một.\n\nĐoạn hai.\n\nĐoạn ba."
        chunks = chunk_text(text)
        assert len(chunks) >= 1
        assert all("text" in c for c in chunks)
        assert all("token_estimate" in c for c in chunks)

    def test_empty_text_returns_empty(self):
        from app.services.text_chunker import chunk_text
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_normalizes_whitespace(self):
        from app.services.text_chunker import chunk_text
        text = "  Hello   world.  \n\n\nNext  para.  "
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert "Hello   world" not in chunks[0]["text"]
        assert "Hello world" in chunks[0]["text"] or "Hello" in chunks[0]["text"]


class TestKnowledgeAPI:
    def test_list_documents_empty(self, client, app_module):
        response = client.get("/knowledge/documents")
        assert response.status_code == 200
        assert response.json() == []

    def test_import_and_list(self, client, app_module, sample_txt):
        with open(sample_txt, "rb") as f:
            response = client.post("/knowledge/documents/import", files={"file": ("sample.txt", f, "text/plain")})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"]
        assert data["file_type"] == "txt"
        list_resp = client.get("/knowledge/documents")
        assert len(list_resp.json()) >= 1
        from app.services.knowledge_store import get_knowledge_store
        get_knowledge_store().clear_knowledge_base()

    def test_search_returns_chunks(self, client, app_module, sample_txt):
        from app.services.document_importer import import_document
        import_document(sample_txt)
        response = client.post("/knowledge/search?query=Kẹo Thông Minh&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        from app.services.knowledge_store import get_knowledge_store
        get_knowledge_store().clear_knowledge_base()

    def test_ask_returns_answer(self, client, app_module, sample_txt):
        from app.services.document_importer import import_document
        import_document(sample_txt)
        response = client.post("/knowledge/ask?query=Kẹo Thông Minh là gì?")
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        from app.services.knowledge_store import get_knowledge_store
        get_knowledge_store().clear_knowledge_base()

    def test_ask_no_relevant_chunks_returns_not_enough(self, client, app_module):
        response = client.post("/knowledge/ask?query=không liên quan gì cả")
        assert response.status_code == 200
        data = response.json()
        assert not data["has_sufficient_context"]

    def test_delete_document(self, client, app_module, sample_txt):
        from app.services.document_importer import import_document
        result = import_document(sample_txt)
        doc_id = result["document_id"]
        response = client.delete(f"/knowledge/documents/{doc_id}")
        assert response.status_code == 200
        get_resp = client.get("/knowledge/documents")
        ids = [d["id"] for d in get_resp.json()]
        assert doc_id not in ids
        from app.services.knowledge_store import get_knowledge_store
        get_knowledge_store().clear_knowledge_base()

    def test_clear_knowledge_requires_confirmation(self, client, app_module):
        response = client.request("DELETE", "/knowledge", json={"confirm": False})
        assert response.status_code == 200
        data = response.json()
        assert not data["ok"]

    def test_import_path_imports_txt(self, client, app_module, sample_txt):
        response = client.post("/knowledge/documents/import-path", json={"path": str(sample_txt)})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"]
        assert data["file_type"] == "txt"
        from app.services.knowledge_store import get_knowledge_store
        get_knowledge_store().clear_knowledge_base()

    def test_import_path_unsupported_extension(self, client, app_module, tmp_path):
        p = tmp_path / "bad.exe"
        p.write_bytes(b"not a document")
        response = client.post("/knowledge/documents/import-path", json={"path": str(p)})
        assert response.status_code == 200
        data = response.json()
        assert not data["ok"]
        assert "unsupported" in data.get("error", "").lower()

    def test_import_path_duplicate_detected(self, client, app_module, sample_txt):
        response1 = client.post("/knowledge/documents/import-path", json={"path": str(sample_txt)})
        assert response1.json()["ok"]
        response2 = client.post("/knowledge/documents/import-path", json={"path": str(sample_txt)})
        data2 = response2.json()
        assert not data2["ok"]
        assert "duplicate" in data2.get("error", "").lower()
        from app.services.knowledge_store import get_knowledge_store
        get_knowledge_store().clear_knowledge_base()

    def test_import_path_file_not_found(self, client, app_module):
        response = client.post("/knowledge/documents/import-path", json={"path": "C:/nonexistent/file.txt"})
        assert response.status_code == 200
        data = response.json()
        assert not data["ok"]
        assert "not found" in data.get("error", "").lower()

    def test_import_path_copies_under_documents_dir(self, client, app_module, sample_txt):
        from app.data_paths import get_documents_dir
        response = client.post("/knowledge/documents/import-path", json={"path": str(sample_txt)})
        assert response.json()["ok"]
        docs_dir = get_documents_dir()
        stored = list(docs_dir.glob("*.txt"))
        assert len(stored) >= 1
        original_content = sample_txt.read_bytes()
        stored_content = stored[0].read_bytes()
        assert stored_content == original_content
        from app.services.knowledge_store import get_knowledge_store
        get_knowledge_store().clear_knowledge_base()

    def test_import_path_with_empty_path_fails_validation(self, client, app_module):
        response = client.post("/knowledge/documents/import-path", json={"path": ""})
        assert response.status_code == 422

    def test_clear_knowledge_with_confirmation(self, client, app_module, sample_txt):
        from app.services.document_importer import import_document
        import_document(sample_txt)
        response = client.request("DELETE", "/knowledge", json={"confirm": True})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"]
        assert data["documents_deleted"] >= 1
