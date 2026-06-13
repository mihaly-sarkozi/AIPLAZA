from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LanguageDetectionResult:
    language_code: str
    language_confidence: float
    chunk_languages: dict[str, str]


__all__ = ["LanguageDetectionResult"]
