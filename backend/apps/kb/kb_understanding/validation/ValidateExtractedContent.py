from __future__ import annotations

from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingValidationError import UnderstandingValidationError


class ValidateExtractedContent:
    def __call__(self, content: ExtractedContentDto) -> None:
        usable_parts = content.text_parts_count + content.table_parts_count + content.ocr_text_parts_count
        if usable_parts <= 0 and not (content.text or "").strip():
            raise UnderstandingValidationError(UnderstandingErrorCode.EMPTY_CONTENT)


__all__ = ["ValidateExtractedContent"]
