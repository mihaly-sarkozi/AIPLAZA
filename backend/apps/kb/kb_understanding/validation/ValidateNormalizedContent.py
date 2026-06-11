from __future__ import annotations

# backend/apps/kb/kb_understanding/validation/ValidateNormalizedContent.py
# Feladat: Normalize lépés kimenetének validálása.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.NormalizedContentDto import NormalizedContentDto
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingValidationError import UnderstandingValidationError


class ValidateNormalizedContent:
    def __call__(self, content: NormalizedContentDto) -> None:
        if not (content.text or "").strip():
            raise UnderstandingValidationError(UnderstandingErrorCode.NORMALIZATION_FAILED)


__all__ = ["ValidateNormalizedContent"]
