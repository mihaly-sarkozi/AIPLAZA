from __future__ import annotations

# backend/apps/kb/kb_understanding/ports/EmbeddingProviderInterface.py
# Feladat: Embedding szolgáltató szerződés — LocalEmbedder / OpenAIEmbedder cserélhető.
# Sárközi Mihály - 2026.06.11

from typing import Protocol


class EmbeddingProviderInterface(Protocol):
    @property
    def model_name(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


__all__ = ["EmbeddingProviderInterface"]
