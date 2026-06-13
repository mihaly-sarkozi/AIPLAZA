from __future__ import annotations

from dataclasses import dataclass, field

from apps.kb.kb_understanding.dto.ExtractPartDto import ExtractPart


@dataclass(frozen=True)
class ExtractResult:
    total_pages: int | None
    parts: list[ExtractPart] = field(default_factory=list)
    total_chars: int = 0
    warnings: list[str] = field(default_factory=list)
    status: str = "completed"
    extractor_name: str = ""
    extractor_version: str = "1.0"
    processed_pages: int = 0
    failed_pages: int = 0
    source_mime: str | None = None
    streaming: bool = False
    text_parts_count: int = 0
    table_parts_count: int = 0
    ocr_text_parts_count: int = 0
    ocr_empty_parts_count: int = 0
    ocr_failed_parts_count: int = 0
    pdf_pages_ocr_scanned: int = 0
    docx_images_ocr_scanned: int = 0
    ocr_engine_available: bool = False
    ocr_language: str = ""

    @classmethod
    def from_counters(
        cls,
        *,
        counters,
        total_pages: int | None,
        processed_pages: int,
        failed_pages: int,
        warnings: list[str],
        status: str,
        extractor_name: str,
        extractor_version: str,
        source_mime: str | None,
        pdf_pages_ocr_scanned: int = 0,
        docx_images_ocr_scanned: int = 0,
        ocr_engine_available: bool = False,
        ocr_language: str = "",
    ) -> "ExtractResult":
        return cls(
            total_pages=total_pages,
            parts=[],
            total_chars=counters.total_chars,
            warnings=list(warnings),
            status=status,
            extractor_name=extractor_name,
            extractor_version=extractor_version,
            processed_pages=processed_pages,
            failed_pages=failed_pages,
            source_mime=source_mime,
            streaming=True,
            text_parts_count=counters.text_parts,
            table_parts_count=counters.table_parts,
            ocr_text_parts_count=counters.ocr_text_parts,
            ocr_empty_parts_count=counters.ocr_empty_parts,
            ocr_failed_parts_count=counters.ocr_failed_parts,
            pdf_pages_ocr_scanned=pdf_pages_ocr_scanned,
            docx_images_ocr_scanned=docx_images_ocr_scanned,
            ocr_engine_available=ocr_engine_available,
            ocr_language=ocr_language,
        )


__all__ = ["ExtractResult"]
