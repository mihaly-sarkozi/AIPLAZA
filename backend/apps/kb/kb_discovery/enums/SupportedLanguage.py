from __future__ import annotations

from enum import Enum


class SupportedLanguage(str, Enum):
    HU = "hu"
    EN = "en"
    ES = "es"
    UNKNOWN = "unknown"


__all__ = ["SupportedLanguage"]
