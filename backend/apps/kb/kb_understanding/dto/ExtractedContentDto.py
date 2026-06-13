from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.kb.kb_understanding.dto.ExtractPartDto import ExtractPart
from apps.kb.kb_understanding.enums.ExtractPartType import NORMALIZABLE_PART_TYPES, ExtractPartType


@dataclass
class ExtractedContentDto:
    extractor_name: str = ""
    extractor_version: str = "1.0"
    total_pages: int | None = None
    total_chars: int = 0
    text_parts_count: int = 0
    table_parts_count: int = 0
    ocr_text_parts_count: int = 0
    ocr_empty_parts_count: int = 0
    ocr_failed_parts_count: int = 0
    status: str = "completed"
    source_mime: str | None = None
    raw_ref: str | None = None
    extracted_content_id: str | None = None
    parts: list[ExtractPart] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    trace_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return self.build_normalize_text()

    @property
    def char_count(self) -> int:
        return self.total_chars

    @property
    def extractor(self) -> str:
        return self.extractor_name

    @property
    def page_map(self) -> list[dict[str, Any]]:
        return self.build_page_map()

    def build_normalize_text(self) -> str:
        chunks: list[str] = []
        for part in self.parts:
            if part.part_type not in {item.value for item in NORMALIZABLE_PART_TYPES}:
                continue
            value = (part.text or "").strip()
            if value:
                chunks.append(value)
        return "\n\n".join(chunks)

    def build_page_map(self) -> list[dict[str, Any]]:
        page_map: list[dict[str, Any]] = []
        offset = 0
        current_page: int | None = None
        page_start = 0
        for part in self.parts:
            if part.part_type not in {item.value for item in NORMALIZABLE_PART_TYPES}:
                continue
            text = (part.text or "").strip()
            if not text:
                continue
            page = part.page_number
            if page != current_page:
                if current_page is not None:
                    page_map.append({"page": current_page, "start": page_start, "end": offset})
                current_page = page
                page_start = offset
            offset += len(text) + 2
        if current_page is not None:
            page_map.append({"page": current_page, "start": page_start, "end": offset})
        return page_map

    @classmethod
    def from_legacy(
        cls,
        *,
        text: str,
        page_map: list[dict[str, Any]] | None = None,
        char_count: int | None = None,
        source_mime: str | None = None,
        extractor: str = "",
    ) -> "ExtractedContentDto":
        part = ExtractPart(
            part_type=ExtractPartType.TEXT.value,
            page_number=(page_map or [{}])[0].get("page") if page_map else 1,
            part_index=0,
            text=text,
            char_count=len(text),
        )
        total_chars = char_count if char_count is not None else len(text)
        return cls(
            extractor_name=extractor,
            total_pages=1 if text.strip() else 0,
            total_chars=total_chars,
            text_parts_count=1 if text.strip() else 0,
            source_mime=source_mime,
            parts=[part],
            trace_summary={"legacy": True},
        )


__all__ = ["ExtractedContentDto"]
