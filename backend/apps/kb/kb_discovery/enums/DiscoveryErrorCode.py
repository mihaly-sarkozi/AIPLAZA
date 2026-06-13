from __future__ import annotations

from enum import Enum


class DiscoveryErrorCode(str, Enum):
    ITEM_NOT_FOUND = "item_not_found"
    JOB_ALREADY_RUNNING = "job_already_running"
    UNDERSTANDING_JOB_NOT_FOUND = "understanding_job_not_found"
    CHUNKS_MISSING = "chunks_missing"
    VALIDATION_FAILED = "validation_failed"
    INTERNAL_ERROR = "internal_error"


__all__ = ["DiscoveryErrorCode"]
