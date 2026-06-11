from __future__ import annotations

# backend/apps/kb/kb_understanding/adapters/LocalEmbedder.py
# Feladat: Lokális embedding szolgáltató (sentence-transformers, BAAI/bge-m3).
# A modell lazy-load: első használatkor töltődik be.
# Sárközi Mihály - 2026.06.11

import threading

from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError


class LocalEmbedder:
    """``EmbeddingProviderInterface`` implementáció lokális modellel."""

    def __init__(self, model_name: str | None = None, batch_size: int | None = None) -> None:
        from core.kernel.config.config_loader import settings

        self._model_name = model_name or str(
            getattr(settings, "embedding_model", "BAAI/bge-m3") or "BAAI/bge-m3"
        )
        self._batch_size = int(
            batch_size or getattr(settings, "embedding_batch_size", 16) or 16
        )
        self._dimension = int(getattr(settings, "embedding_vector_size", 0) or 0)
        self._model = None
        self._lock = threading.Lock()

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load_model()
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            try:
                encoded = model.encode(batch, normalize_embeddings=True)
            except Exception as exc:
                raise UnderstandingProcessingError(
                    UnderstandingErrorCode.EMBEDDING_FAILED, retryable=True
                ) from exc
            vectors.extend([list(map(float, vector)) for vector in encoded])
        if vectors and not self._dimension:
            self._dimension = len(vectors[0])
        return vectors

    def _load_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                except Exception as exc:  # pragma: no cover - dependency guard
                    raise UnderstandingProcessingError(
                        UnderstandingErrorCode.EMBEDDING_PROVIDER_UNAVAILABLE
                    ) from exc
                try:
                    self._model = SentenceTransformer(self._model_name)
                except Exception as exc:
                    raise UnderstandingProcessingError(
                        UnderstandingErrorCode.EMBEDDING_PROVIDER_UNAVAILABLE, retryable=True
                    ) from exc
                detected = getattr(self._model, "get_sentence_embedding_dimension", lambda: 0)()
                if detected:
                    self._dimension = int(detected)
        return self._model


__all__ = ["LocalEmbedder"]
