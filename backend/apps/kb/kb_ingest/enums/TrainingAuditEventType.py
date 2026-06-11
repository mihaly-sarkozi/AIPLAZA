from __future__ import annotations

from enum import Enum


class TrainingAuditEventType(str, Enum):
    """Tanítási napló eseménytípusok — ``kb_ingest_events.event_type`` értékek."""

    TRAINING_BATCH_CREATED = "training_batch_created"
    TRAINING_BATCH_COMPLETED = "training_batch_completed"
    TRAINING_ITEM_ACCEPTED = "training_item_accepted"
    STORAGE_WRITE_STARTED = "storage_write_started"
    STORAGE_WRITE_COMPLETED = "storage_write_completed"
    UNDERSTANDING_REQUESTED = "understanding_requested"


__all__ = ["TrainingAuditEventType"]
