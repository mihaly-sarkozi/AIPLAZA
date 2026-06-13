from __future__ import annotations

import io
import re
from typing import Any

from apps.kb.kb_understanding.adapters.OcrExtractorAdapter import OcrExtractorAdapter
from apps.kb.kb_understanding.config.ExtractConfig import DEFAULT_EXTRACT_CONFIG, ExtractConfig
from apps.kb.kb_understanding.dto.ExtractPartDto import ExtractPart
from apps.kb.kb_understanding.dto.ExtractResultDto import ExtractResult
from apps.kb.kb_understanding.enums.ExtractPartType import ExtractPartType
from apps.kb.kb_understanding.enums.ExtractStatus import ExtractStatus
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.extract.extract_limits import ExtractLimits, finalize_extract_status
from apps.kb.kb_understanding.extract.part_builder import build_table_part, build_text_part, summarize_parts


class PdfExtractorAdapter:
    name = "pdfplumber_layout"
    version = "2.0"

    def __init__(
        self,
        *,
        config: ExtractConfig | None = None,
        ocr_extractor: OcrExtractorAdapter | None = None,
    ) -> None:
        self._config = config or DEFAULT_EXTRACT_CONFIG
        self._ocr = ocr_extractor or OcrExtractorAdapter(self._config)

    def extract(self, data: bytes, *, mime_type: str | None = None) -> ExtractResult:
        import pdfplumber

        limits = ExtractLimits(self._config)
        limits.check_file_size(data)

        parts: list[ExtractPart] = []
        warnings: list[str] = []
        failed_pages = 0
        processed_pages = 0
        part_index = 0

        try:
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                total_pages = len(pdf.pages)
                limits.check_page_count(total_pages)

                for page_number, page in enumerate(pdf.pages, start=1):
                    limits.check_duration()
                    processed_pages += 1
                    page_parts, page_failed = self._extract_page(page, page_number, part_index)
                    if page_failed:
                        failed_pages += 1
                    for part in page_parts:
                        limits.check_part_size(part.text or "")
                        parts.append(part)
                        part_index = part.part_index + 1
        except UnderstandingProcessingError:
            raise
        except Exception as exc:
            raise UnderstandingProcessingError(UnderstandingErrorCode.EXTRACTION_FAILED) from exc

        status = finalize_extract_status(parts=parts, failed_pages=failed_pages, warnings=warnings)
        return ExtractResult(
            total_pages=total_pages if "total_pages" in locals() else 0,
            parts=parts,
            total_chars=summarize_parts(parts),
            warnings=warnings,
            status=status,
            extractor_name=self.name,
            extractor_version=self.version,
            processed_pages=processed_pages,
            failed_pages=failed_pages,
            source_mime=mime_type or "application/pdf",
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
