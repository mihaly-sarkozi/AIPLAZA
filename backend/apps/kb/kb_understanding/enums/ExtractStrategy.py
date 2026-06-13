from __future__ import annotations

from enum import Enum


class ExtractStrategy(str, Enum):
    IN_MEMORY = "IN_MEMORY"
    TEMP_FILE = "TEMP_FILE"
    STREAMING = "STREAMING"
    REJECTED_TOO_LARGE = "REJECTED_TOO_LARGE"


__all__ = ["ExtractStrategy"]
