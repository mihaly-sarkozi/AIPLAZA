from __future__ import annotations

import logging

from apps.kb.kb_embedding.adapters.DummyEmbeddingAdapter import DummyEmbeddingAdapter

logger = logging.getLogger(__name__)


class LocalEmbeddingAdapter:
    """Helyi embedding modell adapter — jelenleg dummy fallback."""

    def __init__(self, dimension: int = 1024) -> None:
        self._fallback = DummyEmbeddingAdapter(dimension=dimension)

    def embed_texts(self, texts: list[str], model: str) -> list[list[float]]:
        logger.warning(
            "LocalEmbeddingAdapter: nincs lokális modell bekötve, dummy vektor használata (model=%s)",
            model,
        )
        return self._fallback.embed_texts(texts, model)


__all__ = ["LocalEmbeddingAdapter"]
