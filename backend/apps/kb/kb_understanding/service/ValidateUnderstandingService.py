from __future__ import annotations

from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.UnderstandingStatus import UnderstandingStatus
from apps.kb.kb_understanding.repository.ChunkRepository import ChunkRepository
from apps.kb.kb_understanding.repository.ContentRepository import ContentRepository
from apps.kb.kb_understanding.validation.ValidateUnderstandingResult import (
    ValidateUnderstandingResult,
)


class ValidateUnderstandingService:
    def __init__(
        self,
        content_repository: ContentRepository,
        chunk_repository: ChunkRepository,
    ) -> None:
        self._content_repository = content_repository
        self._chunk_repository = chunk_repository
        self._validate = ValidateUnderstandingResult()

    def run(self, ctx: UnderstandingJobContext) -> tuple[UnderstandingStatus, object]:
        extracted = self._content_repository.get_extracted_for_item(ctx.training_item_id)
        normalized = self._content_repository.get_normalized_for_item(ctx.training_item_id)
        chunks = self._chunk_repository.list_for_document(ctx.training_item_id)

        checklist = self._validate(
            has_extracted_content=extracted is not None,
            usable_part_count=self._content_repository.count_usable_parts(ctx.training_item_id),
            has_normalized_summary=normalized is not None,
            normalized_part_count=self._content_repository.count_normalized_parts(ctx.training_item_id),
            chunk_count=len(chunks),
            chunks_with_source=sum(1 for chunk in chunks if (chunk.source_id or "").strip()),
        )

        if checklist.core_complete:
            status = UnderstandingStatus.READY_FOR_DISCOVERY
        elif checklist.has_chunks and checklist.has_source_link:
            status = UnderstandingStatus.PARTIAL
        else:
            status = UnderstandingStatus.FAILED
        return status, checklist


__all__ = ["ValidateUnderstandingService"]
