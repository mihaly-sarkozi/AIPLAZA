from __future__ import annotations

# backend/apps/kb/kb_understanding/service/ExtractContentService.py
# Feladat: Tartalom kinyerése a nyers forrásból — adapter-választás mime/fájlnév alapján,
# raw_ref betöltés, validálás, perzisztálás.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.mapper.content_mapper import extracted_dto_to_orm
from apps.kb.kb_understanding.repository.ContentRepository import ContentRepository
from apps.kb.kb_understanding.validation.ValidateExtractedContent import ValidateExtractedContent


class ExtractContentService:
    def __init__(
        self,
        content_repository: ContentRepository,
        file_storage,
        *,
        pdf_extractor,
        docx_extractor,
        text_extractor,
    ) -> None:
        self._content_repository = content_repository
        self._file_storage = file_storage
        self._pdf_extractor = pdf_extractor
        self._docx_extractor = docx_extractor
        self._text_extractor = text_extractor
        self._validate = ValidateExtractedContent()

    def run(self, ctx: UnderstandingJobContext) -> ExtractedContentDto:
        try:
            data = self._file_storage.read_bytes(raw_ref=ctx.raw_ref)
        except Exception as exc:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.STORAGE_ERROR, retryable=True
            ) from exc

        extractor = self._select_extractor(ctx)
        extracted = extractor.extract(data, mime_type=ctx.mime_type)
        self._validate(extracted)
        self._content_repository.replace_extracted(
            ctx.training_item_id, extracted_dto_to_orm(ctx, extracted)
        )
        return extracted

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
