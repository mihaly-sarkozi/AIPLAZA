from __future__ import annotations

# backend/apps/kb/kb_understanding/validation/ValidateEmbeddings.py
# Feladat: Embedding vektorok validálása (dimenzió-konzisztencia, üres vektor tiltás).
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingValidationError import UnderstandingValidationError


class ValidateEmbeddings:
    def __call__(self, vectors: list[list[float]], *, expected_dimension: int) -> None:
        for vector in vectors:
            if not vector:
                raise UnderstandingValidationError(UnderstandingErrorCode.EMBEDDING_FAILED)
            if expected_dimension and len(vector) != expected_dimension:
                raise UnderstandingValidationError(
                    UnderstandingErrorCode.EMBEDDING_FAILED,
                    expected=expected_dimension,
                    actual=len(vector),
                )


__all__ = ["ValidateEmbeddings"]
