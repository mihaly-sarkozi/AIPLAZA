from __future__ import annotations

from apps.kb.kb_understanding.dto.NormalizedContentDto import NormalizedContentDto
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingValidationError import UnderstandingValidationError


class ValidateNormalizedContent:
    def __call__(self, content: NormalizedContentDto) -> None:
        if content.part_count <= 0:
            raise UnderstandingValidationError(UnderstandingErrorCode.NORMALIZATION_FAILED)


__all__ = ["ValidateNormalizedContent"]
