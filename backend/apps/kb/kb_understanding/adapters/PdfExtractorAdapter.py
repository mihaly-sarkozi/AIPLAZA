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
from apps.kb.kb_understanding.extract.part_builder import build_table_part, build_text_part, summarize_parts


class PdfExtractorAdapter:
    name = "pdfplumber_layout"
    version = "2.1"

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
        total_pages = 0
        timed_out = False

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
                        page_parts, page_failed = self._extract_page(page, page_number, part_index)
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
                                metadata={"source": "pdf_page"},
                            )
                        ]

                    if page_failed:
                        failed_pages += 1

                    for part in page_parts:
                        limits.check_part_size(part.text or "")

                    if extract_ctx is not None:
                        limits.check_part_count(extract_ctx.counters.total_parts + len(page_parts))
                        extract_ctx.emit_parts(page_parts, batch_size=self._config.extract_batch_size)
                        if page_parts:
                            part_index = max(part.part_index for part in page_parts) + 1
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
                        if page_parts:
                            part_index = max(part.part_index for part in page_parts) + 1

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
            text_parts_count=sum(1 for part in parts if part.part_type == ExtractPartType.TEXT.value),
            table_parts_count=sum(1 for part in parts if part.part_type == ExtractPartType.TABLE.value),
            ocr_text_parts_count=sum(1 for part in parts if part.part_type == ExtractPartType.OCR_TEXT.value),
            ocr_empty_parts_count=sum(1 for part in parts if part.part_type == ExtractPartType.OCR_EMPTY.value),
            ocr_failed_parts_count=sum(1 for part in parts if part.part_type == ExtractPartType.OCR_FAILED.value),
        )

    def _extract_page(self, page, page_number: int, start_index: int) -> tuple[list[ExtractPart], bool]:
        parts: list[ExtractPart] = []
        index = start_index
        page_failed = False

        page_text = (page.extract_text() or "").strip()
        if page_text:
            for block in self._split_text_blocks(page_text):
                parts.append(
                    build_text_part(
                        page_number=page_number,
                        part_index=index,
                        text=block,
                        metadata={"source": "pdf_text_layer"},
                    )
                )
                index += 1

        for table_index, table in enumerate(page.extract_tables() or []):
            cleaned = [[(cell or "").strip() for cell in row] for row in table if row]
            cleaned = [row for row in cleaned if any(cell for cell in row)]
            if not cleaned:
                continue
            headers = cleaned[0]
            rows = cleaned[1:] if len(cleaned) > 1 else []
            parts.append(
                build_table_part(
                    page_number=page_number,
                    part_index=index,
                    headers=headers,
                    rows=rows,
                    source="pdf_table",
                    metadata={"table_index": table_index},
                )
            )
            index += 1

        text_chars = sum(len(part.text or "") for part in parts)
        if text_chars < self._config.ocr_min_text_chars:
            try:
                image = page.to_image(resolution=200).original
                ocr_part = self._ocr.ocr_page_image(image, page_number=page_number, part_index=index)
                parts.append(ocr_part)
                if ocr_part.part_type == ExtractPartType.OCR_FAILED.value:
                    page_failed = True
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
                        metadata={"source": "pdf_page_image"},
                    )
                )

        return parts, page_failed

    @staticmethod
    def _split_text_blocks(text: str) -> list[str]:
        blocks = [block.strip() for block in re.split(r"\n{2,}", text) if block.strip()]
        return blocks or [text]


__all__ = ["PdfExtractorAdapter"]
