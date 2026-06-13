from __future__ import annotations

from apps.kb.kb_understanding.dto.ExtractPartDto import ExtractPart
from apps.kb.kb_understanding.dto.ExtractResultDto import ExtractResult
from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.orm.ExtractedContent import ExtractedContent
from apps.kb.kb_understanding.orm.ExtractedContentPart import ExtractedContentPart
from apps.kb.shared.ids import new_id


def extracted_result_to_dto(
    ctx: UnderstandingJobContext,
    result: ExtractResult,
    *,
    extracted_content_id: str,
    duration_ms: int,
    extract_strategy: str | None = None,
    file_size_mb: float | None = None,
) -> ExtractedContentDto:
    trace_summary = {
        "extract_strategy": extract_strategy,
        "file_size_mb": file_size_mb,
        "total_pages": result.total_pages,
        "processed_pages": result.processed_pages,
        "failed_pages": result.failed_pages,
        "text_parts": result.text_parts_count,
        "table_parts": result.table_parts_count,
        "ocr_text_parts": result.ocr_text_parts_count,
        "ocr_empty_parts": result.ocr_empty_parts_count,
        "ocr_failed_parts": result.ocr_failed_parts_count,
        "pdf_pages_ocr_scanned": result.pdf_pages_ocr_scanned,
        "docx_images_ocr_scanned": result.docx_images_ocr_scanned,
        "ocr_language": result.ocr_language or None,
        "ocr_engine_available": result.ocr_engine_available,
        "total_chars": result.total_chars,
        "extractor_name": result.extractor_name,
        "extractor_version": result.extractor_version,
        "duration_ms": duration_ms,
        "warnings": list(result.warnings),
        "status": result.status,
    }
    return ExtractedContentDto(
        extracted_content_id=extracted_content_id,
        extractor_name=result.extractor_name,
        extractor_version=result.extractor_version,
        total_pages=result.total_pages,
        total_chars=result.total_chars,
        text_parts_count=result.text_parts_count,
        table_parts_count=result.table_parts_count,
        ocr_text_parts_count=result.ocr_text_parts_count,
        ocr_empty_parts_count=result.ocr_empty_parts_count,
        ocr_failed_parts_count=result.ocr_failed_parts_count,
        status=result.status,
        source_mime=result.source_mime,
        raw_ref=ctx.raw_ref,
        parts=list(result.parts),
        warnings=list(result.warnings),
        trace_summary=trace_summary,
    )


def extracted_dto_to_orm(ctx: UnderstandingJobContext, dto: ExtractedContentDto) -> ExtractedContent:
    return ExtractedContent(
        id=dto.extracted_content_id or new_id("und_extract"),
        job_id=ctx.job_id,
        training_item_id=ctx.training_item_id,
        knowledge_base_id=ctx.knowledge_base_id,
        raw_ref=dto.raw_ref or ctx.raw_ref,
        mime_type=dto.source_mime or ctx.mime_type,
        extractor_name=dto.extractor_name,
        extractor_version=dto.extractor_version,
        total_pages=dto.total_pages,
        total_chars=dto.total_chars,
        text_parts_count=dto.text_parts_count,
        table_parts_count=dto.table_parts_count,
        ocr_text_parts_count=dto.ocr_text_parts_count,
        ocr_empty_parts_count=dto.ocr_empty_parts_count,
        ocr_failed_parts_count=dto.ocr_failed_parts_count,
        status=dto.status,
        metadata_json={
            "warnings": list(dto.warnings),
            "trace_summary": dict(dto.trace_summary),
            "extract_strategy": dto.trace_summary.get("extract_strategy"),
            "file_size_mb": dto.trace_summary.get("file_size_mb"),
        },
    )


def part_dto_to_orm(
    ctx: UnderstandingJobContext,
    extracted_content_id: str,
    part: ExtractPart,
) -> ExtractedContentPart:
    return ExtractedContentPart(
        id=new_id("und_part"),
        extracted_content_id=extracted_content_id,
        job_id=ctx.job_id,
        knowledge_base_id=ctx.knowledge_base_id,
        training_item_id=ctx.training_item_id,
        part_type=part.part_type,
        page_number=part.page_number,
        part_index=part.part_index,
        text=part.text,
        raw_payload_json=dict(part.raw_payload),
        char_count=part.char_count,
        status=part.status,
        error_code=part.error_code,
        error_message=part.error_message,
        metadata_json=dict(part.metadata),
    )


def normalized_summary_to_orm(
    ctx: UnderstandingJobContext,
    *,
    normalized_content_id: str,
    status: str,
    part_count: int = 0,
    total_chars: int = 0,
    metadata_json: dict | None = None,
) -> "NormalizedContent":
    from apps.kb.kb_understanding.orm.NormalizedContent import NormalizedContent

    return NormalizedContent(
        id=normalized_content_id,
        job_id=ctx.job_id,
        training_item_id=ctx.training_item_id,
        knowledge_base_id=ctx.knowledge_base_id,
        status=status,
        part_count=part_count,
        total_chars=total_chars,
        char_count=total_chars,
        metadata_json=dict(metadata_json or {}),
    )


def normalized_part_from_extracted(
    ctx: UnderstandingJobContext,
    *,
    normalized_content_id: str,
    extracted_part,
    normalized_text: str,
    metadata_json: dict,
    status: str = "completed",
    error_code: str | None = None,
    error_message: str | None = None,
) -> "NormalizedContentPart":
    from apps.kb.kb_understanding.orm.NormalizedContentPart import NormalizedContentPart

    raw_metadata = dict(getattr(extracted_part, "metadata_json", None) or {})
    document_order = raw_metadata.get("document_order")
    if document_order is None:
        document_order = getattr(extracted_part, "part_index", None)

    return NormalizedContentPart(
        id=new_id("und_norm_part"),
        normalized_content_id=normalized_content_id,
        source_part_id=getattr(extracted_part, "id", None),
        job_id=ctx.job_id,
        training_item_id=ctx.training_item_id,
        knowledge_base_id=ctx.knowledge_base_id,
        part_type=getattr(extracted_part, "part_type", ""),
        normalized_text=normalized_text,
        page_number=getattr(extracted_part, "page_number", None),
        part_index=int(getattr(extracted_part, "part_index", 0) or 0),
        document_order=document_order,
        metadata_json=dict(metadata_json),
        status=status,
        error_code=error_code,
        error_message=error_message,
    )


def normalized_dto_to_orm(ctx: UnderstandingJobContext, dto) -> "NormalizedContent":
    return normalized_summary_to_orm(
        ctx,
        normalized_content_id=dto.normalized_content_id,
        status=dto.status,
        part_count=dto.part_count,
        total_chars=dto.total_chars,
        metadata_json={
            "applied_rules": dict(getattr(dto, "applied_rules", {}) or {}),
            "trace_summary": dict(getattr(dto, "trace_summary", {}) or {}),
        },
    )


__all__ = [
    "extracted_dto_to_orm",
    "extracted_result_to_dto",
    "normalized_dto_to_orm",
    "normalized_part_from_extracted",
    "normalized_summary_to_orm",
    "part_dto_to_orm",
]
