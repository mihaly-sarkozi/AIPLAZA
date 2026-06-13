from __future__ import annotations

import io
import re

from apps.kb.kb_understanding.adapters.OcrExtractorAdapter import OcrExtractorAdapter
from apps.kb.kb_understanding.config.ExtractConfig import DEFAULT_EXTRACT_CONFIG, ExtractConfig
from apps.kb.kb_understanding.dto.ExtractPartDto import ExtractPart
from apps.kb.kb_understanding.dto.ExtractResultDto import ExtractResult
from apps.kb.kb_understanding.enums.ExtractPartType import ExtractPartType
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.extract.extract_context import ExtractContext
from apps.kb.kb_understanding.extract.extract_limits import ExtractLimits, finalize_extract_status
from apps.kb.kb_understanding.extract.ocr_engine import OcrExtractStats
from apps.kb.kb_understanding.extract.part_builder import build_table_part, build_text_part, summarize_parts
from apps.kb.kb_understanding.extract.pdf_metadata import (
    build_table_metadata,
    build_text_block_metadata,
    group_words_into_blocks,
)


class PdfExtractorAdapter:
    name = "pdfplumber_layout"
    version = "2.3"

    def __init__(
        self,
        *,
        config: ExtractConfig | None = None,
        ocr_extractor: OcrExtractorAdapter | None = None,
    ) -> None:
        self._config = config or DEFAULT_EXTRACT_CONFIG
        self._ocr = ocr_extractor or OcrExtractorAdapter(self._config)

    def extract(self, data: bytes, *, mime_type: str | None = None) -> ExtractResult:
        limits = ExtractLimits(self._config)
        limits.check_file_size(data)
        return self._run_pdf(io.BytesIO(data), mime_type=mime_type, limits=limits, extract_ctx=None)

    def extract_from_path(
        self,
        path: str,
        *,
        mime_type: str | None = None,
        extract_ctx: ExtractContext | None = None,
    ) -> ExtractResult:
        limits = extract_ctx.limits if extract_ctx and extract_ctx.limits else ExtractLimits(self._config)
        return self._run_pdf(path, mime_type=mime_type, limits=limits, extract_ctx=extract_ctx)

    def extract_from_bytes(
        self,
        data: bytes,
        *,
        mime_type: str | None = None,
        extract_ctx: ExtractContext | None = None,
    ) -> ExtractResult:
        limits = extract_ctx.limits if extract_ctx and extract_ctx.limits else ExtractLimits(self._config)
        limits.check_file_size(data)
        return self._run_pdf(io.BytesIO(data), mime_type=mime_type, limits=limits, extract_ctx=extract_ctx)

    def _run_pdf(
        self,
        source,
        *,
        mime_type: str | None,
        limits: ExtractLimits,
        extract_ctx: ExtractContext | None,
    ) -> ExtractResult:
        import pdfplumber

        parts: list[ExtractPart] = []
        warnings: list[str] = []
        failed_pages = 0
        processed_pages = 0
        part_index = 0
        document_order = 0
        total_pages = 0
        timed_out = False
        ocr_stats = self._resolve_ocr_stats(extract_ctx)

        try:
            with pdfplumber.open(source) as pdf:
                total_pages = len(pdf.pages)
                limits.check_page_count(total_pages)

                for page_number, page in enumerate(pdf.pages, start=1):
                    try:
                        limits.check_duration()
                    except UnderstandingProcessingError as exc:
                        if exc.code == UnderstandingErrorCode.EXTRACTION_TIMEOUT.value:
                            timed_out = True
                            warnings.append("extract_timeout")
                            break
                        raise

                    processed_pages += 1
                    try:
                        page_parts, page_failed, next_index, next_order = self._extract_page(
                            page,
                            page_number=page_number,
                            start_index=part_index,
                            document_order=document_order,
                            ocr_stats=ocr_stats,
                        )
                    except Exception as exc:
                        page_failed = True
                        page_parts = [
                            ExtractPart(
                                part_type=ExtractPartType.UNKNOWN.value,
                                page_number=page_number,
                                part_index=part_index,
                                text=None,
                                char_count=0,
                                status="failed",
                                error_code=UnderstandingErrorCode.EXTRACTION_FAILED.value,
                                error_message=str(exc)[:1000],
                                metadata={
                                    "source": "pdf_page",
                                    "document_order": document_order,
                                    "block_kind": "unknown",
                                },
                            )
                        ]
                        next_index = part_index + 1
                        next_order = document_order + 1

                    if page_failed:
                        failed_pages += 1

                    for part in page_parts:
                        limits.check_part_size(part.text or "")

                    if extract_ctx is not None:
                        limits.check_part_count(extract_ctx.counters.total_parts + len(page_parts))
                        extract_ctx.emit_parts(page_parts, batch_size=self._config.extract_batch_size)
                        part_index = next_index
                        document_order = next_order
                        if (
                            extract_ctx.on_progress is not None
                            and page_number % self._config.progress_update_interval_pages == 0
                        ):
                            extract_ctx.on_progress(
                                {
                                    "processed_pages": processed_pages,
                                    "total_pages": total_pages,
                                    "failed_pages": failed_pages,
                                    **extract_ctx.counters.to_dict(),
                                }
                            )
                    else:
                        limits.check_part_count(len(parts) + len(page_parts))
                        parts.extend(page_parts)
                        part_index = next_index
                        document_order = next_order

                if extract_ctx is not None:
                    extract_ctx.flush()
                    if extract_ctx.on_progress is not None:
                        extract_ctx.on_progress(
                            {
                                "processed_pages": processed_pages,
                                "total_pages": total_pages,
                                "failed_pages": failed_pages,
                                **extract_ctx.counters.to_dict(),
                            }
                        )
        except UnderstandingProcessingError:
            raise
        except Exception as exc:
            raise UnderstandingProcessingError(UnderstandingErrorCode.EXTRACTION_FAILED) from exc

        status = finalize_extract_status(
            parts=parts,
            failed_pages=failed_pages,
            warnings=warnings,
            timed_out=timed_out,
            counters=extract_ctx.counters if extract_ctx is not None else None,
        )

        ocr_fields = self._ocr_result_fields(ocr_stats)

        if extract_ctx is not None and extract_ctx.streaming:
            return ExtractResult.from_counters(
                counters=extract_ctx.counters,
                total_pages=total_pages,
                processed_pages=processed_pages,
                failed_pages=failed_pages,
                warnings=warnings,
                status=status,
                extractor_name=self.name,
                extractor_version=self.version,
                source_mime=mime_type or "application/pdf",
                **ocr_fields,
            )

        return ExtractResult(
            total_pages=total_pages,
            parts=parts,
            total_chars=summarize_parts(parts),
            warnings=warnings,
            status=status,
            extractor_name=self.name,
            extractor_version=self.version,
            processed_pages=processed_pages,
            failed_pages=failed_pages,
            source_mime=mime_type or "application/pdf",
            text_parts_count=sum(
                1
                for part in parts
                if part.part_type
                in {ExtractPartType.TEXT.value, ExtractPartType.HEADER.value, ExtractPartType.FOOTER.value}
            ),
            table_parts_count=sum(1 for part in parts if part.part_type == ExtractPartType.TABLE.value),
            ocr_text_parts_count=sum(1 for part in parts if part.part_type == ExtractPartType.OCR_TEXT.value),
            ocr_empty_parts_count=sum(1 for part in parts if part.part_type == ExtractPartType.OCR_EMPTY.value),
            ocr_failed_parts_count=sum(1 for part in parts if part.part_type == ExtractPartType.OCR_FAILED.value),
            **ocr_fields,
        )

    def _resolve_ocr_stats(self, extract_ctx: ExtractContext | None) -> OcrExtractStats:
        stats = extract_ctx.ocr_stats if extract_ctx is not None else OcrExtractStats()
        stats.ocr_engine_available = self._ocr.is_available
        stats.ocr_language = self._config.ocr_languages if self._config.ocr_enabled else ""
        return stats

    @staticmethod
    def _ocr_result_fields(ocr_stats: OcrExtractStats) -> dict[str, int | bool | str]:
        return {
            "pdf_pages_ocr_scanned": ocr_stats.pdf_pages_ocr_scanned,
            "docx_images_ocr_scanned": ocr_stats.docx_images_ocr_scanned,
            "ocr_engine_available": ocr_stats.ocr_engine_available,
            "ocr_language": ocr_stats.ocr_language,
        }

    @staticmethod
    def _page_has_images(page) -> bool:
        return bool(getattr(page, "images", None))

    def _should_run_page_ocr(self, page, text_chars: int) -> tuple[bool, str | None]:
        if not self._config.ocr_enabled:
            return False, None
        if self._config.ocr_run_on_pdf_images and self._page_has_images(page):
            return True, "page_contains_images"
        if self._config.ocr_run_on_low_text_pdf_pages and text_chars < self._config.ocr_min_text_chars:
            return True, "low_text_layer"
        return False, None

    @staticmethod
    def _collect_page_text(parts: list[ExtractPart]) -> str:
        return " ".join(part.text or "" for part in parts if part.text)

    def _append_ocr_part(
        self,
        parts: list[ExtractPart],
        ocr_part: ExtractPart | None,
        *,
        index: int,
        order: int,
    ) -> tuple[int, int, bool]:
        if ocr_part is None:
            return index, order, False
        parts.append(ocr_part)
        page_failed = ocr_part.part_type == ExtractPartType.OCR_FAILED.value
        return index + 1, order + 1, page_failed

    def _extract_page(
        self,
        page,
        *,
        page_number: int,
        start_index: int,
        document_order: int,
        ocr_stats: OcrExtractStats,
    ) -> tuple[list[ExtractPart], bool, int, int]:
        parts: list[ExtractPart] = []
        index = start_index
        order = document_order
        page_failed = False
        page_height = float(getattr(page, "height", 0) or 0)

        words = page.extract_words(extra_attrs=["fontname", "size"]) or []
        blocks = group_words_into_blocks(words, page_height=page_height)
        for block in blocks:
            text = (block.get("text") or "").strip()
            if not text:
                continue
            metadata = build_text_block_metadata(
                block,
                page_number=page_number,
                part_index=index,
                document_order=order,
            )
            part_type = ExtractPartType.HEADER if metadata.get("block_kind") == "header" else (
                ExtractPartType.FOOTER if metadata.get("block_kind") == "footer" else ExtractPartType.TEXT
            )
            for chunk in self._split_text_blocks(text):
                chunk_metadata = dict(metadata)
                chunk_metadata["part_index"] = index
                chunk_metadata["document_order"] = order
                parts.append(
                    ExtractPart(
                        part_type=part_type.value,
                        page_number=page_number,
                        part_index=index,
                        text=chunk,
                        char_count=len(chunk),
                        metadata=chunk_metadata,
                    )
                )
                index += 1
                order += 1

        tables = page.find_tables() or []
        for table_index, table in enumerate(tables):
            cleaned = [[(cell or "").strip() for cell in row] for row in (table.extract() or []) if row]
            cleaned = [row for row in cleaned if any(cell for cell in row)]
            if not cleaned:
                continue
            headers = cleaned[0]
            rows = cleaned[1:] if len(cleaned) > 1 else []
            bbox = None
            if getattr(table, "bbox", None):
                x0, top, x1, bottom = table.bbox
                bbox = {"x0": x0, "y0": top, "x1": x1, "y1": bottom}
            metadata = build_table_metadata(
                page_number=page_number,
                part_index=index,
                document_order=order,
                table_index=table_index,
                bbox=bbox,
                headers=headers,
                rows=rows,
            )
            parts.append(
                build_table_part(
                    page_number=page_number,
                    part_index=index,
                    headers=headers,
                    rows=rows,
                    source="pdf_table",
                    metadata=metadata,
                )
            )
            index += 1
            order += 1

        existing_text = self._collect_page_text(parts)
        text_chars = sum(len(part.text or "") for part in parts)

        should_page_ocr, reason = self._should_run_page_ocr(page, text_chars)
        if should_page_ocr:
            ocr_stats.pdf_pages_ocr_scanned += 1
            try:
                page_image = page.to_image(resolution=200).original
                ocr_part = self._ocr.ocr_page_image(
                    page_image,
                    page_number=page_number,
                    part_index=index,
                    document_order=order,
                    reason=reason or "page_contains_images",
                    existing_text=existing_text,
                )
                index, order, failed = self._append_ocr_part(
                    parts, ocr_part, index=index, order=order
                )
                if failed:
                    page_failed = True
                if ocr_part is not None and ocr_part.text:
                    existing_text = f"{existing_text} {ocr_part.text}".strip()
            except Exception as exc:
                page_failed = True
                parts.append(
                    ExtractPart(
                        part_type=ExtractPartType.OCR_FAILED.value,
                        page_number=page_number,
                        part_index=index,
                        text=None,
                        char_count=0,
                        status="failed",
                        error_code=UnderstandingErrorCode.OCR_FAILED.value,
                        error_message=str(exc)[:1000],
                        metadata={
                            "source": "pdf_page_ocr",
                            "document_order": order,
                            "block_kind": "ocr_text",
                            "reason": reason or "page_contains_images",
                        },
                    )
                )
                index += 1
                order += 1

        if self._config.ocr_enabled and self._config.ocr_run_on_pdf_images and self._page_has_images(page):
            for image_meta in page.images or []:
                try:
                    bbox = (
                        image_meta.get("x0"),
                        image_meta.get("top"),
                        image_meta.get("x1"),
                        image_meta.get("bottom"),
                    )
                    if any(value is None for value in bbox):
                        continue
                    cropped = page.crop(bbox)
                    image = cropped.to_image(resolution=200).original
                    ocr_part = self._ocr.ocr_pdf_embedded_image(
                        image,
                        page_number=page_number,
                        part_index=index,
                        document_order=order,
                        existing_text=existing_text,
                    )
                    index, order, failed = self._append_ocr_part(
                        parts, ocr_part, index=index, order=order
                    )
                    if failed:
                        page_failed = True
                    if ocr_part is not None and ocr_part.text:
                        existing_text = f"{existing_text} {ocr_part.text}".strip()
                except Exception as exc:
                    page_failed = True
                    parts.append(
                        ExtractPart(
                            part_type=ExtractPartType.OCR_FAILED.value,
                            page_number=page_number,
                            part_index=index,
                            text=None,
                            char_count=0,
                            status="failed",
                            error_code=UnderstandingErrorCode.OCR_FAILED.value,
                            error_message=str(exc)[:1000],
                            metadata={
                                "source": "pdf_embedded_image_ocr",
                                "document_order": order,
                                "block_kind": "ocr_text",
                                "reason": "embedded_image",
                            },
                        )
                    )
                    index += 1
                    order += 1

        return parts, page_failed, index, order

    @staticmethod
    def _split_text_blocks(text: str) -> list[str]:
        blocks = [block.strip() for block in re.split(r"\n{2,}", text) if block.strip()]
        return blocks or [text]


__all__ = ["PdfExtractorAdapter"]
