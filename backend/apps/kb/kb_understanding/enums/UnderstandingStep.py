from __future__ import annotations

from enum import Enum


class UnderstandingStep(str, Enum):
    EXTRACT = "extract"
    NORMALIZE = "normalize"
    CHUNKING = "chunking"
    VALIDATION = "validation"


__all__ = ["UnderstandingStep"]
