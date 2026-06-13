from __future__ import annotations

from typing import Protocol

from apps.kb.kb_understanding.dto.ExtractResultDto import ExtractResult


class ExtractorInterface(Protocol):
    name: str
    version: str

    def extract(self, data: bytes, *, mime_type: str | None = None) -> ExtractResult: ...


__all__ = ["ExtractorInterface"]
