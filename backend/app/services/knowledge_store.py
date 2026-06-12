from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("keobot.knowledge")

RRF_K = 60.0


def get_default_db_path() -> Path:
    from app.data_paths import get_indexes_dir
    return get_indexes_dir() / "knowledge.sqlite3"


@lru_cache(maxsize=1)
def get_knowledge_store() -> "KnowledgeStore":
    return KnowledgeStore()


class KnowledgeStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    sha256 TEXT NOT NULL UNIQUE,
                    stored_path TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'imported',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    source_title TEXT,
                    source_location TEXT,
                    token_estimate INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
            """)
            self._create_fts(conn)

    def _create_fts(self, conn: sqlite3.Connection) -> None:
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    text,
                    content='chunks',
                    content_rowid='id',
                    tokenize='unicode61'
                )
            """)
            conn.executescript("""
                CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
                END;
                CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
                END;
                CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
                    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
                    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
                END;
            """)
        except sqlite3.OperationalError:
            logger.warning("FTS5 not available, falling back to LIKE search")

    def add_document(self, filename: str, original_filename: str, file_type: str, size_bytes: int, sha256: str, stored_path: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO documents (filename, original_filename, file_type, size_bytes, sha256, stored_path, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'imported', ?, ?)
                """,
                (filename, original_filename, file_type, size_bytes, sha256, stored_path, now, now),
            )
            doc_id = cursor.lastrowid
        logger.info("Document added: id=%d filename=%s sha256=%s", doc_id, original_filename, sha256)
        return self.get_document(doc_id)

    def update_document_status(self, doc_id: int, status: str, error_message: str | None = None, chunk_count: int | None = None) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            fields = ["status = ?", "updated_at = ?"]
            params: list[Any] = [status, now]
            if error_message is not None:
                fields.append("error_message = ?")
                params.append(error_message)
            if chunk_count is not None:
                fields.append("chunk_count = ?")
                params.append(chunk_count)
            params.append(doc_id)
            conn.execute(f"UPDATE documents SET {', '.join(fields)} WHERE id = ?", params)
        return self.get_document(doc_id)

    def list_documents(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_document(self, doc_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None

    def get_document_by_sha256(self, sha256: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE sha256 = ?", (sha256,)).fetchone()
        return dict(row) if row else None

    def delete_document(self, doc_id: int) -> bool:
        doc = self.get_document(doc_id)
        if doc is None:
            return False
        from app.services.vector_store import get_vector_store
        get_vector_store().remove_vectors_by_document(doc_id, store=self)
        stored_path = doc["stored_path"]
        with self._connect() as conn:
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        if stored_path and Path(stored_path).exists():
            Path(stored_path).unlink(missing_ok=True)
        logger.info("Document deleted: id=%d path=%s", doc_id, stored_path)
        return True

    def add_chunks(self, doc_id: int, chunks: list[dict[str, Any]]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        chunk_ids: list[int] = []
        with self._connect() as conn:
            for i, chunk in enumerate(chunks):
                cursor = conn.execute(
                    """
                    INSERT INTO chunks (document_id, chunk_index, text, source_title, source_location, token_estimate, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (doc_id, i, chunk["text"], chunk.get("source_title"), chunk.get("source_location"), chunk.get("token_estimate", 0), now),
                )
                chunk_ids.append(cursor.lastrowid)
        count = len(chunk_ids)
        self.update_document_status(doc_id, "indexed", chunk_count=count)
        from app.services.vector_store import get_vector_store
        try:
            get_vector_store().add_vectors(chunk_ids, [c["text"] for c in chunks])
        except Exception as exc:
            logger.warning("Vector indexing failed for doc_id=%d: %s", doc_id, exc)
        logger.info("Chunks added: doc_id=%d count=%d", doc_id, count)
        return count

    def search_chunks(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        with self._connect() as conn:
            has_fts = self._check_fts(conn)
            if has_fts:
                try:
                    rows = conn.execute(
                        """
                        SELECT c.id, c.document_id, c.chunk_index, c.text, c.source_title, c.source_location, c.token_estimate, c.created_at,
                               d.filename AS document_filename, d.original_filename AS document_original_filename, d.file_type, d.stored_path
                        FROM chunks_fts f
                        JOIN chunks c ON f.rowid = c.id
                        JOIN documents d ON c.document_id = d.id
                        WHERE chunks_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (query, limit),
                    ).fetchall()
                    return [dict(row) for row in rows]
                except sqlite3.OperationalError:
                    pass
            like_query = f"%{query}%"
            rows = conn.execute(
                """
                SELECT c.id, c.document_id, c.chunk_index, c.text, c.source_title, c.source_location, c.token_estimate, c.created_at,
                       d.filename AS document_filename, d.original_filename AS document_original_filename, d.file_type, d.stored_path
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE c.text LIKE ? OR c.source_title LIKE ?
                LIMIT ?
                """,
                (like_query, like_query, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_all_chunks(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.document_id, c.chunk_index, c.text, c.source_title, c.source_location, c.token_estimate, c.created_at,
                       d.filename AS document_filename, d.original_filename AS document_original_filename, d.file_type, d.stored_path
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                ORDER BY c.document_id, c.chunk_index
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_chunk_ids_for_document(self, document_id: int) -> list[int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id FROM chunks WHERE document_id = ?", (document_id,)
            ).fetchall()
        return [row["id"] for row in rows]

    def get_chunks_for_document(self, document_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chunks WHERE document_id = ? ORDER BY chunk_index",
                (document_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_document_text(self, document_id: int) -> str | None:
        chunks = self.get_chunks_for_document(document_id)
        if not chunks:
            return None
        return "\n\n".join(c["text"] for c in chunks)

    def hybrid_search_chunks(
        self, query: str, limit: int = 5, mode: str = "hybrid"
    ) -> list[dict[str, Any]]:
        if mode == "keyword":
            return self.search_chunks(query, limit=limit)
        fts_results = self.search_chunks(query, limit=limit * 2)
        fts_map: dict[int, dict[str, Any]] = {}
        for rank, r in enumerate(fts_results):
            cid = r["id"]
            r["_fts_rank"] = rank
            r["_fts_score"] = 1.0 / (RRF_K + rank)
            r["_vector_score"] = 0.0
            r["_hybrid_score"] = r["_fts_score"]
            fts_map[cid] = r
        if mode == "semantic":
            from app.services.vector_store import get_vector_store
            vec_store = get_vector_store()
            vec_results = vec_store.search(query, limit=limit * 2)
            for rank, vr in enumerate(vec_results):
                cid = vr["chunk_id"]
                vec_score = 1.0 / (RRF_K + rank)
                if cid in fts_map:
                    fts_map[cid]["_vector_score"] = vec_score
                    fts_map[cid]["_hybrid_score"] = (
                        fts_map[cid]["_fts_score"] + vec_score
                    )
                else:
                    with self._connect() as conn:
                        row = conn.execute(
                            """
                            SELECT c.id, c.document_id, c.chunk_index, c.text,
                                   c.source_title, c.source_location, c.token_estimate, c.created_at,
                                   d.filename AS document_filename,
                                   d.original_filename AS document_original_filename,
                                   d.file_type, d.stored_path
                            FROM chunks c
                            JOIN documents d ON c.document_id = d.id
                            WHERE c.id = ?
                            """,
                            (cid,),
                        ).fetchone()
                    if row is not None:
                        r = dict(row)
                        r["_fts_rank"] = limit * 2
                        r["_fts_score"] = 0.0
                        r["_vector_score"] = vec_score
                        r["_hybrid_score"] = vec_score
                        fts_map[cid] = r
            if mode == "semantic":
                ranked = sorted(
                    fts_map.values(),
                    key=lambda x: x["_vector_score"],
                    reverse=True,
                )[:limit]
                for r in ranked:
                    r["score"] = r["_vector_score"]
                return ranked
        if mode == "hybrid":
            from app.services.vector_store import get_vector_store
            vec_store = get_vector_store()
            vec_results = vec_store.search(query, limit=limit * 2)
            for rank, vr in enumerate(vec_results):
                cid = vr["chunk_id"]
                vec_score = 1.0 / (RRF_K + rank)
                if cid in fts_map:
                    fts_map[cid]["_vector_score"] = vec_score
                    fts_map[cid]["_hybrid_score"] = (
                        fts_map[cid]["_fts_score"] + vec_score
                    )
                else:
                    with self._connect() as conn:
                        row = conn.execute(
                            """
                            SELECT c.id, c.document_id, c.chunk_index, c.text,
                                   c.source_title, c.source_location, c.token_estimate, c.created_at,
                                   d.filename AS document_filename,
                                   d.original_filename AS document_original_filename,
                                   d.file_type, d.stored_path
                            FROM chunks c
                            JOIN documents d ON c.document_id = d.id
                            WHERE c.id = ?
                            """,
                            (cid,),
                        ).fetchone()
                    if row is not None:
                        r = dict(row)
                        r["_fts_rank"] = limit * 2
                        r["_fts_score"] = 0.0
                        r["_vector_score"] = vec_score
                        r["_hybrid_score"] = vec_score
                        fts_map[cid] = r
            ranked = sorted(
                fts_map.values(),
                key=lambda x: x["_hybrid_score"],
                reverse=True,
            )[:limit]
            for r in ranked:
                r["score"] = r["_hybrid_score"]
            return ranked
        return fts_results[:limit]

    def clear_knowledge_base(self) -> int:
        with self._connect() as conn:
            count_row = conn.execute("SELECT COUNT(*) AS count FROM documents").fetchone()
            count = int(count_row["count"]) if count_row else 0
            conn.execute("DELETE FROM chunks")
            conn.execute("DELETE FROM documents")
        from app.services.vector_store import get_vector_store
        get_vector_store().clear()
        logger.info("Knowledge base cleared: %d documents", count)
        return count

    def _check_fts(self, conn: sqlite3.Connection) -> bool:
        try:
            conn.execute("SELECT 1 FROM chunks_fts LIMIT 0").fetchall()
            return True
        except sqlite3.OperationalError:
            return False
