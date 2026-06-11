from __future__ import annotations

# backend/apps/kb/kb_understanding/validation/ValidateChunks.py
# Feladat: Chunking kimenetének validálása (van chunk, nem üres, sorrend konzisztens).
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.KnowledgeChunkDto import KnowledgeChunkDto
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingValidationError import UnderstandingValidationError


class ValidateChunks:
    def __call__(self, chunks: list[KnowledgeChunkDto]) -> None:
        if not chunks:
            raise UnderstandingValidationError(UnderstandingErrorCode.NO_CHUNKS)
        for chunk in chunks:
            if not (chunk.text or "").strip():
                raise UnderstandingValidationError(UnderstandingErrorCode.CHUNKING_FAILED)
            if not chunk.checksum:
                raise UnderstandingValidationError(UnderstandingErrorCode.CHUNKING_FAILED)
        order_indexes = [chunk.order_index for chunk in chunks]
        if sorted(order_indexes) != order_indexes:
            raise UnderstandingValidationError(UnderstandingErrorCode.CHUNKING_FAILED)


__all__ = ["ValidateChunks"]
