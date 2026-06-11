from __future__ import annotations

# backend/apps/kb/kb_understanding/dto/NormalizedContentDto.py
# Feladat: A normalize lépés kimenete.
# Sárközi Mihály - 2026.06.11

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NormalizedContentDto:
    text: str
    page_map: list[dict[str, Any]] = field(default_factory=list)
    char_count: int = 0
    # Alkalmazott szabályok összegzése (pl. removed_header_footer_lines, deduplicated_lines).
    applied_rules: dict[str, Any] = field(default_factory=dict)


__all__ = ["NormalizedContentDto"]
