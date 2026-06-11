from __future__ import annotations

# backend/apps/kb/kb_understanding/dto/ExtractedContentDto.py
# Feladat: Az extract lépés kimenete.
# Sárközi Mihály - 2026.06.11

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExtractedContentDto:
    text: str
    # Oldaltérkép: [{"page": 1, "start": 0, "end": 123}, …]
    page_map: list[dict[str, Any]] = field(default_factory=list)
    char_count: int = 0
    source_mime: str | None = None
    extractor: str = ""


__all__ = ["ExtractedContentDto"]
