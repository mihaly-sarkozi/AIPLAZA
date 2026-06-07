from __future__ import annotations

# backend/apps/kb/kb_training/storage/TrainingRawWriter.py
# Feladat: Tanítási nyers anyag írása a TrainingStorage porton keresztül.
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass

from apps.kb.kb_training.config import MetricsConf
from apps.kb.kb_training.enums.TrainingMetric import TrainingMetric
from apps.kb.kb_training.storage.TrainingRawRefBuilder import build_text_raw_ref
from apps.kb.kb_training.storage.TrainingStorage import TrainingStorage


@dataclass
class TrainingRawWriter:
    storage: TrainingStorage

    def write_text(
        self,
        *,
        tenant: str,
        knowledge_base_id: str,
        training_batch_id: str,
        training_item_id: str,
        content: str,
        content_type: str = "text/plain",
    ) -> str:
        raw_ref = build_text_raw_ref(
            tenant=tenant,
            knowledge_base_id=knowledge_base_id,
            training_batch_id=training_batch_id,
            training_item_id=training_item_id,
        )
        self.storage.put_text(
            key=raw_ref,
            text=content,
            content_type=content_type,
            metadata={
                "knowledge_base_id": str(knowledge_base_id),
                "training_batch_id": str(training_batch_id),
                "training_item_id": str(training_item_id),
            },
        )
        MetricsConf.increment(TrainingMetric.STORAGE_WRITE, input_type="text")
        return raw_ref


__all__ = ["TrainingRawWriter"]
