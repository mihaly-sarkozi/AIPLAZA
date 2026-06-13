from __future__ import annotations

import re
from enum import Enum
from typing import Any

from apps.kb.kb_understanding.extract.extract_metadata import is_ocr_source

_HEADING_NUMBERED = re.compile(r"^\d+(?:\.\d+){0,5}\.?\s+\S+")
_LIST_ITEM = re.compile(r"^\s*(?:[-*•]|[a-zA-Z]\))\s+\S+")
_STEP_ITEM = re.compile(r"^\s*\d+[.)]\s+\S+")
_FAQ_PREFIX = re.compile(r"^\s*(?:q|k|kérdés|question)\s*[:.]", re.IGNORECASE)
_NOTE_PREFIX = re.compile(r"^\s*(?:megjegyzés|note|info|tipp|tip)\s*[:!]", re.IGNORECASE)
_WARNING_PREFIX = re.compile(
    r"^\s*(?:figyelem|figyelmeztetés|fontos|warning|caution|important|attention)\s*[:!]",
    re.IGNORECASE,
)
_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+\S+")

_MAX_HEADING_LENGTH = 120


class LogicalBlockType(str, Enum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    HEADER = "header"
    FOOTER = "footer"
    OCR_TEXT = "ocr_text"
    STEP = "step"
    FAQ = "faq"
    NOTE = "note"
    WARNING = "warning"
    UNKNOWN = "unknown"


class NormalizedPartBlockClassifier:
    def classify(
        self,
        *,
        text: str,
        metadata: dict[str, Any],
        is_first: bool = False,
    ) -> LogicalBlockType:
        cleaned = (text or "").strip()
        if not cleaned:
            return LogicalBlockType.UNKNOWN
        return self._classify_from_metadata(metadata, cleaned, is_first=is_first)

    def _classify_from_metadata(
        self,
        metadata: dict[str, Any],
        text: str,
        *,
        is_first: bool,
    ) -> LogicalBlockType:
        part_type = str(metadata.get("part_type") or "").upper()
        block_kind = str(metadata.get("block_kind") or "").lower()

        if part_type == "TABLE" or block_kind == "table":
            return LogicalBlockType.TABLE
        if part_type == "HEADER" or block_kind == "header" or metadata.get("is_header_candidate"):
            return LogicalBlockType.HEADER
        if part_type == "FOOTER" or block_kind == "footer" or metadata.get("is_footer_candidate"):
            return LogicalBlockType.FOOTER
        if block_kind == "heading" or metadata.get("is_heading"):
            return LogicalBlockType.HEADING
        if metadata.get("is_list") or block_kind == "list":
            return LogicalBlockType.LIST
        if part_type == "OCR_TEXT" or block_kind == "ocr_text" or is_ocr_source(metadata):
            return LogicalBlockType.OCR_TEXT
        if metadata.get("heading_level") == 0:
            return LogicalBlockType.TITLE
        if metadata.get("is_heading_guess"):
            return LogicalBlockType.HEADING
        if block_kind == "paragraph":
            return LogicalBlockType.PARAGRAPH
        return self._classify_heuristic(text, is_first=is_first)

    def _classify_heuristic(self, text: str, *, is_first: bool) -> LogicalBlockType:
        first_line = text.split("\n", 1)[0].strip()
        lines = [line for line in text.split("\n") if line.strip()]

        if _WARNING_PREFIX.match(first_line):
            return LogicalBlockType.WARNING
        if _NOTE_PREFIX.match(first_line):
            return LogicalBlockType.NOTE
        if _FAQ_PREFIX.match(first_line) or (first_line.endswith("?") and len(lines) > 1):
            return LogicalBlockType.FAQ
        if self._is_table(lines):
            return LogicalBlockType.TABLE
        if len(lines) >= 2 and all(_STEP_ITEM.match(line) for line in lines):
            return LogicalBlockType.STEP
        if lines and all(_LIST_ITEM.match(line) for line in lines):
            return LogicalBlockType.LIST
        if self._is_heading(first_line) and len(lines) == 1:
            return LogicalBlockType.TITLE if is_first else LogicalBlockType.HEADING
        return LogicalBlockType.PARAGRAPH

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


__all__ = ["LogicalBlockType", "NormalizedPartBlockClassifier"]
