from __future__ import annotations

# backend/apps/kb/kb_understanding/service/NormalizeContentService.py
# Feladat: A kinyert szöveg tisztítása — whitespace, sortörés, encoding, header/footer,
# oldalszám sorok, duplikált sorok kezelése.
# Sárközi Mihály - 2026.06.11

import re
from collections import Counter
from typing import Any

from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.dto.NormalizedContentDto import NormalizedContentDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.mapper.content_mapper import normalized_dto_to_orm
from apps.kb.kb_understanding.repository.ContentRepository import ContentRepository
from apps.kb.kb_understanding.validation.ValidateNormalizedContent import ValidateNormalizedContent

# Csak oldalszámot tartalmazó sorok: "12", "- 12 -", "Page 12", "12. oldal", "12 / 34".
_PAGE_NUMBER_LINE = re.compile(
    r"^\s*(?:-\s*)?(?:page\s+)?\d{1,4}(?:\s*[./]\s*\d{1,4})?(?:\s*-)?(?:\s*\.?\s*oldal)?\s*$",
    re.IGNORECASE,
)
# Ismétlődő header/footer jelöltek: rövid sor, amely sokszor fordul elő.
_HEADER_FOOTER_MIN_OCCURRENCES = 3
_HEADER_FOOTER_MAX_LENGTH = 80


class NormalizeContentService:
    def __init__(self, content_repository: ContentRepository) -> None:
        self._content_repository = content_repository
        self._validate = ValidateNormalizedContent()

    def run(self, ctx: UnderstandingJobContext, extracted: ExtractedContentDto) -> NormalizedContentDto:
        applied: dict[str, Any] = {}
        text = extracted.text

        text, applied["fixed_encoding"] = self._fix_encoding(text)
        lines = text.split("\n")
        lines, applied["removed_page_number_lines"] = self._remove_page_number_lines(lines)
        lines, applied["removed_header_footer_lines"] = self._remove_repeated_lines(lines)
        lines, applied["deduplicated_lines"] = self._dedupe_consecutive_lines(lines)
        text = "\n".join(lines)
        text, applied["collapsed_whitespace"] = self._collapse_whitespace(text)

        original_length = max(1, len(extracted.text))
        ratio = len(text) / original_length
        page_map = [
            {
                "page": entry.get("page"),
                "start": int(int(entry.get("start", 0)) * ratio),
                "end": int(int(entry.get("end", 0)) * ratio),
            }
            for entry in extracted.page_map
        ]

        normalized = NormalizedContentDto(
            text=text,
            page_map=page_map,
            char_count=len(text),
            applied_rules=applied,
        )
        self._validate(normalized)
        self._content_repository.replace_normalized(
            ctx.training_item_id, normalized_dto_to_orm(ctx, normalized)
        )
        return normalized

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
        # Soron belüli többszörös szóköz / tab összevonása, sorvégi whitespace törlése.
        text = "\n".join(re.sub(r"[ \t]+", " ", line).rstrip() for line in text.split("\n"))
        # 3+ üres sor → 1 üres sor.
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip(), before - len(text)


__all__ = ["NormalizeContentService"]
