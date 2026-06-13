from __future__ import annotations

from enum import Enum


class ProcessingStep(str, Enum):
    EXTRACT_CONTENT = "EXTRACT_CONTENT"
    NORMALIZE_PARTS = "NORMALIZE_PARTS"
    BUILD_CHUNKS = "BUILD_CHUNKS"
    VALIDATE_RESULT = "VALIDATE_RESULT"


__all__ = ["ProcessingStep"]
