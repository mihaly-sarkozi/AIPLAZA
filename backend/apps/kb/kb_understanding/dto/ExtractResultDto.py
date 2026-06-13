from __future__ import annotations

from dataclasses import dataclass, field

from apps.kb.kb_understanding.dto.ExtractPartDto import ExtractPart


@dataclass(frozen=True)
class ExtractResult:
    total_pages: int | None
    parts: list[ExtractPart]
    total_chars: int
    warnings: list[str]
    status: str
    extractor_name: str = ""
    extractor_version: str = "1.0"
    processed_pages: int = 0
    failed_pages: int = 0
    source_mime: str | None = None

    @property
    def text_parts_count(self) -> int:
        return sum(1 for part in self.parts if part.part_type == "TEXT")

    @property
    def table_parts_count(self) -> int:
        return sum(1 for part in self.parts if part.part_type == "TABLE")

    @property
    def ocr_text_parts_count(self) -> int:
        return sum(1 for part in self.parts if part.part_type == "OCR_TEXT")

    @property
    def ocr_empty_parts_count(self) -> int:
        return sum(1 for part in self.parts if part.part_type == "OCR_EMPTY")

    @property
    def ocr_failed_parts_count(self) -> int:
        return sum(1 for part in self.parts if part.part_type == "OCR_FAILED")


__all__ = ["ExtractResult"]
