from __future__ import annotations

import re
from collections import Counter
from typing import Any

from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.dto.NormalizedContentDto import NormalizedContentDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.ExtractPartType import NORMALIZABLE_PART_TYPES
from apps.kb.kb_understanding.extract.extract_metadata import slim_metadata_for_downstream
from apps.kb.kb_understanding.mapper.content_mapper import normalized_dto_to_orm
from apps.kb.kb_understanding.repository.ContentRepository import ContentRepository
from apps.kb.kb_understanding.validation.ValidateNormalizedContent import ValidateNormalizedContent

_PAGE_NUMBER_LINE = re.compile(
    r"^\s*(?:-\s*)?(?:page\s+)?\d{1,4}(?:\s*[./]\s*\d{1,4})?(?:\s*-)?(?:\s*\.?\s*oldal)?\s*$",
    re.IGNORECASE,
)
_HEADER_FOOTER_MIN_OCCURRENCES = 3
_HEADER_FOOTER_MAX_LENGTH = 80


class NormalizeContentService:
    def __init__(self, content_repository: ContentRepository) -> None:
        self._content_repository = content_repository
        self._validate = ValidateNormalizedContent()

    def run(self, ctx: UnderstandingJobContext, extracted: ExtractedContentDto) -> NormalizedContentDto:
        part_types = {item.value for item in NORMALIZABLE_PART_TYPES}
        stored_parts = self._content_repository.list_parts_for_item(
            ctx.training_item_id,
            part_types=part_types,
            completed_only=True,
        )
        source_parts = stored_parts or [
            type(
                "Part",
                (),
                {
                    "id": None,
                    "text": part.text,
                    "page_number": part.page_number,
                    "part_type": part.part_type,
                    "part_index": part.part_index,
                    "metadata_json": dict(part.metadata),
                },
            )()
            for part in extracted.parts
            if part.part_type in part_types
        ]

        applied: dict[str, Any] = {"normalized_part_types": sorted(part_types)}
        normalized_chunks: list[str] = []
        page_map: list[dict[str, Any]] = []
        part_map: list[dict[str, Any]] = []
        offset = 0
        current_page: int | None = None
        page_start = 0

        for part in source_parts:
            text, part_applied = self._normalize_part_text(part.text or "")
            for key, value in part_applied.items():
                applied[key] = applied.get(key, 0) + value
            if not text:
                continue
            start = offset
            normalized_chunks.append(text)
            page = getattr(part, "page_number", None)
            if page != current_page:
                if current_page is not None:
                    page_map.append({"page": current_page, "start": page_start, "end": offset})
                current_page = page
                page_start = offset
            offset += len(text) + 2

            raw_metadata = getattr(part, "metadata_json", None) or {}
            part_map.append(
                {
                    "start": start,
                    "end": offset - 2,
                    "page": page,
                    "part_index": getattr(part, "part_index", None),
                    "part_type": getattr(part, "part_type", None),
                    "source_part_id": getattr(part, "id", None),
                    **slim_metadata_for_downstream(dict(raw_metadata)),
                }
            )

        if current_page is not None:
            page_map.append({"page": current_page, "start": page_start, "end": offset})

        text = "\n\n".join(normalized_chunks)
        normalized = NormalizedContentDto(
            text=text,
            page_map=page_map,
            part_map=part_map,
            char_count=len(text),
            applied_rules=applied,
        )
        self._validate(normalized)
        self._content_repository.replace_normalized(
            ctx.training_item_id, normalized_dto_to_orm(ctx, normalized)
        )
        return normalized

    def _normalize_part_text(self, text: str) -> tuple[str, dict[str, int]]:
        applied: dict[str, int] = {}
        text, count = self._fix_encoding(text)
        applied["fixed_encoding"] = count
        lines = text.split("\n")
        lines, count = self._remove_page_number_lines(lines)
        applied["removed_page_number_lines"] = count
        lines, count = self._remove_repeated_lines(lines)
        applied["removed_header_footer_lines"] = count
        lines, count = self._dedupe_consecutive_lines(lines)
        applied["deduplicated_lines"] = count
        text = "\n".join(lines)
        text, count = self._collapse_whitespace(text)
        applied["collapsed_whitespace"] = count
        return text, applied

    @staticmethod
    def _fix_encoding(text: str) -> tuple[str, int]:
        replacements = {
            "\r\n": "\n",
            "\r": "\n",
            "\u00a0": " ",
            "\u200b": "",
            "\ufeff": "",
            "\ufffd": "",
        }
        count = 0
        for source, target in replacements.items():
            occurrences = text.count(source)
            if occurrences:
                count += occurrences
                text = text.replace(source, target)
        return text, count

    @staticmethod
    def _remove_page_number_lines(lines: list[str]) -> tuple[list[str], int]:
        kept = [line for line in lines if not _PAGE_NUMBER_LINE.match(line)]
        return kept, len(lines) - len(kept)

    @staticmethod
    def _remove_repeated_lines(lines: list[str]) -> tuple[list[str], int]:
        stripped = [line.strip() for line in lines]
        counts = Counter(line for line in stripped if line and len(line) <= _HEADER_FOOTER_MAX_LENGTH)
        repeated = {
            line
            for line, occurrences in counts.items()
            if occurrences >= _HEADER_FOOTER_MIN_OCCURRENCES
        }
        if not repeated:
            return lines, 0
        kept = [line for line in lines if line.strip() not in repeated]
        return kept, len(lines) - len(kept)

    @staticmethod
    def _dedupe_consecutive_lines(lines: list[str]) -> tuple[list[str], int]:
        kept: list[str] = []
        removed = 0
        previous: str | None = None
        for line in lines:
            current = line.strip()
            if current and current == previous:
                removed += 1
                continue
            kept.append(line)
            previous = current
        return kept, removed

    @staticmethod
    def _collapse_whitespace(text: str) -> tuple[str, int]:
        before = len(text)
        text = "\n".join(re.sub(r"[ \t]+", " ", line).rstrip() for line in text.split("\n"))
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip(), before - len(text)


__all__ = ["NormalizeContentService"]
