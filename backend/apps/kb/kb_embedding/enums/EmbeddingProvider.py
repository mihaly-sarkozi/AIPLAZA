from __future__ import annotations

from enum import Enum


class EmbeddingProvider(str, Enum):
    DUMMY = "dummy"
    LOCAL = "local"
    OPENAI = "openai"


__all__ = ["EmbeddingProvider"]
