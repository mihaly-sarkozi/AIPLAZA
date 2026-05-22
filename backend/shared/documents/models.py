# backend/shared/documents/models.py
# Feladat: A dokumentum szövegkinyerés közös adatmodelljeit definiálja. Az ExtractedParagraph bekezdés, listaelem, heading, table_row vagy metadata blokkot ír le layout mezőkkel, az ExtractedDocument pedig teljes text_contentet, blokkokat és extraction metadatát hordoz. Shared contract core és app modulok számára.
# Sárközi Mihály - 2026.05.21

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
