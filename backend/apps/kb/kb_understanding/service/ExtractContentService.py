from __future__ import annotations

import time

from apps.kb.kb_understanding.config.ExtractConfig import DEFAULT_EXTRACT_CONFIG, ExtractConfig
from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.ExtractStatus import ExtractStatus
from apps.kb.kb_understanding.enums.ExtractStrategy import ExtractStrategy
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.extract.extract_context import ExtractContext
from apps.kb.kb_understanding.extract.extract_limits import ExtractLimits
from apps.kb.kb_understanding.extract.extract_strategy import file_size_mb, resolve_extract_strategy
from apps.kb.kb_understanding.extract.temp_file_utils import safe_delete_temp_file
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
        job_repository=None,
        config: ExtractConfig | None = None,
    ) -> None:
        self._content_repository = content_repository
        self._file_storage = file_storage
        self._pdf_extractor = pdf_extractor
        self._docx_extractor = docx_extractor
        self._text_extractor = text_extractor
        self._job_repository = job_repository
        self._config = config or DEFAULT_EXTRACT_CONFIG
        self._validate = ValidateExtractedContent()

    def run(self, ctx: UnderstandingJobContext) -> ExtractedContentDto:
        started = time.monotonic()
        file_size = self._resolve_file_size(ctx.raw_ref)
        strategy = resolve_extract_strategy(file_size, self._config)

        if strategy == ExtractStrategy.REJECTED_TOO_LARGE:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.FILE_REJECTED,
                size_bytes=file_size,
                max_bytes=self._config.max_extract_file_size_bytes,
            )

        extractor = self._select_extractor(ctx)
        extracted_content_id = new_id("und_extract")
        limits = ExtractLimits(self._config)
        limits.check_file_size_bytes(file_size)

        if strategy == ExtractStrategy.IN_MEMORY:
            result = self._extract_in_memory(ctx, extractor, limits)
        else:
            result = self._extract_via_temp_file(
                ctx,
                extractor,
                limits,
                strategy=strategy,
                extracted_content_id=extracted_content_id,
            )

        duration_ms = int((time.monotonic() - started) * 1000)
        dto = extracted_result_to_dto(
            ctx,
            result,
            extracted_content_id=extracted_content_id,
            duration_ms=duration_ms,
            extract_strategy=strategy.value,
            file_size_mb=file_size_mb(file_size),
        )
        self._validate(dto)

        if dto.status in {ExtractStatus.FAILED.value}:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.EMPTY_CONTENT,
                status=dto.status,
            )

        if not result.streaming:
            content_orm = extracted_dto_to_orm(ctx, dto)
            part_orms = [part_dto_to_orm(ctx, extracted_content_id, part) for part in dto.parts]
            self._content_repository.replace_extracted_with_parts(
                ctx.training_item_id,
                content_orm,
                part_orms,
                batch_size=self._config.extract_batch_size,
            )
        else:
            self._content_repository.finalize_extract(
                extracted_content_id,
                patch={
                    "total_pages": dto.total_pages,
                    "total_chars": dto.total_chars,
                    "text_parts_count": dto.text_parts_count,
                    "table_parts_count": dto.table_parts_count,
                    "ocr_text_parts_count": dto.ocr_text_parts_count,
                    "ocr_empty_parts_count": dto.ocr_empty_parts_count,
                    "ocr_failed_parts_count": dto.ocr_failed_parts_count,
                    "status": dto.status,
                    "metadata_json": {
                        "warnings": list(dto.warnings),
                        "trace_summary": dict(dto.trace_summary),
                        "extract_strategy": strategy.value,
                        "file_size_mb": file_size_mb(file_size),
                    },
                },
            )

        return dto

    def _extract_in_memory(self, ctx, extractor, limits: ExtractLimits):
        try:
            data = self._file_storage.read_bytes(raw_ref=ctx.raw_ref)
        except Exception as exc:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.STORAGE_ERROR, retryable=True
            ) from exc
        if hasattr(extractor, "extract_from_bytes"):
            return extractor.extract_from_bytes(data, mime_type=ctx.mime_type)
        return extractor.extract(data, mime_type=ctx.mime_type)

    def _extract_via_temp_file(
        self,
        ctx: UnderstandingJobContext,
        extractor,
        limits: ExtractLimits,
        *,
        strategy: ExtractStrategy,
        extracted_content_id: str,
    ):
        temp_path = None
        keep_temp = False
        try:
            temp_path = self._file_storage.materialize_to_temp_file(raw_ref=ctx.raw_ref)
        except Exception as exc:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.STORAGE_ERROR, retryable=True
            ) from exc

        initial_orm = extracted_dto_to_orm(
            ctx,
            ExtractedContentDto(
                extracted_content_id=extracted_content_id,
                extractor_name=getattr(extractor, "name", ""),
                extractor_version=getattr(extractor, "version", "1.0"),
                status="processing",
                source_mime=ctx.mime_type,
                raw_ref=ctx.raw_ref,
                trace_summary={
                    "extract_strategy": strategy.value,
                    "status": "processing",
                },
            ),
        )
        initial_orm.status = "processing"
        self._content_repository.begin_extract(ctx.training_item_id, initial_orm)

        extract_ctx = ExtractContext(
            streaming=True,
            limits=limits,
            on_parts_batch=lambda parts: self._persist_parts_batch(ctx, extracted_content_id, parts),
            on_progress=lambda progress: self._update_progress(ctx.job_id, progress),
        )

        try:
            if hasattr(extractor, "extract_from_path"):
                return extractor.extract_from_path(
                    temp_path,
                    mime_type=ctx.mime_type,
                    extract_ctx=extract_ctx,
                )
            with open(temp_path, "rb") as handle:
                return extractor.extract_from_bytes(
                    handle.read(),
                    mime_type=ctx.mime_type,
                    extract_ctx=extract_ctx,
                )
        except Exception:
            keep_temp = self._config.keep_temp_files_on_error
            raise
        finally:
            safe_delete_temp_file(temp_path, keep_on_error=keep_temp)

    def _persist_parts_batch(
        self,
        ctx: UnderstandingJobContext,
        extracted_content_id: str,
        parts,
    ) -> None:
        rows = [part_dto_to_orm(ctx, extracted_content_id, part) for part in parts]
        self._content_repository.bulk_insert_parts(rows)

    def _update_progress(self, job_id: str, progress: dict) -> None:
        if self._job_repository is None:
            return
        self._job_repository.update_extract_progress(job_id, progress)

    def _resolve_file_size(self, raw_ref: str) -> int:
        try:
            if hasattr(self._file_storage, "stat_bytes"):
                return int(self._file_storage.stat_bytes(raw_ref=raw_ref))
        except Exception as exc:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.STORAGE_ERROR, retryable=True
            ) from exc
        try:
            data = self._file_storage.read_bytes(raw_ref=raw_ref)
        except Exception as exc:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.STORAGE_ERROR, retryable=True
            ) from exc
        return len(data)

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
