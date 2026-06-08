from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TrainingTextBatchSave:
    batch_id: str
    item_id: str
    tenant: str
    knowledge_base_id: str
    created_by: int
    content_hash: str
    title: str
    raw_ref: str
    mime_type: str
    size_bytes: int
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["TrainingTextBatchSave"]
