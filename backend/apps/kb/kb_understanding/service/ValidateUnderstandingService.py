from __future__ import annotations

# backend/apps/kb/kb_understanding/service/ValidateUnderstandingService.py
# Feladat: A feldolgozás használhatóságának ellenőrzése a perzisztált rétegek alapján —
# kimenet: READY_FOR_INDEXING | PARTIAL | FAILED.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.UnderstandingStatus import UnderstandingStatus
from apps.kb.kb_understanding.repository.ChunkRepository import ChunkRepository
from apps.kb.kb_understanding.repository.ContentRepository import ContentRepository
from apps.kb.kb_understanding.repository.EmbeddingRepository import EmbeddingRepository
from apps.kb.kb_understanding.validation.ValidateUnderstandingResult import (
    UnderstandingChecklist,
    ValidateUnderstandingResult,
)


class ValidateUnderstandingService:
    def __init__(
        self,
        content_repository: ContentRepository,
        chunk_repository: ChunkRepository,
        embedding_repository: EmbeddingRepository,
    ) -> None:
        self._content_repository = content_repository
        self._chunk_repository = chunk_repository
        self._embedding_repository = embedding_repository
        self._validate = ValidateUnderstandingResult()

    def run(
        self,
        ctx: UnderstandingJobContext,
        *,
        had_optional_failures: bool = False,
    ) -> tuple[UnderstandingStatus, UnderstandingChecklist]:
        extracted = self._content_repository.get_extracted_for_item(ctx.training_item_id)
        normalized = self._content_repository.get_normalized_for_item(ctx.training_item_id)
        chunks = self._chunk_repository.list_for_document(ctx.training_item_id)
        chunk_ids = [chunk.id for chunk in chunks]
        embedding_count = self._embedding_repository.count_for_chunks(chunk_ids)

        checklist = self._validate(
            extracted_chars=int(extracted.char_count or 0) if extracted else 0,
            normalized_chars=int(normalized.char_count or 0) if normalized else 0,
            chunk_count=len(chunks),
            chunks_with_source=sum(1 for chunk in chunks if (chunk.source_id or "").strip()),
            embedding_count=embedding_count,
        )

        if checklist.core_complete:
            status = (
                UnderstandingStatus.PARTIAL
                if had_optional_failures
                else UnderstandingStatus.READY_FOR_INDEXING
            )
        elif checklist.has_chunks and checklist.has_source_link:
            # Van kereshető mag, de hiányos (pl. embedding) — részleges eredmény.
            status = UnderstandingStatus.PARTIAL
        else:
            status = UnderstandingStatus.FAILED
        return status, checklist


__all__ = ["ValidateUnderstandingService"]
