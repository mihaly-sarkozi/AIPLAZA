from __future__ import annotations

import logging
from typing import Any

from apps.kb.kb_embedding.errors.LocalEmbeddingError import LocalEmbeddingError

logger = logging.getLogger(__name__)


class QueryEmbeddingProviderAdapter:
    """Runtime query embedding — ugyanaz a provider mint az indexelésnél."""

    def __init__(self, provider: Any, *, default_dimension: int | None = None) -> None:
        self._provider = provider
        self._default_dimension = max(1, int(default_dimension)) if default_dimension else None

    def embed_query(
        self,
        text: str,
        *,
        model: str,
        expected_dimension: int | None = None,
    ) -> tuple[list[float], str, int]:
        resolved_dimension = expected_dimension or self._default_dimension
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
        actual_dimension = len(vector)
        if resolved_dimension is not None and actual_dimension != resolved_dimension:
            raise LocalEmbeddingError(
                "QUERY_EMBEDDING_DIMENSION_MISMATCH",
                message="dimension_mismatch",
                expected=resolved_dimension,
                actual=actual_dimension,
                model=model,
            )
        return vector, model, actual_dimension


__all__ = ["QueryEmbeddingProviderAdapter"]
