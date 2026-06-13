from __future__ import annotations

import time

from apps.kb.kb_understanding.config.ExtractConfig import DEFAULT_EXTRACT_CONFIG, ExtractConfig
from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.ExtractStatus import ExtractStatus
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.mapper.content_mapper import (
    extracted_dto_to_orm,
    extracted_result_to_dto,
    part_dto_to_orm,
)
from apps.kb.kb_understanding.repository.ContentRepository import ContentRepository
from apps.kb.kb_understanding.validation.ValidateExtractedContent import ValidateExtractedContent
from apps.kb.shared.ids import new_id


class ExtractContentService:
    def __init__(
        self,
        content_repository: ContentRepository,
        file_storage,
        *,
        pdf_extractor,
        docx_extractor,
        text_extractor,
        config: ExtractConfig | None = None,
    ) -> None:
        self._content_repository = content_repository
        self._file_storage = file_storage
        self._pdf_extractor = pdf_extractor
        self._docx_extractor = docx_extractor
        self._text_extractor = text_extractor
        self._config = config or DEFAULT_EXTRACT_CONFIG
        self._validate = ValidateExtractedContent()

    def run(self, ctx: UnderstandingJobContext) -> ExtractedContentDto:
        started = time.monotonic()
        try:
            data = self._file_storage.read_bytes(raw_ref=ctx.raw_ref)
        except Exception as exc:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.STORAGE_ERROR, retryable=True
            ) from exc

        extractor = self._select_extractor(ctx)
        result = extractor.extract(data, mime_type=ctx.mime_type)
        duration_ms = int((time.monotonic() - started) * 1000)

        extracted_content_id = new_id("und_extract")
        dto = extracted_result_to_dto(
            ctx,
            result,
            extracted_content_id=extracted_content_id,
            duration_ms=duration_ms,
        )
        self._validate(dto)

        if dto.status == ExtractStatus.FAILED.value:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.EMPTY_CONTENT,
                status=dto.status,
            )

        content_orm = extracted_dto_to_orm(ctx, dto)
        part_orms = [part_dto_to_orm(ctx, extracted_content_id, part) for part in dto.parts]
        self._content_repository.replace_extracted_with_parts(
            ctx.training_item_id,
            content_orm,
            part_orms,
            batch_size=self._config.extract_batch_size,
        )
        return dto

    def _select_extractor(self, ctx: UnderstandingJobContext):
        mime = (ctx.mime_type or "").lower()
        name = (ctx.file_name or "").lower()
        if "pdf" in mime or name.endswith(".pdf"):
            return self._pdf_extractor
        if "wordprocessingml" in mime or name.endswith(".docx"):
            return self._docx_extractor
        if mime.startswith("text/") or name.endswith(".txt") or not name:
            return self._text_extractor
        raise UnderstandingProcessingError(
            UnderstandingErrorCode.UNSUPPORTED_CONTENT_TYPE, mime_type=ctx.mime_type
        )


__all__ = ["ExtractContentService"]
