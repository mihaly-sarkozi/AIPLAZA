from __future__ import annotations

# backend/apps/kb/kb_understanding/validation/ValidateExtractedContent.py
# Feladat: Extract lépés kimenetének validálása.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingValidationError import UnderstandingValidationError


class ValidateExtractedContent:
    def __call__(self, content: ExtractedContentDto) -> None:
        if not (content.text or "").strip():
            raise UnderstandingValidationError(UnderstandingErrorCode.EMPTY_CONTENT)


__all__ = ["ValidateExtractedContent"]
