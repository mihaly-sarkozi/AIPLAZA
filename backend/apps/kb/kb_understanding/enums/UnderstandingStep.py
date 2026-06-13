from __future__ import annotations

from enum import Enum


class UnderstandingStep(str, Enum):
    EXTRACT = "extract"
    NORMALIZE = "normalize"
    STRUCTURE_DETECTION = "structure_detection"
    CHUNKING = "chunking"
    VALIDATION = "validation"


__all__ = ["UnderstandingStep"]
