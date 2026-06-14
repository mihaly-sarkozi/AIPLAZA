from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IndexingDiagnosticsResponse:
    knowledge_base_id: str
    training_item_id: str | None = None
    embedding: dict[str, Any] = field(default_factory=dict)
    indexing: dict[str, Any] = field(default_factory=dict)
    qdrant: dict[str, Any] = field(default_factory=dict)
    readiness: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_base_id": self.knowledge_base_id,
            "training_item_id": self.training_item_id,
            "embedding": self.embedding,
            "indexing": self.indexing,
            "qdrant": self.qdrant,
            "readiness": self.readiness,
        }


__all__ = ["IndexingDiagnosticsResponse"]
