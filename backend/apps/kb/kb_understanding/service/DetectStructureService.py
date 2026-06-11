from __future__ import annotations

# backend/apps/kb/kb_understanding/service/DetectStructureService.py
# Feladat: A normalizált szöveg szerkezetének heurisztikus felismerése —
# cím, alcím, bekezdés, lista, táblázat, FAQ, lépéssor, megjegyzés, figyelmeztetés.
# Sárközi Mihály - 2026.06.11

import re
from typing import Any

from apps.kb.kb_understanding.dto.NormalizedContentDto import NormalizedContentDto
from apps.kb.kb_understanding.dto.StructuredBlockDto import StructuredBlockDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.StructuredBlockType import StructuredBlockType
from apps.kb.kb_understanding.mapper.structure_mapper import block_dto_to_orm
from apps.kb.kb_understanding.repository.StructureRepository import StructureRepository
from apps.kb.kb_understanding.validation.ValidateStructuredBlocks import ValidateStructuredBlocks

_HEADING_NUMBERED = re.compile(r"^\d+(?:\.\d+){0,5}\.?\s+\S+")
_LIST_ITEM = re.compile(r"^\s*(?:[-*•]|[a-zA-Z]\))\s+\S+")
_STEP_ITEM = re.compile(r"^\s*\d+[.)]\s+\S+")
_FAQ_PREFIX = re.compile(r"^\s*(?:q|k|kérdés|question)\s*[:.]", re.IGNORECASE)
_NOTE_PREFIX = re.compile(r"^\s*(?:megjegyzés|note|info|tipp|tip)\s*[:!]", re.IGNORECASE)
_WARNING_PREFIX = re.compile(r"^\s*(?:figyelem|figyelmeztetés|fontos|warning|caution|important)\s*[:!]", re.IGNORECASE)
_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+\S+")

_MAX_HEADING_LENGTH = 120


class DetectStructureService:
    def __init__(self, structure_repository: StructureRepository) -> None:
        self._structure_repository = structure_repository
        self._validate = ValidateStructuredBlocks()

    def run(self, ctx: UnderstandingJobContext, normalized: NormalizedContentDto) -> list[StructuredBlockDto]:
        blocks: list[StructuredBlockDto] = []
        section_title: str | None = None
        order_index = 0
        offset = 0

        for raw_block in self._split_blocks(normalized.text):
            block_text = raw_block.strip()
            start_offset = normalized.text.find(raw_block, offset)
            if start_offset >= 0:
                offset = start_offset + len(raw_block)
            page_number = self._page_for_offset(normalized.page_map, max(start_offset, 0))

            block_type = self._classify(block_text, is_first=order_index == 0)
            if block_type in (StructuredBlockType.TITLE, StructuredBlockType.HEADING):
                section_title = block_text[:512]
                current_section = None if block_type == StructuredBlockType.TITLE else section_title
            else:
                current_section = section_title

            blocks.append(
                StructuredBlockDto(
                    block_type=block_type,
                    text=block_text,
                    order_index=order_index,
                    page_number=page_number,
                    section_title=current_section
                    if block_type not in (StructuredBlockType.TITLE, StructuredBlockType.HEADING)
                    else None,
                )
            )
            order_index += 1

        self._validate(blocks)
        self._structure_repository.replace_for_item(
            ctx.training_item_id,
            [block_dto_to_orm(ctx, block) for block in blocks],
        )
        return blocks

    @staticmethod
    def _split_blocks(text: str) -> list[str]:
        return [block for block in re.split(r"\n\s*\n", text) if block.strip()]

    @staticmethod
    def _page_for_offset(page_map: list[dict[str, Any]], offset: int) -> int | None:
        for entry in page_map:
            if int(entry.get("start", 0)) <= offset < int(entry.get("end", 0)):
                page = entry.get("page")
                return int(page) if page is not None else None
        return None

    def _classify(self, text: str, *, is_first: bool) -> StructuredBlockType:
        first_line = text.split("\n", 1)[0].strip()
        lines = [line for line in text.split("\n") if line.strip()]

        if _WARNING_PREFIX.match(first_line):
            return StructuredBlockType.WARNING
        if _NOTE_PREFIX.match(first_line):
            return StructuredBlockType.NOTE
        if _FAQ_PREFIX.match(first_line) or (first_line.endswith("?") and len(lines) > 1):
            return StructuredBlockType.FAQ
        if self._is_table(lines):
            return StructuredBlockType.TABLE
        if len(lines) >= 2 and all(_STEP_ITEM.match(line) for line in lines):
            return StructuredBlockType.STEP
        if all(_LIST_ITEM.match(line) for line in lines):
            return StructuredBlockType.LIST
        if self._is_heading(first_line) and len(lines) == 1:
            return StructuredBlockType.TITLE if is_first else StructuredBlockType.HEADING
        return StructuredBlockType.PARAGRAPH

    @staticmethod
    def _is_table(lines: list[str]) -> bool:
        if len(lines) < 2:
            return False
        pipe_lines = sum(1 for line in lines if line.count("|") >= 2)
        return pipe_lines >= max(2, len(lines) - 1)

    @staticmethod
    def _is_heading(line: str) -> bool:
        if not line or len(line) > _MAX_HEADING_LENGTH:
            return False
        if _MARKDOWN_HEADING.match(line):
            return True
        if line.endswith((".", ";", ",")):
            return False
        if _HEADING_NUMBERED.match(line):
            return True
        letters = [char for char in line if char.isalpha()]
        if letters and all(char.isupper() for char in letters):
            return True
        # Rövid, írásjel nélküli sor, kevés szóval.
        return len(line.split()) <= 8 and not any(char in line for char in ".!?")


__all__ = ["DetectStructureService"]
