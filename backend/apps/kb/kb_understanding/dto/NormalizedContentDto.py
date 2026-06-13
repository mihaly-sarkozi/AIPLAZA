from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NormalizedContentDto:
    normalized_content_id: str
    status: str
    part_count: int = 0
    total_chars: int = 0
    applied_rules: dict[str, Any] = field(default_factory=dict)
    trace_summary: dict[str, Any] = field(default_factory=dict)
    # Legacy fields kept for backward-compatible callers/tests.
    text: str = ""
    page_map: list[dict[str, Any]] = field(default_factory=list)
    part_map: list[dict[str, Any]] = field(default_factory=list)
    char_count: int = 0


__all__ = ["NormalizedContentDto"]
