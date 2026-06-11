from __future__ import annotations

from enum import Enum


class TrainingErrorCode(str, Enum):
    TEXT_REQUIRED = "text_required"
    TEXT_TOO_LONG = "text_too_long"
    BATCH_NOT_FOUND = "batch_not_found"
    ITEM_NOT_FOUND = "item_not_found"
    DUPLICATE_CONTENT = "duplicate_content"
    VALIDATION_ERROR = "validation_error"
    INVALID_EVENT_PAYLOAD = "invalid_event_payload"
    RAW_REF_REQUIRED = "raw_ref_required"
    RAW_REF_SEGMENT_EMPTY = "raw_ref_segment_empty"
    RAW_REF_SEGMENT_INVALID = "raw_ref_segment_invalid"
    STORAGE_ERROR = "storage_error"
    QUEUE_UNAVAILABLE = "queue_unavailable"
    INTERNAL_ERROR = "internal_error"


__all__ = ["TrainingErrorCode"]
