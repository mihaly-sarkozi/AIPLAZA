from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IndexProfile:
    key: str
    chunking_rule: str = "sentence"
    embedding_strategy: str = "local:BAAI/bge-m3"
    index_type: str = "qdrant_dense"
    metadata_mode: str = "source_payload"
    config: dict[str, Any] = field(default_factory=dict)


DEFAULT_INDEX_PROFILE = IndexProfile(key="basic_chunk_v1")


__all__ = ["DEFAULT_INDEX_PROFILE", "IndexProfile"]
