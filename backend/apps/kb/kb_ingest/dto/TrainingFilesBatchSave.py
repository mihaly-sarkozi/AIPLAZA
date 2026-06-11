from __future__ import annotations

from dataclasses import dataclass, field

from apps.kb.kb_ingest.dto.TrainingFileItemSave import TrainingFileItemSave


@dataclass(frozen=True)
class TrainingFilesBatchSave:
    batch_id: str
    tenant: str
    knowledge_base_id: str
    created_by: int
    items: list[TrainingFileItemSave] = field(default_factory=list)


__all__ = ["TrainingFilesBatchSave"]
