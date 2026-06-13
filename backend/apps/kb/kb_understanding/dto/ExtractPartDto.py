from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExtractPart:
    part_type: str
    page_number: int | None
    part_index: int
    text: str | None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    char_count: int = 0
    status: str = "completed"
    metadata: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None


__all__ = ["ExtractPart"]
