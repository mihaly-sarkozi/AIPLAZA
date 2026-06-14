from __future__ import annotations

from typing import Protocol


class EmbeddingProviderPort(Protocol):
    def embed_texts(self, texts: list[str], model: str) -> list[list[float]]: ...


__all__ = ["EmbeddingProviderPort"]
