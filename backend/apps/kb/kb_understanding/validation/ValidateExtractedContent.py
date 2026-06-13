from __future__ import annotations

from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.enums.ExtractPartType import NORMALIZABLE_PART_TYPES
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingValidationError import UnderstandingValidationError


class ValidateExtractedContent:
    def __call__(self, content: ExtractedContentDto) -> None:
        usable = [
            part
            for part in content.parts
            if part.part_type in {item.value for item in NORMALIZABLE_PART_TYPES}
            and (part.text or "").strip()
        ]
        if not usable and not (content.text or "").strip():
            raise UnderstandingValidationError(UnderstandingErrorCode.EMPTY_CONTENT)


__all__ = ["ValidateExtractedContent"]
