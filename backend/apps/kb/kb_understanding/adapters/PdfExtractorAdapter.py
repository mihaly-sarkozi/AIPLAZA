from __future__ import annotations

# backend/apps/kb/kb_understanding/adapters/PdfExtractorAdapter.py
# Feladat: PDF szövegkinyerés oldaltérképpel (a shared pdfplumber layout parserre építve).
# Sárközi Mihály - 2026.06.11

from typing import Any

from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError


class PdfExtractorAdapter:
    name = "pdfplumber_layout_v1"

    def extract(self, data: bytes, *, mime_type: str | None = None) -> ExtractedContentDto:
        from shared.documents.pdf_layout_parser import extract_pdf_layout

        try:
            document = extract_pdf_layout(data)
        except Exception as exc:
            raise UnderstandingProcessingError(UnderstandingErrorCode.EXTRACTION_FAILED) from exc

        parts: list[str] = []
        page_map: list[dict[str, Any]] = []
        offset = 0
        current_page: int | None = None
        page_start = 0
        for paragraph in document.paragraphs:
            text = (paragraph.text or "").strip()
            if not text:
                continue
            page = paragraph.page_number
            if page != current_page:
                if current_page is not None:
                    page_map.append({"page": current_page, "start": page_start, "end": offset})
                current_page = page
                page_start = offset
            parts.append(text)
            # +2: a join "\n\n" elválasztója.
            offset += len(text) + 2
        if current_page is not None:
            page_map.append({"page": current_page, "start": page_start, "end": offset})

        text_content = "\n\n".join(parts)
        return ExtractedContentDto(
            text=text_content,
            page_map=page_map,
            char_count=len(text_content),
            source_mime=mime_type or "application/pdf",
            extractor=self.name,
        )


__all__ = ["PdfExtractorAdapter"]
