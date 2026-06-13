from __future__ import annotations

import re
from typing import Any

from apps.kb.kb_understanding.config.UnderstandingConf import DEFAULT_UNDERSTANDING_CONFIG, UnderstandingConfig
from apps.kb.kb_understanding.dto.NormalizedContentDto import NormalizedContentDto
from apps.kb.kb_understanding.dto.StructuredBlockDto import StructuredBlockDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.StructuredBlockType import StructuredBlockType
from apps.kb.kb_understanding.extract.heading_path import HeadingPathTracker
from apps.kb.kb_understanding.mapper.structure_mapper import block_dto_to_orm
from apps.kb.kb_understanding.repository.ContentRepository import ContentRepository
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
    def __init__(
        self,
        structure_repository: StructureRepository,
        content_repository: ContentRepository,
        *,
        config: UnderstandingConfig | None = None,
    ) -> None:
        self._structure_repository = structure_repository
        self._content_repository = content_repository
        self._config = config or DEFAULT_UNDERSTANDING_CONFIG
        self._validate = ValidateStructuredBlocks()

    def run(self, ctx: UnderstandingJobContext, normalized: NormalizedContentDto) -> list[StructuredBlockDto]:
        blocks = self._blocks_from_normalized_parts(ctx)
        if not blocks and normalized.text.strip():
            blocks = self._blocks_from_legacy_text(normalized)

        self._validate(blocks)
        self._structure_repository.replace_for_item(
            ctx.training_item_id,
            [block_dto_to_orm(ctx, block) for block in blocks],
        )
        return blocks

    def _blocks_from_normalized_parts(self, ctx: UnderstandingJobContext) -> list[StructuredBlockDto]:
        blocks: list[StructuredBlockDto] = []
        heading_tracker = HeadingPathTracker()
        order_index = 0

        for batch in self._content_repository.iter_normalized_parts_for_item(
            ctx.training_item_id,
            batch_size=self._config.normalize_batch_size,
        ):
            for part in batch:
                block_text = (part.normalized_text or "").strip()
                if not block_text:
                    continue

                metadata = dict(part.metadata_json or {})
                metadata.setdefault("source_part_id", part.source_part_id)
                metadata.setdefault("part_type", part.part_type)
                metadata.setdefault("page_number", part.page_number)
                metadata.setdefault("part_index", part.part_index)
                metadata.setdefault("document_order", part.document_order)

                block_type = self._classify_from_metadata(metadata, block_text, is_first=order_index == 0)
                path_info = self._resolve_heading_path(
                    heading_tracker,
                    metadata=metadata,
                    block_text=block_text,
                    block_type=block_type,
                )
                section_title = path_info.get("current_section_title")

                block_metadata = self._build_block_metadata(metadata, path_info)
                blocks.append(
                    StructuredBlockDto(
                        block_type=block_type,
                        text=block_text,
                        order_index=order_index,
                        page_number=part.page_number,
                        section_title=section_title
                        if block_type
                        not in (
                            StructuredBlockType.TITLE,
                            StructuredBlockType.HEADING,
                            StructuredBlockType.HEADER,
                            StructuredBlockType.FOOTER,
                        )
                        else None,
                        metadata=block_metadata,
                    )
                )
                order_index += 1
        return blocks

    @staticmethod
    def _resolve_heading_path(
        heading_tracker: HeadingPathTracker,
        *,
        metadata: dict[str, Any],
        block_text: str,
        block_type: StructuredBlockType,
    ) -> dict[str, Any]:
        if metadata.get("heading_path"):
            return {
                "heading_path": list(metadata.get("heading_path") or []),
                "heading_levels": list(metadata.get("heading_levels") or []),
                "current_section_title": metadata.get("current_section_title")
                or (metadata.get("heading_path") or [None])[-1],
            }
        if block_type in (StructuredBlockType.TITLE, StructuredBlockType.HEADING):
            level = metadata.get("heading_level")
            if level is None:
                level = 0 if block_type == StructuredBlockType.TITLE else 1
            return heading_tracker.update(int(level), block_text)
        return heading_tracker.current()

    @staticmethod
    def _build_block_metadata(entry: dict[str, Any], path_info: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_part_id": entry.get("source_part_id"),
            "document_order": entry.get("document_order"),
            "part_index": entry.get("part_index"),
            "part_type": entry.get("part_type"),
            "block_kind": entry.get("block_kind"),
            "page_number": entry.get("page_number") or entry.get("page"),
            "style_name": entry.get("style_name"),
            "style_id": entry.get("style_id"),
            "heading_level": entry.get("heading_level"),
            "is_heading": entry.get("is_heading"),
            "is_list": entry.get("is_list"),
            "list_level": entry.get("list_level"),
            "numbering_id": entry.get("numbering_id"),
            "numbering_level": entry.get("numbering_level"),
            "list_marker": entry.get("list_marker"),
            "runs": entry.get("runs"),
            "bbox": entry.get("bbox"),
            "font_names": entry.get("font_names"),
            "font_sizes": entry.get("font_sizes"),
            "dominant_font_size": entry.get("dominant_font_size"),
            "is_bold_guess": entry.get("is_bold_guess"),
            "is_heading_guess": entry.get("is_heading_guess"),
            "heading_confidence": entry.get("heading_confidence"),
            "is_header_candidate": entry.get("is_header_candidate"),
            "is_footer_candidate": entry.get("is_footer_candidate"),
            "header_footer_confidence": entry.get("header_footer_confidence"),
            "table_index": entry.get("table_index"),
            "headers": entry.get("headers"),
            "rows": entry.get("rows"),
            "row_count": entry.get("row_count"),
            "column_count": entry.get("column_count"),
            "ocr_confidence": entry.get("ocr_confidence"),
            "ocr_language": entry.get("ocr_language"),
            "heading_path": list(path_info.get("heading_path") or []),
            "heading_levels": list(path_info.get("heading_levels") or []),
            "current_section_title": path_info.get("current_section_title"),
        }

    def _blocks_from_legacy_text(self, normalized: NormalizedContentDto) -> list[StructuredBlockDto]:
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

    def _classify_from_metadata(
        self,
        metadata: dict[str, Any],
        text: str,
        *,
        is_first: bool,
    ) -> StructuredBlockType:
        part_type = str(metadata.get("part_type") or "").upper()
        block_kind = str(metadata.get("block_kind") or "").lower()

        if part_type == "TABLE" or block_kind == "table":
            return StructuredBlockType.TABLE
        if block_kind == "header" or part_type == "HEADER" or metadata.get("is_header_candidate"):
            return StructuredBlockType.HEADER
        if block_kind == "footer" or part_type == "FOOTER" or metadata.get("is_footer_candidate"):
            return StructuredBlockType.FOOTER
        if block_kind == "list" or metadata.get("is_list"):
            return StructuredBlockType.LIST
        if part_type == "OCR_TEXT" or block_kind == "ocr_text":
            return StructuredBlockType.PARAGRAPH
        if metadata.get("heading_level") == 0:
            return StructuredBlockType.TITLE
        if block_kind == "heading" or metadata.get("is_heading") or metadata.get("is_heading_guess"):
            return StructuredBlockType.HEADING
        if block_kind == "paragraph":
            return StructuredBlockType.PARAGRAPH
        return self._classify(text, is_first=is_first)

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
        return len(line.split()) <= 8 and not any(char in line for char in ".!?")


__all__ = ["DetectStructureService"]
