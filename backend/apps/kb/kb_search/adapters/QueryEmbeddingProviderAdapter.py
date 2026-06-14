from __future__ import annotations

import logging
from typing import Any

from apps.kb.kb_embedding.errors.LocalEmbeddingError import LocalEmbeddingError

logger = logging.getLogger(__name__)


class QueryEmbeddingProviderAdapter:
    """Runtime query embedding — ugyanaz a provider mint az indexelésnél."""

    def __init__(self, provider: Any, *, expected_dimension: int) -> None:
        self._provider = provider
        self._expected_dimension = max(1, int(expected_dimension))

    def embed_query(self, text: str, *, model: str) -> tuple[list[float], str, int]:
        normalized = str(text or "").strip() or " "
        try:
            if hasattr(self._provider, "ensure_model_loaded"):
                self._provider.ensure_model_loaded(model)
            vectors = self._provider.embed_texts([normalized], model)
        except LocalEmbeddingError:
            raise
        except Exception as exc:
            logger.exception("Query embedding failed (model=%s)", model)
            raise LocalEmbeddingError(
                "QUERY_EMBEDDING_FAILED",
                message=str(exc),
                model=model,
            ) from exc

        if not vectors or not vectors[0]:
            raise LocalEmbeddingError("QUERY_EMBEDDING_FAILED", message="empty_vector", model=model)

        vector = [float(v) for v in vectors[0]]
        if len(vector) != self._expected_dimension:
            raise LocalEmbeddingError(
                "QUERY_EMBEDDING_DIMENSION_MISMATCH",
                message="dimension_mismatch",
                expected=self._expected_dimension,
                actual=len(vector),
                model=model,
            )
        return vector, model, len(vector)


__all__ = ["QueryEmbeddingProviderAdapter"]
