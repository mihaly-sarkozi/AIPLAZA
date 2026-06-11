from __future__ import annotations

# backend/apps/kb/kb_understanding/validation/ValidateStructuredBlocks.py
# Feladat: Structure detection kimenetének validálása.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.StructuredBlockDto import StructuredBlockDto
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingValidationError import UnderstandingValidationError


class ValidateStructuredBlocks:
    def __call__(self, blocks: list[StructuredBlockDto]) -> None:
        if not blocks:
            raise UnderstandingValidationError(UnderstandingErrorCode.STRUCTURE_DETECTION_FAILED)
        if any(not (block.text or "").strip() for block in blocks):
            raise UnderstandingValidationError(UnderstandingErrorCode.STRUCTURE_DETECTION_FAILED)


__all__ = ["ValidateStructuredBlocks"]
