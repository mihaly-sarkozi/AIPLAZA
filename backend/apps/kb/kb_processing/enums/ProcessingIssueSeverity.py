from __future__ import annotations

from enum import Enum


class ProcessingIssueSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


__all__ = ["ProcessingIssueSeverity"]
