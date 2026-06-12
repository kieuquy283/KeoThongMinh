from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.services.embedding_provider import EMBEDDING_DIM, get_embedding_provider

logger = logging.getLogger("keobot.vector_store")

VECTOR_FILENAME = "vectors.npz"


def get_default_vector_path() -> Path:
    from app.data_paths import get_indexes_dir
    return get_indexes_dir() / VECTOR_FILENAME


@lru_cache(maxsize=1)
def get_vector_store() -> "VectorStore":
    return VectorStore()


class VectorStore:
    def __init__(self, vectors_path: Path | None = None) -> None:
        self.vectors_path = vectors_path or get_default_vector_path()
        self._vectors: np.ndarray | None = None
        self._chunk_ids: list[int] = []
        self._dirty = False

    def _load(self) -> None:
        if self.vectors_path.exists():
            try:
                data = np.load(self.vectors_path)
                self._vectors = data["vectors"]
                self._chunk_ids = data["chunk_ids"].tolist()
                logger.info(
                    "Vector store loaded: %d vectors, dim=%d",
                    len(self._chunk_ids),
                    self._vectors.shape[1] if self._vectors is not None else 0,
                )
            except Exception as exc:
                logger.warning("Failed to load vector store, reinitializing: %s", exc)
                self._vectors = None
                self._chunk_ids = []
        if self._vectors is None:
            self._vectors = np.empty((0, EMBEDDING_DIM), dtype=np.float32)
            self._chunk_ids = []

    def _save(self) -> None:
        if self._vectors is None or len(self._chunk_ids) == 0:
            if self.vectors_path.exists():
                self.vectors_path.unlink(missing_ok=True)
            return
        self.vectors_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            self.vectors_path,
            vectors=self._vectors,
            chunk_ids=np.array(self._chunk_ids, dtype=np.int64),
        )
        logger.debug("Vector store saved: %d vectors", len(self._chunk_ids))

    def _ensure_loaded(self) -> None:
        if self._vectors is None:
            self._load()

    def add_vectors(self, chunk_ids: list[int], texts: list[str]) -> int:
        self._ensure_loaded()
        if not chunk_ids or not texts:
            return 0
        provider = get_embedding_provider()
        if not provider.is_available():
            logger.warning("Embedding provider not available, skipping vector add")
            return 0
        chunks_data = [{"text": t} for t in texts]
        embeddings = provider.embed_chunks(chunks_data)
        if not embeddings or len(embeddings) == 0:
            return 0
        new_vectors = np.array(embeddings, dtype=np.float32)
        if self._vectors is None or self._vectors.shape[0] == 0:
            self._vectors = new_vectors
            self._chunk_ids = list(chunk_ids)
        else:
            self._vectors = np.vstack([self._vectors, new_vectors])
            self._chunk_ids.extend(chunk_ids)
        self._save()
        logger.info(
            "Vectors added: %d chunks, total=%d", len(chunk_ids), len(self._chunk_ids)
        )
        return len(chunk_ids)

    def remove_vectors(self, chunk_ids: set[int]) -> int:
        self._ensure_loaded()
        if not chunk_ids or self._vectors is None or self._vectors.shape[0] == 0:
            return 0
        before = len(self._chunk_ids)
        keep_mask = [cid not in chunk_ids for cid in self._chunk_ids]
        self._vectors = self._vectors[keep_mask]
        self._chunk_ids = [
            cid for cid in self._chunk_ids if cid not in chunk_ids
        ]
        removed = before - len(self._chunk_ids)
        if removed > 0:
            self._save()
            logger.info("Vectors removed: %d chunks", removed)
        return removed

    def remove_vectors_by_document(self, document_id: int, store: Any = None) -> int:
        if store is None:
            from app.services.knowledge_store import get_knowledge_store
            store = get_knowledge_store()
        chunk_ids = store.get_chunk_ids_for_document(document_id)
        return self.remove_vectors(set(chunk_ids))

    def search(
        self, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        self._ensure_loaded()
        if self._vectors is None or self._vectors.shape[0] == 0:
            return []
        provider = get_embedding_provider()
        if not provider.is_available():
            return []
        query_vec = np.array(provider.embed_query(query), dtype=np.float32)
        if query_vec.shape[0] != EMBEDDING_DIM:
            logger.warning(
                "Query embedding dim mismatch: got %d, expected %d",
                query_vec.shape[0], EMBEDDING_DIM,
            )
            return []
        query_norm = np.linalg.norm(query_vec)
        if query_norm < 1e-10:
            return []
        query_vec = query_vec / query_norm
        norms = np.linalg.norm(self._vectors, axis=1, keepdims=True)
        norms = np.where(norms < 1e-10, 1.0, norms)
        normalized = self._vectors / norms
        similarities = np.dot(normalized, query_vec)
        top_k = min(limit, len(similarities))
        if top_k <= 0:
            return []
        top_indices = np.argpartition(similarities, -top_k)[-top_k:]
        top_indices = top_indices[np.argsort(-similarities[top_indices])]
        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score < 0.1:
                continue
            chunk_id = self._chunk_ids[idx]
            results.append({"chunk_id": chunk_id, "score": score})
        logger.debug(
            "Vector search: query='%s' results=%d", query, len(results)
        )
        return results

    def clear(self) -> int:
        self._ensure_loaded()
        count = len(self._chunk_ids)
        self._vectors = np.empty((0, EMBEDDING_DIM), dtype=np.float32)
        self._chunk_ids = []
        if self.vectors_path.exists():
            self.vectors_path.unlink(missing_ok=True)
        logger.info("Vector store cleared: %d vectors", count)
        return count

    def get_count(self) -> int:
        self._ensure_loaded()
        return len(self._chunk_ids)
