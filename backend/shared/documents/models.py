from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExtractedParagraph:
    text: str
    block_type: str = "paragraph"
    page_number: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    font_size: float | None = None
    is_bold: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExtractedDocument:
    text_content: str = ""
    paragraphs: list[ExtractedParagraph] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["ExtractedDocument", "ExtractedParagraph"]
