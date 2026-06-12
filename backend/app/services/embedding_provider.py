from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from enum import Enum
from functools import lru_cache
from typing import Any

import numpy as np

logger = logging.getLogger("keobot.embedding")

EMBEDDING_DIM = 128


class EmbeddingProviderType(str, Enum):
    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"
    LOCAL = "local"


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def provider_type(self) -> str:
        ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        ...

    @abstractmethod
    def embed_chunks(self, chunks: list[dict[str, Any]]) -> list[list[float]]:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...


class DisabledEmbeddingProvider(EmbeddingProvider):
    provider_type = EmbeddingProviderType.DISABLED

    def embed_query(self, text: str) -> list[float]:
        return []

    def embed_chunks(self, chunks: list[dict[str, Any]]) -> list[list[float]]:
        return []

    def is_available(self) -> bool:
        return False


class DeterministicEmbeddingProvider(EmbeddingProvider):
    provider_type = EmbeddingProviderType.DETERMINISTIC

    def _text_to_vector(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        rng = np.frombuffer(h, dtype=np.uint32)[0]
        np.random.seed(int(rng))
        vec = np.random.randn(EMBEDDING_DIM).astype(np.float32)
        vec = vec / (np.linalg.norm(vec) + 1e-10)
        return vec.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._text_to_vector(text)

    def embed_chunks(self, chunks: list[dict[str, Any]]) -> list[list[float]]:
        return [self._text_to_vector(c["text"]) for c in chunks]

    def is_available(self) -> bool:
        return True


class LocalEmbeddingProvider(EmbeddingProvider):
    provider_type = EmbeddingProviderType.LOCAL

    def __init__(self) -> None:
        self._dim = EMBEDDING_DIM

    def _text_to_vector(self, text: str) -> list[float]:
        words = text.lower().split()
        vec = np.zeros(self._dim, dtype=np.float32)
        if not words:
            return vec.tolist()
        for word in words:
            h = hashlib.md5(word.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "little") % self._dim
            sign = 1.0 if (h[4] & 1) == 0 else -1.0
            vec[idx] += sign
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._text_to_vector(text)

    def embed_chunks(self, chunks: list[dict[str, Any]]) -> list[list[float]]:
        return [self._text_to_vector(c["text"]) for c in chunks]

    def is_available(self) -> bool:
        return True


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    from app.config import get_settings
    settings = get_settings()
    mode = getattr(settings, "EMBEDDING_PROVIDER", "local")
    if mode == "disabled":
        logger.info("Embedding provider: disabled")
        return DisabledEmbeddingProvider()
    if mode == "deterministic":
        logger.info("Embedding provider: deterministic (test mode)")
        return DeterministicEmbeddingProvider()
    logger.info("Embedding provider: local (hash-based)")
    return LocalEmbeddingProvider()
